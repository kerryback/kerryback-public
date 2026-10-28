"""Voiceover Builder — FastAPI backend. Implements CONTRACT.md."""
import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from builderlib import config, db, deck, events, jobs, store

db.init()

# No auth: this runs locally as a skill, launched per-deck by the author.
app = FastAPI(title="Voiceover Builder")


# --------------------------------------------------------------------------- #
# Decks
# --------------------------------------------------------------------------- #
def _summary(p: dict) -> dict:
    return {
        "id": p["id"], "name": p["name"], "state": p["state"],
        "stale": store.is_stale(p["id"]),
        "files": store.file_status(p["id"]),
        "updated_at": p["updated_at"],
    }


@app.get("/api/projects")
async def list_projects():
    return [_summary(p) for p in db.list_projects()]


def _ingest_pdf(pid: str, name: str, data: bytes, source_path: Path | None,
                upload_name: str = "") -> dict:
    """Write a PDF into the deck folder and start reading it.

    Shared by all three ways a PDF arrives — the launcher's path, a browser
    upload, and re-reading an edited file from its original path. The deck keeps
    its id and its folder every time, which is what lets an existing script be
    carried onto the new slides (jobs._ingest).
    """
    config.project_dir(pid).mkdir(parents=True, exist_ok=True)
    if db.get_project(pid) is None:
        db.create_project(pid, name, "pdf", "loading")
    store.pdf_path(pid).write_bytes(data)
    db.update_project(pid, source_type="pdf",
                      source_path=str(source_path.resolve()) if source_path else "",
                      upload_name=upload_name)
    jobs.start_ingest(pid)
    return _summary(db.get_project(pid))


class OpenBody(BaseModel):
    pdf: str
    name: str | None = None
    project: str | None = None


@app.post("/api/projects")
async def open_deck(body: OpenBody):
    """Open (or reopen) a deck from a PDF already on disk — how the launcher
    opens the deck the author named.

    `project` re-reads the PDF into an existing deck instead of deriving the
    deck id from the filename, for a re-export saved under a different name
    (which would otherwise start a second deck from scratch).
    """
    pdf = Path(body.pdf).expanduser()
    if not pdf.is_file():
        raise HTTPException(400, f"PDF not found: {pdf}")
    if not deck.is_pdf(pdf):
        raise HTTPException(400, deck.NOT_PDF_MESSAGE)
    if body.project:
        if not db.get_project(body.project):
            raise HTTPException(404, "not found")
        return _ingest_pdf(body.project, body.name or pdf.stem, pdf.read_bytes(),
                           pdf)
    pid = deck.deck_slug(pdf.stem)
    return _ingest_pdf(pid, body.name or pdf.stem, pdf.read_bytes(), pdf)


@app.post("/api/projects/upload", status_code=202)
async def upload_new_deck(file: UploadFile = File(...)):
    """Start a new deck from a PDF uploaded in the browser — the Upload screen
    when no deck is open, which is how a bare launch (`/voiceover` with no deck
    named) gets its slides.

    The deck id is a slug of the uploaded filename, so uploading the same deck
    again reopens it rather than starting a second copy of it.
    """
    name = file.filename or "deck.pdf"
    if not deck.is_pdf(Path(name)):
        raise HTTPException(400, deck.NOT_PDF_MESSAGE)
    data = await file.read()
    if not data:
        raise HTTPException(400, "That file is empty.")
    pid = deck.deck_slug(Path(name).stem)
    return _ingest_pdf(pid, Path(name).stem, data, None, upload_name=name)


@app.post("/api/projects/{pid}/pdf", status_code=202)
async def upload_pdf(pid: str, file: UploadFile = File(...)):
    """Upload a new PDF into this deck from the browser — the Upload screen with
    a deck already open.

    The deck keeps its id, its settings and its script: the new slides are
    matched against the previous ingest by content, so an inserted or reordered
    slide doesn't shift everyone's narration by one.
    """
    if not db.get_project(pid):
        raise HTTPException(404, "not found")
    name = file.filename or "deck.pdf"
    if not deck.is_pdf(Path(name)):
        raise HTTPException(400, deck.NOT_PDF_MESSAGE)
    data = await file.read()
    if not data:
        raise HTTPException(400, "That file is empty.")
    return _ingest_pdf(pid, db.get_project(pid)["name"], data, None,
                       upload_name=name)


