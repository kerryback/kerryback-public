"""Optional MCP wrapper around the litdb core.

The CLI is the primary, always-available surface; this module exposes the same
operations as MCP tools for clients that prefer native tool calls. It requires
the optional ``mcp`` dependency (``pip install 'litdb[mcp]'``) and is not needed
for Phase 1 use — the SKILL.md drives the CLI directly.

Run with:  python -m litdb.server
"""

from __future__ import annotations

from . import db
from .ingest import zotero
from .retrieval import keyword_search

try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError:  # pragma: no cover
    raise SystemExit(
        "The MCP wrapper needs the optional 'mcp' package. Install with: "
        "pip install 'litdb[mcp]'  (the litdb CLI works without it)."
    )

mcp = FastMCP("litdb")


def _conn():
    conn = db.connect()
    db.init_db(conn)
    return conn


@mcp.tool()
def search(query: str, k: int = 10, type: str = "all") -> list[dict]:
    """Keyword (BM25) search over your papers and notes. Search here before any
    external source. `type` is 'paper', 'note', or 'all'."""
    return keyword_search(_conn(), query, k=k, owner_type=None if type == "all" else type)


@mcp.tool()
def add_note(body: str, title: str = "", confidential: bool = False,
             link_paper_ids: list[int] | None = None, relation: str = "") -> dict:
    """Add a user note, optionally linked to papers by id. Set confidential=True
    to keep the note local-only for embeddings."""
    nid = db.add_note(
        _conn(), body, title=title or None, confidential=confidential,
        link_paper_ids=link_paper_ids or [], relation=relation or None,
    )
    return {"note_id": nid}


@mcp.tool()
def link_note(note_id: int, paper_id: int, relation: str = "") -> dict:
    """Link an existing note to a paper."""
    db.link_note_paper(_conn(), note_id, paper_id, relation or None)
    return {"ok": True}


@mcp.tool()
def import_zotero(file: str = "", url: str = "", limit: int = 100) -> dict:
    """Import papers from a Zotero JSON export file, or the local API when no
    file is given."""
    conn = _conn()
    records = zotero.read_file(file) if file else zotero.read_local_api(
        url or "http://localhost:23119/api/users/0/items", limit=limit
    )
    out = db.import_papers(conn, records)
    out["read"] = len(records)
    return out


@mcp.tool()
def discover(query: str, source: str = "auto", k: int = 10) -> dict:
    """Corpus-first discovery: local hits plus external (OpenAlex/S2) results not
    already held. Read-only; import chosen results separately."""
    from . import discovery, config as _cfg
    return discovery.discover(_conn(), _cfg.load_config(), query, source=source, k=k)


@mcp.tool()
def import_doi(doi: str, source: str = "auto") -> dict:
    """Fetch a paper by DOI from OpenAlex (default) or Semantic Scholar and add it
    to the corpus, deduplicating against what you already have."""
    from . import discovery, config as _cfg
    from .external import openalex, semanticscholar
    conn = _conn()
    ext = _cfg.load_config().get("external", {})
    src = source if source != "auto" else ext.get("default_source", "openalex")
    rec = (openalex.get_by_doi(doi, mailto=ext.get("openalex_mailto", ""))
           if src == "openalex" else
           semanticscholar.get_by_doi(doi, api_key_env=ext.get("s2_api_key_env", "S2_API_KEY")))
    if not rec:
        return {"error": "not found", "doi": doi}
    return discovery.import_records(conn, [rec])


@mcp.tool()
def most_cited(k: int = 20) -> list[dict]:
    """Papers most cited by others in your own library (needs cite-fetch first)."""
    from . import citegraph
    return citegraph.most_cited(_conn(), k=k)


@mcp.tool()
def missing_refs(k: int = 20) -> list[dict]:
    """Papers your library references most but that you don't own yet — the best
    'what should I add next' signal (needs cite-fetch first)."""
    from . import citegraph, config as _cfg
    return citegraph.missing_refs(_conn(), _cfg.load_config(), k=k)


@mcp.tool()
def status() -> dict:
    """Corpus statistics and database location."""
    return db.status(_conn())


if __name__ == "__main__":
    mcp.run()
