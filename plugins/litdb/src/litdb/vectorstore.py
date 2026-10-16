"""Persist and search vectors.

Vectors are stored as float32 BLOBs in the ``embedding`` table, namespaced by
``model_id``. KNN is brute-force cosine similarity — vectors are L2-normalized at
write time, so similarity is a dot product. This is fully portable (no native
extension) and fast enough for a personal corpus; numpy is used when available
purely as an accelerator. sqlite-vec can replace the KNN later without changing
this interface.
"""

from __future__ import annotations

import array
import sqlite3
from typing import List, Tuple

try:  # optional acceleration
    import numpy as _np
except ModuleNotFoundError:  # pragma: no cover
    _np = None


def pack(vec: List[float]) -> bytes:
    return array.array("f", vec).tobytes()


def unpack(blob: bytes) -> array.array:
    a = array.array("f")
    a.frombytes(blob)
    return a


def upsert(conn: sqlite3.Connection, chunk_id: int, model_id: str, vec: List[float],
           content_hash: str | None) -> None:
    conn.execute(
        "INSERT INTO embedding(chunk_id, model_id, dim, content_hash, vec) VALUES (?,?,?,?,?) "
        "ON CONFLICT(chunk_id, model_id) DO UPDATE SET "
        "dim=excluded.dim, content_hash=excluded.content_hash, vec=excluded.vec",
        (chunk_id, model_id, len(vec), content_hash, pack(vec)),
    )


def cached_hash(conn: sqlite3.Connection, chunk_id: int, model_id: str) -> str | None:
    row = conn.execute(
        "SELECT content_hash FROM embedding WHERE chunk_id=? AND model_id=?",
        (chunk_id, model_id),
    ).fetchone()
    return row["content_hash"] if row else None


def models_present(conn: sqlite3.Connection) -> List[str]:
    return [r["model_id"] for r in conn.execute("SELECT DISTINCT model_id FROM embedding").fetchall()]


def knn(conn: sqlite3.Connection, query_vec: List[float], model_id: str, *, k: int = 20,
        owner_type: str | None = None) -> List[Tuple[int, float]]:
    """Return up to k (chunk_id, cosine_similarity) for one model space."""
    sql = "SELECT e.chunk_id AS cid, e.vec AS vec FROM embedding e"
    params: list = [model_id]
    if owner_type:
        sql += " JOIN chunk c ON c.id = e.chunk_id WHERE e.model_id=? AND c.owner_type=?"
        params.append(owner_type)
    else:
        sql += " WHERE e.model_id=?"
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return []

    if _np is not None:
        q = _np.asarray(query_vec, dtype=_np.float32)
        mat = _np.frombuffer(b"".join(r["vec"] for r in rows), dtype=_np.float32)
        mat = mat.reshape(len(rows), -1)
        sims = mat @ q  # both sides L2-normalized -> cosine
        ids = [r["cid"] for r in rows]
        order = _np.argsort(-sims)[:k]
        return [(ids[i], float(sims[i])) for i in order]

    # pure-Python fallback
    scored = []
    for r in rows:
        v = unpack(r["vec"])
        scored.append((r["cid"], sum(a * b for a, b in zip(v, query_vec))))
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:k]
