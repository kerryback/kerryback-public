"""SQLite schema and core data operations.

Design notes:
- ``chunk`` is the unit of retrieval. In Phase 1 a paper is one chunk
  (title + abstract) and a note is one chunk (title + body); Phase 4 splits
  PDFs into finer chunks. Keeping chunks now means Phase 2 only has to attach
  vectors to existing rows.
- FTS5 (external-content) over ``chunk.text`` provides BM25 keyword search with
  no third-party dependency. Triggers keep the index in sync.
- ``meta`` records schema version and the active embedding model (used later).
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Iterable

from . import config

SCHEMA_VERSION = 6

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS paper (
    id             INTEGER PRIMARY KEY,
    doi            TEXT UNIQUE,
    zotero_key     TEXT UNIQUE,
    openalex_id    TEXT,
    s2_id          TEXT,
    citation_key   TEXT,   -- Better BibTeX citekey, e.g. jegadeesh1993returns
    title          TEXT NOT NULL,
    authors        TEXT,
    year           INTEGER,
    venue          TEXT,
    abstract       TEXT,
    extra          TEXT,
    -- reading / screening workflow (triage from abstracts)
    reading_status TEXT NOT NULL DEFAULT 'unseen',  -- unseen|screened|to_read|reading|read|rejected
    priority       INTEGER,
    screening_note TEXT,
    screened_at    TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- structured keywords/tags with provenance. Lightly populated in Phase 1
-- (author keywords + Zotero tags); filled out by OpenAlex/S2 concepts later.
CREATE TABLE IF NOT EXISTS keyword (
    id         INTEGER PRIMARY KEY,
    term       TEXT NOT NULL,        -- first-seen display form
    normalized TEXT NOT NULL UNIQUE  -- lowercased match key
);

CREATE TABLE IF NOT EXISTS paper_keyword (
    paper_id   INTEGER NOT NULL REFERENCES paper(id)   ON DELETE CASCADE,
    keyword_id INTEGER NOT NULL REFERENCES keyword(id) ON DELETE CASCADE,
    source     TEXT NOT NULL DEFAULT 'author',  -- author|zotero|openalex|s2|llm|user
    PRIMARY KEY (paper_id, keyword_id, source)
);
CREATE INDEX IF NOT EXISTS idx_paper_keyword_kw ON paper_keyword(keyword_id);

CREATE TABLE IF NOT EXISTS note (
    id           INTEGER PRIMARY KEY,
    title        TEXT,
    body         TEXT NOT NULL,
    source       TEXT,
    kind         TEXT,               -- idea|summary|critique|question|todo|quote, or NULL
    confidential INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS note_paper (
    note_id  INTEGER NOT NULL REFERENCES note(id)  ON DELETE CASCADE,
    paper_id INTEGER NOT NULL REFERENCES paper(id) ON DELETE CASCADE,
    relation TEXT,
    page     INTEGER,   -- page the note refers to (optional)
    quote    TEXT,      -- verbatim passage the note is about (optional)
    PRIMARY KEY (note_id, paper_id)
);

CREATE TABLE IF NOT EXISTS chunk (
    id          INTEGER PRIMARY KEY,
    owner_type  TEXT NOT NULL CHECK (owner_type IN ('paper','note')),
    owner_id    INTEGER NOT NULL,
    ordinal     INTEGER NOT NULL DEFAULT 0,
    kind        TEXT NOT NULL DEFAULT 'abstract',  -- abstract|fulltext
    page        INTEGER,
    section     TEXT,
    text        TEXT NOT NULL,
    token_count INTEGER,
    content_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_chunk_owner ON chunk(owner_type, owner_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
    text,
    content='chunk',
    content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS chunk_ai AFTER INSERT ON chunk BEGIN
    INSERT INTO chunk_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunk_ad AFTER DELETE ON chunk BEGIN
    INSERT INTO chunk_fts(chunk_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS chunk_au AFTER UPDATE ON chunk BEGIN
    INSERT INTO chunk_fts(chunk_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO chunk_fts(rowid, text) VALUES (new.id, new.text);
END;

-- Vectors are stored as float32 BLOBs and namespaced by model_id, so multiple
-- embedding models (e.g. a hosted default + a local model for confidential
-- notes) coexist without mixing incomparable vector spaces. Portable by design:
-- no native extension required (see vectorstore.py).
CREATE TABLE IF NOT EXISTS embedding (
    chunk_id     INTEGER NOT NULL REFERENCES chunk(id) ON DELETE CASCADE,
    model_id     TEXT NOT NULL,
    dim          INTEGER NOT NULL,
    content_hash TEXT,
    vec          BLOB NOT NULL,
    PRIMARY KEY (chunk_id, model_id)
);
CREATE INDEX IF NOT EXISTS idx_embedding_model ON embedding(model_id);

-- Citation edges, stored by OpenAlex work id so the graph exists even for works
-- not (yet) in the corpus. Join to paper.openalex_id to relate edges to owned
-- papers; unmatched cited ids are import candidates.
CREATE TABLE IF NOT EXISTS citation (
    citing_ext TEXT NOT NULL,
    cited_ext  TEXT NOT NULL,
    source     TEXT NOT NULL DEFAULT 'openalex',
    PRIMARY KEY (citing_ext, cited_ext)
);
CREATE INDEX IF NOT EXISTS idx_citation_cited ON citation(cited_ext);

-- Ledger of PDF files already ingested, keyed by content hash, so an inbox can be
-- rescanned idempotently: a file whose bytes were seen before is skipped (even if
-- renamed or moved), preventing duplicate records for DOI-less papers.
CREATE TABLE IF NOT EXISTS ingested_file (
    sha256      TEXT PRIMARY KEY,
    path        TEXT,
    paper_id    INTEGER,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Named projects/collections. A paper or note may belong to many; the same work
-- legitimately spans several projects, so membership is many-to-many. `owner` is
-- polymorphic (mirroring `chunk`) — no FK, so it is cleaned up explicitly on
-- paper delete/merge (notes have no delete path yet).
CREATE TABLE IF NOT EXISTS project (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,          -- display form (first seen), renameable
    slug       TEXT NOT NULL UNIQUE,   -- lowercased/whitespace-collapsed match key
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS project_member (
    project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    owner_type TEXT NOT NULL CHECK (owner_type IN ('paper','note')),
    owner_id   INTEGER NOT NULL,
    source     TEXT NOT NULL DEFAULT 'user',  -- folder|cwd|user
    added_at   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (project_id, owner_type, owner_id)
);
CREATE INDEX IF NOT EXISTS idx_project_member_owner
    ON project_member(owner_type, owner_id);
"""