@app.post("/api/projects/{pid}/reload", status_code=202)
async def reload_deck(pid: str):
    """Re-read the PDF this deck was opened from — after re-exporting it in
    place. Only available when the deck was opened by path; an uploaded PDF has
    no file to go back to, so re-upload it instead."""
    if not db.get_project(pid):
        raise HTTPException(404, "not found")
    src = store.source_pdf(pid)
    if not src or not src.is_file():
        raise HTTPException(
            409,
            "This deck's PDF isn't on disk where the app opened it. Upload the "
            "PDF instead.")
    return _ingest_pdf(pid, db.get_project(pid)["name"], src.read_bytes(), src)


@app.get("/api/projects/{pid}")
async def get_project(pid: str):
    proj = db.get_project(pid)
    if not proj:
        raise HTTPException(404, "not found")
    slides = []
    for s in sorted(store.read_narration(pid).get("slides", []),
                    key=lambda s: s["index"]):
        i = s["index"]
        png = store.slides_dir(pid) / f"slide-{i + 1:03d}.png"
        slides.append({
            "index": i,
            "title": s.get("title", ""),
            "narration": s.get("narration", ""),
            # "edited" | "new" when a re-uploaded PDF moved this slide's content.
            "change": s.get("change") or None,
            "image_url": (f"api/projects/{pid}/slides/slide-{i + 1:03d}.png"
                          if png.exists() else None),
        })
    return {
        "id": proj["id"], "name": proj["name"], "state": proj["state"],
        "stale": store.is_stale(pid), "files": store.file_status(pid),
        "slides": slides, "config": store.read_config(pid),
        "review": store.read_review(pid), "log": proj.get("log", ""),
        # Cache-buster for the in-app video player: a rebuild changes this.
        "updated_at": proj.get("updated_at", 0),
    }


# --------------------------------------------------------------------------- #
# Narration — the script. The app owns it; Claude Code and the author both
# write to it through here.
# --------------------------------------------------------------------------- #
@app.get("/api/projects/{pid}/narration")
async def get_narration(pid: str):
    """The script slide by slide, each with the page's extracted text for
    context, plus `review` — what the last re-uploaded PDF changed.

    Slides the re-upload moved carry `change: "edited" | "new"`; that is how
    Claude knows which slides to redraft rather than rewriting a deck whose
    script is mostly still good.
    """
    if not db.get_project(pid):
        raise HTTPException(404, "not found")
    data = store.read_narration(pid)
    data["review"] = store.read_review(pid)
    return data


class NarrationBody(BaseModel):
    narration: str


@app.put("/api/projects/{pid}/narration/{index}")
async def put_narration(pid: str, index: int, body: NarrationBody):
    """One slide's script — the editor's autosave."""
    if not db.get_project(pid):
        raise HTTPException(404, "not found")
    if not store.set_narration(pid, index, body.narration):
        raise HTTPException(404, f"No slide {index} in this deck.")
    return {"ok": True}


class NarrationSlide(BaseModel):
    index: int
    narration: str


class NarrationBulkBody(BaseModel):
    slides: list[NarrationSlide]


@app.put("/api/projects/{pid}/narration")
async def put_narration_bulk(pid: str, body: NarrationBulkBody):
    """Several slides at once — how Claude delivers a draft. Slides not named
    are left alone, so a partial redraft doesn't blank the rest."""
    if not db.get_project(pid):
        raise HTTPException(404, "not found")
    written = store.set_narration_bulk(
        pid, {s.index: s.narration for s in body.slides})
    return {"ok": True, "written": written}


class ClearReviewBody(BaseModel):
    indexes: list[int] | None = None


@app.post("/api/projects/{pid}/review/clear")
async def clear_review(pid: str, body: ClearReviewBody):
    """Mark re-upload-flagged slides as dealt with without editing them — the
    editor's "keep as is". Omit `indexes` to clear every flag."""
    if not db.get_project(pid):
        raise HTTPException(404, "not found")
    return {"cleared": store.clear_flags(pid, body.indexes)}


class ConfigBody(BaseModel):
    voice_id: str | None = None
    model: str | None = None
    stability: float | None = None
    similarity_boost: float | None = None
    style: float | None = None
    use_speaker_boost: bool | None = None
    speed: float | None = None


@app.put("/api/projects/{pid}/config")
async def put_config(pid: str, body: ConfigBody):
    if not db.get_project(pid):
        raise HTTPException(404, "not found")
    merged = store.write_config(pid, body.model_dump())
    return {"ok": True, "config": merged}


