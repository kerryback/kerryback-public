"""litdb command-line interface.

This is the stable surface the SKILL.md drives and the smoke tests exercise.
Every command prints JSON to stdout so an agent can parse results directly;
pass ``--human`` for readable output. Exit code is non-zero on error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import db
from . import config
from . import indexer
from . import retrieval
from . import vectorstore
from . import discovery
from . import citegraph
from . import scanner
from . import pdf as pdfmod
from .ingest import zotero, betterbibtex
from .external import openalex, semanticscholar
from .embeddings import registry


def _out(obj, human: bool) -> None:
    if human:
        print(_humanize(obj))
    else:
        print(json.dumps(obj, indent=2, ensure_ascii=False))


def _humanize(obj) -> str:
    if isinstance(obj, list):
        lines = []
        for i, hit in enumerate(obj, 1):
            if "type" not in hit and "name" in hit and ("papers" in hit or "notes" in hit):
                lines.append(
                    f"{i}. {hit['name']}  "
                    f"({hit.get('papers', 0)} papers, {hit.get('notes', 0)} notes)"
                )
                continue
            if hit.get("type") == "paper":
                who = hit.get("authors") or ""
                yr = hit.get("year") or ""
                tags = []
                if hit.get("reading_status") and hit["reading_status"] != "unseen":
                    tags.append(hit["reading_status"])
                if hit.get("priority") is not None:
                    tags.append(f"p{hit['priority']}")
                if hit.get("citation_key"):
                    tags.insert(0, f"@{hit['citation_key']}")
                suffix = f"  <{', '.join(tags)}>" if tags else ""
                lines.append(f"{i}. [paper] {hit.get('title','')} ({who} {yr}){suffix}".rstrip())
            else:
                lines.append(f"{i}. [note] {hit.get('title') or '(untitled)'}")
            if hit.get("snippet"):
                lines.append(f"     {hit['snippet']}")
        return "\n".join(lines) or "(no results)"
    return json.dumps(obj, indent=2, ensure_ascii=False)


def _note_projects(args) -> tuple[list[str], str]:
    """Project tags for an added note: explicit --project wins; else the cwd
    basename (which the skill has the agent confirm/override); --no-project opts
    out entirely."""
    if getattr(args, "no_project", False):
        return [], "cwd"
    if getattr(args, "project", None):
        return list(args.project), "user"
    return [Path(os.getcwd()).name], "cwd"


def cmd_init(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    _out({"ok": True, "db_path": str(config.db_path())}, args.human)
    return 0


def cmd_import_zotero(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    cfg = config.load_config()
    if not args.file and not args.use_local and not args.bbt:
        _out({"error": "provide --file PATH, --local, or --bbt"}, args.human)
        return 1
    source = "file"
    if args.file:
        records = zotero.read_file(args.file)
    else:
        # Reading from a running Zotero: prefer Better BibTeX (captures citekeys)
        # automatically when available. Explicit flags win; otherwise honor the
        # user's recorded preference; otherwise auto-detect.
        bbt_url = cfg["zotero"]["bbt_rpc"]
        pref_bbt = cfg["preferences"].get("use_better_bibtex")
        no_bbt = args.no_bbt or (pref_bbt is False and not args.bbt)
        use_bbt = args.bbt or (not no_bbt and betterbibtex.available(bbt_url) is not None)
        if use_bbt:
            if args.bbt and betterbibtex.available(bbt_url) is None:
                _out({"error": "Better BibTeX not reachable. Is Zotero running with the "
                               "Better BibTeX add-on installed?", "endpoint": bbt_url}, args.human)
                return 1
            records = betterbibtex.read_library(bbt_url)
            source = "better-bibtex"
        else:
            url = args.url or cfg["zotero"]["local_api"]
            records = zotero.read_local_api(url, limit=args.limit)
            source = "zotero-local-api"
    result = db.import_papers(conn, records)
    result["read"] = len(records)
    result["source"] = source
    result["with_citation_key"] = sum(1 for r in records if r.get("citation_key"))
    _out(result, args.human)
    return 0


def cmd_add_note(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    body = args.body
    if body == "-" or body is None:
        body = sys.stdin.read()
    nid = db.add_note(
        conn,
        body,
        title=args.title,
        source=args.source,
        confidential=args.confidential,
        kind=args.kind,
        link_paper_ids=args.link or [],
        relation=args.relation,
    )
    # A page/quote attaches to the linked paper(s): re-link (upsert) to record them.
    if (args.page is not None or args.quote) and args.link:
        for pid in args.link:
            db.link_note_paper(conn, nid, pid, args.relation, page=args.page, quote=args.quote)
    names, src = _note_projects(args)
    for name in names:
        db.tag_project(conn, "note", nid, name, source=src)
    conn.commit()
    _out({"ok": True, "note_id": nid, "kind": args.kind, "linked": args.link or [],
          "projects": names}, args.human)
    return 0


def cmd_link(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    db.link_note_paper(conn, args.note, args.paper, args.relation,
                       page=args.page, quote=args.quote)
    _out({"ok": True, "note_id": args.note, "paper_id": args.paper,
          "relation": args.relation, "page": args.page, "quote": args.quote}, args.human)
    return 0


def cmd_notes(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    if args.search:
        # Two-track retrieval: notes only, recall-biased, returned as FULL notes
        # (the caller reads them whole — a note is short and you want the thought,
        # not a passage). Hybrid when embeddings exist, else keyword.
        cfg = config.load_config()
        mode = "hybrid" if vectorstore.models_present(conn) else "keyword"
        if mode == "keyword":
            hits = retrieval.keyword_search(conn, args.search, k=args.k, owner_type="note")
        else:
            providers = retrieval.resolve_query_providers(conn, cfg)
            hits = retrieval.hybrid_search(conn, args.search, providers, k=args.k, owner_type="note")
        out = []
        for h in hits:
            n = db.get_note(conn, h["id"])
            if n:
                if h.get("score") is not None:
                    n["score"] = h["score"]
                out.append(n)
        _out(out, args.human)
        return 0
    notes = db.list_notes(
        conn,
        paper_id=args.paper,
        kind=args.kind,
        project=args.project,
        since=args.since,
        confidential=True if args.confidential else None,
        limit=args.k,
    )
    _out(notes, args.human)
    return 0


def cmd_note(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    n = db.get_note(conn, args.id)
    if n is None:
        _out({"error": "note not found", "id": args.id}, args.human)
        return 1
    _out(n, args.human)
    return 0


def cmd_search(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    cfg = config.load_config()
    owner = args.type if args.type != "all" else None
    project_owners = None
    if args.project:
        project_owners = db.project_members(conn, args.project)
        if not project_owners:
            print(f"warning: no items tagged with project {args.project!r}", file=sys.stderr)
    common = dict(k=args.k, owner_type=owner, year_min=args.year_min,
                  year_max=args.year_max, reading_status=args.status,
                  project_owners=project_owners)

    mode = args.mode
    if mode == "auto":
        mode = "hybrid" if vectorstore.models_present(conn) else "keyword"

    if mode == "keyword":
        hits = retrieval.keyword_search(conn, args.query, **common)
    else:  # hybrid (vector-only is hybrid with BM25 contributing too)
        providers = retrieval.resolve_query_providers(conn, cfg)
        hits = retrieval.hybrid_search(conn, args.query, providers, **common)
    _out(hits, args.human)
    return 0


def cmd_embed(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    cfg = config.load_config()
    default = registry.build_default(cfg, provider=args.provider, model=args.model, dim=args.dim)
    local = registry.build_local(cfg)
    # Avoid a redundant second pass when the local provider equals the default.
    if local is not None and local.model_id == default.model_id:
        local = None
    result = indexer.embed_corpus(conn, default, local_provider=local, force=args.force)
    _out(result, args.human)
    return 0


def cmd_screen(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    ok = db.screen_paper(
        conn, args.paper, status=args.status, note=args.note, priority=args.priority
    )
    if not ok:
        _out({"error": "paper not found", "id": args.paper}, args.human)
        return 1
    _out({"ok": True, "paper_id": args.paper, "status": args.status}, args.human)
    return 0


def cmd_list(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    _out(db.list_papers(conn, reading_status=args.status, limit=args.k), args.human)
    return 0


def cmd_paper(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    p = db.get_paper(conn, args.id)
    if p is None:
        _out({"error": "not found", "id": args.id}, args.human)
        return 1
    _out(p, args.human)
    return 0


def cmd_update(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    fields = {}
    for col in db.UPDATABLE_FIELDS:
        val = getattr(args, col, None)
        if val is not None:
            fields[col] = val
    if not fields:
        _out({"error": "provide at least one field to update (e.g. --doi, --citation-key, "
                       "--title, --authors, --year, --venue, --openalex-id)"}, args.human)
        return 1
    try:
        updated = db.update_paper(conn, args.id, fields)
    except ValueError as exc:
        _out({"error": str(exc), "id": args.id}, args.human)
        return 1
    if updated is None:
        _out({"error": "not found", "id": args.id}, args.human)
        return 1
    _out(updated, args.human)
    return 0


def cmd_merge(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    try:
        result = db.merge_papers(conn, args.keep, args.dupe)
    except ValueError as exc:
        _out({"error": str(exc)}, args.human)
        return 1
    if result is None:
        _out({"error": "paper not found", "keep": args.keep, "dupe": args.dupe}, args.human)
        return 1
    _out(result, args.human)
    return 0


def cmd_delete(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    ok = db.delete_paper(conn, args.id)
    if not ok:
        _out({"error": "not found", "id": args.id}, args.human)
        return 1
    _out({"ok": True, "deleted": args.id}, args.human)
    return 0


def cmd_external_search(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    cfg = config.load_config()
    recs = discovery.external_search(
        conn, cfg, args.query, source=args.source, limit=args.k,
        year_min=args.year_min, year_max=args.year_max,
    )
    if args.import_new:
        new = [r for r in recs if not r["in_corpus"]]
        result = discovery.import_records(conn, new)
        _out({"imported": result, "candidates": len(recs), "new": len(new)}, args.human)
    else:
        _out(recs, args.human)
    return 0


def cmd_discover(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    cfg = config.load_config()
    out = discovery.discover(conn, cfg, args.query, source=args.source, k=args.k,
                             year_min=args.year_min, year_max=args.year_max)
    _out(out, args.human)
    return 0


def cmd_import_doi(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    cfg = config.load_config()
    ext = cfg.get("external", {})
    src = args.source if args.source != "auto" else ext.get("default_source", "openalex")
    if src == "openalex":
        rec = openalex.get_by_doi(args.doi, mailto=ext.get("openalex_mailto", ""),
                                  timeout=ext.get("timeout", 20))
    else:
        rec = semanticscholar.get_by_doi(args.doi, api_key_env=ext.get("s2_api_key_env", "S2_API_KEY"),
                                         timeout=ext.get("timeout", 20))
    if not rec:
        _out({"error": "not found", "doi": args.doi, "source": src}, args.human)
        return 1
    result = discovery.import_records(conn, [rec])
    pid = db.find_paper_by_ids(conn, doi=rec.get("doi"), openalex_id=rec.get("openalex_id"),
                               s2_id=rec.get("s2_id"))
    _out({"imported": result, "paper_id": pid, "title": rec.get("title")}, args.human)
    return 0


def _ingest_one_pdf(conn, cfg, paper_id, file_path):
    chunks = pdfmod.extract_and_chunk(file_path)
    n = db.set_fulltext_chunks(conn, paper_id, chunks)
    return n


def _locate_pdf_auto(conn, cfg, paper_id):
    row = conn.execute("SELECT citation_key FROM paper WHERE id=?", (paper_id,)).fetchone()
    if not row or not row["citation_key"]:
        return None
    paths = betterbibtex.attachment_paths(row["citation_key"], cfg["zotero"]["bbt_rpc"])
    from pathlib import Path
    for p in paths:
        if str(p).lower().endswith(".pdf") and Path(p).is_file():
            return p
    return None


def _ingest_all(conn, cfg) -> dict:
    """Ingest full text for every paper that has a citekey, lacks full text, and
    whose PDF Better BibTeX can locate. Shared by `ingest-pdf --all` and sync."""
    rows = conn.execute("SELECT id FROM paper WHERE citation_key IS NOT NULL").fetchall()
    done, skipped, failed = [], 0, []
    for r in rows:
        pid = r["id"]
        if db.has_fulltext(conn, pid):
            skipped += 1
            continue
        path = _locate_pdf_auto(conn, cfg, pid)
        if not path:
            skipped += 1
            continue
        try:
            n = _ingest_one_pdf(conn, cfg, pid, path)
            done.append({"paper_id": pid, "chunks": n})
        except (ImportError, RuntimeError, OSError) as exc:
            failed.append({"paper_id": pid, "error": str(exc)[:120]})
    return {"ingested": done, "skipped": skipped, "failed": failed}


def cmd_ingest_pdf(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    cfg = config.load_config()
    if not pdfmod.available():
        _out({"error": "PDF support not installed. Run: pip install 'litdb[pdf]' (pypdf)."}, args.human)
        return 1

    if args.all:
        _out(_ingest_all(conn, cfg), args.human)
        return 0

    if args.paper is None:
        _out({"error": "provide --paper ID (with --file or --auto), or --all --auto"}, args.human)
        return 1
    path = args.file or (_locate_pdf_auto(conn, cfg, args.paper) if args.auto else None)
    if not path:
        _out({"error": "no PDF found. Pass --file PATH, or --auto with Better BibTeX + a citekey."}, args.human)
        return 1
    n = _ingest_one_pdf(conn, cfg, args.paper, path)
    _out({"ok": True, "paper_id": args.paper, "chunks": n, "source": str(path)}, args.human)
    return 0


def cmd_scan_pdfs(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    cfg = config.load_config()
    result = scanner.scan_directory(
        conn, cfg, args.dir, recursive=not args.no_recursive, limit=args.limit,
        keep_unresolved=args.keep_unresolved,
    )
    # The agent asks the user for the project/topic and passes it via --project;
    # there is no folder-basename default (folder names make poor topic tags).
    names = args.project or []
    if names:
        ids = [r["paper_id"] for r in result["resolved"]]
        ids += [r["paper_id"] for r in result["unresolved"] if r.get("paper_id")]
        for pid in ids:
            for name in names:
                db.tag_project(conn, "paper", pid, name, source="user")
        conn.commit()
        result["projects"] = names
    if args.embed and result["resolved"]:
        from . import indexer
        from .embeddings import registry
        default = registry.build_default(cfg)
        local = registry.build_local(cfg)
        if local is not None and local.model_id == default.model_id:
            local = None
        result["embed"] = indexer.embed_corpus(conn, default, local_provider=local)
    _out(result, args.human)
    return 0


def cmd_cite_fetch(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    cfg = config.load_config()
    if args.all:
        _out(citegraph.ingest_all(conn, cfg, cited_by_limit=args.cited_by), args.human)
        return 0
    if args.paper is None:
        _out({"error": "provide --paper ID or --all"}, args.human)
        return 1
    _out(citegraph.ingest_for_paper(conn, cfg, args.paper, cited_by_limit=args.cited_by), args.human)
    return 0


def cmd_refs(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    cfg = config.load_config()
    _out(citegraph.references(conn, cfg, args.paper, k=args.k), args.human)
    return 0


def cmd_cited_by(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    cfg = config.load_config()
    _out(citegraph.cited_by(conn, cfg, args.paper, k=args.k), args.human)
    return 0


def cmd_most_cited(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    _out(citegraph.most_cited(conn, k=args.k), args.human)
    return 0


def cmd_missing_refs(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    cfg = config.load_config()
    _out(citegraph.missing_refs(conn, cfg, k=args.k), args.human)
    return 0


def _parse_pref_value(v: str):
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "none"):
        return None
    try:
        return int(v)
    except ValueError:
        return v


def cmd_prefs(args) -> int:
    # Accept both verb form (`prefs set KEY VALUE`, `prefs get KEY`, `prefs list`)
    # and shorthand (`prefs`, `prefs KEY`, `prefs KEY VALUE`).
    a, b, c = args.a, args.b, args.c
    if a in ("set",):
        if b is None or c is None:
            _out({"error": "usage: prefs set KEY VALUE"}, args.human)
            return 1
        key, value = b, c
    elif a in ("get",):
        if b is None:
            _out({"error": "usage: prefs get KEY"}, args.human)
            return 1
        _out({b: config.get_pref(b)}, args.human)
        return 0
    elif a in (None, "list"):
        _out(config.load_prefs(), args.human)
        return 0
    else:  # shorthand: a is a key
        key, value = a, b

    if value is None:
        _out({key: config.get_pref(key)}, args.human)
    else:
        updated = config.set_pref(key, _parse_pref_value(value))
        _out({"set": {key: updated[key]}, "preferences": updated}, args.human)
    return 0


def cmd_onboarded(args) -> int:
    if args.mark:
        config.mark_onboarded()
        _out({"onboarded": True, "marker": str(config.onboarded_marker())}, args.human)
    elif args.reset:
        was = config.reset_onboarded()
        _out({"onboarded": False, "reset": was}, args.human)
    else:
        _out({"onboarded": config.is_onboarded(), "marker": str(config.onboarded_marker())}, args.human)
    return 0


def _mask_key(key: str) -> str:
    return ("…" + key[-4:]) if key and len(key) > 4 else "set"


def cmd_s2key(args) -> int:
    action = args.action or "status"
    if action == "status":
        present = config.has_s2_api_key()
        _out({"s2_api_key_present": present, "source": config.s2_api_key_source(),
              "path": str(config.s2_key_path()),
              "env_var": config.load_config()["external"].get("s2_api_key_env", "S2_API_KEY")},
             args.human)
        return 0
    if action == "set":
        key = args.key
        if key == "-" or key is None:
            key = sys.stdin.read().strip()
        if not key:
            _out({"error": "no key provided (pass the key, or '-' to read stdin)"}, args.human)
            return 1
        path = config.set_s2_api_key(key)
        config.set_pref("has_s2_api_key", True)
        _out({"ok": True, "stored": _mask_key(key), "path": str(path),
              "has_s2_api_key": True}, args.human)
        return 0
    if action == "clear":
        removed = config.clear_s2_api_key()
        # Only claim "no key" if the environment isn't still supplying one.
        config.set_pref("has_s2_api_key", config.has_s2_api_key())
        _out({"ok": True, "removed_file": removed,
              "has_s2_api_key": config.has_s2_api_key()}, args.human)
        return 0
    _out({"error": f"unknown action {action!r}; use status|set|clear"}, args.human)
    return 1


import re as _re


def _fallback_citekey(rec: dict) -> str:
    authors = (rec.get("authors") or "").split(";")
    first = authors[0].strip() if authors and authors[0].strip() else "anon"
    surname = _re.sub(r"[^a-z]", "", first.split()[-1].lower()) if first.split() else "anon"
    yr = rec.get("year") or ""
    words = _re.findall(r"[a-z]+", (rec.get("title") or "").lower())
    kw = next((w for w in words if len(w) > 3), "")
    return f"{surname}{yr}{kw}" or "ref"


def _bibtex_entry(rec: dict, key: str) -> str:
    authors = " and ".join(a.strip() for a in (rec.get("authors") or "").split(";") if a.strip())
    etype = "article" if (rec.get("venue") and rec.get("year")) else "misc"
    fields = []
    if authors:
        fields.append(("author", authors))
    if rec.get("title"):
        fields.append(("title", rec["title"]))
    if rec.get("venue"):
        fields.append(("journal", rec["venue"]))
    if rec.get("year"):
        fields.append(("year", str(rec["year"])))
    if rec.get("doi"):
        fields.append(("doi", rec["doi"]))
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields)
    return f"@{etype}{{{key},\n{body}\n}}"


def cmd_export_bib(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    recs = db.papers_for_export(conn, ids=args.ids, reading_status=args.status)
    # Resolve keys, disambiguating collisions with a/b/c suffixes so the .bib is valid.
    base = [(r, r.get("citation_key") or _fallback_citekey(r)) for r in recs]
    counts, seen, resolved = {}, {}, []
    for _, k in base:
        counts[k] = counts.get(k, 0) + 1
    for r, k in base:
        if counts[k] > 1:
            i = seen.get(k, 0)
            seen[k] = i + 1
            k = k + chr(ord("a") + i)
        resolved.append((r, k))
    text = "\n\n".join(_bibtex_entry(r, k) for r, k in resolved) + ("\n" if resolved else "")
    no_key = sum(1 for r in recs if not r.get("citation_key"))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        out = {"ok": True, "written": len(resolved), "path": args.out}
        if no_key:
            out["generated_fallback_keys"] = no_key
        if config.get_pref("source_of_truth", "litdb") == "zotero":
            out["note"] = ("source_of_truth=zotero: Better BibTeX is authoritative for "
                           "citation keys; this export mirrors litdb's copy.")
        _out(out, args.human)
    else:
        sys.stdout.write(text)
    return 0


def _do_push(conn, cfg, recs) -> tuple[list, list]:
    """Push records to Zotero in chunks; mark successes. Returns (pushed_ids, errors)."""
    import uuid
    connector = cfg["zotero"].get("connector", "http://localhost:23119")
    pushed, errors, conn_err = [], [], None
    for start in range(0, len(recs), 20):
        chunk = recs[start:start + 20]
        try:
            code, body = zotero.save_items([zotero._push_item(r) for r in chunk],
                                           connector=connector, session_id=uuid.uuid4().hex)
        except ConnectionError as exc:
            conn_err = str(exc)
            break
        if code in (200, 201):
            pushed += [r["id"] for r in chunk]
        else:
            errors.append({"http": code, "body": body[:200]})
    if pushed:
        db.mark_zotero_pushed(conn, pushed)
    if conn_err:
        errors.append({"error": conn_err})
    return pushed, errors


def cmd_push_zotero(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    cfg = config.load_config()
    recs = db.papers_for_push(conn, ids=args.ids, reading_status=args.status,
                              include_pushed=args.force)
    if not recs:
        _out({"ok": True, "pushed": 0,
              "note": "nothing to push (already pushed? use --force, or narrow with --ids/--status)"},
             args.human)
        return 0
    if args.dry_run:
        _out({"dry_run": True, "would_push": len(recs),
              "sample": [zotero._push_item(r) for r in recs[:3]]}, args.human)
        return 0
    pushed, errors = _do_push(conn, cfg, recs)
    out = {"ok": not errors, "pushed": len(pushed), "paper_ids": pushed}
    if errors:
        out["errors"] = errors
    _out(out, args.human)
    return 0 if not errors else 1


def _zotero_records(cfg):
    """Read the Zotero library (Better BibTeX when available/enabled, else the
    local API). Returns (records, source). Mirrors `import-zotero --local`."""
    bbt_url = cfg["zotero"]["bbt_rpc"]
    pref_bbt = cfg["preferences"].get("use_better_bibtex")
    use_bbt = (pref_bbt is not False) and betterbibtex.available(bbt_url) is not None
    if use_bbt:
        return betterbibtex.read_library(bbt_url), "better-bibtex"
    return zotero.read_local_api(cfg["zotero"]["local_api"], limit=1000), "zotero-local-api"


def cmd_sync_zotero(args) -> int:
    """Pull new papers from Zotero into litdb: import metadata + citekeys, ingest
    PDFs for anything new, embed. Incremental — safe to run every session."""
    conn = db.connect()
    db.init_db(conn)
    cfg = config.load_config()
    try:
        records, source = _zotero_records(cfg)
    except (ConnectionError, FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
        # Fail soft: the caller (session-start sync) should proceed with existing data.
        _out({"synced": False,
              "error": f"Zotero not reachable (is it running?): {str(exc)[:120]}"}, args.human)
        return 1
    imp = db.import_papers(conn, records)
    imp.update(read=len(records), source=source)
    result = {"synced": True, "import": imp}
    if pdfmod.available():
        result["ingest"] = _ingest_all(conn, cfg)
    else:
        result["ingest"] = {"skipped": "pypdf not installed"}
    default = registry.build_default(cfg)
    local = registry.build_local(cfg)
    if local is not None and local.model_id == default.model_id:
        local = None
    result["embed"] = indexer.embed_corpus(conn, default, local_provider=local)
    _out(result, args.human)
    return 0


def cmd_sync_inbox(args) -> int:
    """Ingest new PDFs from the configured inbox folder. Idempotent by content
    hash (already-ingested files are skipped), so it is safe to run every session.
    Returns any new DOI-less stubs under `needs_resolution` for the agent to
    resolve (read PDF -> OpenAlex -> update), mirroring add-folder.md step 3."""
    from pathlib import Path
    conn = db.connect()
    db.init_db(conn)
    cfg = config.load_config()
    inbox = config.get_pref("inbox")
    if not inbox:
        _out({"error": "no inbox configured. Set one: litdb prefs set inbox <folder>"}, args.human)
        return 1
    if not Path(inbox).expanduser().is_dir():
        _out({"error": f"inbox is not a directory: {inbox}"}, args.human)
        return 1
    if not pdfmod.available():
        _out({"error": "PDF support not installed. Run: pip install 'litdb[pdf]' (pypdf)."}, args.human)
        return 1
    skip = db.ingested_hashes(conn)
    result = scanner.scan_directory(conn, cfg, inbox, recursive=True,
                                    keep_unresolved=True, skip_hashes=skip)
    added = result["resolved"] + [u for u in result["unresolved"] if u.get("added")]
    # scan_directory already records ingested-file paths (idempotent by hash).
    if added:
        default = registry.build_default(cfg)
        local = registry.build_local(cfg)
        if local is not None and local.model_id == default.model_id:
            local = None
        result["embed"] = indexer.embed_corpus(conn, default, local_provider=local)
    result["needs_resolution"] = [{"paper_id": u["paper_id"], "file": u["file"]}
                                  for u in result["unresolved"] if u.get("added")]
    _out(result, args.human)
    return 0


def cmd_migrate_to_zotero(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    cfg = config.load_config()
    recs = db.papers_for_push(conn, include_pushed=args.force)  # the whole corpus, minus already-pushed
    if args.dry_run:
        _out({"dry_run": True, "would_push": len(recs),
              "would_set": {"source_of_truth": "zotero"}}, args.human)
        return 0
    pushed, errors = _do_push(conn, cfg, recs) if recs else ([], [])
    if errors:
        # Do NOT flip the source of truth on a partial migration — leave litdb authoritative.
        _out({"ok": False, "pushed": len(pushed), "errors": errors,
              "note": "source_of_truth left unchanged because the push had errors; "
                      "fix Zotero (is it running?) and re-run"}, args.human)
        return 1
    config.set_pref("source_of_truth", "zotero")
    _out({"ok": True, "migrated": len(pushed), "source_of_truth": "zotero",
          "next": "run import-zotero to pull Better BibTeX citation keys back into litdb"},
         args.human)
    return 0


def cmd_status(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    st = db.status(conn)
    st["s2_api_key_present"] = config.has_s2_api_key()
    st["source_of_truth"] = config.get_pref("source_of_truth", "litdb")
    _out(st, args.human)
    return 0


def cmd_projects(args) -> int:
    conn = db.connect()
    db.init_db(conn)
    if args.action == "list":
        _out(db.list_projects(conn), args.human)
    elif args.action == "rename":
        ok = db.rename_project(conn, args.old, args.new)
        _out({"ok": ok, "old": args.old, "new": args.new}, args.human)
    else:  # tag | untag
        fn = db.tag_project if args.action == "tag" else db.untag_project
        n = 0
        for oid in args.paper or []:
            fn(conn, "paper", oid, args.name)
            n += 1
        for oid in args.note or []:
            fn(conn, "note", oid, args.name)
            n += 1
        conn.commit()
        _out({"ok": True, "action": args.action, "project": args.name, "items": n}, args.human)
    return 0


def build_parser() -> argparse.ArgumentParser:
    # A shared parent carrying --human so the flag is accepted both before and
    # after the subcommand (natural for interactive/agent use).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--human", action="store_true", help="human-readable output instead of JSON")

    p = argparse.ArgumentParser(
        prog="litdb", parents=[common],
        description="Personal literature + notes knowledge base",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, **kw):
        return sub.add_parser(name, parents=[common], **kw)

    add("init", help="create the database").set_defaults(func=cmd_init)

    imp = add("import-zotero", help="import papers from a Zotero JSON export or a running Zotero")
    g = imp.add_mutually_exclusive_group()
    g.add_argument("--file", help="path to a CSL-JSON or Zotero JSON export")
    g.add_argument("--local", dest="use_local", action="store_true",
                   help="read from a running Zotero (Better BibTeX if available, else local API)")
    imp.add_argument("--url", help="override the Zotero local API URL")
    imp.add_argument("--limit", type=int, default=100)
    imp.add_argument("--bbt", action="store_true", help="require Better BibTeX (error if unavailable)")
    imp.add_argument("--no-bbt", action="store_true", help="skip Better BibTeX; use the plain local API")
    imp.set_defaults(func=cmd_import_zotero)

    note = add("add-note", help="add a user note (optionally linked to papers)")
    note.add_argument("--body", help="note text, or '-' to read stdin", default="-")
    note.add_argument("--title")
    note.add_argument("--source")
    note.add_argument("--kind", choices=list(db.NOTE_KINDS),
                      help="note kind: idea|summary|critique|question|todo|quote")
    note.add_argument("--confidential", action="store_true", help="keep local-only for embeddings")
    note.add_argument("--link", type=int, action="append", metavar="PAPER_ID")
    note.add_argument("--relation", help="relation label for the links, e.g. about/critique/cites")
    note.add_argument("--page", type=int, help="page in the linked paper the note refers to")
    note.add_argument("--quote", help="verbatim passage from the linked paper the note is about")
    note.add_argument("--project", action="append", metavar="NAME",
                      help="tag the note with a project (repeatable); default: cwd basename")
    note.add_argument("--no-project", action="store_true",
                      help="do not auto-tag the note with a project")
    note.set_defaults(func=cmd_add_note)

    ln = add("link", help="link an existing note to a paper")
    ln.add_argument("--note", type=int, required=True)
    ln.add_argument("--paper", type=int, required=True)
    ln.add_argument("--relation")
    ln.add_argument("--page", type=int, help="page in the paper the note refers to")
    ln.add_argument("--quote", help="verbatim passage the note is about")
    ln.set_defaults(func=cmd_link)

    nts = add("notes", help="list your notes, or search notes only (returns full notes)")
    nts.add_argument("--search", metavar="QUERY",
                     help="hybrid keyword+semantic search over notes only; returns full bodies")
    nts.add_argument("--paper", type=int, help="only notes linked to this paper id")
    nts.add_argument("--kind", choices=list(db.NOTE_KINDS), help="only notes of this kind")
    nts.add_argument("--project", metavar="NAME", help="only notes tagged with this project")
    nts.add_argument("--since", metavar="YYYY-MM-DD", help="only notes created on/after this date")
    nts.add_argument("--confidential", action="store_true", help="only confidential notes")
    nts.add_argument("-k", type=int, default=50, help="max notes to return")
    nts.set_defaults(func=cmd_notes)

    nsh = add("note", help="show one note with its links (full body)")
    nsh.add_argument("id", type=int)
    nsh.set_defaults(func=cmd_note)

    s = add("search", help="keyword (BM25) search over papers and notes")
    s.add_argument("query")
    s.add_argument("-k", type=int, default=10)
    s.add_argument("--type", choices=["paper", "note", "all"], default="all")
    s.add_argument("--year-min", type=int, dest="year_min")
    s.add_argument("--year-max", type=int, dest="year_max")
    s.add_argument("--status", choices=list(db.READING_STATUSES),
                   help="restrict to papers with this reading status")
    s.add_argument("--project", metavar="NAME", help="restrict results to a project")
    s.add_argument("--mode", choices=["auto", "keyword", "hybrid"], default="auto",
                   help="auto = hybrid if embeddings exist, else keyword")
    s.set_defaults(func=cmd_search)

    em = add("embed", help="embed the corpus for semantic/hybrid search (Phase 2)")
    em.add_argument("--provider", choices=["hash", "ollama", "fastembed", "voyage", "openai"],
                    help="override the configured provider (also swaps the active vector space)")
    em.add_argument("--model", help="override the model name")
    em.add_argument("--dim", type=int, help="override/truncate the embedding dimension")
    em.add_argument("--force", action="store_true", help="re-embed everything, ignoring the cache")
    em.set_defaults(func=cmd_embed)

    sc = add("screen", help="set a paper's reading status / triage note")
    sc.add_argument("--paper", type=int, required=True)
    sc.add_argument("--status", choices=list(db.READING_STATUSES))
    sc.add_argument("--note", help="short screening note: why (not) read")
    sc.add_argument("--priority", type=int)
    sc.set_defaults(func=cmd_screen)

    ls = add("list", help="list papers (optionally by reading status), for triage")
    ls.add_argument("--status", choices=list(db.READING_STATUSES))
    ls.add_argument("-k", type=int, default=50)
    ls.set_defaults(func=cmd_list)

    def _ext_args(parser):
        parser.add_argument("query")
        parser.add_argument("-k", type=int, default=10)
        parser.add_argument("--source", choices=["auto", "openalex", "s2", "both"], default="auto")
        parser.add_argument("--year-min", type=int, dest="year_min")
        parser.add_argument("--year-max", type=int, dest="year_max")

    es = add("external-search", help="search OpenAlex/Semantic Scholar (annotated with local-corpus membership)")
    _ext_args(es)
    es.add_argument("--import", dest="import_new", action="store_true",
                    help="import results not already in the corpus")
    es.set_defaults(func=cmd_external_search)

    dv = add("discover", help="corpus-first: local hits plus new external candidates")
    _ext_args(dv)
    dv.set_defaults(func=cmd_discover)

    idoi = add("import-doi", help="fetch a paper by DOI from an external source and add it")
    idoi.add_argument("doi")
    idoi.add_argument("--source", choices=["auto", "openalex", "s2"], default="auto")
    idoi.set_defaults(func=cmd_import_doi)

    sp = add("scan-pdfs", help="bulk-import a folder of loose PDFs (resolve DOIs via OpenAlex, ingest full text)")
    sp.add_argument("dir", help="directory to scan for PDFs")
    sp.add_argument("--no-recursive", action="store_true", help="do not descend into subfolders")
    sp.add_argument("--limit", type=int, help="cap the number of PDFs processed")
    sp.add_argument("--keep-unresolved", action="store_true",
                    help="also add papers for PDFs with no findable DOI (filename title + full text)")
    sp.add_argument("--embed", action="store_true", help="embed the newly added papers afterward")
    sp.add_argument("--project", action="append", metavar="NAME",
                    help="project/topic tag for ingested papers (repeatable). The agent "
                         "asks the user for this before ingesting; no folder-name default.")
    sp.set_defaults(func=cmd_scan_pdfs)

    cf = add("cite-fetch", help="fetch citation edges (references + citing works) from OpenAlex")
    cf.add_argument("--paper", type=int, help="paper id")
    cf.add_argument("--all", action="store_true", help="build the graph for the whole corpus")
    cf.add_argument("--cited-by", type=int, default=50, dest="cited_by",
                    help="max citing works to sample per paper")
    cf.set_defaults(func=cmd_cite_fetch)

    rf = add("refs", help="list a paper's references (annotated with what you hold)")
    rf.add_argument("--paper", type=int, required=True)
    rf.add_argument("-k", type=int, default=50)
    rf.set_defaults(func=cmd_refs)

    cb = add("cited-by", help="list works citing a paper (annotated with what you hold)")
    cb.add_argument("--paper", type=int, required=True)
    cb.add_argument("-k", type=int, default=50)
    cb.set_defaults(func=cmd_cited_by)

    mc = add("most-cited", help="papers most cited by others in your library")
    mc.add_argument("-k", type=int, default=20)
    mc.set_defaults(func=cmd_most_cited)

    mr = add("missing-refs", help="papers your library references most but you don't own (import ideas)")
    mr.add_argument("-k", type=int, default=20)
    mr.set_defaults(func=cmd_missing_refs)

    ip = add("ingest-pdf", help="extract a paper's PDF full text into searchable chunks")
    ip.add_argument("--paper", type=int, help="paper id to attach the text to")
    ip.add_argument("--file", help="path to the PDF")
    ip.add_argument("--auto", action="store_true",
                    help="locate the PDF via Better BibTeX using the paper's citekey")
    ip.add_argument("--all", action="store_true",
                    help="bulk: ingest PDFs for all papers with a citekey and no full text (implies --auto)")
    ip.set_defaults(func=cmd_ingest_pdf)

    pp = add("paper", help="show a paper and its linked notes")
    pp.add_argument("id", type=int)
    pp.set_defaults(func=cmd_paper)

    up = add("update", help="patch a paper's metadata in place (doi, citekey, title, authors, year, ...)")
    up.add_argument("id", type=int)
    up.add_argument("--doi")
    up.add_argument("--zotero-key", dest="zotero_key")
    up.add_argument("--openalex-id", dest="openalex_id")
    up.add_argument("--s2-id", dest="s2_id")
    up.add_argument("--citation-key", dest="citation_key")
    up.add_argument("--title")
    up.add_argument("--authors")
    up.add_argument("--year", type=int)
    up.add_argument("--venue")
    up.add_argument("--abstract")
    up.add_argument("--extra")
    up.set_defaults(func=cmd_update)

    mg = add("merge", help="absorb one paper into another (move full text + links, then delete the dupe)")
    mg.add_argument("--keep", type=int, required=True, help="paper id to keep")
    mg.add_argument("--dupe", type=int, required=True, help="paper id to absorb and delete")
    mg.set_defaults(func=cmd_merge)

    dl = add("delete", help="delete a paper, its chunks/embeddings, and its links")
    dl.add_argument("id", type=int)
    dl.set_defaults(func=cmd_delete)

    add("status", help="show corpus statistics").set_defaults(func=cmd_status)

    pj = add("projects", help="list, rename, or edit project tags")
    pjsub = pj.add_subparsers(dest="action", required=True)
    pjsub.add_parser("list", parents=[common], help="list projects with paper/note counts"
                     ).set_defaults(func=cmd_projects)
    pjr = pjsub.add_parser("rename", parents=[common], help="rename a project (folds into an existing target)")
    pjr.add_argument("old")
    pjr.add_argument("new")
    pjr.set_defaults(func=cmd_projects)
    for _act, _help in (("tag", "add papers/notes to a project"),
                        ("untag", "remove papers/notes from a project")):
        pja = pjsub.add_parser(_act, parents=[common], help=_help)
        pja.add_argument("name")
        pja.add_argument("--paper", type=int, action="append", metavar="ID")
        pja.add_argument("--note", type=int, action="append", metavar="ID")
        pja.set_defaults(func=cmd_projects)

    pz = add("push-zotero", help="add litdb papers to a running Zotero via the connector API")
    pz.add_argument("--ids", type=int, nargs="*", help="only these paper ids")
    pz.add_argument("--status", choices=list(db.READING_STATUSES),
                    help="only papers with this reading status")
    pz.add_argument("--force", action="store_true",
                    help="include papers already pushed (may create duplicates)")
    pz.add_argument("--dry-run", action="store_true",
                    help="show what would be pushed without contacting Zotero")
    pz.set_defaults(func=cmd_push_zotero)

    add("sync-zotero",
        help="pull new papers from Zotero into litdb (import + ingest PDFs + embed; incremental)"
        ).set_defaults(func=cmd_sync_zotero)

    add("sync-inbox",
        help="ingest new PDFs from the configured inbox folder (idempotent by content hash)"
        ).set_defaults(func=cmd_sync_inbox)

    mz = add("migrate-to-zotero",
             help="push the whole litdb corpus into Zotero and switch source_of_truth to zotero")
    mz.add_argument("--force", action="store_true", help="include papers already pushed")
    mz.add_argument("--dry-run", action="store_true",
                    help="show what would happen without contacting Zotero or changing prefs")
    mz.set_defaults(func=cmd_migrate_to_zotero)

    xb = add("export-bib", help="export BibTeX for the corpus (or a subset) from stored citation keys")
    xb.add_argument("--out", help="write to this file (default: stdout)")
    xb.add_argument("--status", choices=list(db.READING_STATUSES),
                    help="only papers with this reading status")
    xb.add_argument("--ids", type=int, nargs="*", help="only these paper ids")
    xb.set_defaults(func=cmd_export_bib)

    sk = add("s2-key", help="store/check the Semantic Scholar API key (enables --source s2/both)")
    sk.add_argument("action", nargs="?", choices=["status", "set", "clear"], default="status",
                    help="status (default), set (store a key), or clear")
    sk.add_argument("key", nargs="?", help="the API key for 'set' (or '-' to read stdin)")
    sk.set_defaults(func=cmd_s2key)

    pr = add("prefs", help="get/set user preferences: 'prefs' lists all, "
                           "'prefs set KEY VALUE', 'prefs get KEY'")
    pr.add_argument("a", nargs="?", help="'set'/'get'/'list', or a key (shorthand)")
    pr.add_argument("b", nargs="?", help="key (after set/get) or value (shorthand)")
    pr.add_argument("c", nargs="?", help="value (after 'set KEY')")
    pr.set_defaults(func=cmd_prefs)

    ob = add("onboarded", help="check, mark, or reset first-run onboarding")
    ob.add_argument("--mark", action="store_true", help="record that onboarding is complete")
    ob.add_argument("--reset", action="store_true", help="clear the marker so onboarding runs again")
    ob.set_defaults(func=cmd_onboarded)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # normalize import-zotero: --local sets file=None so the API path is taken
    if getattr(args, "use_local", False):
        args.file = None
    try:
        return args.func(args)
    except db.FTS5Unavailable as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    except (ConnectionError, FileNotFoundError, ValueError, RuntimeError) as exc:
        # Includes external API failures (HTTP errors, rate limits, timeouts) so
        # the CLI always emits a clean error rather than a traceback.
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
