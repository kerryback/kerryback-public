"""OpenAlex client.

Free, no API key. We join the "polite pool" by sending a mailto (configurable).
Returns records normalized to litdb's shape, with OpenAlex "concepts" mapped to
keywords (source=openalex) and the abstract reconstructed from its inverted
index.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import urllib.error
from typing import List, Optional

BASE = "https://api.openalex.org/works"
USER_AGENT = "litdb/0.1 (https://github.com/; research tool)"


def _abstract_from_inverted(inv: Optional[dict]) -> Optional[str]:
    if not inv:
        return None
    positions = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    text = " ".join(w for _, w in positions)
    return text or None


def _strip_doi(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    return doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip().lower() or None


def _basename_id(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    return url.rstrip("/").split("/")[-1]


def _normalize(work: dict) -> dict:
    authors = [
        a.get("author", {}).get("display_name")
        for a in work.get("authorships", [])
    ]
    authors = [a for a in authors if a]
    source = (work.get("primary_location") or {}).get("source") or {}
    concepts = [c.get("display_name") for c in (work.get("concepts") or [])[:6]]
    concepts = [c for c in concepts if c]
    return {
        "title": work.get("title") or work.get("display_name"),
        "authors": "; ".join(authors) or None,
        "year": work.get("publication_year"),
        "venue": source.get("display_name"),
        "doi": _strip_doi(work.get("doi")),
        "abstract": _abstract_from_inverted(work.get("abstract_inverted_index")),
        "openalex_id": _basename_id(work.get("id")),
        "keywords": concepts,
        "keyword_source": "openalex",
        "extra": json.dumps({"cited_by_count": work.get("cited_by_count")}),
    }


def _get(url: str, timeout: float) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - network
        raise RuntimeError(f"OpenAlex HTTP {exc.code}: {exc.read().decode('utf-8', 'ignore')[:200]}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:  # pragma: no cover - network
        raise ConnectionError(f"Could not reach OpenAlex ({exc}).") from exc


def search(query: str, *, limit: int = 10, year_min: int | None = None,
           year_max: int | None = None, mailto: str = "", timeout: float = 20) -> List[dict]:
    params = {"search": query, "per-page": min(max(limit, 1), 50)}
    filters = []
    if year_min is not None:
        filters.append(f"from_publication_date:{year_min}-01-01")
    if year_max is not None:
        filters.append(f"to_publication_date:{year_max}-12-31")
    if filters:
        params["filter"] = ",".join(filters)
    if mailto:
        params["mailto"] = mailto
    url = f"{BASE}?{urllib.parse.urlencode(params)}"
    data = _get(url, timeout)
    return [_normalize(w) for w in data.get("results", [])]


def get_by_doi(doi: str, *, mailto: str = "", timeout: float = 20) -> dict | None:
    doi = _strip_doi(doi)
    if not doi:
        return None
    params = {"mailto": mailto} if mailto else {}
    q = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{BASE}/https://doi.org/{doi}{q}"
    try:
        return _normalize(_get(url, timeout))
    except RuntimeError:
        return None


def get_work_raw(oaid_or_doi: str, *, mailto: str = "", timeout: float = 20) -> dict | None:
    """Fetch a single work's raw JSON (includes referenced_works). Accepts an
    OpenAlex id (W...) or a DOI."""
    ident = oaid_or_doi
    if "/" in ident or ident.lower().startswith("10."):
        doi = _strip_doi(ident)
        ident = f"https://doi.org/{doi}"
    params = {"mailto": mailto} if mailto else {}
    q = f"?{urllib.parse.urlencode(params)}" if params else ""
    try:
        return _get(f"{BASE}/{ident}{q}", timeout)
    except RuntimeError:
        return None


def referenced_ids(work: dict) -> list[str]:
    return [_basename_id(w) for w in (work.get("referenced_works") or []) if w]


def fetch_by_ids(ids: list[str], *, mailto: str = "", timeout: float = 20) -> list[dict]:
    """Batch-fetch normalized records for OpenAlex ids (for titles of refs)."""
    out: list[dict] = []
    for i in range(0, len(ids), 50):
        batch = [b for b in ids[i:i + 50] if b]
        if not batch:
            continue
        params = {"filter": "openalex_id:" + "|".join(batch), "per-page": 50}
        if mailto:
            params["mailto"] = mailto
        data = _get(f"{BASE}?{urllib.parse.urlencode(params)}", timeout)
        out.extend(_normalize(w) for w in data.get("results", []))
    return out


def cited_by(oaid: str, *, limit: int = 50, mailto: str = "", timeout: float = 20) -> list[dict]:
    """Normalized records for works that cite the given OpenAlex id."""
    params = {"filter": f"cites:{oaid}", "per-page": min(max(limit, 1), 50)}
    if mailto:
        params["mailto"] = mailto
    data = _get(f"{BASE}?{urllib.parse.urlencode(params)}", timeout)
    return [_normalize(w) for w in data.get("results", [])]
