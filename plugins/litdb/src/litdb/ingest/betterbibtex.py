"""Better BibTeX (BBT) integration via its JSON-RPC endpoint.

BBT is a Zotero add-on that gives every item a stable, LaTeX-friendly citation
key (e.g. ``jegadeesh1993returns``). When a running Zotero has BBT, litdb
prefers this path so those citekeys are captured — otherwise it falls back to
the plain Zotero local API or a file export.

Endpoint: http://localhost:23119/better-bibtex/json-rpc
  - api.ready()            -> version info (used to detect BBT)
  - item.search(terms)     -> Zotero-shaped items, augmented with the citekey

We reuse the Zotero normalizer, which already reads the item-level citekey.
BBT blocks browser access for security, but programmatic (urllib) calls work.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any

from . import zotero

DEFAULT_RPC = "http://localhost:23119/better-bibtex/json-rpc"


def _rpc(url: str, method: str, params: list, timeout: float = 20) -> Any:
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": "litdb/0.1"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError(f"Better BibTeX error: {payload['error']}")
    return payload.get("result") if isinstance(payload, dict) else payload


def available(url: str = DEFAULT_RPC, timeout: float = 5) -> dict | None:
    """Return BBT/Zotero version info if reachable, else None (never raises)."""
    try:
        info = _rpc(url, "api.ready", [], timeout=timeout)
        return info if isinstance(info, dict) else {"ok": True}
    except (urllib.error.URLError, TimeoutError, RuntimeError, ValueError):
        return None


def read_library(url: str = DEFAULT_RPC, *, terms: str = "", timeout: float = 60) -> list[dict]:
    """Fetch all (or matching) items with citekeys, normalized to litdb records."""
    items = _rpc(url, "item.search", [terms], timeout=timeout)
    if not isinstance(items, list):
        raise RuntimeError(f"Unexpected Better BibTeX item.search response: {type(items)}")
    return zotero.normalize_items(items)


def attachment_paths(citekey: str, url: str = DEFAULT_RPC, timeout: float = 20) -> list[str]:
    """Return local file paths of a citekey's attachments (PDFs first)."""
    try:
        res = _rpc(url, "item.attachments", [citekey], timeout=timeout)
    except (urllib.error.URLError, TimeoutError, RuntimeError, ValueError):
        return []
    paths = []
    for att in res or []:
        if not isinstance(att, dict):
            continue
        path = att.get("path") or att.get("localPath") or att.get("file")
        if path:
            paths.append(path)
    # Prefer PDFs.
    paths.sort(key=lambda p: (not str(p).lower().endswith(".pdf"), p))
    return paths
