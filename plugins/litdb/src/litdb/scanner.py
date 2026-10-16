"""Bulk-ingest a folder of loose PDFs.

For scattered PDFs on disk, this walks a directory, reads each PDF's opening
pages, finds an embedded DOI, resolves full metadata from OpenAlex, creates the
paper (deduped on DOI), and stores the PDF's full text as searchable chunks.

PDFs with no findable DOI (older scans, working papers) are reported as
"unresolved" so they can be routed through Zotero's metadata retrieval — they are
not turned into junk records unless ``keep_unresolved`` is set.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from . import db
from . import pdf as pdfmod
from .external import openalex

# DOIs look like 10.<registrant>/<suffix>; stop at whitespace and trim trailing
# punctuation that commonly abuts a DOI in running text.
_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.IGNORECASE)


def find_doi(text: str) -> str | None:
    m = _DOI_RE.search(text or "")
    if not m:
        return None
    return m.group(0).rstrip(".,;:)]}>").lower()


def _find_pdfs(root: Path, recursive: bool) -> list[Path]:
    globber = root.rglob if recursive else root.glob
    return sorted(p for p in globber("*.pdf") if p.is_file())


def _title_from_filename(path: Path) -> str:
    stem = re.sub(r"[_\-]+", " ", path.stem).strip()
    return stem or path.name


def scan_directory(
    conn: sqlite3.Connection,
    config: dict,
    root: str | Path,
    *,
    recursive: bool = True,
    limit: int | None = None,
    keep_unresolved: bool = False,
    head_pages: int = 3,
    skip_hashes: set[str] | None = None,
) -> dict:
    root = Path(root).expanduser()
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    if not pdfmod.available():
        raise RuntimeError("PDF support not installed. Run: pip install 'litdb[pdf]' (pypdf).")

    mailto = config.get("external", {}).get("openalex_mailto", "")
    pdfs = _find_pdfs(root, recursive)
    if limit:
        pdfs = pdfs[:limit]

    skip_hashes = skip_hashes or set()
    resolved, unresolved, errors, skipped = [], [], [], []
    for path in pdfs:
        # Content hash first, so an already-ingested file (by bytes, even if
        # renamed/moved) is skipped without re-reading or re-resolving it. This
        # makes repeated scans of an inbox idempotent — no duplicate stubs.
        try:
            fhash = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            errors.append({"file": str(path), "error": str(exc)[:120]})
            continue
        if fhash in skip_hashes:
            skipped.append({"file": str(path), "hash": fhash})
            continue

        try:
            pages = pdfmod.extract_pages(path)
        except Exception as exc:  # malformed/encrypted PDF
            errors.append({"file": str(path), "error": str(exc)[:120]})
            continue

        doi = find_doi("\n".join(pages[:head_pages]))
        rec = openalex.get_by_doi(doi, mailto=mailto) if doi else None

        if rec:
            pid, created = db.upsert_paper(conn, rec)
            n = db.set_fulltext_chunks(conn, pid, pdfmod.chunk_pages(pages))
            conn.commit()
            resolved.append({"file": str(path), "hash": fhash, "paper_id": pid,
                             "doi": rec.get("doi") or doi, "created": created,
                             "chunks": n, "title": rec.get("title")})
        elif keep_unresolved:
            pid, created = db.upsert_paper(conn, {
                "title": _title_from_filename(path),
                "extra": json.dumps({"source_path": str(path), "unresolved": True}),
            })
            n = db.set_fulltext_chunks(conn, pid, pdfmod.chunk_pages(pages))
            conn.commit()
            unresolved.append({"file": str(path), "hash": fhash, "paper_id": pid, "added": True,
                               "reason": "doi_found_but_unresolved" if doi else "no_doi"})
        else:
            unresolved.append({"file": str(path), "hash": fhash, "added": False,
                               "reason": "doi_found_but_unresolved" if doi else "no_doi"})

    # Record where each ingested PDF lives so the paper's location is queryable
    # (and repeat scans stay idempotent by content hash). Covers resolved papers
    # and unresolved stubs we actually created; false unresolved rows have no id.
    added = resolved + [u for u in unresolved if u.get("added")]
    db.record_ingested(conn, [(e["hash"], e["file"], e["paper_id"]) for e in added])

    return {
        "scanned": len(pdfs),
        "resolved": resolved,
        "unresolved": unresolved,
        "skipped": skipped,
        "errors": errors,
        "summary": {"resolved": len(resolved),
                    "unresolved": len(unresolved),
                    "skipped": len(skipped),
                    "errors": len(errors)},
    }
