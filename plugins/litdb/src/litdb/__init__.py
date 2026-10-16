"""litdb — a personal literature + notes knowledge base.

Phase 1 provides a local SQLite store (papers, notes, optional note<->paper
links), Zotero ingestion, and BM25 keyword search over FTS5. Later phases add
vector embeddings (behind a swappable provider interface) and external
discovery (OpenAlex / Semantic Scholar).

The public surface is the CLI (``litdb ...`` / ``python -m litdb``); an optional
MCP wrapper in ``litdb.server`` exposes the same operations as MCP tools.
"""

__version__ = "0.1.0"
