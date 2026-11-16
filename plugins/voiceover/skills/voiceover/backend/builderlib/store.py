"""Per-deck file I/O: narration.json, fingerprints.json, config.json, meta.json.

A deck folder holds everything the app owns: the slide images (rendered from a
PDF's pages, or taken from a reveal.js deck in headless Chrome), the narration
script, the per-slide content fingerprints used to carry that script across a
re-upload, the TTS audio, and the voice settings. A PDF deck also keeps its PDF
here; a reveal.js deck is read where it is, or from an unpacked upload.

The narration lives here, not in a source deck: a PDF has nowhere to put it, and
a rendered reveal.js file is rewritten on every Quarto render.
That makes this folder the single copy, edited in the app (autosaved) or by
Claude Code through the narration API.
"""
import hashlib
import json
from pathlib import Path

from . import config, db

DEFAULT_CONFIG = {
    # ElevenLabs voice + model. "J9NvviOEdVm6E7Hwdpdj" is "Jerry B."; the
    # author picks a different one (including a cloned voice) from the
    # account's voice list in the UI.
    "voice_id": "J9NvviOEdVm6E7Hwdpdj",
    # v3 is the expressive model. The v2 family is deliberately even-toned, which
    # on a long narrated lecture comes out sounding flat — that is the model, not
    # the account tier, and not something a paid upgrade changes.
    "model": "eleven_v3",
    "stability": 0.5,
    "similarity_boost": 0.75,
    # Expression controls. `style` is lifted above ElevenLabs' own default of
    # 0.0, which reads flat over a full lecture; the rest match their server-side
    # defaults, so they change nothing until the author moves them.
    "style": 0.5,
    "use_speaker_boost": True,
    "speed": 1.0,
    # Kokoro voice + speed, used when the account's engine is Kokoro. Both sets
    # are kept on the deck, so switching engine and back loses neither.
    "kokoro_voice": "af_heart",
    "kokoro_speed": 1.0,
}

# The settings each engine's audio depends on. The build signature covers only
# the engine in force, so tuning the idle engine's settings does not mark the
# video stale, and an ElevenLabs deck built before engines existed keeps the
# signature it was stamped with.
ELEVEN_KEYS = ("voice_id", "model", "stability", "similarity_boost", "style",
               "use_speaker_boost", "speed")
KOKORO_KEYS = ("kokoro_voice", "kokoro_speed")


def pdir(pid: str) -> Path:
    return config.project_dir(pid)


def narration_path(pid: str) -> Path:
    return pdir(pid) / "narration.json"


def fingerprints_path(pid: str) -> Path:
    """Per-slide content shas from the last ingest. Kept out of narration.json so
    the payload Claude reads stays about narration."""
    return pdir(pid) / "fingerprints.json"


def config_path(pid: str) -> Path:
    return pdir(pid) / "config.json"


def meta_path(pid: str) -> Path:
    return pdir(pid) / "meta.json"


def audio_dir(pid: str) -> Path:
    return pdir(pid) / "audio"


def slides_dir(pid: str) -> Path:
    return pdir(pid) / "slides"


def pdf_path(pid: str) -> Path:
    """The app's copy of the deck PDF. A copy rather than a reference because the
    PDF also arrives by upload from the browser, which has no path to point at —
    and because an ingest must keep matching the page images it produced."""
    return pdir(pid) / "deck.pdf"


# The two deck formats. The file type picks one when a deck arrives; meta.json
# keeps it as source_type. A deck from before reveal.js decks were supported
# has "pdf" or nothing, which both mean PDF.
PDF = "pdf"
REVEALJS = "revealjs"


def deck_format(pid: str) -> str:
    return REVEALJS if read_meta(pid).get("source_type") == REVEALJS else PDF


def is_revealjs(pid: str) -> bool:
    return deck_format(pid) == REVEALJS


