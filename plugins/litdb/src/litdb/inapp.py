"""Open litdb's local web forms inside Academic Studio instead of the system browser.

Academic Studio ships an extension that
coordinates with local skill apps through two files in a shared directory:

  inapp     a capability marker the extension writes on activation, containing its
            own process id. Its presence (with a live pid) means "I will open the
            tab for you" — so the launcher skips the external browser.
  app-url   the launcher writes the URL here; the extension watches the file and
            opens whatever appears in an in-editor Simple Browser tab.

Today that extension only watches ``~/.voiceover``, so litdb publishes there when
that channel is live. ``~/.academic-studio`` is checked first: it is the generic
channel a future Studio build should use, and litdb will prefer it automatically
once one exists. Nothing here is required — outside Studio no marker is live and
callers fall back to :mod:`webbrowser`, exactly as before.
"""

from __future__ import annotations

import os
from pathlib import Path


def _channels() -> list[Path]:
    """Coordination directories to try, most-preferred first."""
    generic = os.environ.get("ACADEMIC_STUDIO_HOME")
    voiceover = os.environ.get("VOICEOVER_HOME")
    return [
        Path(generic) if generic else Path.home() / ".academic-studio",
        Path(voiceover) if voiceover else Path.home() / ".voiceover",
    ]


def _is_live(marker: Path) -> bool:
    """True when `marker` holds the pid of a still-running editor process. A stale
    marker left behind by a closed editor is ignored."""
    try:
        pid = int(marker.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def publish_url(url: str) -> bool:
    """Hand `url` to a live Academic Studio, which will open it in an in-editor tab.

    Returns True when Studio took it (the caller must NOT also open the system
    browser), False when no editor is listening. ``LITDB_NO_BROWSER=1`` forces True
    without publishing anywhere, for headless runs and tests.
    """
    if os.environ.get("LITDB_NO_BROWSER"):
        return True
    for home in _channels():
        if not _is_live(home / "inapp"):
            continue
        try:
            home.mkdir(parents=True, exist_ok=True)
            (home / "app-url").write_text(url, encoding="utf-8")
        except OSError:
            continue
        return True
    return False
