"""The embedding provider interface and shared helpers.

A provider implements ``_embed(texts) -> list[list[float]]`` (raw model call).
The base class handles the two things every caller must get right and no caller
should have to think about:

* asymmetric prefixes — many models need a different instruction for queries vs
  documents (e.g. nomic's ``search_query:`` / ``search_document:``);
* L2 normalization — so downstream cosine similarity is a plain dot product.

``model_id`` (e.g. ``"ollama:nomic-embed-text"``) namespaces stored vectors and
lets the registry rebuild the right provider for an existing vector space.
"""

from __future__ import annotations

import math
from typing import List


def l2_normalize(vec: List[float]) -> List[float]:
    n = math.sqrt(sum(x * x for x in vec))
    if n == 0.0:
        return list(vec)
    return [x / n for x in vec]


class EmbeddingProvider:
    #: stable identity, "provider:model"; namespaces stored vectors
    model_id: str = "base"
    #: vector dimension (may be set after the first call for some providers)
    dim: int = 0
    #: whether text stays on this machine (drives confidential-note routing)
    is_local: bool = True
    max_tokens: int = 8192
    #: prefixes applied to queries / documents before embedding
    query_prefix: str = ""
    doc_prefix: str = ""

    # --- providers implement this ---
    def _embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

    # --- callers use these ---
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        raw = self._embed([self.doc_prefix + (t or "") for t in texts])
        return [l2_normalize(v) for v in raw]

    def embed_query(self, text: str) -> List[float]:
        raw = self._embed([self.query_prefix + (text or "")])[0]
        return l2_normalize(raw)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{type(self).__name__} model_id={self.model_id} dim={self.dim} local={self.is_local}>"
