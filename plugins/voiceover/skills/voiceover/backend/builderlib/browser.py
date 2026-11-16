"""Headless Chrome, driven by Playwright, for reading and recording a deck.

The installed Google Chrome is used when there is one, so most people download
nothing. Otherwise Playwright's own Chromium is used, downloaded once (by the launcher, or here)
the first time a reveal.js deck is read with no Chrome installed. A PDF deck
never starts a browser.

Both jobs (ingest and build) open the deck the same way: load the HTML file,
wait for reveal.js to be ready, then turn off everything that is for a live
presenter rather than a video: the navigation arrows, the progress bar, the
URL hash, the keyboard, and Quarto's menu and chalkboard buttons.
"""
from contextlib import contextmanager
from pathlib import Path

LAUNCH_ARGS = [
    # Video and audio elements on a slide should play without a click.
    "--autoplay-policy=no-user-gesture-required",
    # Keep animation timing steady when the window is not focused.
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
]

# Presenter furniture that has no place in a video.
HIDE_CSS = """
.reveal .controls, .reveal .progress, .slide-menu-button,
.slide-chalkboard-buttons, .reveal .slide-menu, .quarto-revealjs-menu,
.chalkboard-buttons, #reveal-pointer { display: none !important; }
html, body, .reveal { cursor: none !important; }
"""

READY_JS = "() => !!(window.Reveal && Reveal.isReady && Reveal.isReady())"

QUIET_JS = """() => {
  Reveal.configure({controls: false, progress: false, hash: false,
                    history: false, keyboard: false, mouseWheel: false,
                    autoSlide: 0, help: false, overview: false,
                    touch: false, loop: false});
}"""


class NotRevealDeck(Exception):
    pass


def _launch(p):
    """Google Chrome when installed, else Playwright's Chromium. Returns
    (browser, errors)."""
    errors = []
    for kwargs in ({"channel": "chrome"}, {}):
        try:
            return p.chromium.launch(headless=True, args=LAUNCH_ARGS, **kwargs), errors
        except Exception as e:  # not installed, or blocked
            errors.append(str(e).splitlines()[0])
    return None, errors


def _install_chromium() -> bool:
    """Download Playwright's Chromium (~150 MB), once. Only a reveal.js deck
    needs a browser, so a PDF-only author never pays for it."""
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                       capture_output=True, text=True)
    return r.returncode == 0


@contextmanager
def chrome():
    """A launched browser. Raises a readable error when none can start."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser, errors = _launch(p)
        if browser is None and _install_chromium():
            browser, errors = _launch(p)
        if browser is None:
            raise RuntimeError(
                "Could not start a headless browser, which a reveal.js deck needs. "
                "Install Google Chrome, or run `python -m playwright install "
                "chromium` in the app environment. (" + "; ".join(errors) + ")")
        try:
            yield browser
        finally:
            browser.close()


def deck_size(browser, html: Path) -> tuple[int, int]:
    """The deck's own slide size from its reveal.js config (Quarto's default is
    1050x700). The video takes the same shape, so nothing is letterboxed."""
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    try:
        _load(page, html)
        w, h = page.evaluate(
            "() => [Reveal.getConfig().width, Reveal.getConfig().height]")
    finally:
        page.close()
    try:
        w, h = float(w), float(h)
    except (TypeError, ValueError):
        w, h = 1920.0, 1080.0
    if w < 1 or h < 1:
        w, h = 1920.0, 1080.0
    return w, h


def viewport_for(w: float, h: float, height: int = 1080) -> dict:
    """1080 pixels high, width from the deck's aspect, both even (libx264)."""
    width = int(round(height * w / h))
    width = min(max(width, 2), 2560)
    return {"width": width - width % 2, "height": height - height % 2}


def open_deck(browser, html: Path, viewport: dict):
    """A page showing the deck, presenter furniture off. Caller closes it."""
    page = browser.new_page(viewport=viewport, device_scale_factor=1)
    _load(page, html)
    page.add_style_tag(content=HIDE_CSS)
    page.evaluate(QUIET_JS)
    return page


def _load(page, html: Path) -> None:
    page.goto(Path(html).resolve().as_uri(), wait_until="load", timeout=60000)
    try:
        page.wait_for_function(READY_JS, timeout=30000)
    except Exception:
        raise NotRevealDeck(
            f"{Path(html).name} did not start a reveal.js presentation. This app "
            "reads reveal.js decks (Quarto revealjs output, or any reveal.js "
            "page). If it is a Quarto deck, check that it rendered without "
            "errors and that its _files folder sits next to it.")
