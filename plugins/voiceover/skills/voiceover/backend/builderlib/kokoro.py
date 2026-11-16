"""Kokoro text-to-speech: the open-source engine, run on this computer.

Kokoro (82M parameters, Apache 2.0) through kokoro-onnx. The model files are
downloaded once, on first use, to the app home's models folder
(~/.voiceover/models), outside the skill directory
so an update does not delete them. kokoro-onnx's espeakng-loader
dependency ships the espeak-ng library and its data, so nothing else needs
installing.

The model loads once, lazily, and every synthesis goes through one lock: Kokoro
is CPU-bound, and two at once only make both slower. Clips are written as MP3
with the bundled ffmpeg, so the audio cache, the manifest and the video step
treat them exactly like ElevenLabs clips.
"""
import os
import subprocess
import tempfile
import threading
import urllib.request
import wave
from pathlib import Path

from . import config

MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
MODEL_FILE = "kokoro-v1.0.onnx"
VOICES_FILE = "voices-v1.0.bin"
DOWNLOAD_MB = 340   # both files together, roughly
DEFAULT_VOICE = "af_heart"
DEFAULT_SPEED = 1.0
SPEED_RANGE = (0.7, 1.3)

# The English voices, with Kokoro's own quality grades (its VOICES.md). Ordered
# best-first within each group. Prefix: a = American, b = British; f/m = female/male.
VOICES = [
    ("af_heart", "A"), ("af_bella", "A-"), ("af_nicole", "B-"), ("af_aoede", "C+"),
    ("af_kore", "C+"), ("af_sarah", "C+"), ("af_alloy", "C"), ("af_nova", "C"),
    ("af_sky", "C-"), ("af_jessica", "D"), ("af_river", "D"),
    ("am_fenrir", "C+"), ("am_michael", "C+"), ("am_puck", "C+"), ("am_echo", "D"),
    ("am_eric", "D"), ("am_liam", "D"), ("am_onyx", "D"), ("am_santa", "D-"),
    ("am_adam", "F+"),
    ("bf_emma", "B-"), ("bf_isabella", "C"), ("bf_alice", "D"), ("bf_lily", "D"),
    ("bm_fable", "C"), ("bm_george", "C"), ("bm_lewis", "D+"), ("bm_daniel", "D"),
]
GRADES = dict(VOICES)
GROUPS = {"af": "American, female", "am": "American, male",
          "bf": "British, female", "bm": "British, male"}

PREVIEW_TEXT = ("Here is how I sound. In this lecture we will work through the "
                "idea one step at a time, and look at an example as we go.")

_lock = threading.Lock()
_model = None


def voice_list() -> list:
    return [{"id": v, "name": v.split("_", 1)[1].capitalize(), "grade": g,
             "group": GROUPS[v[:2]]} for v, g in VOICES]


def lang(voice: str) -> str:
    return "en-gb" if voice.startswith("b") else "en-us"


def check_voice(voice: str) -> str:
    if voice not in GRADES:
        raise ValueError(f"Unknown Kokoro voice {voice!r}.")
    return voice


def clamp_speed(speed) -> float:
    try:
        s = float(speed)
    except (TypeError, ValueError):
        s = DEFAULT_SPEED
    return round(min(max(s, SPEED_RANGE[0]), SPEED_RANGE[1]), 2)


def _has_models(d) -> bool:
    return bool(d) and (d / MODEL_FILE).exists() and (d / VOICES_FILE).exists()


def models_dir() -> Path:
    """Where the model files are, or will be downloaded."""
    return config.KOKORO_MODELS_DIR


def downloaded() -> bool:
    return _has_models(models_dir())


def loaded() -> bool:
    return _model is not None


def _download(url: str, dest: Path) -> None:
    """Fetch to a sibling .part and rename at the end, so an interrupted
    download is never mistaken for a model file."""
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as r, open(part, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        part.rename(dest)
    finally:
        part.unlink(missing_ok=True)


def _get():
    """The loaded model; downloads the files the first time. Call under _lock."""
    global _model
    if _model is None:
        d = models_dir()
        try:
            _download(MODEL_URL + MODEL_FILE, d / MODEL_FILE)
            _download(MODEL_URL + VOICES_FILE, d / VOICES_FILE)
        except OSError as e:
            raise RuntimeError(
                f"Could not download the Kokoro voice model ({e}). It is a "
                f"one-time download of about {DOWNLOAD_MB} MB from GitHub; check "
                "the internet connection and press Generate again.") from e
        from kokoro_onnx import Kokoro
        _model = Kokoro(str(d / MODEL_FILE), str(d / VOICES_FILE))
    return _model


def _ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _speak(text: str, voice: str, speed: float):
    """(samples, rate) for one piece of text."""
    with _lock:
        return _get().create(text, voice=voice, speed=clamp_speed(speed),
                             lang=lang(voice))


def synthesize(text: str, out_path: Path, voice: str = DEFAULT_VOICE,
               speed: float = DEFAULT_SPEED) -> None:
    """Speak `text` into an MP3 at out_path (written to .part, then renamed)."""
    voice = check_voice(voice)
    samples, rate = _speak(text, voice, speed)
    _write_mp3(samples, rate, out_path)


def synthesize_segments(pieces: list, out_path: Path, voice: str = DEFAULT_VOICE,
                        speed: float = DEFAULT_SPEED) -> list:
    """Speak each piece in turn into one MP3. Returns the second at which each
    piece starts, followed by the end of the clip (len(pieces) + 1 values). An
    empty piece takes no time. Kokoro returns no word
    timings, so a caller that needs to know when a given point in the text is
    spoken splits the text there and reads the start of the next piece."""
    import numpy as np

    voice = check_voice(voice)
    chunks, starts, at, rate = [], [], 0, 24000
    for piece in pieces:
        starts.append(at / rate)
        if piece.strip():
            samples, rate = _speak(piece, voice, speed)
            chunks.append(samples)
            at += len(samples)
    if not chunks:
        raise ValueError("Nothing to speak.")
    _write_mp3(np.concatenate(chunks), rate, out_path)
    return starts + [at / rate]


def _write_mp3(samples, rate: int, out_path: Path) -> None:
    import numpy as np

    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    part = out_path.with_name(out_path.name + ".part")
    try:
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm)
        r = subprocess.run(
            [_ffmpeg(), "-y", "-loglevel", "error", "-i", wav_path,
             "-ar", "44100", "-codec:a", "libmp3lame", "-b:a", "128k",
             "-f", "mp3", str(part)],
            capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"Could not encode the Kokoro clip: {r.stderr[-300:]}")
        os.replace(part, out_path)
    finally:
        Path(wav_path).unlink(missing_ok=True)
        part.unlink(missing_ok=True)


def preview(voice: str, speed: float = DEFAULT_SPEED) -> Path:
    """A short sample of `voice`, cached under ~/.voiceover/kokoro-previews."""
    voice = check_voice(voice)
    speed = clamp_speed(speed)
    path = config.HOME_DIR / "kokoro-previews" / f"{voice}-{speed:g}.mp3"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        synthesize(PREVIEW_TEXT, path, voice, speed)
    return path