class FTS5Unavailable(RuntimeError):
    pass


def connect(path: Path | None = None, *, create_parent: bool = True) -> sqlite3.Connection:
    p = Path(path) if path else config.db_path()
    if create_parent:
        p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fts5_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE temp._fts_probe USING fts5(x)")
        conn.execute("DROP TABLE temp._fts_probe")
        return True
    except sqlite3.OperationalError:
        return False


def init_db(conn: sqlite3.Connection) -> None:
    if not fts5_available(conn):
        raise FTS5Unavailable(
            "This Python's sqlite3 was built without FTS5. Install a Python with "
            "FTS5 support (most do), or use pysqlite3-binary."
        )
    conn.executescript(_SCHEMA)
    _migrate(conn)
    conn.execute(
        "INSERT INTO meta(key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive column migrations for databases created by older schema versions.
    CREATE TABLE IF NOT EXISTS does not alter existing tables, so add columns."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(paper)").fetchall()}
    if "citation_key" not in cols:
        conn.execute("ALTER TABLE paper ADD COLUMN citation_key TEXT")
    if "zotero_pushed_at" not in cols:
        conn.execute("ALTER TABLE paper ADD COLUMN zotero_pushed_at TEXT")
    ccols = {r["name"] for r in conn.execute("PRAGMA table_info(chunk)").fetchall()}
    for col, ddl in (("kind", "kind TEXT NOT NULL DEFAULT 'abstract'"),
                     ("page", "page INTEGER"), ("section", "section TEXT")):
        if col not in ccols:
            conn.execute(f"ALTER TABLE chunk ADD COLUMN {ddl}")
    ncols = {r["name"] for r in conn.execute("PRAGMA table_info(note)").fetchall()}
    if "kind" not in ncols:
        conn.execute("ALTER TABLE note ADD COLUMN kind TEXT")
    npcols = {r["name"] for r in conn.execute("PRAGMA table_info(note_paper)").fetchall()}
    for col, ddl in (("page", "page INTEGER"), ("quote", "quote TEXT")):
        if col not in npcols:
            conn.execute(f"ALTER TABLE note_paper ADD COLUMN {ddl}")


# --------------------------------------------------------------------------- #
# chunking (Phase 1: one chunk per owner)
# --------------------------------------------------------------------------- #

def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reindex_owner(conn: sqlite3.Connection, owner_type: str, owner_id: int, text: str) -> None:
    """Set the owner's single abstract-level chunk (title+abstract, or note body).

    Only touches the kind='abstract' chunk, so full-text chunks added later are
    left intact. Updates in place when possible so the chunk id (and any cached
    embedding) survives a re-import; the embedding is recomputed only when the
    content hash changes.
    """
    text = (text or "").strip()
    existing = conn.execute(
        "SELECT id FROM chunk WHERE owner_type=? AND owner_id=? AND kind='abstract' ORDER BY id",
        (owner_type, owner_id),
    ).fetchall()
    if not text:
        conn.execute(
            "DELETE FROM chunk WHERE owner_type=? AND owner_id=? AND kind='abstract'",
            (owner_type, owner_id),
        )
        return
    h = _hash(text)
    if len(existing) == 1:
        conn.execute(
            "UPDATE chunk SET text=?, token_count=?, content_hash=?, ordinal=0 WHERE id=?",
            (text, len(text.split()), h, existing[0]["id"]),
        )
        return
    conn.execute(
        "DELETE FROM chunk WHERE owner_type=? AND owner_id=? AND kind='abstract'",
        (owner_type, owner_id),
    )
    conn.execute(
        "INSERT INTO chunk(owner_type, owner_id, ordinal, kind, text, token_count, content_hash) "
        "VALUES (?,?,?, 'abstract', ?,?,?)",
        (owner_type, owner_id, 0, text, len(text.split()), h),
    )


