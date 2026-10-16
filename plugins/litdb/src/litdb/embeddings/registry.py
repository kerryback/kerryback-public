"""Construct providers from config, and rebuild a provider for an existing
vector space by its model_id.

This is the single place that maps configuration to a concrete provider, so the
rest of litdb never imports a specific provider class. Adding a provider means
adding one branch here.
"""

from __future__ import annotations

from .base import EmbeddingProvider
from .hashing import HashingProvider
from .ollama import OllamaProvider
from .voyage import VoyageProvider
from .openai import OpenAIProvider


def _make(provider: str, model: str | None, cfg: dict, dim: int | None) -> EmbeddingProvider:
    provider = provider.lower()
    if provider == "hash":
        return HashingProvider(dim=dim or 256)
    if provider == "ollama":
        url = cfg.get("ollama", {}).get("url", "http://localhost:11434")
        return OllamaProvider(model=model or "nomic-embed-text", url=url, dim=dim)
    if provider == "voyage":
        key_env = cfg.get("voyage", {}).get("api_key_env", "VOYAGE_API_KEY")
        return VoyageProvider(model=model or "voyage-3", api_key_env=key_env, dim=dim)
    if provider == "openai":
        key_env = cfg.get("openai", {}).get("api_key_env", "OPENAI_API_KEY")
        return OpenAIProvider(model=model or "text-embedding-3-small", api_key_env=key_env, dim=dim)
    if provider == "fastembed":
        from .fastembed import FastEmbedProvider  # optional dependency
        return FastEmbedProvider(model=model or "BAAI/bge-small-en-v1.5")
    raise ValueError(f"unknown embedding provider: {provider!r}")


def build_default(config: dict, *, provider: str | None = None, model: str | None = None,
                  dim: int | None = None) -> EmbeddingProvider:
    """The provider named in config[embedding], with optional CLI overrides."""
    emb = config.get("embedding", {})
    return _make(
        provider or emb.get("provider", "ollama"),
        model if model is not None else emb.get("model"),
        config,
        dim if dim is not None else emb.get("dim"),
    )


def build_local(config: dict) -> EmbeddingProvider | None:
    """The provider used for confidential content, per policy. None if the
    default is already local (no separate routing needed)."""
    policy = config.get("policy", {})
    if not policy.get("confidential_stay_local", True):
        return None
    spec = policy.get("local_provider", "ollama:nomic-embed-text")
    prov, _, model = spec.partition(":")
    return _make(prov, model or None, config, config.get("embedding", {}).get("dim"))


def from_model_id(model_id: str, config: dict) -> EmbeddingProvider | None:
    """Rebuild a provider able to embed *queries* into an existing vector space.

    Returns None if the provider type is unknown (so the caller can skip that
    space rather than crash).
    """
    provider, _, model = model_id.partition(":")
    try:
        if provider == "hash":
            return HashingProvider(dim=int(model))
        return _make(provider, model or None, config, None)
    except (ValueError, ImportError):
        return None