# --------------------------------------------------------------------------- #
# ElevenLabs
# --------------------------------------------------------------------------- #
@app.get("/api/tts/status")
async def tts_status():
    """Whether an ElevenLabs key is configured. Cheap (no network call) so the
    app-wide key banner can poll it without hitting ElevenLabs."""
    return {
        "configured": bool(config.ELEVENLABS_API_KEY),
        "concurrency": config.TTS_CONCURRENCY,
    }


class KeyBody(BaseModel):
    api_key: str


class ConcurrencyBody(BaseModel):
    concurrency: int


@app.post("/api/tts/concurrency")
async def set_tts_concurrency(body: ConcurrencyBody):
    """Set how many TTS requests run at once, and persist it account-wide.

    ElevenLabs caps concurrent requests per plan and returns 429 above it, which
    fails the build. The API exposes the plan tier but not its concurrency
    number, so this cannot be detected — the author sets it from what their
    plan allows.
    """
    n = int(body.concurrency)
    if not 1 <= n <= 15:
        raise HTTPException(400, "Concurrency must be between 1 and 15.")
    config.set_tts_concurrency(n)
    return {"concurrency": config.TTS_CONCURRENCY}


@app.post("/api/tts/key")
async def set_tts_key(body: KeyBody):
    """Validate an ElevenLabs key against the API and, if good, persist it to
    ~/.voiceover/.env and load it live — so the author never edits a file,
    and the key survives a skill update."""
    key = (body.api_key or "").strip()
    if not key:
        raise HTTPException(400, "Enter your ElevenLabs API key.")
    import httpx
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.get("https://api.elevenlabs.io/v1/user",
                                 headers={"xi-api-key": key})
        except httpx.HTTPError as e:
            raise HTTPException(502, f"Could not reach ElevenLabs: {e}")
    if r.status_code in (401, 403):
        raise HTTPException(400, "ElevenLabs rejected that key. Check it and try again.")
    if r.status_code != 200:
        raise HTTPException(502, f"ElevenLabs error ({r.status_code}).")
    config.set_elevenlabs_key(key)
    return {"configured": True}


@app.get("/api/tts/voices")
async def tts_voices():
    """List the account's ElevenLabs voices (including cloned voices) for the
    voice picker. Returns configured=False when no key is set so the UI can
    prompt for one instead of erroring."""
    if not config.ELEVENLABS_API_KEY:
        return {"configured": False, "voices": []}
    import httpx
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get("https://api.elevenlabs.io/v1/voices",
                             headers={"xi-api-key": config.ELEVENLABS_API_KEY})
    if r.status_code != 200:
        raise HTTPException(502, f"ElevenLabs voices error ({r.status_code})")
    voices = [{"voice_id": v["voice_id"], "name": v.get("name", ""),
               "category": v.get("category", "")}
              for v in r.json().get("voices", [])]
    return {"configured": True, "voices": voices}


@app.get("/api/tts/voices/{voice_id}")
async def tts_voice(voice_id: str):
    """Resolve one voice id to its name, labels and preview clip.

    Two lookups, because neither alone covers both cases. /v1/voices/{id}
    answers only for voices the account already holds — its premade set and its
    clones — and 400s on anything else. The Voice Library is reached instead
    through /v1/shared-voices, whose `search` matches an id exactly.

    Text-to-speech accepts a library voice directly, with no add-to-my-voices
    step; ElevenLabs files it under the account the first time it is used, so
    after one build it also answers to the first lookup.
    """
    voice_id = voice_id.strip()
    if not config.ELEVENLABS_API_KEY:
        raise HTTPException(400, "Add your ElevenLabs API key first.")
    headers = {"xi-api-key": config.ELEVENLABS_API_KEY}
    import httpx
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.get(
                f"https://api.elevenlabs.io/v1/voices/{voice_id}",
                headers=headers)
            if r.status_code == 200:
                v = r.json()
                labels = v.get("labels") or {}
                return {
                    "voice_id": v.get("voice_id", voice_id),
                    "name": v.get("name", ""),
                    "category": v.get("category", ""),
                    "preview_url": v.get("preview_url", ""),
                    # Only the labels worth showing, in the order they read best.
                    "labels": [labels[k] for k in
                               ("gender", "age", "accent", "language", "use_case")
                               if labels.get(k)],
                }
            if r.status_code in (401, 403):
                raise HTTPException(400, "ElevenLabs rejected your API key.")

            # Not one of the account's own — try the Voice Library.
            r = await client.get(
                "https://api.elevenlabs.io/v1/shared-voices",
                params={"search": voice_id, "page_size": 1}, headers=headers)
        except httpx.HTTPError as e:
            raise HTTPException(502, f"Could not reach ElevenLabs: {e}")
    if r.status_code != 200:
        raise HTTPException(502, f"ElevenLabs voice error ({r.status_code})")
    # `search` is a match, not a lookup, so confirm the hit is the id we asked
    # for rather than a near miss.
    hits = [v for v in r.json().get("voices", [])
            if v.get("voice_id") == voice_id]
    if not hits:
        raise HTTPException(404, f"No ElevenLabs voice with id {voice_id}.")
    v = hits[0]
    return {
        "voice_id": v["voice_id"],
        "name": v.get("name", ""),
        "category": v.get("category", ""),
        "preview_url": v.get("preview_url", ""),
        "labels": [v[k] for k in
                   ("gender", "age", "accent", "language", "use_case")
                   if v.get(k)],
    }


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
@app.post("/api/projects/{pid}/build", status_code=202)
async def build(pid: str):
    proj = db.get_project(pid)
    if not proj:
        raise HTTPException(404, "not found")
    if proj["state"] == "loading":
        raise HTTPException(409, "The deck is still loading.")
    if proj["state"] == "load_failed":
        raise HTTPException(409, "The deck could not be loaded — fix that first.")
    # The live job, not the saved state: a server stopped mid-build leaves
    # "building" on disk with nothing running.
    if jobs.is_building(pid):
        raise HTTPException(409, "A build is already running.")
    jobs.start_build(pid)
    return {"started": True}


