"""Ingest a reveal.js deck: one thumbnail per slide, plus the text, step counts
and fingerprints that everything downstream leans on.

A deck is a rendered reveal.js HTML file: Quarto's revealjs output, or any page
that starts reveal.js. Headless Chrome loads it and, slide by slide in reading
order (vertical stacks flattened top to bottom):

- counts its fragment steps — how many times the deck advances before it moves
  to the next slide. A slide's script needs one `[next]` marker per step;
- reads its text, title and speaker notes, so Claude can draft from cheap text
  instead of reading every thumbnail;
- takes a thumbnail with every fragment shown and every animation finished.

Fingerprints (thumbnail sha + text sha) let a re-read deck be matched against
the previous ingest, so the script is carried onto the right slides (see
slidematch).
"""
import hashlib
import re
import shutil
import zipfile
from pathlib import Path

from . import browser
from .deck import deck_slug

THUMB_HEIGHT = 720
HTML_EXTS = {".html", ".htm"}


def is_html(path: Path) -> bool:
    return Path(path).suffix.lower() in HTML_EXTS


def is_zip(path: Path) -> bool:
    return Path(path).suffix.lower() == ".zip"


NOT_HTML_MESSAGE = (
    "A reveal.js deck is the rendered .html file (Quarto writes one when it "
    "renders a revealjs presentation). Open it by path so its _files folder "
    "comes along, or upload a .zip of the folder that holds both, or a "
    "self-contained .html (Quarto `embed-resources: true`)."
)


def unpack_upload(name: str, data: bytes, dest: Path) -> Path:
    """Put an uploaded deck in `dest` and return the HTML file to open.

    A browser upload is one file, so a deck that needs its `_files` folder
    arrives as a zip. The zip is extracted whole (rejecting paths that climb
    out of `dest`) and the presentation is the HTML file nearest the top; on a
    tie, the one with a sibling `<stem>_files` folder, which is how Quarto lays
    a deck out.
    """
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    if is_html(Path(name)):
        out = dest / deck_slug(Path(name).name)
        out.write_bytes(data)
        return out
    if not is_zip(Path(name)):
        raise ValueError(NOT_HTML_MESSAGE)
    zpath = dest / "_upload.zip"
    zpath.write_bytes(data)
    root = dest.resolve()
    try:
        with zipfile.ZipFile(zpath) as zf:
            for member in zf.infolist():
                target = (dest / member.filename).resolve()
                if root != target and root not in target.parents:
                    raise ValueError(f"Unsafe path in zip: {member.filename}")
            zf.extractall(dest)
    except zipfile.BadZipFile:
        raise ValueError(f"{name} is not a readable zip file.")
    finally:
        zpath.unlink(missing_ok=True)
    candidates = [p for p in dest.rglob("*") if p.is_file() and is_html(p)
                  and "_files" not in "/".join(p.relative_to(dest).parts[:-1])
                  and not p.name.startswith(".")
                  and "__MACOSX" not in p.parts]
    if not candidates:
        raise ValueError(f"{name} holds no .html file.")

    def rank(p: Path):
        has_files = (p.parent / f"{p.stem}_files").is_dir()
        return (len(p.relative_to(dest).parts), not has_files, p.name)

    return sorted(candidates, key=rank)[0]


# Everything the app needs from one slide, read in the page. `clean` drops
# notes, scripts and styles before taking the text, so a slide's CSS or its
# speaker notes are not mistaken for what it shows.
_SLIDES_JS = r"""() => {
  const clean = (el) => {
    const c = el.cloneNode(true);
    c.querySelectorAll('aside.notes, script, style, .slide-number').forEach(n => n.remove());
    return (c.textContent || '').replace(/\s+/g, ' ').trim();
  };
  return Reveal.getSlides().map((s) => {
    const ix = Reveal.getIndices(s);
    const frags = [...s.querySelectorAll('.fragment')]
      .filter(f => !f.closest('aside.notes'));
    const steps = new Set(frags.map(f => f.getAttribute('data-fragment-index'))).size;
    const head = s.querySelector('h1, h2, h3');
    const notes = [...s.querySelectorAll('aside.notes')]
      .map(n => (n.textContent || '').replace(/\s+/g, ' ').trim()).join(' ');
    return {h: ix.h, v: ix.v || 0, steps: steps,
            title: head ? (head.textContent || '').replace(/\s+/g, ' ').trim() : '',
            slide_text: clean(s), notes: notes};
  });
}"""


def read_slides(html: Path, slides_dir: Path, progress=None) -> dict:
    """Load the deck once: per-slide records, thumbnails, and the slide size."""
    slides_dir.mkdir(parents=True, exist_ok=True)
    with browser.chrome() as b:
        w, h = browser.deck_size(b, html)
        page = browser.open_deck(b, html, browser.viewport_for(w, h, THUMB_HEIGHT))
        try:
            # Thumbnails show each slide's end state, arrived at with no
            # transition, so the shot doesn't catch a slide mid-way in.
            page.evaluate("() => Reveal.configure({transition: 'none', "
                          "backgroundTransition: 'none', autoAnimate: false})")
            records = page.evaluate(_SLIDES_JS)
            total = len(records)
            for i, rec in enumerate(records):
                last = rec["steps"] - 1 if rec["steps"] else -1
                page.evaluate(f"() => Reveal.slide({rec['h']}, {rec['v']}, {last})")
                page.wait_for_timeout(150)
                page.screenshot(path=str(slides_dir / f"slide-{i + 1:03d}.png"),
                                animations="disabled")
                if progress:
                    progress(i + 1, total, "Reading slides")
        finally:
            page.close()
    for png in slides_dir.glob("slide-*.png"):
        try:
            if int(png.stem.split("-")[1]) > len(records):
                png.unlink()
        except (IndexError, ValueError):
            continue
    return {"records": records, "size": [w, h]}


def fingerprints(slides_dir: Path, text: list) -> list:
    """Per-slide content shas, used to match a re-read deck against the previous
    ingest: the thumbnail (catches a chart or diagram edit that leaves the words
    alone) and the normalized text."""
    out = []
    for i, page in enumerate(text):
        png = slides_dir / f"slide-{i + 1:03d}.png"
        try:
            image_sha = hashlib.sha256(png.read_bytes()).hexdigest()
        except OSError:
            image_sha = ""
        words = re.sub(r"\s+", " ", page.get("slide_text", "")).strip()
        out.append({
            "index": i,
            "image_sha": image_sha,
            "text_sha": hashlib.sha256(words.encode("utf-8")).hexdigest() if words else "",
        })
    return out


def ingest(html: Path, slides_dir: Path, progress=None) -> dict:
    """Read one deck. Returns {"slides", "fingerprints", "pages", "size"}.

    `slides` entries are {index, h, v, steps, title, slide_text, notes,
    narration}, narration empty — carrying a previous script onto them is the
    caller's job (jobs._ingest), because only it knows the deck before.
    """
    html = Path(html)
    if not html.is_file():
        raise ValueError(f"Deck not found: {html}")
    result = read_slides(html, slides_dir, progress=progress)
    recs = result["records"]
    if not recs:
        raise ValueError(f"{html.name} has no slides.")
    slides = [{"index": i, "h": r["h"], "v": r["v"], "steps": r["steps"],
               "title": r["title"][:80], "slide_text": r["slide_text"],
               "notes": r["notes"], "narration": ""}
              for i, r in enumerate(recs)]
    return {"slides": slides, "fingerprints": fingerprints(slides_dir, slides),
            "pages": len(slides), "size": result["size"]}
