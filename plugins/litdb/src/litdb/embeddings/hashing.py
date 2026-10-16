"""A deterministic, dependency-free embedding provider.

This is NOT a good semantic model — it is a hashed bag-of-words projection. It
exists so that:
  * the hybrid pipeline is testable offline with no model or network, and
  * search still works out of the box before a user installs Ollama.

Swap it for ``ollama`` (local) or ``voyage``/``openai`` (hosted) for real
semantic quality; the interface and storage are identical.
"""

from __future__ import annotations

import hashlib
import re
from typing import List

from .base import EmbeddingProvider

_WORD = re.compile(r"[A-Za-z0-9]+")


class HashingProvider(EmbeddingProvider):
    is_local = True

    def __init__(self, dim: int = 256):
        self.dim = int(dim)
        self.model_id = f"hash:{self.dim}"

    def _embed(self, texts: List[str]) -> List[List[float]]:
        out = []
        for text in texts:
            vec = [0.0] * self.dim
            for tok in _WORD.findall((text or "").lower()):
                h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
                idx = h % self.dim
                sign = 1.0 if (h >> 8) & 1 else -1.0  # signed hashing reduces collisions
                vec[idx] += sign
            out.append(vec)
        return out
