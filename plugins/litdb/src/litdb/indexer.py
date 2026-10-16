"""Embed the corpus into the vector store.

Routing: each chunk is embedded by the default provider, EXCEPT chunks that
belong to confidential notes, which go to the local provider (per policy) so
their text never leaves the machine — even when the default is a hosted API.

Caching: a chunk is re-embedded only when its ``content_hash`` differs from the
stored embedding for that model. The default provider's model becomes the
"active" model recorded in meta.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from typing import List

from . import db
from . import vectorstore
from .embeddings.base import EmbeddingProvider


def _batched(seq: List, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def embed_corpus(
    conn: sqlite3.Connection,
    default_provider: EmbeddingProvider,
    *,
    local_provider: EmbeddingProvider | None = None,
    force: bool = False,
    batch_size: int = 64,
) -> dict:
    confidential = {
        r["id"]
        for r in conn.execute("SELECT id FROM note WHERE confidential=1").fetchall()
    }
    rows = conn.execute(
        "SELECT id, owner_type, owner_id, text, content_hash FROM chunk"
    ).fetchall()

    # Group work by the provider that should embed it.
    work: dict[int, list] = defaultdict(list)   # id(provider) -> list of rows
    providers: dict[int, EmbeddingProvider] = {}
    for r in rows:
        use_local = (
            local_provider is not None
            and r["owner_type"] == "note"
            and r["owner_id"] in confidential
        )
        prov = local_provider if use_local else default_provider
        providers[id(prov)] = prov
        if not force:
            cached = vectorstore.cached_hash(conn, r["id"], prov.model_id)
            if cached is not None and cached == r["content_hash"]:
                continue
        work[id(prov)].append(r)

    counts: dict[str, int] = {}
    errors: dict[str, str] = {}
    for pid, items in work.items():
        prov = providers[pid]
        if not items:
            continue
        try:
            for batch in _batched(items, batch_size):
                vecs = prov.embed_documents([r["text"] for r in batch])
                for r, vec in zip(batch, vecs):
                    vectorstore.upsert(conn, r["id"], prov.model_id, vec, r["content_hash"])
                conn.commit()  # persist progress per batch
            counts[prov.model_id] = counts.get(prov.model_id, 0) + len(items)
        except (ConnectionError, RuntimeError) as exc:
            # One provider being unavailable (daemon down, missing key) must not
            # discard work already done by other providers.
            errors[prov.model_id] = str(exc)

    # Record the active model only if it was actually usable this run.
    if default_provider.model_id not in errors:
        db.set_meta(conn, "active_embedding_model", default_provider.model_id)
    conn.commit()
    return {
        "embedded": counts,
        "errors": errors,
        "active_embedding_model": db.get_meta(conn, "active_embedding_model"),
        "skipped_cached": len(rows) - sum(len(v) for v in work.values()),
    }
