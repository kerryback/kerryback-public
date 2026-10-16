"""Retrieval over the corpus.

Two modes share one result shape:
- keyword: BM25 via FTS5.
- hybrid: BM25 plus one vector rank-list per embedding model present (a hosted
  default and a local model for confidential notes may coexist). The rank-lists
  are fused with Reciprocal Rank Fusion, which needs no score calibration across
  incomparable sources — exactly the situation here.
"""

from __future__ import annotations

import sqlite3
from typing import Dict, List, Sequence, Set, Tuple

from . import db
from . import vectorstore
from .embeddings.base import EmbeddingProvider

RRF_K = 60


def _fts_query(text: str) -> str:
    tokens = [t for t in text.replace('"', " ").split() if t]
    return " ".join(f'"{t}"' for t in tokens)


# --------------------------------------------------------------------------- #
# rank lists
# --------------------------------------------------------------------------- #

def _bm25_hits(conn: sqlite3.Connection, query: str, n: int) -> List[dict]:
    match = _fts_query(query)
    if not match:
        return []
    rows = conn.execute(
        """
        SELECT c.id AS chunk_id, c.owner_type, c.owner_id, c.kind, c.page,
               bm25(chunk_fts) AS score,
               snippet(chunk_fts, 0, '[', ']', ' … ', 14) AS snippet
        FROM chunk_fts JOIN chunk c ON c.id = chunk_fts.rowid
        WHERE chunk_fts MATCH ? ORDER BY score LIMIT ?
        """,
        (match, n),
    ).fetchall()
    return [dict(r) for r in rows]


def _vector_hits(conn: sqlite3.Connection, qvec: List[float], model_id: str, n: int) -> List[dict]:
    out = []
    for cid, sim in vectorstore.knn(conn, qvec, model_id, k=n):
        row = conn.execute(
            "SELECT owner_type, owner_id FROM chunk WHERE id=?", (cid,)
        ).fetchone()
        if row:
            out.append({"chunk_id": cid, "owner_type": row["owner_type"],
                        "owner_id": row["owner_id"], "score": sim})
    return out


def _rrf(rank_lists: Sequence[List[dict]]) -> Dict[int, float]:
    scores: Dict[int, float] = {}
    for hits in rank_lists:
        for rank, h in enumerate(hits):
            scores[h["chunk_id"]] = scores.get(h["chunk_id"], 0.0) + 1.0 / (RRF_K + rank + 1)
    return scores


# --------------------------------------------------------------------------- #
# public search
# --------------------------------------------------------------------------- #

def keyword_search(conn, query, *, k=10, owner_type=None, year_min=None,
                   year_max=None, reading_status=None,
                   project_owners: Set[Tuple[str, int]] | None = None) -> List[dict]:
    # A project filter narrows an already-capped candidate pool, so widen it when
    # one is set — a small project inside a large corpus still fills k.
    pool = max(k * 20, 200) if project_owners is not None else max(k * 8, 40)
    hits = _bm25_hits(conn, query, pool)
    results, seen = [], set()
    for h in hits:
        key = (h["owner_type"], h["owner_id"])
        if key in seen:  # collapse multiple chunks of one paper to its best hit
            continue
        seen.add(key)
        rec = _hydrate(conn, h["owner_type"], h["owner_id"],
                       {"score_bm25": round(float(h["score"]), 4), "snippet": h["snippet"],
                        "matched": {"kind": h["kind"], "page": h["page"]}})
        if rec and _passes(rec, owner_type, year_min, year_max, reading_status, project_owners):
            results.append(rec)
        if len(results) >= k:
            break
    return results