def upload_dir(pid: str) -> Path:
    """Where an uploaded reveal.js deck (a self-contained .html, or an unpacked
    .zip) lives. A reveal.js deck opened by path is not copied: its HTML leans
    on a `_files` folder and sometimes on images above it, and only the
    original location has all of them."""
    return pdir(pid) / "upload"


def deck_html(pid: str) -> Path | None:
    """The reveal.js .html file the app reads and records: the original file for
    a deck opened by path, the unpacked upload otherwise."""
    meta = read_meta(pid)
    if meta.get("source_path"):
        return Path(meta["source_path"])
    if meta.get("upload_html"):
        return Path(meta["upload_html"])
    return None


def output_base(pid: str) -> str:
    """Filename stem for a deck's visible outputs in the project folder."""
    return pid


def video_path(pid: str) -> Path:
    """The finished MP4. When launched by the skill it lives in the author's
    project folder (config.OUTPUT_DIR) so the output is easy to find; otherwise it
    stays inside the deck folder."""
    if config.OUTPUT_DIR:
        return Path(config.OUTPUT_DIR).expanduser() / f"{output_base(pid)}.mp4"
    return pdir(pid) / "video.mp4"


def transcript_path(pid: str) -> Path:
    if config.OUTPUT_DIR:
        return Path(config.OUTPUT_DIR).expanduser() / f"{output_base(pid)}.txt"
    return pdir(pid) / "transcript.txt"


# --------------------------------------------------------------------------- #
# Narration — the script, slide by slide. The app owns this copy.
# --------------------------------------------------------------------------- #
def read_narration(pid: str) -> dict:
    p = narration_path(pid)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            return {"slides": []}
    return {"slides": []}


def write_narration(pid: str, data: dict) -> None:
    narration_path(pid).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def set_narration(pid: str, index: int, text: str) -> bool:
    """Write one slide's script. Returns False if there is no such slide.

    Editing a slide is exactly what a re-upload flag was asking for, so the flag
    goes with the edit.
    """
    data = read_narration(pid)
    for s in data.get("slides", []):
        if s["index"] == index:
            s["narration"] = text
            s.pop("change", None)
            write_narration(pid, data)
            _drop_review_if_clean(pid, data)
            return True
    return False


def set_narration_bulk(pid: str, by_index: dict) -> int:
    """Write several slides at once — how Claude delivers a draft. Slides not
    named are left alone. Returns how many were written."""
    data = read_narration(pid)
    written = 0
    for s in data.get("slides", []):
        if s["index"] in by_index:
            s["narration"] = by_index[s["index"]]
            s.pop("change", None)
            written += 1
    if written:
        write_narration(pid, data)
        _drop_review_if_clean(pid, data)
    return written


# --------------------------------------------------------------------------- #
# Fingerprints + the re-upload review
# --------------------------------------------------------------------------- #
def read_fingerprints(pid: str) -> list:
    p = fingerprints_path(pid)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("slides", [])
        except ValueError:
            return []
    return []


def write_fingerprints(pid: str, slides: list) -> None:
    fingerprints_path(pid).write_text(
        json.dumps({"slides": slides}, indent=2), encoding="utf-8")


def set_review(pid: str, review: dict | None) -> None:
    """Record (or clear) what the last re-upload changed, for the UI banner."""
    db.update_project(pid, review=review or None)


def read_review(pid: str) -> dict:
    return read_meta(pid).get("review") or {}


def clear_flags(pid: str, indexes: list | None = None) -> int:
    """Drop the `change` flag from slides the author (or Claude) has dealt
    with. `indexes` None clears every flag. Returns how many were cleared."""
    data = read_narration(pid)
    wanted = None if indexes is None else set(indexes)
    cleared = 0
    for s in data.get("slides", []):
        if s.get("change") and (wanted is None or s["index"] in wanted):
            s.pop("change", None)
            cleared += 1
    if cleared:
        write_narration(pid, data)
        _drop_review_if_clean(pid, data)
    return cleared


