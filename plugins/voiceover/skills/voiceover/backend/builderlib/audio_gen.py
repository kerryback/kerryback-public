"""Per-slide TTS audio generation.

Synthesizes one MP3 per slide that has narration, with the account's engine:
ElevenLabs (voice_id + model + voice settings) or Kokoro (voice + speed, run
locally; see kokoro.py).

A reveal.js deck is built with `timed=True`: every clip also gets a timing file
beside it (`<name>.json`, one start time per character), which the recorder
uses to fire each `[next]` marker at the word it sits before. ElevenLabs then
uses its with-timestamps endpoint; Kokoro, which returns no timestamps, speaks
the text in pieces cut at the markers (synthesize_kokoro_timed). The text spoken
is the narration with its markers stripped (markers.split). A PDF deck is built
without timings, exactly as before.

Each MP3 is named for a sha of the text it speaks plus the voice signature, so
the audio directory is a content-addressed cache: a rebuild re-synthesizes only
what actually changed, and — because nothing is keyed by slide position —
inserting or reordering slides reuses every clip that still says the same thing
in the same voice.
"""
import base64
import hashlib
import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from . import config, kokoro, markers

ELEVEN_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
# The same voice with character timestamps, for a reveal.js deck's markers.
ELEVEN_TIMED_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
OUTPUT_FORMAT = "mp3_44100_128"

# Transient failures worth another try: 429 is the per-plan concurrency/rate cap,
# 5xx is ElevenLabs being busy. Everything else (401 bad key or exhausted quota,
# 400 bad request) will fail identically on a retry, so it is raised at once.
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 5


class Cancelled(Exception):
    """The author pressed Stop. Not a failure: clips already spoken stay in
    the cache, so the next build picks up where this one left off."""


def _check(cancel) -> None:
    if cancel is not None and cancel.is_set():
        raise Cancelled()


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


def _kokoro_settings(k: dict | None) -> dict:
    k = k or {}
    return {"voice": k.get("voice") or kokoro.DEFAULT_VOICE,
            "speed": kokoro.clamp_speed(k.get("speed", kokoro.DEFAULT_SPEED))}


def _kokoro_sig(k: dict) -> str:
    """Kokoro's counterpart of _voice_sig. The "kokoro|" prefix keeps the two
    engines' clips apart in the cache: a switch of engine re-synthesizes, and a
    Kokoro clip is never served for an ElevenLabs build or the reverse."""
    return f"kokoro|{k['voice']}|speed={k['speed']}"


def timing_path(mp3: Path) -> Path:
    """The character timestamps saved beside a clip."""
    return mp3.with_suffix(".json")


