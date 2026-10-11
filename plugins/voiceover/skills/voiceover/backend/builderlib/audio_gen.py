"""Per-slide TTS audio generation.

Synthesizes one ElevenLabs MP3 per slide that has narration, parameterized by
voice_id + model + voice settings.

Each MP3 is named for a sha of the text it speaks plus the voice signature, so
the audio directory is a content-addressed cache: a rebuild re-synthesizes only
what actually changed, and — because nothing is keyed by slide position —
inserting or reordering slides reuses every clip that still says the same thing
in the same voice.
"""
import hashlib
import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from . import config

ELEVEN_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
OUTPUT_FORMAT = "mp3_44100_128"

# Transient failures worth another try: 429 is the per-plan concurrency/rate cap,
# 5xx is ElevenLabs being busy. Everything else (401 bad key or exhausted quota,
# 400 bad request) will fail identically on a retry, so it is raised at once.
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 5


def _retry_delay(response, attempt: int) -> float:
    """Seconds to wait before attempt+1.

    Honour Retry-After when the server sends one; otherwise exponential backoff.
    The jitter matters more than it looks: every worker thread trips the
    concurrency cap at the same instant, so a fixed delay would march them into
    the cap together on every retry.
    """
    if response is not None:
        raw = (response.headers.get("retry-after") or "").strip()
        if raw:
            try:
                return max(0.0, min(float(raw), 30.0))
            except ValueError:
                pass
    return min(2 ** attempt, 16) * (0.5 + random.random())

# Every voice_settings field we send, in signature order. `style` and
# `use_speaker_boost` drive how much expression the model puts in; leaving them
# out (as this app used to) means asking for the model's flattest read and then
# wondering why the result sounds flat. `speed` trims pacing without re-recording.
VOICE_SETTING_KEYS = ("stability", "similarity_boost", "style",
                      "use_speaker_boost", "speed")

DEFAULT_VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True,
    "speed": 1.0,
}


def _sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _merged_settings(settings: dict | None) -> dict:
    """Fill in defaults for anything the caller left unset."""
    merged = dict(DEFAULT_VOICE_SETTINGS)
    for k, v in (settings or {}).items():
        if k in DEFAULT_VOICE_SETTINGS and v is not None:
            merged[k] = v
    return merged


def _voice_sig(voice_id: str, model: str, settings: dict) -> str:
    """A signature of everything besides the text that affects the audio, so a
    voice/model/settings change re-synthesizes even when narration is unchanged.

    Every field in VOICE_SETTING_KEYS is included and named, so adding a field
    later invalidates old hashes (a rebuild re-renders) instead of silently
    serving audio made with different settings.
    """
    fields = ",".join(f"{k}={settings.get(k)}" for k in VOICE_SETTING_KEYS)
    return f"{voice_id}|{model}|{fields}"