def _drop_review_if_clean(pid: str, data: dict) -> None:
    """The review banner is a to-do list; it disappears once nothing is flagged."""
    if not any(s.get("change") for s in data.get("slides", [])):
        set_review(pid, None)


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def read_config(pid: str) -> dict:
    p = config_path(pid)
    cfg = dict(DEFAULT_CONFIG)
    if p.exists():
        try:
            cfg.update(json.loads(p.read_text(encoding="utf-8")))
        except ValueError:
            pass
    return cfg


def write_config(pid: str, cfg: dict) -> dict:
    merged = read_config(pid)
    merged.update({k: v for k, v in cfg.items() if v is not None})
    config_path(pid).write_text(
        json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    return merged


# --------------------------------------------------------------------------- #
# Meta / the file this deck came from
# --------------------------------------------------------------------------- #
def read_meta(pid: str) -> dict:
    p = meta_path(pid)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def source_file(pid: str) -> Path | None:
    """Where the deck (a PDF or a reveal.js .html) came from on disk, when it was
    opened by path rather than uploaded through the browser. Kept so the app
    can notice a re-export or re-render and offer to pick it up."""
    src = read_meta(pid).get("source_path", "")
    return Path(src) if src else None


def _mtime(path: Path | None) -> float:
    try:
        return path.stat().st_mtime if path else 0.0
    except OSError:
        return 0.0


def record_source(pid: str) -> None:
    """Snapshot the origin file's mtime, so a later re-export shows up as changed."""
    db.update_project(pid, source_mtime=_mtime(source_file(pid)))


def file_status(pid: str) -> dict:
    """What the app knows about the file behind this deck.

    `changed` is the useful one: the author edited their slides and exported
    or rendered them again, so the slides the app is narrating are out of date.
    For a PDF it is an offer, not an alarm: nothing breaks until they take it.
    A reveal.js deck is recorded from the file itself, so Generate refuses until
    the deck is read again (jobs._build), or the narration would not line up.
    """
    meta = read_meta(pid)
    src = source_file(pid)
    now = _mtime(src)
    name = src.name if src else meta.get("upload_name", "")
    return {
        "format": deck_format(pid),
        "deck": name,
        "pdf": name,
        "source_path": str(src) if src else "",
        "source_dir": str(src.parent) if src else "",
        "missing": bool(src and not src.is_file()),
        "changed": bool(now and now > meta.get("source_mtime", 0) + 0.5),
        "uploaded": not src,
    }


# --------------------------------------------------------------------------- #
# Build signature — is the rendered video still the one this script describes?
# --------------------------------------------------------------------------- #
def build_signature(pid: str) -> str:
    """A sha over everything that determines the output: every slide's narration,
    in order, plus the engine's voice settings, and for a reveal.js deck the deck
    as last read. Comparing it to the signature stored at build time answers "is
    this video current?" without tracking edits one by one. A PDF deck's
    signature has no format line, so it is the same as before reveal.js decks
    were supported and an existing video is not marked stale."""
    slides = sorted(read_narration(pid).get("slides", []), key=lambda s: s["index"])
    cfg = read_config(pid)
    parts = [f"{s['index']}:{s.get('narration', '')}" for s in slides]
    if is_revealjs(pid):
        parts.append(f"deck={read_meta(pid).get('deck_sha', '')}")
    if config.tts_engine() == "kokoro":
        parts += ["engine=kokoro"] + [f"{k}={cfg.get(k)}" for k in KOKORO_KEYS]
    else:
        parts += [f"{k}={cfg.get(k)}" for k in sorted(ELEVEN_KEYS)]
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()


def is_stale(pid: str) -> bool:
    proj = db.get_project(pid)
    if not proj or proj.get("state") != "built":
        return False
    return proj.get("build_sig", "") != build_signature(pid)


def set_state(pid: str, state: str, log: str = None) -> None:
    fields = {"state": state}
    if log is not None:
        fields["log"] = log
    db.update_project(pid, **fields)
