#!/usr/bin/env python3
"""Launch Smithers and open it in the browser.

Invoked by the `smithers` skill. It:
  1. ensures the app environment (venv) exists,
  2. starts the Gmail/Calendar connector on 127.0.0.1:<connector-port> (8800),
  3. starts the FastAPI app on http://127.0.0.1:<port> (default 8020),
  4. asks for a fresh briefing (POST /api/briefing/refresh-request) — opening
     Smithers is itself the request; Claude Code answers it by rewriting the
     Overview,
  5. opens the app — in an editor tab when running inside Academic Studio,
     otherwise in the system browser.

The app holds the mailbox, calendar, tasks, and drafts. It contains no model and
needs no API key: Claude Code is the assistant, reading through the connector and
writing back over HTTP (POST /api/drafts, POST /api/briefing).

Personal state — tasks, drafts, the saved briefing, and the Google OAuth
credentials and tokens — lives in ~/.smithers, never in this package, so
updating the skill never disturbs it.

Usage:
  python scripts/skill_launch.py [--port 8020] [--connector-port 8800]

Runs in the foreground and keeps both servers alive; stop with Ctrl-C.
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

SKILL = Path(__file__).resolve().parent.parent
BACKEND = SKILL / "backend"
CONNECTOR = SKILL / "mcp-servers"

HOME_DIR = Path(os.environ.get("SMITHERS_HOME", Path.home() / ".smithers")).expanduser()
VENV_DIR = HOME_DIR / "venv"


def log(msg):
    print(f"[smithers] {msg}", flush=True)


def _channels() -> list[Path]:
    """Directories an editor extension may use to coordinate opening the app in
    an in-editor tab, most-preferred first.

    ~/.academic-studio is the generic channel. ~/.voiceover is included because
    Academic Studio builds shipped before this plugin existed watch only that
    one --- publishing to both means Smithers opens in-app on today's Studio as
    well as on the next build.
    """
    generic = os.environ.get("ACADEMIC_STUDIO_HOME")
    voiceover = os.environ.get("VOICEOVER_HOME")
    return [
        Path(generic) if generic else Path.home() / ".academic-studio",
        Path(voiceover) if voiceover else Path.home() / ".voiceover",
        HOME_DIR,
    ]


def _open_in_editor() -> bool:
    """True when an editor extension will open the app in an in-editor browser
    tab, so we skip the external browser. The extension signals this by writing a
    capability marker containing its own process id; a stale marker left by a
    closed editor is ignored. Force with SMITHERS_NO_BROWSER=1."""
    if os.environ.get("SMITHERS_NO_BROWSER"):
        return True
    for channel in _channels():
        try:
            pid = int((channel / "inapp").read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            continue
    return False


def _publish_url(url: str) -> None:
    """Hand the URL to a live editor extension, which opens it in a tab. Written
    to every channel; the extension de-dupes so only one tab opens."""
    for channel in _channels():
        try:
            channel.mkdir(parents=True, exist_ok=True)
            (channel / "app-url").write_text(url, encoding="utf-8")
        except OSError:
            pass


def ensure_venv() -> Path:
    py = VENV_DIR / "bin" / "python"
    if py.exists():
        return py
    log("Creating the app environment + installing requirements (first run only)…")
    VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    subprocess.run([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"], check=True)
    for req in (BACKEND / "requirements.txt", CONNECTOR / "requirements.txt"):
        subprocess.run([str(py), "-m", "pip", "install", "-q", "-r", str(req)], check=True)
    return py


def preflight() -> bool:
    """Report setup state. Returns True when the app can actually reach a mailbox.

    An unconfigured install still launches --- the app shows a setup banner and
    the tabs come up empty --- so a first-time user sees something real while
    Claude Code walks them through connecting an account.
    """
    sys.path.insert(0, str(SKILL / "scripts"))
    import setup as setup_mod                      # noqa: E402  (same directory)

    st = setup_mod.status()
    if st["ready"]:
        return True
    log("Smithers is not connected to a mailbox yet.")
    log(f"  Next: {st['next_step_help']}")
    log(f"  Run: python {SKILL / 'scripts' / 'setup.py'} --status")
    log("Starting anyway so you can see the app; mail and calendar will be empty.")
    return False


def request_briefing_refresh(base: str) -> None:
    """Opening Smithers is itself a request for a fresh Overview.

    The app has no model, so it cannot write the briefing --- it just records
    that one was asked for and shows "refreshing" on the Overview tab. The lines
    printed here are the instruction Claude Code acts on: it re-reads the
    calendar and inbox and POSTs a new briefing.
    """
    try:
        req = urllib.request.Request(base + "/api/briefing/refresh-request",
                                     data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:
            state = json.loads(r.read().decode("utf-8"))
    except Exception as ex:
        log(f"Could not request a briefing refresh ({ex}).")
        return
    was = state.get("generated_at") or "never"
    log(f"BRIEFING REFRESH REQUESTED — the Overview on screen is from {was}.")
    log("Claude Code: regenerate the briefing now (SKILL.md → 'The morning "
        "briefing') and POST it to /api/briefing.")


def wait_up(url: str, timeout: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except urllib.error.HTTPError:
            return True          # answered with any status = up
        except Exception:
            time.sleep(0.5)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8020, help="app port (default 8020)")
    ap.add_argument("--connector-port", type=int, default=8800,
                    help="Gmail/Calendar connector port (default 8800)")
    args = ap.parse_args()

    HOME_DIR.mkdir(parents=True, exist_ok=True)
    py = ensure_venv()
    configured = preflight()

    env = dict(os.environ)
    env["SMITHERS_HOME"] = str(HOME_DIR)
    env["PYTHONDONTWRITEBYTECODE"] = "1"   # keep the packaged skill dir clean

    conn_url = f"http://127.0.0.1:{args.connector_port}/mcp"
    base = f"http://127.0.0.1:{args.port}"

    # Reuse anything already listening rather than starting a second copy — and
    # so a port that is busy for another reason is reported, not silently adopted
    # as if it were ours.
    connector = None
    if wait_up(conn_url, timeout=1.5):
        log(f"Using the connector already running on port {args.connector_port}.")
    else:
        log(f"Starting the Gmail/Calendar connector on port {args.connector_port} …")
        connector = subprocess.Popen(
            [str(py), str(CONNECTOR / "gmail_mcp.py")],
            cwd=CONNECTOR, env={**env, "PORT": str(args.connector_port)})
        if not wait_up(conn_url):
            raise SystemExit(
                f"The connector did not come up on port {args.connector_port}. If "
                "that port is in use, rerun with --connector-port 8801.")

    server = None
    try:
        if wait_up(base + "/api/ping", timeout=1.5):
            log(f"Smithers is already running on {base} — opening it.")
        else:
            log(f"Starting the app on {base} …")
            server = subprocess.Popen(
                [str(py), "-m", "uvicorn", "app:app", "--host", "127.0.0.1",
                 "--port", str(args.port)],
                cwd=BACKEND, env={**env, "CONNECTOR_URL": conn_url})
            if not wait_up(base + "/api/ping"):
                raise SystemExit(
                    f"The app did not come up on port {args.port}. If that port is "
                    "in use, rerun with --port 8021.")

        if configured:
            request_briefing_refresh(base)

        _publish_url(base)
        if _open_in_editor():
            log("Opening in the editor (an extension will show it in a browser tab)…")
        else:
            webbrowser.open(base)
        log(f"Open: {base}")
        log(f"Personal data + Google tokens: {HOME_DIR}")
        if not configured:
            log("Reminder: no mailbox connected yet — see the setup steps above.")
        if server is None:
            log("Nothing new to run — the app was already up.")
            return
        log("Leave this running while you work. Press Ctrl-C to stop.")
        server.wait()
    finally:
        for proc in (server, connector):
            if proc is not None and proc.poll() is None:
                proc.terminate()


if __name__ == "__main__":
    main()