def set_fulltext_chunks(conn: sqlite3.Connection, paper_id: int, chunks: list[dict]) -> int:
    """Replace a paper's full-text chunks. Each chunk dict: {text, page?, section?}.

    Returns the number of chunks stored. FK cascade removes embeddings for any
    dropped chunks; new chunks get embedded on the next `embed` run.
    """
    conn.execute("DELETE FROM chunk WHERE owner_type='paper' AND owner_id=? AND kind='fulltext'",
                 (paper_id,))
    n = 0
    for i, ch in enumerate(chunks, start=1):
        text = (ch.get("text") or "").strip()
        if not text:
            continue
        conn.execute(
            "INSERT INTO chunk(owner_type, owner_id, ordinal, kind, page, section, "
            "text, token_count, content_hash) VALUES ('paper', ?, ?, 'fulltext', ?, ?, ?, ?, ?)",
            (paper_id, i, ch.get("page"), ch.get("section"), text,
             len(text.split()), _hash(text)),
        )
        n += 1
    conn.commit()
    return n


def has_fulltext(conn: sqlite3.Connection, paper_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM chunk WHERE owner_type='paper' AND owner_id=? AND kind='fulltext' LIMIT 1",
        (paper_id,),
    ).fetchone() is not None


def ingested_hashes(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT sha256 FROM ingested_file").fetchall()}


def record_ingested(conn: sqlite3.Connection, rows: list[tuple[str, str, int]]) -> None:
    """rows: (sha256, path, paper_id). Idempotent on the hash."""
    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO ingested_file(sha256, path, paper_id) VALUES (?,?,?)", rows
        )
        conn.commit()


# The location shown for a paper whose PDF was never ingested (metadata-only
# record, e.g. from import-doi). Kept as a plain string so callers never have to
# special-case a null and the user sees an answer instead of an empty field.
NOT_DOWNLOADED = "not downloaded"


def locations_for(conn: sqlite3.Connection, paper_ids: list[int]) -> dict[int, str]:
    """Map paper_id -> on-disk PDF path for the given papers (one per paper).

    Papers with no ingested file are absent from the map; callers substitute
    NOT_DOWNLOADED. Reads the ingested_file ledger directly — no filesystem hit —
    so surfacing a paper's location is a single cheap query, not a disk crawl.
    """
    if not paper_ids:
        return {}
    q = ",".join("?" * len(paper_ids))
    out: dict[int, str] = {}
    for pid, path in conn.execute(
        f"SELECT paper_id, path FROM ingested_file WHERE paper_id IN ({q}) "
        "ORDER BY ingested_at",
        list(paper_ids),
    ).fetchall():
        out[pid] = path  # last one wins if a paper has several files
    return out


def paper_location(conn: sqlite3.Connection, paper_id: int) -> str:
    """On-disk PDF path for a paper, or NOT_DOWNLOADED if it was never ingested."""
    return locations_for(conn, [paper_id]).get(paper_id, NOT_DOWNLOADED)


