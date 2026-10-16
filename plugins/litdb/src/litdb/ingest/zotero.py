"""Read papers from Zotero into litdb records.

Two source shapes are supported, both mapping to the same normalized dict
(title, authors, year, venue, doi, abstract, zotero_key, extra):

1. A JSON *export file*:
   - CSL-JSON (Better BibTeX / Zotero "CSL JSON" export), or
   - Zotero API item JSON (Better BibTeX "Zotero" / the web+local API shape).
   Using a file keeps ingestion offline and testable with no running Zotero.

2. The Zotero 7 *local API* (http://localhost:23119/...), read live via urllib
   so there is no third-party HTTP dependency in the core.

We deliberately never touch zotero.sqlite directly (it is locked while Zotero
runs and its schema is private).
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any


def _push_item(rec: dict) -> dict:
    """Map a litdb paper row to a Zotero connector (translator) item."""
    creators = []
    for a in (rec.get("authors") or "").split(";"):
        a = a.strip()
        if not a:
            continue
        parts = a.split()
        if len(parts) == 1:
            creators.append({"creatorType": "author", "lastName": parts[0], "firstName": ""})
        else:
            creators.append({"creatorType": "author",
                             "firstName": " ".join(parts[:-1]), "lastName": parts[-1]})
    item = {
        "itemType": "journalArticle" if rec.get("venue") else "preprint",
        "title": rec.get("title") or "Untitled",
        "creators": creators,
        "tags": [{"tag": "litdb"}],
    }
    if rec.get("venue"):
        item["publicationTitle"] = rec["venue"]
    if rec.get("year"):
        item["date"] = str(rec["year"])
    if rec.get("doi"):
        item["DOI"] = rec["doi"]
    return item


def save_items(items: list[dict], *, connector: str = "http://localhost:23119",
               session_id: str = "litdb", timeout: float = 30) -> tuple[int, str]:
    """POST translator items to a running Zotero via the connector server.

    Returns (http_status, body). 201 means the items were saved. Raises
    ConnectionError if Zotero is not reachable (not running).
    """
    url = connector.rstrip("/") + "/connector/saveItems"
    payload = {"sessionID": session_id, "uri": "http://litdb.local/push", "items": items}
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Zotero-Connector-API-Version": "3",
        "X-Zotero-Version": "6.0",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "ignore")
    except urllib.error.URLError as exc:
        raise ConnectionError(
            f"Zotero connector not reachable at {connector} — is Zotero running?"
        ) from exc


def _authors_csl(item: dict) -> str | None:
    people = item.get("author") or []
    names = []
    for p in people:
        if "literal" in p:
            names.append(p["literal"])
        else:
            fam, given = p.get("family", ""), p.get("given", "")
            names.append(", ".join(x for x in (fam, given) if x) or p.get("name", ""))
    names = [n for n in names if n]
    return "; ".join(names) or None


def _year_csl(item: dict) -> int | None:
    issued = item.get("issued") or {}
    parts = issued.get("date-parts") or []
    if parts and parts[0]:
        try:
            return int(parts[0][0])
        except (TypeError, ValueError):
            return None
    return None


def _keywords_csl(item: dict) -> list[str]:
    kw = item.get("keyword")
    if isinstance(kw, str):
        return [k.strip() for k in kw.replace(";", ",").split(",") if k.strip()]
    if isinstance(kw, list):
        return [str(k).strip() for k in kw if str(k).strip()]
    return []


def _csl_citation_key(item: dict) -> str | None:
    # CSL 1.0 has an explicit field; Better CSL JSON exports also set `id` to the
    # citekey. Use `id` only when it looks like a citekey, not a URL or number.
    ck = item.get("citation-key")
    if ck:
        return str(ck)
    cid = item.get("id")
    if isinstance(cid, str) and not cid.startswith(("http://", "https://")) and not cid.isdigit():
        return cid
    return None


def _from_csl(item: dict) -> dict:
    return {
        "title": item.get("title"),
        "authors": _authors_csl(item),
        "year": _year_csl(item),
        "venue": item.get("container-title") or item.get("publisher"),
        "doi": item.get("DOI"),
        "abstract": item.get("abstract"),
        "citation_key": _csl_citation_key(item),
        "keywords": _keywords_csl(item),
        "keyword_source": "author",
        "extra": None,
    }


def _authors_zotero(item: dict) -> str | None:
    creators = item.get("creators") or []
    names = []
    for c in creators:
        if c.get("creatorType") not in (None, "author"):
            continue
        if "name" in c:
            names.append(c["name"])
        else:
            last, first = c.get("lastName", ""), c.get("firstName", "")
            names.append(", ".join(x for x in (last, first) if x))
    names = [n for n in names if n]
    return "; ".join(names) or None


def _year_zotero(item: dict) -> int | None:
    date = item.get("date") or ""
    for token in str(date).replace("/", "-").split("-"):
        token = token.strip()
        if len(token) == 4 and token.isdigit():
            return int(token)
    # Zotero often stores YYYY at the end/start; fall back to any 4-digit run.
    import re

    m = re.search(r"(19|20)\d{2}", str(date))
    return int(m.group(0)) if m else None


def _keywords_zotero(data: dict) -> list[str]:
    tags = data.get("tags") or []
    out = []
    for t in tags:
        if isinstance(t, dict) and t.get("tag"):
            out.append(str(t["tag"]).strip())
        elif isinstance(t, str) and t.strip():
            out.append(t.strip())
    return out


def _zotero_citation_key(item: dict, data: dict) -> str | None:
    # Better BibTeX's item.search adds `citekey`/`citationKey` at the item level;
    # otherwise a pinned key lives in the Extra field as "Citation Key: xyz".
    for k in ("citekey", "citationKey"):
        if item.get(k):
            return str(item[k])
        if data.get(k):
            return str(data[k])
    extra = data.get("extra") or ""
    for line in str(extra).splitlines():
        if line.lower().startswith("citation key:"):
            return line.split(":", 1)[1].strip() or None
    return None


def _from_zotero(item: dict) -> dict:
    # A Zotero API record may nest fields under "data".
    data = item.get("data", item)
    return {
        "title": data.get("title"),
        "authors": _authors_zotero(data),
        "year": _year_zotero(data),
        "venue": data.get("publicationTitle") or data.get("bookTitle") or data.get("publisher"),
        "doi": data.get("DOI") or data.get("doi"),
        "abstract": data.get("abstractNote"),
        "zotero_key": data.get("key") or item.get("key"),
        "citation_key": _zotero_citation_key(item, data),
        "keywords": _keywords_zotero(data),
        "keyword_source": "zotero",
        "extra": None,
    }


def _looks_like_csl(item: dict) -> bool:
    return "DOI" in item or "container-title" in item or "issued" in item or "author" in item


def normalize_items(items: list[dict]) -> list[dict]:
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        # Skip attachments/notes coming from Zotero API exports.
        itype = (item.get("data", item)).get("itemType")
        if itype in ("attachment", "note", "annotation"):
            continue
        rec = _from_csl(item) if _looks_like_csl(item) else _from_zotero(item)
        if rec.get("title"):
            out.append(rec)
    return out


def _extract_list(payload: Any) -> list[dict]:
    """Accept either a bare JSON array or an object wrapping the array."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "references", "records"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def read_file(path: str | Path) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return normalize_items(_extract_list(payload))


def read_local_api(url: str, *, limit: int = 100, timeout: float = 10.0) -> list[dict]:
    """Fetch items from the Zotero local API (Zotero 7+). Raises on failure."""
    sep = "&" if "?" in url else "?"
    full = f"{url}{sep}limit={limit}&format=json"
    req = urllib.request.Request(full, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as exc:  # pragma: no cover - network
        raise ConnectionError(
            f"Could not reach the Zotero local API at {url}. Is Zotero running "
            f"with the local API enabled? ({exc})"
        ) from exc
    return normalize_items(_extract_list(payload))
