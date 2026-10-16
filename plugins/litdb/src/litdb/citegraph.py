"""Citation graph — build and query citation edges via OpenAlex.

``cite-fetch`` populates edges for a paper (the works it references, plus a
sample of works that cite it). Edges are stored by OpenAlex id, so the graph
includes works you don't own — which powers the most useful query,
``missing-refs``: papers your library leans on but that you haven't added yet.

OpenAlex is the source (free, no key, complete reference lists). Semantic
Scholar citation endpoints are a later addition.
"""

from __future__ import annotations

import sqlite3

from . import db
from .external import openalex


def _paper_oaid(conn: sqlite3.Connection, paper_id: int, mailto: str) -> str | None:
    """Return a paper's OpenAlex id, resolving+persisting it from the DOI if needed."""
    row = conn.execute("SELECT openalex_id, doi FROM paper WHERE id=?", (paper_id,)).fetchone()
    if row is None:
        return None
    if row["openalex_id"]:
        return row["openalex_id"]
    if row["doi"]:
        rec = openalex.get_by_doi(row["doi"], mailto=mailto)
        if rec and rec.get("openalex_id"):
            conn.execute("UPDATE paper SET openalex_id=? WHERE id=?", (rec["openalex_id"], paper_id))
            conn.commit()
            return rec["openalex_id"]
    return None


def ingest_for_paper(conn, config, paper_id: int, *, cited_by_limit: int = 50) -> dict:
    mailto = config.get("external", {}).get("openalex_mailto", "")
    oaid = _paper_oaid(conn, paper_id, mailto)
    if not oaid:
        return {"error": "no OpenAlex id (need a DOI or OpenAlex-sourced paper)", "paper_id": paper_id}

    work = openalex.get_work_raw(oaid, mailto=mailto)
    refs = openalex.referenced_ids(work) if work else []
    out_edges = [(oaid, r) for r in refs]

    citing = openalex.cited_by(oaid, limit=cited_by_limit, mailto=mailto)
    in_edges = [(c["openalex_id"], oaid) for c in citing if c.get("openalex_id")]

    stored = db.add_citations(conn, out_edges + in_edges)
    return {"paper_id": paper_id, "openalex_id": oaid,
            "references": len(refs), "cited_by_sampled": len(in_edges), "edges_stored": stored}


def ingest_all(conn, config, *, cited_by_limit: int = 25) -> dict:
    rows = conn.execute(
        "SELECT id FROM paper WHERE openalex_id IS NOT NULL OR doi IS NOT NULL"
    ).fetchall()
    done, failed = 0, 0
    edges = 0
    for r in rows:
        try:
            res = ingest_for_paper(conn, config, r["id"], cited_by_limit=cited_by_limit)
            if "error" in res:
                failed += 1
            else:
                done += 1
                edges += res["edges_stored"]
        except (ConnectionError, RuntimeError):
            failed += 1
    return {"papers_processed": done, "papers_failed": failed, "edges_stored": edges}


def _titles_for(conn, config, ext_ids: list[str]) -> dict:
    mailto = config.get("external", {}).get("openalex_mailto", "")
    recs = openalex.fetch_by_ids(ext_ids, mailto=mailto) if ext_ids else []
    return {r["openalex_id"]: r for r in recs if r.get("openalex_id")}


def references(conn, config, paper_id: int, *, k: int = 50) -> list[dict]:
    oaid = conn.execute("SELECT openalex_id FROM paper WHERE id=?", (paper_id,)).fetchone()
    if not oaid or not oaid["openalex_id"]:
        return []
    rows = conn.execute(
        "SELECT cited_ext FROM citation WHERE citing_ext=? LIMIT ?",
        (oaid["openalex_id"], k),
    ).fetchall()
    ext = [r["cited_ext"] for r in rows]
    return _annotate_ext(conn, config, ext)


def cited_by(conn, config, paper_id: int, *, k: int = 50) -> list[dict]:
    oaid = conn.execute("SELECT openalex_id FROM paper WHERE id=?", (paper_id,)).fetchone()
    if not oaid or not oaid["openalex_id"]:
        return []
    rows = conn.execute(
        "SELECT citing_ext FROM citation WHERE cited_ext=? LIMIT ?",
        (oaid["openalex_id"], k),
    ).fetchall()
    ext = [r["citing_ext"] for r in rows]
    return _annotate_ext(conn, config, ext)


def _annotate_ext(conn, config, ext_ids: list[str]) -> list[dict]:
    """Annotate external OpenAlex ids with local paper id (if held) and title."""
    held = {}
    for eid in ext_ids:
        row = conn.execute("SELECT id, title FROM paper WHERE openalex_id=?", (eid,)).fetchone()
        if row:
            held[eid] = {"paper_id": row["id"], "title": row["title"]}
    missing = [e for e in ext_ids if e not in held]
    titles = _titles_for(conn, config, missing)
    out = []
    for eid in ext_ids:
        if eid in held:
            out.append({"openalex_id": eid, "in_corpus": True, **held[eid]})
        else:
            rec = titles.get(eid, {})
            out.append({"openalex_id": eid, "in_corpus": False, "paper_id": None,
                        "title": rec.get("title"), "year": rec.get("year"),
                        "doi": rec.get("doi")})
    return out


def most_cited(conn, *, k: int = 20) -> list[dict]:
    """Papers in the corpus ranked by how many other corpus papers cite them."""
    rows = conn.execute(
        """
        SELECT p.id, p.title, p.year, COUNT(*) AS cited_by_in_corpus
        FROM citation c
        JOIN paper p  ON p.openalex_id  = c.cited_ext
        JOIN paper pc ON pc.openalex_id = c.citing_ext
        GROUP BY p.id ORDER BY cited_by_in_corpus DESC, p.year DESC LIMIT ?
        """,
        (k,),
    ).fetchall()
    return [{"type": "paper", **dict(r)} for r in rows]


def missing_refs(conn, config, *, k: int = 20) -> list[dict]:
    """Works your library references most often but that you don't own — the
    strongest 'what should I add next' signal."""
    rows = conn.execute(
        """
        SELECT c.cited_ext, COUNT(DISTINCT c.citing_ext) AS referenced_by
        FROM citation c
        JOIN paper pc ON pc.openalex_id = c.citing_ext         -- citing paper is in corpus
        LEFT JOIN paper pd ON pd.openalex_id = c.cited_ext      -- cited work is NOT
        WHERE pd.id IS NULL
        GROUP BY c.cited_ext ORDER BY referenced_by DESC LIMIT ?
        """,
        (k,),
    ).fetchall()
    ext = [r["cited_ext"] for r in rows]
    counts = {r["cited_ext"]: r["referenced_by"] for r in rows}
    titles = _titles_for(conn, config, ext)
    out = []
    for eid in ext:
        rec = titles.get(eid, {})
        out.append({"openalex_id": eid, "referenced_by": counts[eid],
                    "title": rec.get("title"), "year": rec.get("year"), "doi": rec.get("doi")})
    return out