def add_citations(conn: sqlite3.Connection, edges: list[tuple[str, str]], source: str = "openalex") -> int:
    """Insert (citing_ext, cited_ext) OpenAlex-id edges, ignoring duplicates."""
    clean = [(a, b, source) for a, b in edges if a and b and a != b]
    if clean:
        conn.executemany(
            "INSERT OR IGNORE INTO citation(citing_ext, cited_ext, source) VALUES (?,?,?)", clean
        )
        conn.commit()
    return len(clean)


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def get_meta(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


READING_STATUSES = ("unseen", "screened", "to_read", "reading", "read", "rejected")
NOTE_KINDS = ("idea", "summary", "critique", "question", "todo", "quote")


def _paper_text(title: str, abstract: str | None, keywords: list[str] | None = None) -> str:
    # Keywords are appended to the indexed text so a term that appears in both
    # the keywords and the abstract scores higher in BM25 (an implicit boost)
    # without special-casing the generic chunk model.
    kw = " ".join(keywords or [])
    return "\n".join(x for x in (title, abstract or "", kw) if x).strip()


def _note_text(title: str | None, body: str) -> str:
    return "\n".join(x for x in (title or "", body) if x).strip()


# --------------------------------------------------------------------------- #
# papers
# --------------------------------------------------------------------------- #

def add_keywords(
    conn: sqlite3.Connection, paper_id: int, terms, source: str = "author"
) -> None:
    for raw in terms or []:
        term = str(raw).strip()
        if not term:
            continue
        normalized = term.lower()
        conn.execute(
            "INSERT INTO keyword(term, normalized) VALUES (?,?) "
            "ON CONFLICT(normalized) DO NOTHING",
            (term, normalized),
        )
        kid = conn.execute(
            "SELECT id FROM keyword WHERE normalized=?", (normalized,)
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO paper_keyword(paper_id, keyword_id, source) VALUES (?,?,?) "
            "ON CONFLICT(paper_id, keyword_id, source) DO NOTHING",
            (paper_id, kid, source),
        )


def paper_keyword_terms(conn: sqlite3.Connection, paper_id: int) -> list[str]:
    return [
        r["term"]
        for r in conn.execute(
            "SELECT k.term FROM paper_keyword pk JOIN keyword k ON k.id = pk.keyword_id "
            "WHERE pk.paper_id=? ORDER BY k.term",
            (paper_id,),
        ).fetchall()
    ]


def upsert_paper(conn: sqlite3.Connection, rec: dict) -> tuple[int, bool]:
    """Insert or update a paper, matching on DOI then zotero_key.

    Returns (paper_id, created).
    """
    doi = (rec.get("doi") or "").strip().lower() or None
    zkey = (rec.get("zotero_key") or "").strip() or None
    oaid = (rec.get("openalex_id") or "").strip() or None
    s2id = (rec.get("s2_id") or "").strip() or None
    ckey = (rec.get("citation_key") or "").strip() or None

    # Identity resolution: match on any stable id, in priority order, so the same
    # work arriving from Zotero, OpenAlex, and S2 collapses to one row.
    row = None
    for col, val in (("doi", doi), ("zotero_key", zkey), ("openalex_id", oaid),
                     ("s2_id", s2id), ("citation_key", ckey)):
        if val is not None:
            row = conn.execute(f"SELECT id FROM paper WHERE {col}=?", (val,)).fetchone()
            if row is not None:
                break

    fields = dict(
        doi=doi,
        zotero_key=zkey,
        openalex_id=oaid,
        s2_id=s2id,
        citation_key=ckey,
        title=(rec.get("title") or "Untitled").strip(),
        authors=rec.get("authors"),
        year=rec.get("year"),
        venue=rec.get("venue"),
        abstract=rec.get("abstract"),
        extra=rec.get("extra"),
    )

    if row is None:
        cols = ", ".join(fields)
        ph = ", ".join(["?"] * len(fields))
        cur = conn.execute(f"INSERT INTO paper({cols}) VALUES ({ph})", tuple(fields.values()))
        pid = int(cur.lastrowid)
        created = True
    else:
        pid = int(row["id"])
        # Merge: only overwrite with non-empty incoming values, so importing the
        # same paper from a second source enriches rather than erases (e.g. an
        # OpenAlex import keeps the existing zotero_key).
        updates = {k: v for k, v in fields.items() if v not in (None, "")}
        if updates:
            sets = ", ".join(f"{k}=?" for k in updates)
            conn.execute(
                f"UPDATE paper SET {sets}, updated_at=datetime('now') WHERE id=?",
                (*updates.values(), pid),
            )
        created = False

    if rec.get("keywords"):
        add_keywords(conn, pid, rec["keywords"], rec.get("keyword_source", "author"))

    terms = paper_keyword_terms(conn, pid)
    reindex_owner(conn, "paper", pid, _paper_text(fields["title"], fields["abstract"], terms))
    return pid, created


# Metadata columns a user may patch via `update`. Reading/screening state has its
# own command (`screen`); identity ids and descriptive fields live here.
UPDATABLE_FIELDS = (
    "doi", "zotero_key", "openalex_id", "s2_id", "citation_key",
    "title", "authors", "year", "venue", "abstract", "extra",
)
_UNIQUE_FIELDS = ("doi", "zotero_key")


def _normalize_field(col: str, value):
    """Coerce an incoming metadata value the same way upsert_paper does."""
    if value is None:
        return None
    if col == "year":
        if value in ("", None):
            return None
        return int(value)
    s = str(value).strip()
    if col == "doi":
        return s.lower() or None
    if col in ("zotero_key", "openalex_id", "s2_id", "citation_key", "authors",
               "venue", "abstract", "extra"):
        return s or None
    return s  # title


def update_paper(conn: sqlite3.Connection, paper_id: int, fields: dict) -> dict | None:
    """Patch a paper's metadata in place and re-index its abstract chunk.

    Only keys in ``fields`` (intersected with UPDATABLE_FIELDS) are touched, so a
    caller can set just the DOI without disturbing the rest. Full-text chunks and
    embeddings are left alone; the abstract chunk is rebuilt from the new
    title/abstract/keywords (its cached embedding is invalidated by the content
    hash and recomputed on the next `embed`). ``title`` may not be blanked.
    Returns the updated paper (as get_paper), or None if the id doesn't exist.
    Raises ValueError if a unique id (doi/zotero_key) collides with another paper.
    """
    if conn.execute("SELECT 1 FROM paper WHERE id=?", (paper_id,)).fetchone() is None:
        return None
    updates = {}
    for col in UPDATABLE_FIELDS:
        if col not in fields:
            continue
        val = _normalize_field(col, fields[col])
        if col == "title" and not val:
            raise ValueError("title cannot be empty")
        updates[col] = val

    for col in _UNIQUE_FIELDS:
        if updates.get(col):
            clash = conn.execute(
                f"SELECT id FROM paper WHERE {col}=? AND id<>?", (updates[col], paper_id)
            ).fetchone()
            if clash is not None:
                raise ValueError(
                    f"{col}={updates[col]!r} already belongs to paper {clash['id']}; "
                    f"use `merge` to combine them"
                )

    if updates:
        sets = ", ".join(f"{k}=?" for k in updates)
        conn.execute(
            f"UPDATE paper SET {sets}, updated_at=datetime('now') WHERE id=?",
            (*updates.values(), paper_id),
        )
    row = conn.execute("SELECT title, abstract FROM paper WHERE id=?", (paper_id,)).fetchone()
    terms = paper_keyword_terms(conn, paper_id)
    reindex_owner(conn, "paper", paper_id, _paper_text(row["title"], row["abstract"], terms))
    conn.commit()
    return get_paper(conn, paper_id)


def merge_papers(conn: sqlite3.Connection, keep_id: int, dupe_id: int) -> dict | None:
    """Absorb ``dupe_id`` into ``keep_id`` and delete the duplicate.

    Full-text chunks move to ``keep`` only if it has none of its own (embeddings
    follow, since chunk ids are unchanged); note links and keywords are repointed;
    ``keep``'s empty metadata fields are filled from the dupe (non-destructive, so
    a metadata-rich stub enriches a full-text record and vice versa). Citation
    edges need no move — they are keyed by external work id, not paper id.
    Returns a summary dict, or None if either id is missing. keep_id != dupe_id.
    """
    if keep_id == dupe_id:
        raise ValueError("keep and dupe must be different papers")
    dupe = conn.execute("SELECT * FROM paper WHERE id=?", (dupe_id,)).fetchone()
    keep = conn.execute("SELECT * FROM paper WHERE id=?", (keep_id,)).fetchone()
    if dupe is None or keep is None:
        return None

    moved_fulltext = 0
    if not has_fulltext(conn, keep_id):
        cur = conn.execute(
            "UPDATE chunk SET owner_id=? WHERE owner_type='paper' AND owner_id=? AND kind='fulltext'",
            (keep_id, dupe_id),
        )
        moved_fulltext = cur.rowcount

    conn.execute(
        "INSERT OR IGNORE INTO note_paper(note_id, paper_id, relation) "
        "SELECT note_id, ?, relation FROM note_paper WHERE paper_id=?",
        (keep_id, dupe_id),
    )
    conn.execute(
        "INSERT OR IGNORE INTO paper_keyword(paper_id, keyword_id, source) "
        "SELECT ?, keyword_id, source FROM paper_keyword WHERE paper_id=?",
        (keep_id, dupe_id),
    )
    conn.execute(
        "INSERT OR IGNORE INTO project_member(project_id, owner_type, owner_id, source) "
        "SELECT project_id, 'paper', ?, source FROM project_member "
        "WHERE owner_type='paper' AND owner_id=?",
        (keep_id, dupe_id),
    )
    conn.execute(
        "DELETE FROM project_member WHERE owner_type='paper' AND owner_id=?", (dupe_id,)
    )

    # Delete the dupe (its remaining chunks first, so their embeddings cascade;
    # this also frees any unique doi/zotero_key before we copy it onto keep).
    conn.execute("DELETE FROM chunk WHERE owner_type='paper' AND owner_id=?", (dupe_id,))
    conn.execute("DELETE FROM paper WHERE id=?", (dupe_id,))

    # Enrich keep from dupe for any field keep is missing.
    enriched = {}
    for col in UPDATABLE_FIELDS:
        if (keep[col] in (None, "")) and (dupe[col] not in (None, "")):
            enriched[col] = dupe[col]
    if enriched:
        sets = ", ".join(f"{k}=?" for k in enriched)
        conn.execute(
            f"UPDATE paper SET {sets}, updated_at=datetime('now') WHERE id=?",
            (*enriched.values(), keep_id),
        )

    row = conn.execute("SELECT title, abstract FROM paper WHERE id=?", (keep_id,)).fetchone()
    terms = paper_keyword_terms(conn, keep_id)
    reindex_owner(conn, "paper", keep_id, _paper_text(row["title"], row["abstract"], terms))
    conn.commit()
    return {
        "kept": keep_id,
        "deleted": dupe_id,
        "moved_fulltext_chunks": moved_fulltext,
        "enriched_fields": sorted(enriched),
    }


def delete_paper(conn: sqlite3.Connection, paper_id: int) -> bool:
    """Delete a paper, its chunks (embeddings cascade), and its links.

    chunk.owner_id is polymorphic (no FK), so chunks are removed explicitly;
    paper_keyword and note_paper cascade via their FKs. Citation edges, keyed by
    external work id, are left in place. Returns False if the id doesn't exist.
    """
    if conn.execute("SELECT 1 FROM paper WHERE id=?", (paper_id,)).fetchone() is None:
        return False
    conn.execute("DELETE FROM chunk WHERE owner_type='paper' AND owner_id=?", (paper_id,))
    conn.execute("DELETE FROM project_member WHERE owner_type='paper' AND owner_id=?", (paper_id,))
    conn.execute("DELETE FROM paper WHERE id=?", (paper_id,))
    conn.commit()
    return True


def screen_paper(
    conn: sqlite3.Connection,
    paper_id: int,
    *,
    status: str | None = None,
    note: str | None = None,
    priority: int | None = None,
) -> bool:
    if status is not None and status not in READING_STATUSES:
        raise ValueError(f"status must be one of {READING_STATUSES}")
    if conn.execute("SELECT 1 FROM paper WHERE id=?", (paper_id,)).fetchone() is None:
        return False
    sets, params = [], []
    if status is not None:
        sets += ["reading_status=?", "screened_at=datetime('now')"]
        params.append(status)
    if note is not None:
        sets.append("screening_note=?")
        params.append(note)
    if priority is not None:
        sets.append("priority=?")
        params.append(priority)
    if not sets:
        return True
    params.append(paper_id)
    conn.execute(f"UPDATE paper SET {', '.join(sets)} WHERE id=?", params)
    conn.commit()
    return True


def list_papers(
    conn: sqlite3.Connection,
    *,
    reading_status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    sql = "SELECT id, title, authors, year, venue, reading_status, priority FROM paper"
    params: list = []
    if reading_status:
        sql += " WHERE reading_status=?"
        params.append(reading_status)
    sql += " ORDER BY (priority IS NULL), priority, year DESC LIMIT ?"
    params.append(limit)
    rows = [{"type": "paper", **dict(r)} for r in conn.execute(sql, params).fetchall()]
    locs = locations_for(conn, [r["id"] for r in rows])
    for r in rows:
        r["location"] = locs.get(r["id"], NOT_DOWNLOADED)
    return rows


def papers_for_export(conn: sqlite3.Connection, *, ids=None,
                      reading_status: str | None = None) -> list[dict]:
    """Rows needed to emit BibTeX: id, citation_key, doi, title, authors, year, venue."""
    sql = "SELECT id, citation_key, doi, title, authors, year, venue FROM paper"
    clauses, params = [], []
    if ids:
        clauses.append(f"id IN ({','.join(['?'] * len(ids))})")
        params += list(ids)
    if reading_status:
        clauses.append("reading_status=?")
        params.append(reading_status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY (authors IS NULL), authors, year"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def papers_for_push(conn: sqlite3.Connection, *, ids=None,
                    reading_status: str | None = None,
                    include_pushed: bool = False) -> list[dict]:
    """Papers to send to Zotero. By default skips those already pushed
    (`zotero_pushed_at` set) so re-runs don't create duplicates."""
    sql = ("SELECT id, citation_key, doi, title, authors, year, venue, zotero_pushed_at "
           "FROM paper")
    clauses, params = [], []
    if ids:
        clauses.append(f"id IN ({','.join(['?'] * len(ids))})")
        params += list(ids)
    if reading_status:
        clauses.append("reading_status=?")
        params.append(reading_status)
    if not include_pushed:
        clauses.append("zotero_pushed_at IS NULL")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY (authors IS NULL), authors, year"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def mark_zotero_pushed(conn: sqlite3.Connection, ids: Iterable[int]) -> None:
    conn.executemany("UPDATE paper SET zotero_pushed_at=datetime('now') WHERE id=?",
                     [(int(i),) for i in ids])
    conn.commit()


def import_papers(conn: sqlite3.Connection, records: Iterable[dict]) -> dict:
    created = updated = 0
    for rec in records:
        _, was_created = upsert_paper(conn, rec)
        created += int(was_created)
        updated += int(not was_created)
    conn.commit()
    return {"created": created, "updated": updated}


def find_paper_by_ids(conn: sqlite3.Connection, *, doi=None, openalex_id=None,
                      s2_id=None, zotero_key=None, citation_key=None) -> int | None:
    for col, val in (("doi", doi), ("openalex_id", openalex_id), ("s2_id", s2_id),
                     ("zotero_key", zotero_key), ("citation_key", citation_key)):
        if val:
            v = val.lower() if col == "doi" else val
            r = conn.execute(f"SELECT id FROM paper WHERE {col}=?", (v,)).fetchone()
            if r:
                return int(r["id"])
    return None


def get_paper(conn: sqlite3.Connection, paper_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM paper WHERE id=?", (paper_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["location"] = paper_location(conn, paper_id)
    d["keywords"] = paper_keyword_terms(conn, paper_id)
    d["notes"] = [
        dict(r)
        for r in conn.execute(
            "SELECT n.id, n.title, np.relation FROM note_paper np "
            "JOIN note n ON n.id = np.note_id WHERE np.paper_id=?",
            (paper_id,),
        ).fetchall()
    ]
    return d


# --------------------------------------------------------------------------- #
# notes
# --------------------------------------------------------------------------- #

def add_note(
    conn: sqlite3.Connection,
    body: str,
    *,
    title: str | None = None,
    source: str | None = None,
    confidential: bool = False,
    kind: str | None = None,
    link_paper_ids: Iterable[int] = (),
    relation: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO note(title, body, source, kind, confidential) VALUES (?,?,?,?,?)",
        (title, body, source, kind, int(confidential)),
    )
    nid = int(cur.lastrowid)
    reindex_owner(conn, "note", nid, _note_text(title, body))
    for pid in link_paper_ids:
        link_note_paper(conn, nid, int(pid), relation)
    conn.commit()
    return nid


def link_note_paper(
    conn: sqlite3.Connection, note_id: int, paper_id: int, relation: str | None = None,
    *, page: int | None = None, quote: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO note_paper(note_id, paper_id, relation, page, quote) VALUES (?,?,?,?,?) "
        "ON CONFLICT(note_id, paper_id) DO UPDATE SET relation=excluded.relation, "
        "page=excluded.page, quote=excluded.quote",
        (note_id, paper_id, relation, page, quote),
    )
    conn.commit()


def get_note(conn: sqlite3.Connection, note_id: int) -> dict | None:
    """One note with its full body, kind, linked papers (relation/page/quote), and
    project tags. Notes are read whole — the retrieval unit is the entire note."""
    row = conn.execute(
        "SELECT id, title, body, kind, confidential, created_at, updated_at "
        "FROM note WHERE id=?",
        (note_id,),
    ).fetchone()
    if row is None:
        return None
    d = {"type": "note", **dict(row)}
    d["confidential"] = bool(d["confidential"])
    d["papers"] = [
        dict(x)
        for x in conn.execute(
            "SELECT np.paper_id, p.title, p.citation_key, np.relation, np.page, np.quote "
            "FROM note_paper np JOIN paper p ON p.id = np.paper_id "
            "WHERE np.note_id=? ORDER BY np.paper_id",
            (note_id,),
        ).fetchall()
    ]
    d["projects"] = project_names(conn, "note", note_id)
    return d


def list_notes(
    conn: sqlite3.Connection,
    *,
    paper_id: int | None = None,
    kind: str | None = None,
    project: str | None = None,
    since: str | None = None,
    confidential: bool | None = None,
    limit: int = 50,
) -> list[dict]:
    """Notes matching the filters, newest first, each as a full `get_note` dict.
    Filters compose with AND. `project` is applied via `project_members` so this
    doesn't depend on the project-tag table's column names."""
    joins, where, params = [], [], []
    if paper_id is not None:
        joins.append("JOIN note_paper np ON np.note_id = n.id")
        where.append("np.paper_id=?")
        params.append(int(paper_id))
    if kind:
        where.append("n.kind=?")
        params.append(kind)
    if since:
        where.append("n.created_at >= ?")
        params.append(since)
    if confidential is not None:
        where.append("n.confidential=?")
        params.append(int(confidential))
    sql = "SELECT DISTINCT n.id, n.created_at FROM note n " + " ".join(joins)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY n.created_at DESC, n.id DESC"
    ids = [r["id"] for r in conn.execute(sql, params).fetchall()]
    if project:
        allowed = {oid for (ot, oid) in project_members(conn, project) if ot == "note"}
        ids = [i for i in ids if i in allowed]
    ids = ids[: int(limit)]
    return [n for n in (get_note(conn, i) for i in ids) if n]


# --------------------------------------------------------------------------- #
# projects / collections
# --------------------------------------------------------------------------- #

def _project_slug(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip()).lower()


def upsert_project(conn: sqlite3.Connection, name: str) -> int:
    slug = _project_slug(name)
    if not slug:
        raise ValueError("project name cannot be empty")
    conn.execute(
        "INSERT INTO project(name, slug) VALUES (?, ?) ON CONFLICT(slug) DO NOTHING",
        (name.strip(), slug),
    )
    return int(conn.execute("SELECT id FROM project WHERE slug=?", (slug,)).fetchone()["id"])


def tag_project(
    conn: sqlite3.Connection, owner_type: str, owner_id: int, name: str, source: str = "user"
) -> int:
    """Add (owner) to project ``name``, creating the project if needed. Idempotent."""
    pid = upsert_project(conn, name)
    conn.execute(
        "INSERT INTO project_member(project_id, owner_type, owner_id, source) "
        "VALUES (?,?,?,?) ON CONFLICT(project_id, owner_type, owner_id) DO NOTHING",
        (pid, owner_type, owner_id, source),
    )
    return pid


def untag_project(conn: sqlite3.Connection, owner_type: str, owner_id: int, name: str) -> bool:
    cur = conn.execute(
        "DELETE FROM project_member WHERE owner_type=? AND owner_id=? AND project_id="
        "(SELECT id FROM project WHERE slug=?)",
        (owner_type, owner_id, _project_slug(name)),
    )
    return cur.rowcount > 0


def project_names(conn: sqlite3.Connection, owner_type: str, owner_id: int) -> list[str]:
    return [
        r["name"]
        for r in conn.execute(
            "SELECT p.name FROM project_member pm JOIN project p ON p.id = pm.project_id "
            "WHERE pm.owner_type=? AND pm.owner_id=? ORDER BY p.name",
            (owner_type, owner_id),
        ).fetchall()
    ]


def project_members(conn: sqlite3.Connection, name: str) -> set[tuple[str, int]]:
    """The (owner_type, owner_id) set belonging to a project. Empty if unknown."""
    rows = conn.execute(
        "SELECT pm.owner_type, pm.owner_id FROM project_member pm "
        "JOIN project p ON p.id = pm.project_id WHERE p.slug=?",
        (_project_slug(name),),
    ).fetchall()
    return {(r["owner_type"], r["owner_id"]) for r in rows}


def project_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM project WHERE slug=?", (_project_slug(name),)
    ).fetchone() is not None


def list_projects(conn: sqlite3.Connection) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT p.id, p.name, "
            "  COALESCE(SUM(pm.owner_type='paper'), 0) AS papers, "
            "  COALESCE(SUM(pm.owner_type='note'),  0) AS notes "
            "FROM project p LEFT JOIN project_member pm ON pm.project_id = p.id "
            "GROUP BY p.id ORDER BY p.name"
        ).fetchall()
    ]


