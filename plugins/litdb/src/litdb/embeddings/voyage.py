"""Hosted embeddings via Voyage AI.

Higher retrieval quality than local models, at the cost of sending text to a
third party — so confidential notes are never routed here (see policy in
``registry``/``indexer``). API key from the environment variable named in config
(default VOYAGE_API_KEY). Uses urllib; no third-party HTTP dependency.

Voyage uses an ``input_type`` field ('query' | 'document') rather than text
prefixes, which the base-class prefixes leave empty.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import List

from .base import EmbeddingProvider, l2_normalize

_DIMS = {"voyage-3": 1024, "voyage-3-lite": 512, "voyage-3-large": 1024, "voyage-2": 1024}


class VoyageProvider(EmbeddingProvider):
    is_local = False

    def __init__(self, model: str = "voyage-3", api_key_env: str = "VOYAGE_API_KEY",
                 dim: int | None = None):
        self.model = model
        self.api_key_env = api_key_env
        self.api_key = os.environ.get(api_key_env)
        self.model_id = f"voyage:{model}"
        self.dim = int(dim) if dim else _DIMS.get(model, 1024)

    def _call(self, texts: List[str], input_type: str) -> List[List[float]]:
        if not self.api_key:
            raise RuntimeError(
                f"Voyage API key not set. Export {self.api_key_env} to use the voyage provider."
            )
        body = json.dumps({"model": self.model, "input": texts, "input_type": input_type}).encode()
        req = urllib.request.Request(
            "https://api.voyageai.com/v1/embeddings",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            raise RuntimeError(f"Voyage API error {exc.code}: {exc.read().decode('utf-8', 'ignore')}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:  # pragma: no cover - network
            raise ConnectionError(f"Could not reach the Voyage API ({exc}).") from exc
        return [item["embedding"] for item in sorted(data["data"], key=lambda d: d["index"])]

    def _embed(self, texts: List[str]) -> List[List[float]]:  # documents
        return self._call(texts, "document")

    # Override so queries get input_type='query'; base handles normalization.
    def embed_query(self, text: str) -> List[float]:
        return l2_normalize(self._call([text or ""], "query")[0])
