#!/usr/bin/env python3
"""Launch Voiceover and open it in the browser.

Invoked by the `voiceover` skill. It:
  1. ensures the app environment (venv) and the built frontend exist, and for a
     reveal.js deck a headless browser,
  2. starts the FastAPI app on http://127.0.0.1:<port> (default 8010),
  3. opens the given deck — a PDF, or a rendered reveal.js .html — and
     deep-links the browser into it.

The deck is optional: with none named, the app opens on its Upload screen and the
author drops a PDF (or a reveal.js .html or .zip) in there instead. Either way
the deck ends up in the same place, and `GET /api/projects` is how the agent
finds out which one it is.

The file type picks the method. A PDF is copied into the deck folder and each
page becomes a still image. A reveal.js deck is read where it is, so its _files
folder comes along, and is recorded in headless Chrome with its animations.
Either way the app holds the narration itself, so the edit cycle is typing in
the app (or asking Claude) and reading the deck again when the slides change.

Each deck's working files live under {project}/.voiceover/decks/<deck-name>
(the project folder = --output-dir). The finished MP4 and transcript are written
straight to --output-dir (default: the current working directory) each time a
build completes, so the outputs sit where they are easy to find — there is no
in-app download.

Usage:
  python scripts/skill_launch.py [/path/to/deck.pdf|deck.html] [--output-dir DIR]
                                 [--port 8010] [--engine kokoro|elevenlabs]

--engine records the text-to-speech engine for every deck, as TTS_ENGINE in
~/.voiceover/.env (the same place the app's engine switch writes it). The skill
passes it once, after asking the author; leave it off after that.

Runs in the foreground and keeps the server alive; stop it with Ctrl-C.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
FRONTEND = REPO / "frontend"

PPTX_EXTS = {".pptx", ".ppt", ".key"}
HTML_EXTS = {".html", ".htm"}
SOURCE_EXTS = {".qmd", ".md", ".rmd"}
CHROME_APPS = [Path("/Applications/Google Chrome.app"),
               Path.home() / "Applications" / "Google Chrome.app"]

# Runtime state lives OUTSIDE the skill directory so that (a) reinstalling or
# updating the skill never wipes decks, and (b) the package source stays clean
# for repackaging. Override the data location with DATA_DIR in the environment.
# The Python environment is shared and built once, in the user's home.
HOME_DIR = Path(os.environ.get("VOICEOVER_HOME", Path.home() / ".voiceover"))
VENV_DIR = HOME_DIR / "venv"


def _open_in_editor() -> bool:
    """True when an editor extension will open the app in an in-editor browser tab,
    so we skip the external browser. The extension signals this by writing a
    capability marker at ~/.voiceover/inapp containing its own process id; a stale
    marker left by a closed editor is ignored (the process id is no longer alive).
    Force with VOICEOVER_NO_BROWSER=1."""
    if os.environ.get("VOICEOVER_NO_BROWSER"):
        return True
    try:
        pid = int((HOME_DIR / "inapp").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    try:
        os.kill(pid, 0)   # editor process still alive → it will open the tab
        return True
    except OSError:
        return False


def log(msg):
    print(f"[voiceover] {msg}", flush=True)


def ensure_backend_venv() -> Path:
    py = VENV_DIR / "bin" / "python"
    stamp = VENV_DIR / "requirements.sha"
    want = _requirements_sha()
    if py.exists() and stamp.exists() and stamp.read_text().strip() == want:
        return py
    if not py.exists():
        log("Creating the app environment + installing requirements (first run only)…")
        VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
        subprocess.run([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"],
                       check=True)
    else:
        # The skill updated and now wants different packages.
        log("Updating the app environment…")
    subprocess.run([str(py), "-m", "pip", "install", "-q", "-r",
                    str(BACKEND / "requirements.txt")], check=True)
    stamp.write_text(want)
    return py


def _requirements_sha() -> str:
    import hashlib
    return hashlib.sha256(
        (BACKEND / "requirements.txt").read_bytes()).hexdigest()


def ensure_frontend_built():
    # The published package ships a prebuilt frontend/dist, so this is a no-op in
    # normal use. It only rebuilds when running from source with dist removed.
    if (FRONTEND / "dist" / "index.html").exists():
        return
    log("Building the frontend (requires Node/npm)…")
    subprocess.run(["npm", "install"], cwd=FRONTEND, check=True)
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND, check=True)


ENGINES = ("kokoro", "elevenlabs")


def _env_file_values() -> dict:
    values = {}
    try:
        for raw in (HOME_DIR / ".env").read_text(encoding="utf-8").splitlines():
            name, sep, value = raw.strip().partition("=")
            if sep and not name.startswith("#"):
                values[name.strip()] = value.strip()
    except OSError:
        pass
    return values


def save_engine(engine: str) -> None:
    """Write TTS_ENGINE to ~/.voiceover/.env, keeping every other line."""
    path = HOME_DIR / ".env"
    HOME_DIR.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [l for l in lines if not l.lstrip().startswith("TTS_ENGINE")]
    lines.append(f"TTS_ENGINE={engine}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"Voice engine set to {engine} (change it any time under Audio settings).")


def preflight():
    """Surface the one missing prerequisite that matters, up front. Reading the
    deck and writing the narration need neither engine; with ElevenLabs, a key
    is needed only to generate audio. Kokoro needs no key."""
    stored = _env_file_values()
    engine = (os.environ.get("TTS_ENGINE") or stored.get("TTS_ENGINE", "")).lower()
    has_key = bool(os.environ.get("ELEVENLABS_API_KEY") or stored.get("ELEVENLABS_API_KEY"))
    if engine not in ENGINES:
        engine = "elevenlabs" if has_key else "kokoro"
    if engine == "kokoro":
        log("Voice: Kokoro, on this computer. The first Generate downloads its "
            "model (about 340 MB) once.")
    elif not has_key:
        log("NOTE: the voice engine is ElevenLabs and no ELEVENLABS_API_KEY is set. "
            "Paste a key in the app (banner at the top), or switch to Kokoro under "
            "Audio settings; until then, Generate will not run. Writing and "
            "reviewing the narration work without it.")


def wait_up(base: str, timeout: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(base + "/api/projects", timeout=2)
            return True
        except urllib.error.HTTPError:
            return True  # server answered (any status) = up
        except Exception:
            time.sleep(0.5)
    return False


def _have_chrome() -> bool:
    if any(p.exists() for p in CHROME_APPS):
        return True
    import shutil
    return any(shutil.which(n) for n in ("google-chrome", "google-chrome-stable",
                                         "chrome"))


def ensure_browser(py: Path) -> None:
    """A reveal.js deck is read and recorded in headless Chrome. The installed
    Google Chrome is used when there is one; otherwise Playwright's Chromium is
    downloaded once (~150 MB). Called only for a reveal.js deck: a PDF never
    needs a browser."""
    if _have_chrome():
        return
    stamp = VENV_DIR / "chromium.installed"
    if stamp.exists():
        return
    log("No Google Chrome found — downloading a headless Chromium (first run only)…")
    subprocess.run([str(py), "-m", "playwright", "install", "chromium"], check=True)
    stamp.write_text("ok")


def ensure_frontend_built():
    # The published package ships a prebuilt frontend/dist, so this is a no-op in
    # normal use. It only rebuilds when running from source with dist removed.
    if (FRONTEND / "dist" / "index.html").exists():
        return
    log("Building the frontend (requires Node/npm)…")
    subprocess.run(["npm", "install"], cwd=FRONTEND, check=True)
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND, check=True)


ENGINES = ("kokoro", "elevenlabs")


def open_deck(base: str, path: Path) -> str:
    body = json.dumps({"deck": str(path), "name": path.stem}).encode()
    req = urllib.request.Request(base + "/api/projects", data=body,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)["id"]
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(detail).get("detail", detail)
        except ValueError:
            pass
        raise SystemExit(f"Could not open the deck: {detail}")


def wait_loaded(base: str, pid: str, timeout: float = 180.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with urllib.request.urlopen(f"{base}/api/projects/{pid}", timeout=10) as resp:
            proj = json.load(resp)
        if proj["state"] == "load_failed":
            # Not fatal: the app shows the reason and offers Upload, which is
            # where a bad file gets replaced.
            first = (proj.get("log") or "").splitlines()
            log(f"Could not read the deck: {first[0] if first else 'unknown error'}")
            return
        if proj["state"] != "loading":
            slides = proj.get("slides", [])
            narrated = sum(1 for s in slides if s.get("narration"))
            if proj.get("format") == "revealjs":
                steps = sum(s.get("steps") or 0 for s in slides)
                log(f"Read {len(slides)} slides ({steps} fragment steps), "
                    f"{narrated} with narration.")
            else:
                log(f"Read {len(slides)} slides, {narrated} with narration.")
            return
        time.sleep(1.0)
    log("Still loading; opening anyway.")


def _rendered_for(src: Path) -> Path | None:
    """The rendered .html for a .qmd: beside it, or (for a Quarto project that
    renders into docs/ or _site/) the newest same-named .html in one of those
    folders, next to the source or one level up."""
    beside = src.with_suffix(".html")
    if beside.is_file():
        return beside
    hits = []
    for base in {src.parent, src.parent.parent, Path.cwd()}:
        for out in ("docs", "_site"):
            root = base / out
            if root.is_dir():
                hits += [p for p in root.rglob(f"{src.stem}.html")
                         if "_files" not in "/".join(p.parts)]
    return max(hits, key=lambda p: p.stat().st_mtime) if hits else None


def resolve_deck(args) -> Path | None:
    """The one input: a PDF, or a rendered reveal.js .html. Useful answers for
    the near misses: a Quarto source (.qmd) means its rendered .html; PowerPoint
    or Keynote means export to PDF first.

    None when no deck was named — the app opens on its Upload screen.
    """
    if not args.deck:
        return None
    path = Path(args.deck).expanduser().resolve()
    ext = path.suffix.lower()
    if ext in SOURCE_EXTS:
        html = _rendered_for(path)
        if html is None:
            raise SystemExit(
                f"{path.name} is the source. Render it first (quarto render "
                f"{path.name}), then open the .html it writes, or a PDF of it.")
        log(f"Using the rendered reveal.js deck {html} for {path.name}.")
        return html
    if ext in PPTX_EXTS:
        sibling = path.with_suffix(".pdf")
        hint = (f" Its PDF looks like it is already there: {sibling}."
                if sibling.is_file() else
                " Export it to PDF first — in PowerPoint, File ▸ Export ▸ Create "
                "PDF/XPS.")
        raise SystemExit(f"Voiceover takes the PDF, not {path.name}.{hint}")
    if ext != ".pdf" and ext not in HTML_EXTS:
        raise SystemExit(f"Not a deck Voiceover reads: {path.name}. It takes a PDF "
                         "of your slides, or a rendered reveal.js .html.")
    if not path.is_file():
        raise SystemExit(f"Deck not found: {path}")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", nargs="?",
                    help="the deck: a PDF, or a rendered reveal.js .html "
                         "(omit to upload one in the app)")
    ap.add_argument("--output-dir", default=os.getcwd(),
                    help="where finished .mp4/.txt are saved (default: cwd)")
    ap.add_argument("--port", type=int, default=8010)
    ap.add_argument("--engine", choices=ENGINES,
                    help="record the text-to-speech engine for every deck")
    args = ap.parse_args()

    deck = resolve_deck(args)
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    # Per-deck working files (page images, audio) live beside the project, in
    # {project}/.voiceover/decks/<name>, so a project folder is self-contained.
    # Finished MP4s + transcripts go to the project folder itself.
    data_dir = Path(os.environ.get("DATA_DIR") or (output_dir / ".voiceover")).expanduser()

    if args.engine:
        save_engine(args.engine)
    py = ensure_backend_venv()
    if deck and deck.suffix.lower() in HTML_EXTS:
        ensure_browser(py)
    ensure_frontend_built()
    preflight()

    env = dict(os.environ)
    env["VOICEOVER_OUTPUT_DIR"] = str(output_dir)
    env["DATA_DIR"] = str(data_dir)
    # Don't scatter __pycache__ into the (possibly read-only / packaged) skill dir.
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    base = f"http://127.0.0.1:{args.port}"
    log(f"Starting the app on {base} …")
    server = subprocess.Popen(
        [str(py), "-m", "uvicorn", "app:app", "--host", "127.0.0.1",
         "--port", str(args.port)],
        cwd=BACKEND, env=env)
    try:
        if not wait_up(base):
            raise SystemExit(
                f"Server did not come up on port {args.port}. If that port is in "
                "use, rerun with a different one, e.g. --port 8011.")
        if deck:
            pid = open_deck(base, deck)
            log(f"Opened '{pid}' from {deck.name}.")
            wait_loaded(base, pid)
            url = f"{base}/?project={pid}"
        else:
            log("No deck named — the app opens on Upload; drop a PDF or a "
                "reveal.js deck there.")
            url = f"{base}/"
        # Publish the URL so an editor extension (if any) can open it in an
        # in-editor browser tab; harmless everywhere else.
        try:
            HOME_DIR.mkdir(parents=True, exist_ok=True)
            (HOME_DIR / "app-url").write_text(url, encoding="utf-8")
        except OSError:
            pass
        if _open_in_editor():
            log("Opening in the editor (an extension will show it in a browser tab)…")
        else:
            webbrowser.open(url)
        log(f"Open: {url}")
        log(f"Finished MP4 + transcript will be saved to: {output_dir}")
        log("Leave this running while you work. Press Ctrl-C to stop the app.")
        server.wait()
    finally:
        if server.poll() is None:
            server.terminate()


if __name__ == "__main__":
    main()
