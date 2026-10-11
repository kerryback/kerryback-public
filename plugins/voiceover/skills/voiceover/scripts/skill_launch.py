#!/usr/bin/env python3
"""Launch Voiceover Builder and open it in the browser.

Invoked by the `voiceover` skill. It:
  1. ensures the app environment (venv) and the built frontend exist,
  2. starts the FastAPI app on http://127.0.0.1:<port> (default 8010),
  3. opens the given deck — a PDF — and deep-links the browser into it.

The deck is optional: with none named, the app opens on its Upload screen and the
author drops a PDF in there instead. Either way the deck ends up in the same
place, and `GET /api/projects` is how the agent finds out which one it is.

A deck is one file: the PDF you exported from your slides. The app copies it
into the deck folder, renders a page image per slide, and holds the narration
itself, so the whole edit cycle is typing in the app (or asking Claude) and
uploading the PDF again when the slides themselves change.

Each deck's working files live under {project}/.voiceover/decks/<deck-name>
(the project folder = --output-dir). The finished MP4 and transcript are written
straight to --output-dir (default: the current working directory) each time a
build completes, so the outputs sit where they are easy to find — there is no
in-app download.

Usage:
  python scripts/skill_launch.py [/path/to/deck.pdf] [--output-dir DIR]
                                 [--port 8010]

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
DECK_EXTS = {".qmd", ".md", ".html"}

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


def preflight():
    """Surface the one missing prerequisite that matters, up front. Reading the
    deck and writing the narration work without a key — it is needed only to
    generate audio."""
    if not os.environ.get("ELEVENLABS_API_KEY"):
        log("NOTE: ELEVENLABS_API_KEY not found in the environment. You can paste "
            "a key in the app (banner at the top); until then, Generate will not "
            "run. Writing and reviewing the narration work without it.")


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


def open_deck(base: str, pdf: Path) -> str:
    body = json.dumps({"pdf": str(pdf), "name": pdf.stem}).encode()
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
            log(f"Could not read the PDF: {proj.get('log', '').splitlines()[0]}")
            return
        if proj["state"] != "loading":
            n = len(proj.get("slides", []))
            narrated = sum(1 for s in proj.get("slides", []) if s.get("narration"))
            log(f"Read {n} slides, {narrated} with narration.")
            return
        time.sleep(1.0)
    log("Still loading; opening anyway.")


def resolve_pdf(args) -> Path | None:
    """The one input, with a useful complaint for the two near misses: being
    handed the deck someone wrote (export it first) rather than a PDF, and being
    pointed at a PDF that has a sibling of the same name they may have meant.

    None when no deck was named — the app opens on its Upload screen.
    """
    if not args.deck:
        return None
    pdf = Path(args.deck).expanduser().resolve()
    ext = pdf.suffix.lower()
    if ext in PPTX_EXTS or ext in DECK_EXTS:
        sibling = pdf.with_suffix(".pdf")
        hint = (f" Its PDF looks like it is already there: {sibling}."
                if sibling.is_file() else
                " Export it to PDF first — in PowerPoint, File ▸ Export ▸ Create "
                "PDF/XPS; in Quarto, render the deck and print to PDF with "
                "`pdf-separate-fragments: false`.")
        raise SystemExit(f"Voiceover takes the PDF, not {pdf.name}.{hint}")
    if ext != ".pdf":
        raise SystemExit(f"Not a PDF: {pdf.name}. Voiceover takes a PDF deck.")
    if not pdf.is_file():
        raise SystemExit(f"PDF not found: {pdf}")
    return pdf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", nargs="?",
                    help="path to the deck's PDF (omit to upload one in the app)")
    ap.add_argument("--output-dir", default=os.getcwd(),
                    help="where finished .mp4/.txt are saved (default: cwd)")
    ap.add_argument("--port", type=int, default=8010)
    args = ap.parse_args()

    pdf = resolve_pdf(args)
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    # Per-deck working files (page images, audio) live beside the project, in
    # {project}/.voiceover/decks/<name>, so a project folder is self-contained.
    # Finished MP4s + transcripts go to the project folder itself.
    data_dir = Path(os.environ.get("DATA_DIR") or (output_dir / ".voiceover")).expanduser()

    py = ensure_backend_venv()
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
        if pdf:
            pid = open_deck(base, pdf)
            log(f"Opened '{pid}' from {pdf.name}.")
            wait_loaded(base, pid)
            url = f"{base}/?project={pid}"
        else:
            log("No deck named — the app opens on Upload; drop a PDF there.")
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
