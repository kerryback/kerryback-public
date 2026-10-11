"""Background jobs: ingest (read the PDF) and build (TTS + video).
Each runs in a thread and reports progress via events.

The narration itself is not written here. It is written in the app, or by the
Claude Code agent through the narration API; an ingest only ever carries an
existing script onto the slides of a newly uploaded PDF.
"""
import threading
import traceback

from . import audio_gen, db, deck, events, slidematch, store, video_gen


def _run_bg(fn, pid, *args):
    def wrapper():
        events.start(pid)
        try:
            fn(pid, *args)
        except Exception as e:
            log = f"{e}\n{traceback.format_exc()}"
            store.set_state(pid, _fail_state(db.get_project(pid)), log=log)
            events.emit(pid, "error", db.get_project(pid)["state"], message=str(e))
        finally:
            events.finish(pid)
    threading.Thread(target=wrapper, daemon=True).start()


def _fail_state(proj) -> str:
    state = proj["state"] if proj else ""
    mapping = {"loading": "load_failed", "building": "building_failed"}
    return mapping.get(state, f"{state}_failed")


# --------------------------------------------------------------------------- #
# Ingest — render the PDF's pages, carry any existing narration onto them
# --------------------------------------------------------------------------- #
def start_ingest(pid: str):
    _run_bg(_ingest, pid)


def _ingest(pid: str):
    store.set_state(pid, "loading", log="")
    events.emit(pid, "load", "loading", 0, 1, "Reading the PDF")

    # Snapshot the previous ingest before this one overwrites it, so a deck the
    # author edited and re-uploaded can be matched against what it was. A
    # deck whose narration.json is unreadable ingests as if it were new rather
    # than failing — losing the old script beats being unable to re-upload at all.
    prior = {s["index"]: s for s in store.read_narration(pid).get("slides", [])}
    prior_fps = store.read_fingerprints(pid)
    had_script = any((s.get("narration") or "").strip() for s in prior.values())

    def prog(done, total, msg):
        events.emit(pid, "load", "loading", done, total, msg)

    result = deck.ingest(store.pdf_path(pid), store.slides_dir(pid), progress=prog)
    slides = result["slides"]

    review = None
    if had_script and prior_fps:
        review = _carry_over(slides, prior, prior_fps, result["fingerprints"])
    elif prior:
        # Nothing to preserve carefully — carry by index and move on.
        for s in slides:
            s["narration"] = prior.get(s["index"], {}).get("narration", "")

    store.write_narration(pid, {"slides": slides})
    store.write_fingerprints(pid, result["fingerprints"])
    store.set_review(pid, review)
    store.record_source(pid)
    if not store.config_path(pid).exists():
        store.write_config(pid, {})

    n = len(slides)
    narrated = sum(1 for s in slides if (s.get("narration") or "").strip())
    store.set_state(pid, "ready", log="")
    events.emit(pid, "load", "ready", 1, 1, f"{n} slides · {narrated} narrated")


def _carry_over(slides: list, prior: dict, prior_fps: list,
                fingerprints: list) -> dict | None:
    """Move the previous ingest's narration onto the re-uploaded deck.

    Matching is by content, not index (see slidematch): insert a page and every
    later slide would otherwise inherit its neighbour's script. Slides that
    survive keep their narration; those whose content moved are flagged, so the
    author sees what to re-read and Claude knows what to redraft. Narration
    on an edited slide is kept rather than blanked — it is the right starting
    point, and sometimes it still fits.

    Audio is not touched: clips are named for the text they speak, so a script
    that lands on a different slide brings its audio with it.
    """
    by_index = {s["index"]: s for s in slides}
    result = slidematch.align(_with_text(prior_fps, prior),
                              _with_text(fingerprints, by_index))
    pairs, status = result["pairs"], result["status"]

    for s in slides:
        j = s["index"]
        old = pairs.get(j)
        if old is not None:
            s["narration"] = prior.get(old, {}).get("narration", "")
        if status.get(j):
            s["change"] = status[j]

    summary = result["summary"]
    if not (summary["edited"] or summary["new"] or summary["removed"]):
        return None
    return summary


def _with_text(fingerprints: list, slides: dict) -> list:
    """Attach each slide's page text to its fingerprint. The shas alone can only
    say same-or-different; the text is what lets slidematch recognize a slide
    that was reworded rather than replaced (fingerprints.json stays sha-only,
    since narration.json already holds the text)."""
    return [dict(fp, text=slides.get(fp["index"], {}).get("slide_text", ""))
            for fp in fingerprints]


# --------------------------------------------------------------------------- #
# Build — synthesize audio, render the video and transcript
# --------------------------------------------------------------------------- #
def start_build(pid: str):
    _run_bg(_build, pid)


def _build(pid: str):
    store.set_state(pid, "building", log="")
    slides = store.read_narration(pid)["slides"]
    if not any((s.get("narration") or "").strip() for s in slides):
        raise RuntimeError(
            "No slide has narration yet — there is nothing to speak. Write it on "
            "the Narration screen, or ask Claude to draft it.")

    cfg = store.read_config(pid)

    events.emit(pid, "build", "building", 0, 2, "Generating audio")

    # "(4/12)" was read as "working on slide 4". It was always a completion
    # count -- clips finish out of order under the thread pool -- so say so.
    def aprog(done, total, msg):
        events.emit(pid, "build", "building", 0, 2,
                    f"{msg} — {done} of {total} complete")

    stats = audio_gen.generate(
        slides, store.audio_dir(pid), cfg["voice_id"], cfg["model"],
        {k: cfg[k] for k in audio_gen.VOICE_SETTING_KEYS if k in cfg},
        progress=aprog)

    def vprog(done, total, msg):
        events.emit(pid, "build", "building", 1, 2,
                    f"{msg} — {done} of {total} complete")

    events.emit(pid, "build", "building", 1, 2, "Rendering video")
    store.video_path(pid).parent.mkdir(parents=True, exist_ok=True)
    video_gen.generate(pid, progress=vprog)

    _write_transcript(pid)
    _announce_outputs(pid)

    # Stamp what this video was built from, so a later script or settings change
    # shows up as "needs regenerating" without tracking edits one by one.
    db.update_project(pid, build_sig=store.build_signature(pid))
    store.set_state(pid, "built")
    events.emit(pid, "build", "built", 2, 2,
                f"Built ({stats['synthesized']} synthesized, "
                f"{stats['skipped']} reused)")


def _announce_outputs(pid: str) -> None:
    """The MP4 + transcript are written directly to their final location (the
    project folder when launched by the skill; the deck folder otherwise) — just
    report where."""
    base = store.output_base(pid)
    where = store.video_path(pid).parent
    events.emit(pid, "build", "building", 2, 2,
                f"Saved {base}.mp4 and {base}.txt to {where}")


def _write_transcript(pid: str) -> None:
    """Write the transcript: the spoken narration, slide by slide."""
    proj = db.get_project(pid)
    title = proj["name"] if proj else "Transcript"
    slides = sorted(store.read_narration(pid)["slides"], key=lambda s: s["index"])
    lines = [
        title,
        "Narration transcript",
        "Generated from the narration in the Voiceover app. To change the script, "
        "edit it there — edits made directly to this file are replaced on the "
        "next build.",
        "",
    ]
    for s in slides:
        head = f"Slide {s['index'] + 1}"
        if s.get("title"):
            head += f" — {s['title']}"
        lines.append(head)
        lines.append((s.get("narration") or "(silent)").strip())
        lines.append("")
    store.transcript_path(pid).write_text(
        "\n".join(lines).rstrip() + "\n", encoding="utf-8")