def synthesize(text: str, out_path: Path, voice_id: str, model: str,
               settings: dict | None = None) -> None:
    """Stream one ElevenLabs MP3 to out_path. Reads ELEVENLABS_API_KEY.

    `settings` is passed through to voice_settings as given. Note that v3 defines
    only three stability levels (0.0 / 0.5 / 1.0) while the v2-family models take
    a continuous 0–1; the API accepts in-between values on v3 without erroring, so
    nothing is snapped here — the picker offers the defined levels instead.
    """
    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError(
            "ELEVENLABS_API_KEY is not set — paste your key in the app's banner, "
            "or export it in your shell.")
    merged = _merged_settings(settings)
    url = ELEVEN_TTS_URL.format(voice_id=voice_id)
    headers = {"xi-api-key": config.ELEVENLABS_API_KEY, "accept": "audio/mpeg"}
    payload = {
        "text": text,
        "model_id": model,
        "voice_settings": {k: merged[k] for k in VOICE_SETTING_KEYS},
    }
    params = {"output_format": OUTPUT_FORMAT}
    # Stream to a sibling .part and rename only once the body is complete. The
    # cache decides a clip exists by filename alone, so a half-written mp3 left
    # by a failed attempt would be reused forever as a truncated slide.
    tmp_path = out_path.with_name(out_path.name + ".part")
    last_error = ""
    try:
        for attempt in range(MAX_ATTEMPTS):
            wait = None
            try:
                with httpx.stream("POST", url, headers=headers, json=payload,
                                  params=params, timeout=120.0) as response:
                    if response.status_code == 200:
                        with open(tmp_path, "wb") as f:
                            for chunk in response.iter_bytes():
                                f.write(chunk)
                        os.replace(tmp_path, out_path)
                        return
                    body = response.read().decode("utf-8", "replace")
                    last_error = (f"ElevenLabs TTS error "
                                  f"({response.status_code}): {body[:300]}")
                    if response.status_code not in RETRY_STATUSES:
                        raise RuntimeError(last_error)
                    wait = _retry_delay(response, attempt)
            except httpx.HTTPError as e:
                # Dropped mid-stream or never connected — same treatment.
                last_error = f"ElevenLabs request failed: {e}"
                wait = _retry_delay(None, attempt)
            if attempt == MAX_ATTEMPTS - 1:
                break
            time.sleep(wait)
    finally:
        tmp_path.unlink(missing_ok=True)
    raise RuntimeError(f"{last_error} (gave up after {MAX_ATTEMPTS} attempts)")


def generate(slides: list, audio_dir: Path, voice_id: str, model: str,
             settings: dict | None = None, progress=None) -> dict:
    """(Re)synthesize audio for `slides`, write the manifest, prune the cache.

    `slides` is the deck's narration — {index, narration, ...} — in any order.
    Slides with no narration get no audio and are shown silently in the video.

    progress: optional callable(done, total, message).
    Returns {"total", "narrated", "synthesized", "skipped"}.
    """
    audio_dir.mkdir(parents=True, exist_ok=True)
    merged = _merged_settings(settings)
    sig = _voice_sig(voice_id, model, merged)

    manifest = []
    tasks = {}       # filename -> text still to synthesize (deduped)
    keep = set()
    narrated = 0

    for s in sorted(slides, key=lambda s: s["index"]):
        text = (s.get("narration") or "").strip()
        entry = {"index": s["index"], "file": None, "words": len(text.split())}
        if text:
            narrated += 1
            filename = f"{_sha(text + chr(0) + sig)[:32]}.mp3"
            entry["file"] = filename
            keep.add(filename)
            if not (audio_dir / filename).exists():
                tasks[filename] = text
        manifest.append(entry)

    # Two slides with identical narration share one clip, so `skipped` counts every
    # slide that needed no new request — cache hits and duplicates alike.
    skipped = narrated - len(tasks)
    done = skipped
    total = narrated
    # The count opens at the number of reused clips, so a rebuild that reuses
    # 11 of 12 jumps straight to "11 of 12" -- which looks like a slide pointer
    # unless the reuse is named.
    if progress:
        label = f"Generating audio ({skipped} reused)" if skipped else "Generating audio"
        progress(done, total, label)

    lock = threading.Lock()

    def _render(item):
        nonlocal done
        filename, text = item
        synthesize(text, audio_dir / filename, voice_id, model, merged)
        with lock:
            done += 1
            if progress:
                progress(done, total, "Generating audio")

    if tasks:
        workers = max(1, min(config.TTS_CONCURRENCY, len(tasks)))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_render, item) for item in tasks.items()]
            for f in as_completed(futures):
                exc = f.exception()
                if exc:
                    raise exc

    (audio_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    _prune(audio_dir, keep)

    return {"total": len(slides), "narrated": narrated,
            "synthesized": len(tasks), "skipped": skipped}


def _prune(audio_dir: Path, keep: set) -> None:
    """Drop clips no slide points at any more. The cache is only worth keeping
    for the current deck: an old clip can never be hit again, because its name
    encodes text that no slide says."""
    for mp3 in audio_dir.glob("*.mp3"):
        if mp3.name not in keep:
            try:
                mp3.unlink()
            except OSError:
                pass
