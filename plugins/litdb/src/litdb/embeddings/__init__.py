"""Swappable embedding providers.

The rest of litdb only ever touches the ``EmbeddingProvider`` interface in
``base``; concrete providers (local Ollama/FastEmbed/hash, hosted Voyage/OpenAI)
are constructed from config by ``registry``. Switching provider is a config edit
plus a one-time ``litdb embed`` reindex — different models produce incompatible
vector spaces, so vectors are namespaced by ``model_id``.
"""