def hybrid_search(conn, query, query_providers: Dict[str, EmbeddingProvider], *, k=10,
                  owner_type=None, year_min=None, year_max=None, reading_status=None,
                  project_owners: Set[Tuple[str, int]] | None = None) -> List[dict]:
    """Fuse BM25 with a vector rank-list per model space. Falls back to keyword
    search when no usable embeddings are present."""
    pool = max(k * 20, 200) if project_owners is not None else max(k * 6, 30)
    bm25 = _bm25_hits(conn, query, pool)
    lists: List[List[dict]] = [bm25]
    snippets = {h["chunk_id"]: h["snippet"] for h in bm25}
    used_vectors = False
    for model_id, provider in query_providers.items():
        try:
            qvec = provider.embed_query(query)
        except (ConnectionError, RuntimeError):
            continue  # provider unavailable (daemon down / no key) -> skip this space
        vhits = _vector_hits(conn, qvec, model_id, pool)
        if vhits:
            lists.append(vhits)
            used_vectors = True

    if not used_vectors and not bm25:
        return []
    if not used_vectors:
        return keyword_search(conn, query, k=k, owner_type=owner_type, year_min=year_min,
                              year_max=year_max, reading_status=reading_status,
                              project_owners=project_owners)

    fused = sorted(_rrf(lists).items(), key=lambda kv: kv[1], reverse=True)
    results, seen = [], set()
    for chunk_id, score in fused:
        owner = conn.execute(
            "SELECT owner_type, owner_id, kind, page, text FROM chunk WHERE id=?", (chunk_id,)
        ).fetchone()
        if owner is None:
            continue
        key = (owner["owner_type"], owner["owner_id"])
        if key in seen:  # collapse multiple chunks of one paper
            continue
        seen.add(key)
        snippet = snippets.get(chunk_id) or (owner["text"][:200] + (" …" if len(owner["text"]) > 200 else ""))
        rec = _hydrate(conn, owner["owner_type"], owner["owner_id"],
                       {"score_rrf": round(score, 5), "snippet": snippet,
                        "matched": {"kind": owner["kind"], "page": owner["page"]}})
        if rec and _passes(rec, owner_type, year_min, year_max, reading_status, project_owners):
            results.append(rec)
        if len(results) >= k:
            break
    return results


def resolve_query_providers(conn, config) -> Dict[str, EmbeddingProvider]:
    """Build query-side providers for every embedding model present in the DB
    that we can reconstruct. At most a couple (default + local)."""
    from .embeddings import registry

    providers: Dict[str, EmbeddingProvider] = {}
    for model_id in vectorstore.models_present(conn):
        prov = registry.from_model_id(model_id, config)
        if prov is not None:
            providers[model_id] = prov
    return providers


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _passes(rec, owner_type, year_min, year_max, reading_status, project_owners=None) -> bool:
    if project_owners is not None and (rec["type"], rec["id"]) not in project_owners:
        return False
    if owner_type and rec["type"] != owner_type:
        return False
    if rec["type"] == "paper":
        yr = rec.get("year")
        if year_min is not None and (yr is None or yr < year_min):
            return False
        if year_max is not None and (yr is None or yr > year_max):
            return False
        if reading_status is not None and rec.get("reading_status") != reading_status:
            return False
    elif reading_status is not None:
        return False
    return True


def _hydrate(conn, owner_type, owner_id, extra: dict) -> dict | None:
    base = {"type": owner_type, **extra}
    if owner_type == "paper":
        p = conn.execute(
            "SELECT id, title, authors, year, venue, doi, citation_key, reading_status "
            "FROM paper WHERE id=?",
            (owner_id,),
        ).fetchone()
        if p is None:
            return None
        base.update(id=p["id"], title=p["title"], authors=p["authors"], year=p["year"],
                    venue=p["venue"], doi=p["doi"], citation_key=p["citation_key"],
                    reading_status=p["reading_status"])
        base["linked_notes"] = int(
            conn.execute("SELECT COUNT(*) FROM note_paper WHERE paper_id=?", (p["id"],)).fetchone()[0]
        )
    else:
        n = conn.execute(
            "SELECT id, title, confidential FROM note WHERE id=?", (owner_id,)
        ).fetchone()
        if n is None:
            return None
        base.update(id=n["id"], title=n["title"], confidential=bool(n["confidential"]))
        base["linked_papers"] = [
            dict(x) for x in conn.execute(
                "SELECT p.id, p.title, np.relation FROM note_paper np "
                "JOIN paper p ON p.id = np.paper_id WHERE np.note_id=?", (n["id"],)
            ).fetchall()
        ]
    base["projects"] = db.project_names(conn, owner_type, owner_id)
    return base