@app.post("/api/projects/{pid}/build/cancel", status_code=202)
async def cancel_build(pid: str):
    """Stop the running build. It ends at the next clip or segment boundary and
    the deck returns to its previous state (see jobs._build)."""
    if not db.get_project(pid):
        raise HTTPException(404, "not found")
    if not jobs.cancel_build(pid):
        raise HTTPException(409, "No build is running.")
    return {"stopping": True}


@app.get("/api/projects/{pid}/events")
async def project_events(pid: str, request: Request):
    if not db.get_project(pid):
        raise HTTPException(404, "not found")

    async def gen():
        since = 0
        idle = 0
        while True:
            if await request.is_disconnected():
                break
            new, since, active = events.snapshot(pid, since)
            for evt in new:
                yield f"data: {json.dumps(evt)}\n\n"
            if not new:
                idle += 1
            else:
                idle = 0
            if not active and not new:
                yield "event: done\ndata: {}\n\n"
                break
            if idle > 600:  # ~5 min with no activity
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/projects/{pid}/slides/{fname}")
async def slide_image(pid: str, fname: str):
    if "/" in fname or ".." in fname:
        raise HTTPException(400, "bad name")
    path = store.slides_dir(pid) / fname
    if not path.exists():
        raise HTTPException(404, "not found")
    return FileResponse(path)


# --------------------------------------------------------------------------- #
# Rendered video — in-app preview only. The finished MP4 + transcript are written
# to the author's working directory at build time (see jobs._build); there is
# no in-app download.
# --------------------------------------------------------------------------- #
@app.get("/api/projects/{pid}/video")
async def project_video(pid: str):
    if not db.get_project(pid):
        raise HTTPException(404, "not found")
    path = store.video_path(pid)
    if not path.exists():
        raise HTTPException(404, "not built yet")
    # Served inline so the viewer's <video> can stream/seek it (Range-aware).
    return FileResponse(path, media_type="video/mp4")


# --------------------------------------------------------------------------- #
# SPA (optional) — mounted last so API routes win.
# --------------------------------------------------------------------------- #
if config.FRONTEND_DIST.exists():
    class SPAStatic(StaticFiles):
        async def get_response(self, path, scope):
            resp = await super().get_response(path, scope)
            if resp.status_code == 404:
                resp = await super().get_response("index.html", scope)
            # index.html must always revalidate. Vite gives every JS/CSS bundle a
            # content-hashed name, so those are safe to cache forever — but the
            # HTML that points at them keeps the same URL, and a viewer that
            # caches it heuristically (VS Code's Simple Browser and other
            # embedded webviews do) keeps loading the previous build's assets
            # after an update, which looks exactly like "the app didn't change".
            ctype = resp.headers.get("content-type", "")
            if ctype.startswith("text/html"):
                resp.headers["Cache-Control"] = "no-cache, must-revalidate"
            elif "/assets/" in scope.get("path", ""):
                resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resp

    app.mount("/", SPAStatic(directory=str(config.FRONTEND_DIST), html=True), name="spa")
else:
    @app.get("/")
    async def root():
        return {"app": "Voiceover Builder", "frontend": "not built (frontend/dist missing)"}
