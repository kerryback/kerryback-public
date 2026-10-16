"""Local embeddings via Ollama (default provider).

Cross-platform: Ollama runs natively on macOS and Windows and exposes the same
HTTP endpoint, so this works identically for all colleagues. Uses urllib (no
third-party HTTP dependency).

Set up with:  ollama pull nomic-embed-text
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import List

from .base import EmbeddingProvider

# Per-model asymmetric prefixes. Getting these right materially affects recall.
_PREFIXES = {
    "nomic-embed-text": ("search_query: ", "search_document: "),
    "snowflake-arctic-embed2": ("query: ", ""),
    "snowflake-arctic-embed": ("query: ", ""),
    "bge-m3": ("", ""),
    "mxbai-embed-large": ("Represent this sentence for searching relevant passages: ", ""),
}


class OllamaProvider(EmbeddingProvider):
    is_local = True

    def __init__(self, model: str = "nomic-embed-text", url: str = "http://localhost:11434",
                 dim: int | None = None):
        self.model = model
        self.base_url = url.rstrip("/")
        self.model_id = f"ollama:{model}"
        self.dim = int(dim) if dim else 0
        base = model.split(":")[0]
        self.query_prefix, self.doc_prefix = _PREFIXES.get(base, ("", ""))

    def _embed(self, texts: List[str]) -> List[List[float]]:
        # Batch endpoint (Ollama >= 0.1.x): one request per batch of inputs.
        payload = json.dumps({"model": self.model, "input": list(texts)}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            if exc.code == 404:
                raise RuntimeError(
                    f"Ollama has no model '{self.model}'. Pull it first: "
                    f"ollama pull {self.model}"
                ) from exc
            raise RuntimeError(f"Ollama API error {exc.code}: {exc.read().decode('utf-8', 'ignore')}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:  # pragma: no cover - network
            raise ConnectionError(
                f"Could not reach Ollama at {self.base_url}. Is it running? "
                f"(start it with `ollama serve`)  ({exc})"
            ) from exc
        vecs = data.get("embeddings")
        if not vecs:
            raise RuntimeError(f"Ollama returned no embeddings for model {self.model}: {data}")
        if not self.dim:
            self.dim = len(vecs[0])
        return vecs
