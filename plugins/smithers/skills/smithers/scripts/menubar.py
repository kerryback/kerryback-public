"""
macOS menu-bar launcher for Smithers — an alternative to `skill_launch.py` for
people who want Smithers running all day with meeting reminders.

Starts the Gmail/Calendar MCP connector, the app server, and the reminders
process, then opens the app in a native window. The menu-bar icon stays
available to reopen the window or quit everything.

This mode is optional and macOS-only. It needs two extra packages that the app
itself does not:
    ~/.smithers/venv/bin/pip install -r scripts/requirements-menubar.txt
    ~/.smithers/venv/bin/python scripts/menubar.py

Everything personal (accounts, tokens, tasks, drafts) lives in ~/.smithers, the
same as every other entry point. Run scripts/setup.py first if this is a fresh
install.
"""

import multiprocessing
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import rumps

SKILL = Path(__file__).resolve().parent.parent
HOME_DIR = Path(os.environ.get("SMITHERS_HOME", Path.home() / ".smithers")).expanduser()
ICON_PATH = HOME_DIR / "Smithers.icns"  # optional, the user\'s own
VENV_PY = HOME_DIR / "venv" / "bin" / "python"
PY = str(VENV_PY) if VENV_PY.exists() else sys.executable
APP_PORT = int(os.environ.get("SMITHERS_PORT", "8020"))
CONNECTOR_PORT = int(os.environ.get("CONNECTOR_PORT", "8800"))
APP_URL = f"http://localhost:{APP_PORT}"


def _focus_window() -> None:
    """Bring the webview window to the front (AppKit, macOS only)."""
    try:
        from AppKit import NSApp
        NSApp.activateIgnoringOtherApps_(True)
        for win in NSApp.windows():
            win.makeKeyAndOrderFront_(None)
    except Exception:
        pass


def _set_dock_icon() -> None:
    """Set the Dock icon for the webview process. rumps sets the menu-bar
    icon from Smithers.icns, but the Dock icon belongs to this separate
    pywebview process and must be set explicitly."""
    try:
        from AppKit import NSApplication, NSImage
        img = NSImage.alloc().initWithContentsOfFile_(str(ICON_PATH))
        if img is not None:
            NSApplication.sharedApplication().setApplicationIconImage_(img)
    except Exception:
        pass


def _webview_worker(focus_event: multiprocessing.Event) -> None:
    import threading
    import webview
    from PyObjCTools import AppHelper

    def _focus_watcher():
        # AppKit calls (activate / makeKeyAndOrderFront) MUST run on the main
        # thread; calling them from this background thread traps with SIGTRAP
        # ("Python quit unexpectedly"). Marshal onto the main run loop instead.
        while True:
            focus_event.wait()
            focus_event.clear()
            AppHelper.callAfter(_focus_window)

    threading.Thread(target=_focus_watcher, daemon=True).start()

    # Handle dock-icon clicks (applicationShouldHandleReopen).
    # pywebview owns the NSApplication delegate and installs it itself during
    # window creation; its delegate does NOT implement reopen. Subclass
    # pywebview's delegate to add reopen and slot it into its class BEFORE the
    # window is created, so pywebview installs ours.
    try:
        from webview.platforms import cocoa

        class _SmithersAppDelegate(cocoa.BrowserView.AppDelegate):
            def applicationShouldHandleReopen_hasVisibleWindows_(self, app, has_visible):
                _focus_window()
                return True

        cocoa.BrowserView.AppDelegate = _SmithersAppDelegate
    except Exception:
        pass

    AppHelper.callAfter(_set_dock_icon)

    webview.create_window("Smithers", APP_URL, width=1280, height=900)
    webview.start()


def kill_existing():
    pids = []
    for port in (APP_PORT, CONNECTOR_PORT):
        result = subprocess.run(["lsof", "-ti", f"tcp:{port}"], capture_output=True, text=True)
        pids.extend(result.stdout.strip().split())
    for pid in pids:
        subprocess.run(["kill", pid], capture_output=True)
    if pids:
        time.sleep(0.6)


def _wait_for(url: str, tries: int = 30) -> None:
    for _ in range(tries):
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except Exception:
            time.sleep(0.5)


def start_connector():
    proc = subprocess.Popen(
        [PY, str(SKILL / "mcp-servers" / "gmail_mcp.py")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "PORT": str(CONNECTOR_PORT)},
    )
    # The MCP endpoint answers even to a plain GET once the server is up.
    _wait_for(f"http://127.0.0.1:{CONNECTOR_PORT}/mcp", tries=20)
    return proc


def start_server():
    proc = subprocess.Popen(
        [PY, "-m", "uvicorn", "app:app",
         "--host", "127.0.0.1", "--port", str(APP_PORT)],
        cwd=str(SKILL / "backend"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_for(f"{APP_URL}/api/ping")
    return proc


def start_reminders():
    return subprocess.Popen(
        [PY, str(SKILL / "scripts" / "reminders.py")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class SmithersApp(rumps.App):
    def __init__(self, procs):
        super().__init__(
            "Smithers",
            icon=str(ICON_PATH) if ICON_PATH.exists() else None,
            quit_button=None,
        )
        self.procs = procs
        self.menu = ["Open Smithers", None, "Quit"]
        self._window = None
        self._focus_event = multiprocessing.Event()
        self._open_window()

    def _open_window(self):
        if self._window and self._window.is_alive():
            self._focus_event.set()   # already open --- just bring to front
            return
        self._focus_event.clear()
        self._window = multiprocessing.Process(
            target=_webview_worker,
            args=(self._focus_event,),
            daemon=True,
        )
        self._window.start()

    @rumps.clicked("Open Smithers")
    def open_window(self, _):
        self._open_window()

    @rumps.clicked("Quit")
    def quit_app(self, _):
        if self._window:
            self._window.terminate()
        for p in self.procs:
            p.terminate()
        for p in self.procs:
            try:
                p.wait(timeout=5)
            except Exception:
                pass
        rumps.quit_application()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    kill_existing()
    connector = start_connector()
    server = start_server()
    reminders = start_reminders()
    SmithersApp([reminders, server, connector]).run()
