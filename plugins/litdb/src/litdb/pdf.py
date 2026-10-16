"""PDF full-text extraction and chunking.

Uses pypdf (pure Python, no native/system dependency) so the plugin stays
portable across macOS and Windows. Extraction is best-effort: it handles
text-based PDFs well and scanned/image PDFs not at all (those need OCR, out of
scope). Chunking is a page-anchored sliding window over words — section-aware
splitting is deferred; each chunk records the page it starts on so retrieval can
cite a location.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List


def available() -> bool:
    try:
        import pypdf  # noqa: F401
        return True
    except ModuleNotFoundError:
        return False


def extract_pages(path: str | Path) -> List[str]:
    """Return a list of page texts. Raises ImportError if pypdf is missing."""
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise ImportError("PDF support needs pypdf: pip install 'litdb[pdf]'") from exc
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # pragma: no cover - malformed page
            pages.append("")
    return pages


_WS = re.compile(r"[ \t]*\n[ \t]*")
_MULTISPACE = re.compile(r"[ \t]{2,}")


def _clean(text: str) -> str:
    # De-hyphenate line breaks, collapse newlines/spaces into readable flow.
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = _WS.sub(" ", text)
    return _MULTISPACE.sub(" ", text).strip()


def chunk_pages(pages: List[str], *, target_words: int = 220, overlap_words: int = 40) -> List[dict]:
    """Sliding-window chunks over the whole document, tagged with a start page.

    Windows are sized in words (roughly a few hundred tokens) with overlap so a
    concept spanning a boundary is still retrievable. Small overlap keeps storage
    and embedding cost modest.
    """
    tokens: list[tuple[str, int]] = []  # (word, page_number)
    for pageno, raw in enumerate(pages, start=1):
        for word in _clean(raw).split():
            tokens.append((word, pageno))
    if not tokens:
        return []

    step = max(target_words - overlap_words, 1)
    chunks: List[dict] = []
    for start in range(0, len(tokens), step):
        window = tokens[start:start + target_words]
        if not window:
            break
        text = " ".join(w for w, _ in window)
        if len(text.strip()) < 30:  # skip trivially small tail windows
            continue
        chunks.append({"text": text, "page": window[0][1]})
        if start + target_words >= len(tokens):
            break
    return chunks


def extract_and_chunk(path: str | Path, **kw) -> List[dict]:
    return chunk_pages(extract_pages(path), **kw)