def read_timing(mp3: Path) -> dict:
    try:
        return json.loads(timing_path(mp3).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def synthesize_kokoro_timed(text: str, offsets: list, out_path: Path, k: dict) -> None:
    """One Kokoro clip of `text`, and its timings beside it.

    Kokoro returns no character timestamps, so the text is spoken in pieces cut
    at the [next] markers' offsets and joined: each marker then falls exactly
    where its piece starts. The timing file has the same shape as ElevenLabs'
    (`alignment.character_start_times_seconds`, one per character), exact at
    every marker and spread evenly between them, so markers.times reads both
    engines alike. The mp3 is written first and the timing file last; the cache
    treats a clip without its timings as missing.
    """
    bounds = [0] + sorted(min(max(o, 0), len(text)) for o in offsets) + [len(text)]
    pieces = [text[a:b] for a, b in zip(bounds, bounds[1:])]
    at = kokoro.synthesize_segments(pieces, out_path, k["voice"], k["speed"])
    starts = []
    for i, piece in enumerate(pieces):
        span = at[i + 1] - at[i]
        starts += [at[i] + span * j / len(piece) for j in range(len(piece))]
    json_path = timing_path(out_path)
    tmp_json = json_path.with_name(json_path.name + ".part")
    tmp_json.write_text(json.dumps({
        "text": text, "engine": "kokoro",
        "alignment": {"characters": list(text),
                      "character_start_times_seconds": starts},
    }), encoding="utf-8")
    os.replace(tmp_json, json_path)


def synthesize(text: str, out_path: Path, voice_id: str, model: str,
               settings: dict | None = None, cancel=None) -> None:
    """Stream one ElevenLabs MP3 to out_path. Reads ELEVENLABS_API_KEY.

    `settings` is passed through to voice_settings as given. Note that v3 defines
    only three stability levels (0.0 / 0.5 / 1.0) while the v2-family models take
    a continuous 0–1; the API accepts in-between values on v3 without erroring, so
    nothing is snapped here — the picker offers the defined levels instead.

    `cancel` (a threading.Event) is checked between attempts, never mid-stream:
    a request already sent is billed, so it is allowed to land in the cache.
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
            # Wait on the cancel flag rather than sleeping, so Stop doesn't sit
            # out a backoff of up to 16 seconds.
            if cancel is not None:
                if cancel.wait(wait):
                    raise Cancelled()
            else:
                time.sleep(wait)
    finally:
        tmp_path.unlink(missing_ok=True)
    raise RuntimeError(f"{last_error} (gave up after {MAX_ATTEMPTS} attempts)")


def synthesize_timed(text: str, out_path: Path, voice_id: str, model: str,
               settings: dict | None = None, cancel=None) -> None:
    """Write one ElevenLabs MP3 to out_path, and its timings beside it. Reads ELEVENLABS_API_KEY.

    `settings` is passed through to voice_settings as given. Note that v3 defines
    only three stability levels (0.0 / 0.5 / 1.0) while the v2-family models take
    a continuous 0–1; the API accepts in-between values on v3 without erroring, so
    nothing is snapped here — the picker offers the defined levels instead.

    `cancel` (a threading.Event) is checked between attempts, never mid-stream:
    a request already sent is billed, so it is allowed to land in the cache.
    """
    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError(
            "ELEVENLABS_API_KEY is not set — paste your key in the app's banner, "
            "or export it in your shell.")
    merged = _merged_settings(settings)
    url = ELEVEN_TIMED_URL.format(voice_id=voice_id)
    headers = {"xi-api-key": config.ELEVENLABS_API_KEY}
    payload = {
        "text": text,
        "model_id": model,
        "voice_settings": {k: merged[k] for k in VOICE_SETTING_KEYS},
    }
    params = {"output_format": OUTPUT_FORMAT}
    # Write to sibling .part files and rename only once complete. The cache
    # decides a clip exists by filename alone, so a half-written mp3 left by a
    # failed attempt would be reused forever as a truncated slide. The timing
    # file is renamed first, so an mp3 never exists without its timings.
    tmp_path = out_path.with_name(out_path.name + ".part")
    json_path = timing_path(out_path)
    tmp_json = json_path.with_name(json_path.name + ".part")
    last_error = ""
    try:
        for attempt in range(MAX_ATTEMPTS):
            wait = None
            try:
                response = httpx.post(url, headers=headers, json=payload,
                                      params=params, timeout=180.0)
                if response.status_code == 200:
                    body = response.json()
                    tmp_path.write_bytes(base64.b64decode(body["audio_base64"]))
                    tmp_json.write_text(json.dumps({
                        "text": text,
                        "alignment": body.get("alignment") or {},
                    }), encoding="utf-8")
                    os.replace(tmp_json, json_path)
                    os.replace(tmp_path, out_path)
                    return
                last_error = (f"ElevenLabs TTS error "
                              f"({response.status_code}): {response.text[:300]}")
                if response.status_code not in RETRY_STATUSES:
                    raise RuntimeError(last_error)
                wait = _retry_delay(response, attempt)
            except (httpx.HTTPError, ValueError, KeyError) as e:
                # Dropped, never connected, or a garbled body — same treatment.
                last_error = f"ElevenLabs request failed: {e}"
                wait = _retry_delay(None, attempt)
            if attempt == MAX_ATTEMPTS - 1:
                break
            # Wait on the cancel flag rather than sleeping, so Stop doesn't sit
            # out a backoff of up to 16 seconds.
            if cancel is not None:
                if cancel.wait(wait):
                    raise Cancelled()
            else:
                time.sleep(wait)
    finally:
        tmp_path.unlink(missing_ok=True)
        tmp_json.unlink(missing_ok=True)
    raise RuntimeError(f"{last_error} (gave up after {MAX_ATTEMPTS} attempts)")


def generate(slides: list, audio_dir: Path, voice_id: str, model: str,
             settings: dict | None = None, progress=None, cancel=None,
             engine: str = "elevenlabs", kokoro_settings: dict | None = None,
             timed: bool = False) -> dict:
    """(Re)synthesize audio for `slides`, write the manifest, prune the cache.

    engine: "elevenlabs" uses voice_id, model and settings; "kokoro" uses
    kokoro_settings ({"voice", "speed"}) and needs no key.

    timed: a reveal.js deck. The narration's [next] markers are stripped before
    speaking, and every clip gets a timing file beside it. A Kokoro clip is
    spoken in pieces cut at the markers, so its name also covers where the
    markers sit: moving one re-speaks that slide. An ElevenLabs clip's name
    covers only the spoken text.

    `slides` is the deck's narration — {index, narration, ...} — in any order.
    Slides with no narration get no audio and are shown silently in the video.

    progress: optional callable(done, total, message).
    cancel: optional threading.Event; once set, no new clip is started and
    Cancelled is raised. The manifest is left alone and nothing is pruned.
    Returns {"total", "narrated", "synthesized", "skipped"}.
    """
    audio_dir.mkdir(parents=True, exist_ok=True)
    merged = _merged_settings(settings)
    ksettings = _kokoro_settings(kokoro_settings)
    use_kokoro = engine == "kokoro"
    sig = _kokoro_sig(ksettings) if use_kokoro else _voice_sig(voice_id, model, merged)

    manifest = []
    tasks = {}       # filename -> (text, marker offsets) still to synthesize
    keep = set()
    narrated = 0

    for s in sorted(slides, key=lambda s: s["index"]):
        if timed:
            text, offsets = markers.split(s.get("narration") or "")
        else:
            text, offsets = (s.get("narration") or "").strip(), []
        entry = {"index": s["index"], "file": None, "words": len(text.split())}
        if text:
            narrated += 1
            key = text + chr(0) + sig
            if timed and use_kokoro:
                key += chr(0) + ",".join(map(str, offsets))
            filename = f"{_sha(key)[:32]}.mp3"
            entry["file"] = filename
            keep.add(filename)
            clip = audio_dir / filename
            if not (clip.exists() and (not timed or timing_path(clip).exists())):
                tasks[filename] = (text, offsets)
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

    # Kokoro's first use downloads and loads the model, which takes a while
    # with nothing to count. Say so, rather than sit at "0 of N".
    if use_kokoro and tasks and not kokoro.loaded():
        if progress:
            note = ("Loading the Kokoro voice" if kokoro.downloaded() else
                    f"Downloading the Kokoro voice model (about "
                    f"{kokoro.DOWNLOAD_MB} MB, first time only)")
            progress(done, total, note)

    def _render(item):
        nonlocal done
        filename, (text, offsets) = item
        _check(cancel)
        out = audio_dir / filename
        if timed and use_kokoro:
            synthesize_kokoro_timed(text, offsets, out, ksettings)
        elif timed:
            synthesize_timed(text, out, voice_id, model, merged, cancel)
        elif use_kokoro:
            kokoro.synthesize(text, out, ksettings["voice"], ksettings["speed"])
        else:
            synthesize(text, out, voice_id, model, merged, cancel)
        with lock:
            done += 1
            if progress:
                progress(done, total, "Generating audio")

    if tasks:
        # Kokoro runs on this computer's CPU, one clip at a time (kokoro.py
        # serializes it anyway); the concurrency setting is ElevenLabs' cap.
        cap = 1 if use_kokoro else config.TTS_CONCURRENCY
        workers = max(1, min(cap, len(tasks)))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_render, item) for item in tasks.items()]
            try:
                for f in as_completed(futures):
                    exc = f.exception()
                    if exc:
                        raise exc
            except BaseException:
                # Drop queued clips; the `with` exit still waits for the ones
                # already at ElevenLabs, so they finish and are cached.
                ex.shutdown(wait=False, cancel_futures=True)
                raise

    (audio_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    _prune(audio_dir, keep)

    return {"total": len(slides), "narrated": narrated,
            "synthesized": len(tasks), "skipped": skipped}


def _prune(audio_dir: Path, keep: set) -> None:
    """Drop clips no slide points at any more. The cache is only worth keeping
    for the current deck: an old clip can never be hit again, because its name
    encodes text that no slide says."""
    for f in list(audio_dir.glob("*.mp3")) + list(audio_dir.glob("*.json")):
        if f.name == "manifest.json":
            continue
        if f.with_suffix(".mp3").name not in keep:
            try:
                f.unlink()
            except OSError:
                pass
