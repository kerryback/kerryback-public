"""Semantic Scholar (Academic Graph) client.

Works without a key; an optional key (env var named in config) raises rate
limits. Maps S2 fields-of-study to keywords (source=s2) and keeps the TLDR in
`extra`.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
import urllib.error
from typing import List

SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper"
FIELDS = "title,abstract,year,authors,venue,externalIds,fieldsOfStudy,citationCount,tldr"


def _normalize(p: dict) -> dict:
    authors = [a.get("name") for a in (p.get("authors") or []) if a.get("name")]
    ext = p.get("externalIds") or {}
    fos = [f for f in (p.get("fieldsOfStudy") or []) if f]
    tldr = (p.get("tldr") or {}).get("text")
    return {
        "title": p.get("title"),
        "authors": "; ".join(authors) or None,
        "year": p.get("year"),
        "venue": p.get("venue") or None,
        "doi": (ext.get("DOI") or "").lower() or None,
        "abstract": p.get("abstract"),
        "s2_id": p.get("paperId"),
        "keywords": fos,
        "keyword_source": "s2",
        "extra": json.dumps({"citation_count": p.get("citationCount"), "tldr": tldr}),
    }


def _headers() -> dict:
    h = {"Accept": "application/json", "User-Agent": "litdb/0.1 (research tool)"}
    from .. import config
    key = config.get_s2_api_key()  # env var (configured name), then the key file
    if key:
        h["x-api-key"] = key
    return h


def _get(url: str, timeout: float) -> dict:
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - network
        if exc.code == 429:
            raise RuntimeError("Semantic Scholar rate limit (429). Set an API key to raise limits.") from exc
        raise RuntimeError(f"Semantic Scholar HTTP {exc.code}: {exc.read().decode('utf-8', 'ignore')[:200]}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:  # pragma: no cover - network
        raise ConnectionError(f"Could not reach Semantic Scholar ({exc}).") from exc


def search(query: str, *, limit: int = 10, year_min: int | None = None,
           year_max: int | None = None, api_key_env: str = "S2_API_KEY",
           timeout: float = 20) -> List[dict]:
    os.environ["_LITDB_S2_KEY_ENV"] = api_key_env
    params = {"query": query, "limit": min(max(limit, 1), 50), "fields": FIELDS}
    if year_min is not None or year_max is not None:
        lo = year_min if year_min is not None else ""
        hi = year_max if year_max is not None else ""
        params["year"] = f"{lo}-{hi}"
    url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"
    data = _get(url, timeout)
    return [_normalize(p) for p in data.get("data", []) if p.get("title")]


def get_by_doi(doi: str, *, api_key_env: str = "S2_API_KEY", timeout: float = 20) -> dict | None:
    os.environ["_LITDB_S2_KEY_ENV"] = api_key_env
    url = f"{PAPER_URL}/DOI:{urllib.parse.quote(doi)}?fields={FIELDS}"
    try:
        return _normalize(_get(url, timeout))
    except RuntimeError:
        return None
