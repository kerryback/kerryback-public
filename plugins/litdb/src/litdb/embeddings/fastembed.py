"""Optional local embeddings via FastEmbed (ONNX, CPU, no PyTorch).

A lightweight alternative to Ollama for users who prefer an in-process model.
Requires the optional dependency:  pip install 'litdb[fastembed]'.
"""

from __future__ import annotations

from typing import List

from .base import EmbeddingProvider


class FastEmbedProvider(EmbeddingProvider):
    is_local = True

    def __init__(self, model: str = "BAAI/bge-small-en-v1.5"):
        try:
            from fastembed import TextEmbedding
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise ImportError(
                "The fastembed provider needs the optional 'fastembed' package: "
                "pip install 'litdb[fastembed]'"
            ) from exc
        self._model = TextEmbedding(model_name=model)
        self.model_id = f"fastembed:{model}"
        self.dim = 0

    def _embed(self, texts: List[str]) -> List[List[float]]:
        vecs = [list(map(float, v)) for v in self._model.embed(list(texts))]
        if vecs and not self.dim:
            self.dim = len(vecs[0])
        return vecs
