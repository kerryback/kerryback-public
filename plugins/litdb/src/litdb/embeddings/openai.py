"""Hosted embeddings via the OpenAI API.

Like Voyage, hosted: confidential notes are never routed here. Supports the
Matryoshka ``dimensions`` parameter on text-embedding-3 models to shrink storage.
API key from the environment variable named in config (default OPENAI_API_KEY).
Uses urllib; no third-party HTTP dependency.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import List

from .base import EmbeddingProvider

_DIMS = {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072, "text-embedding-ada-002": 1536}


class OpenAIProvider(EmbeddingProvider):
    is_local = False

    def __init__(self, model: str = "text-embedding-3-small", api_key_env: str = "OPENAI_API_KEY",
                 dim: int | None = None):
        self.model = model
        self.api_key_env = api_key_env
        self.api_key = os.environ.get(api_key_env)
        self.model_id = f"openai:{model}"
        self._truncate = int(dim) if dim else None
        self.dim = self._truncate or _DIMS.get(model, 1536)

    def _embed(self, texts: List[str]) -> List[List[float]]:
        if not self.api_key:
            raise RuntimeError(
                f"OpenAI API key not set. Export {self.api_key_env} to use the openai provider."
            )
        payload = {"model": self.model, "input": texts}
        if self._truncate and self.model.startswith("text-embedding-3"):
            payload["dimensions"] = self._truncate
        req = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            raise RuntimeError(f"OpenAI API error {exc.code}: {exc.read().decode('utf-8', 'ignore')}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:  # pragma: no cover - network
            raise ConnectionError(f"Could not reach the OpenAI API ({exc}).") from exc
        return [item["embedding"] for item in sorted(data["data"], key=lambda d: d["index"])]