def rename_project(conn: sqlite3.Connection, old: str, new: str) -> bool:
    """Rename a project. Folds into the target if ``new`` already exists."""
    src = conn.execute("SELECT id FROM project WHERE slug=?", (_project_slug(old),)).fetchone()
    if src is None:
        return False
    new_slug = _project_slug(new)
    if not new_slug:
        raise ValueError("new project name cannot be empty")
    dst = conn.execute("SELECT id FROM project WHERE slug=?", (new_slug,)).fetchone()
    if dst is None:
        conn.execute(
            "UPDATE project SET name=?, slug=? WHERE id=?", (new.strip(), new_slug, src["id"])
        )
    else:  # fold memberships into the existing target, then drop the old row
        conn.execute(
            "INSERT OR IGNORE INTO project_member(project_id, owner_type, owner_id, source) "
            "SELECT ?, owner_type, owner_id, source FROM project_member WHERE project_id=?",
            (dst["id"], src["id"]),
        )
        conn.execute("DELETE FROM project WHERE id=?", (src["id"],))
    conn.commit()
    return True


# --------------------------------------------------------------------------- #
# stats
# --------------------------------------------------------------------------- #

def status(conn: sqlite3.Connection) -> dict:
    def count(sql: str) -> int:
        return int(conn.execute(sql).fetchone()[0])

    by_status = {
        r["reading_status"]: r["n"]
        for r in conn.execute(
            "SELECT reading_status, COUNT(*) AS n FROM paper GROUP BY reading_status"
        ).fetchall()
    }
    emb_by_model = {
        r["model_id"]: r["n"]
        for r in conn.execute(
            "SELECT model_id, COUNT(*) AS n FROM embedding GROUP BY model_id"
        ).fetchall()
    }
    return {
        "db_path": str(config.db_path()),
        "papers": count("SELECT COUNT(*) FROM paper"),
        "notes": count("SELECT COUNT(*) FROM note"),
        "projects": count("SELECT COUNT(*) FROM project"),
        "note_paper_links": count("SELECT COUNT(*) FROM note_paper"),
        "keywords": count("SELECT COUNT(*) FROM keyword"),
        "chunks": count("SELECT COUNT(*) FROM chunk"),
        "papers_with_fulltext": count(
            "SELECT COUNT(DISTINCT owner_id) FROM chunk WHERE owner_type='paper' AND kind='fulltext'"
        ),
        "citation_edges": count("SELECT COUNT(*) FROM citation"),
        "embeddings": emb_by_model,
        "active_embedding_model": get_meta(conn, "active_embedding_model"),
        "reading_status": by_status,
        "schema_version": SCHEMA_VERSION,
    }
