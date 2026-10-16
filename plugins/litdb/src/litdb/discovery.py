"""External discovery orchestration — corpus-first, with DOI/id dedup.

The everyday flow: search the user's own corpus first, then reach OpenAlex /
Semantic Scholar for anything new. External results are annotated with whether
they already exist locally (by DOI or source id) and are NOT written unless the
caller explicitly imports them (human-in-the-loop).
"""

from __future__ import annotations

import sqlite3

from . import db
from .external import openalex, semanticscholar


def _client_search(source: str, query: str, config: dict, *, limit, year_min, year_max):
    ext = config.get("external", {})
    timeout = ext.get("timeout", 20)
    if source == "openalex":
        return openalex.search(query, limit=limit, year_min=year_min, year_max=year_max,
                               mailto=ext.get("openalex_mailto", ""), timeout=timeout)
    if source == "s2":
        return semanticscholar.search(query, limit=limit, year_min=year_min, year_max=year_max,
                                      api_key_env=ext.get("s2_api_key_env", "S2_API_KEY"),
                                      timeout=timeout)
    raise ValueError(f"unknown source {source!r}")


def _annotate(conn: sqlite3.Connection, recs: list[dict]) -> list[dict]:
    out = []
    for r in recs:
        pid = db.find_paper_by_ids(
            conn, doi=r.get("doi"), openalex_id=r.get("openalex_id"), s2_id=r.get("s2_id")
        )
        out.append({**r, "in_corpus": pid is not None, "paper_id": pid})
    return out


def external_search(conn, config, query, *, source="auto", limit=10,
                    year_min=None, year_max=None) -> list[dict]:
    """Read-only external search, annotated with local-corpus membership."""
    if source == "auto":
        source = config.get("external", {}).get("default_source", "openalex")
    sources = ["openalex", "s2"] if source == "both" else [source]

    seen, merged = set(), []
    for src in sources:
        for rec in _client_search(src, query, config, limit=limit,
                                  year_min=year_min, year_max=year_max):
            key = rec.get("doi") or rec.get("openalex_id") or rec.get("s2_id") or rec.get("title")
            if key in seen:
                continue
            seen.add(key)
            merged.append(rec)
    return _annotate(conn, merged)


def import_records(conn, recs: list[dict]) -> dict:
    """Upsert chosen external records into the corpus (dedup + keyword merge)."""
    return db.import_papers(conn, recs)


def discover(conn, config, query, *, source="auto", k=10, year_min=None, year_max=None) -> dict:
    """Corpus-first: local hits plus external candidates not already held."""
    from .retrieval import keyword_search, hybrid_search, resolve_query_providers
    from . import vectorstore

    if vectorstore.models_present(conn):
        local = hybrid_search(conn, query, resolve_query_providers(conn, config), k=k)
    else:
        local = keyword_search(conn, query, k=k)

    external = external_search(conn, config, query, source=source, limit=k,
                               year_min=year_min, year_max=year_max)
    external_new = [r for r in external if not r["in_corpus"]]
    return {"local": local, "external_new": external_new,
            "external_already_held": sum(1 for r in external if r["in_corpus"])}
