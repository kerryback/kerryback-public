"""Ingest a PDF deck: one page image per slide, plus the text and fingerprints
that everything downstream leans on.

A deck is one file — the PDF the author exported from Quarto, PowerPoint,
Keynote, Beamer or anything else. The app copies it into the deck folder and
renders each page to a PNG; the narration is written in the app, against those
pages, and lives in narration.json.

Two other things come out of the same pass:
- `slide_text`, the page's extracted words, so Claude can draft from cheap text
  instead of reading every page as an image;
- fingerprints, so a re-uploaded PDF can be matched against the previous ingest
  and the script carried onto the right slides (see slidematch).
"""
import hashlib
import re
from pathlib import Path

DPI = 150


def deck_slug(name: str) -> str:
    """Filesystem-safe, human-readable deck id/folder name from a filename."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", (name or "deck")).strip("-.") or "deck"


def is_pdf(path: Path) -> bool:
    return Path(path).suffix.lower() == ".pdf"


# What to say when someone hands the app the deck they wrote rather than a PDF.
# Both formats used to be read directly; a PDF is now the only input, because it
# is the one thing every slide tool exports and the one thing that renders
# faithfully (LibreOffice mangles PowerPoint; Quarto needs a render step).
NOT_PDF_MESSAGE = (
    "Only PDF slide decks are supported. Export your deck to PDF first — in "
    "PowerPoint, File ▸ Export ▸ Create PDF/XPS; in Quarto, render the deck and "
    "print it to PDF with `pdf-separate-fragments: false` so each slide is one "
    "page — then open that PDF."
)


def page_count(pdf_path: Path) -> int:
    fitz = _fitz()
    with fitz.open(pdf_path) as doc:
        return doc.page_count


def render_pdf(pdf_path: Path, out_dir: Path, progress=None) -> int:
    """Render every PDF page to `slide-NNN.png` (1-based). Returns the count.

    Stale PNGs from a previous, longer deck are removed, so a deck that lost
    slides doesn't leave orphans for the video renderer to find.
    """
    fitz = _fitz()
    out_dir.mkdir(parents=True, exist_ok=True)
    zoom = DPI / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(pdf_path) as doc:
        total = doc.page_count
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix)
            pix.save(out_dir / f"slide-{i + 1:03d}.png")
            if progress:
                progress(i + 1, total, "Rendering slides")
    for png in out_dir.glob("slide-*.png"):
        try:
            if int(png.stem.split("-")[1]) > total:
                png.unlink()
        except (IndexError, ValueError):
            continue
    return total


def extract_text(pdf_path: Path, pages: int) -> list:
    """Per-page {title, slide_text}. A page with no extractable text — scanned,
    or all graphics — comes back empty, and Claude falls back to that page's
    image for just those slides."""
    fitz = _fitz()
    out = []
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                raw = page.get_text("text") or ""
                lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
                out.append({
                    "title": lines[0][:80] if lines else "",
                    "slide_text": re.sub(r"\s+", " ", raw).strip(),
                })
    except Exception:
        out = []
    out += [{"title": "", "slide_text": ""} for _ in range(pages - len(out))]
    return out[:pages]


def fingerprints(slides_dir: Path, text: list) -> list:
    """Per-slide content shas, used to match a re-uploaded deck against the
    previous ingest. Two per slide: the rendered page PNG (catches a chart or
    diagram edit that leaves the words alone) and the page's normalized text
    (stable when a re-export re-rasterizes identical content)."""
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


def ingest(pdf_path: Path, slides_dir: Path, progress=None) -> dict:
    """Render + read one PDF. Returns {"slides", "fingerprints", "pages"}.

    `slides` entries are {index, title, slide_text, narration}, with narration
    empty — carrying a previous script onto them is the caller's job (jobs._ingest),
    because only it knows what the deck looked like before.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise ValueError(f"PDF not found: {pdf_path}")
    pages = render_pdf(pdf_path, slides_dir, progress=progress)
    if not pages:
        raise ValueError(f"{pdf_path.name} has no pages.")
    text = extract_text(pdf_path, pages)
    slides = [{"index": i, "title": text[i]["title"],
               "slide_text": text[i]["slide_text"], "narration": ""}
              for i in range(pages)]
    return {"slides": slides, "fingerprints": fingerprints(slides_dir, text),
            "pages": pages}


def _fitz():
    try:
        import fitz
        return fitz
    except ImportError:
        import pymupdf
        return pymupdf
