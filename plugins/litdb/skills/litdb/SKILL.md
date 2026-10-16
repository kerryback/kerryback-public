---
name: litdb
description: Personal literature and notes knowledge base. Use whenever the user wants to search their own papers/library, add papers (a folder of PDFs or a Zotero library), capture notes tied to papers, triage reading, find new work on a topic, or explore citations — e.g. "what do I have on momentum crashes", "add this folder of PDFs", "import my Zotero library", "add a note about this paper", "what should I read next on X". Always search the user's own corpus before any external source. Backed by a local SQLite store with keyword + semantic (hybrid) search; driven through the litdb CLI.
---

# litdb

A per-user, local, private knowledge base of the user's papers and notes —
keyword, semantic, and hybrid search, plus external discovery and a citation
graph. You operate it through the `litdb` CLI. Search the user's own corpus
before reaching for any external or web source.

This file is a router: it handles session start and points to a task file for
each kind of request. Read the matching task file with your file tool before
acting — don't guess the steps.

## Start of every session

1. Resolve the runtime. litdb runs from a fixed virtualenv in the litdb home,
   `~/.litdb`. The interpreter (call it LITDB_PY) is `~/.litdb/.venv/bin/python`
   (macOS/Linux) or `~/.litdb/.venv/Scripts/python.exe` (Windows). If it does not
   exist or `"$LITDB_PY" -m litdb --help` fails, read `SKILL_DIR/setup.md` and
   follow it (it bootstraps the runtime via the bundled `setup.py`), then retry.
   Use `"$LITDB_PY" -m litdb …` for every command. The home does not depend on any
   project or repo folder.

   The task files referenced below (`setup.md`, `onboarding.md`, `add-folder.md`,
   etc.) live in this skill's own directory — the folder containing this SKILL.md
   (call it SKILL_DIR). Read them from there. If the user asks to set up, install,
   or repair litdb directly, follow `SKILL_DIR/setup.md`.

2. Check onboarding: `"$LITDB_PY" -m litdb onboarded`.
   - `{"onboarded": false}` → read `SKILL_DIR/onboarding.md` and follow it. It
     records preferences and marks onboarding complete at the end.
   - `{"onboarded": true}` → load preferences with `"$LITDB_PY" -m litdb prefs`
     and honor them for the rest of the session (see below). The `has_s2_api_key`
     preference is the quick startup signal for whether Semantic Scholar discovery
     is available; the live truth is `"$LITDB_PY" -m litdb s2-key status`.

3. Session-start catch-up (once now, before the user's task). Which sync to run
   depends on the mode; both are incremental and safe every session, and both
   catch only what arrived *before* this session — so also run the matching one on
   demand when the user says they just added something.
   - `source_of_truth=zotero` → `"$LITDB_PY" -m litdb sync-zotero` (import + ingest
     new PDFs + embed). If it returns `"synced": false` (Zotero not running), do
     NOT treat it as an error: proceed with existing data and note results may be
     slightly stale.
   - `source_of_truth=litdb` → if an `inbox` preference is set, run
     `"$LITDB_PY" -m litdb sync-inbox`. It ingests new PDFs dropped in that folder
     (idempotent by content hash) and returns any DOI-less stubs under
     `needs_resolution`; resolve those with the subagent protocol from
     `add-folder.md` step 3 (read PDF → OpenAlex → verify → `update`). If no
     `inbox` is set, skip — the user ingests via `scan-pdfs` on demand.

## Preferences

Per-user preferences are stored by the app and read with `litdb prefs`
(no args lists all; `prefs KEY` gets one; `prefs KEY VALUE` sets one). Honor
them:

- `uses_tex` — the user writes LaTeX. When true, surface `citation_key` values
  so they can `\cite{…}`.
- `use_better_bibtex` — whether to use Better BibTeX for Zotero imports. The
  `import-zotero` command already honors this automatically.
- `source_of_truth` — `litdb` (default) or `zotero`. Determines who owns paper
  membership and citation keys.
  - `litdb`: litdb is authoritative and fully programmatic. New papers enter via
    litdb ingest, litdb mints `citation_key`s, and `export-bib` emits the `.bib`
    the user cites from. Do not require Zotero. If they later adopt Zotero,
    `migrate-to-zotero` pushes the whole corpus in and switches to zotero mode.
  - `zotero`: the user's Zotero library (with Better BibTeX) is authoritative.
    Bring papers in with `import-zotero` and treat the BBT `citation_key` as
    canonical; litdb is a derived index. `export-bib` still works but mirrors
    litdb's copy — flag that BBT owns the keys. Never force this mode on a user
    who does not already run Zotero. To keep this mode click-free, add
    litdb-ingested or newly-discovered papers to Zotero programmatically with
    `push-zotero` (requires Zotero running), then re-`import-zotero` so BBT keys
    flow back.
- `inbox` — (litdb mode) a folder the user drops new PDF downloads into. When
  set, session start runs `sync-inbox` to ingest new files from it (idempotent by
  content hash). Change it anytime with `prefs set inbox <folder>`; unset means no
  auto-ingest (use `scan-pdfs` on demand).
- `has_s2_api_key` — whether the user has a Semantic Scholar API key stored.
  When true, external discovery may use `--source s2`/`both` (higher rate limit,
  citation-aware). When false or unset, prefer `--source openalex` for discovery
  and, if the user wants better external coverage, offer to add a key (store it
  with `s2-key set <KEY>`; see `onboarding.md` step 8). The authoritative check is
  `s2-key status`; the key itself lives in `~/.litdb/s2_api_key` (0600) or the
  `S2_API_KEY` environment variable — never print it in full.
- Whenever the user states a durable preference about how litdb should behave
  (default search scope, verbosity, a preferred source, etc.), record it:
  `"$LITDB_PY" -m litdb prefs set <key> <value>`.

## Routing — when the user wants to…

Read the named file from SKILL_DIR (this skill's own directory) before acting.

| …do this | read and follow |
|---|---|
| add a folder of PDFs, import Zotero, get papers in | `SKILL_DIR/add-folder.md` |
| capture a note / a thought about a paper, in any form the user wrote it | `SKILL_DIR/add-note.md` |
| find papers, search, "what do I have on…", find new work, what to read next | `SKILL_DIR/search.md` |

For anything else (triage/reading status, showing a paper, corpus stats), use the
CLI directly — see the reference below.

Notes are paper-anchored raw material for synthesis, not an editor. The user writes
the note however they like --- a sentence in chat, a paragraph pasted in, a file on
disk --- and you do the structuring: `add-note` with a `kind`
(idea/summary/critique/question/todo/quote), anchored to a page or a verbatim
`quote`, linked to one or more papers. Never make the user supply the fields. A note
is embedded whole (one vector per note) and searchable next to the library.
Retrieve with `notes` /
`notes --search` and read notes IN FULL — they outrank papers and are read as a
separate first track (see `search.md`). Rich editing still belongs to the user's own
note app (Obsidian, Markdown, Zotero annotations); litdb complements that rather than
replacing it. Deliberately still out of scope (revisit before building): synthesis
commands, Markdown/Obsidian export, Zotero note push, note-to-note links.

## Conventions (always)

- Corpus-first: search the user's library before any external/web source.
- The CLI prints JSON by default; parse it. Add `--human` when showing the user.
- Saving downloaded PDFs: the user may keep papers for different projects in
  different folders (e.g. a per-project `Literature` folder), so when you download
  or obtain a paper's PDF, save it into the folder for the project it belongs to —
  then ingest from there (`scan-pdfs`, or drop it in the `inbox`). If you are not
  sure which folder a paper belongs in, ask; don't guess. Each paper's `location`
  field (on `paper`/`list`) records where its PDF resides, or `not downloaded` if
  none is on disk.
- Never leave a paper with neither an abstract nor full text. It is then indexed on
  its title alone and will not come back from a semantic search, so the user
  effectively does not have it. Fetch the abstract from the landing page when the
  PDF is out of reach --- see `search.md`, step 2.
- Propose note↔paper links and important imports; let the user confirm.
- Confidential notes stay local and are never sent to a hosted embedder.
- Installing dependencies: when something litdb needs is missing — a Python
  package, `uv`, Ollama and its embedding model, or Better BibTeX — do not just
  print the command for the user to run. Ask whether they'd like you to install
  it; if yes, run the install yourself (via the shell) and report the result; if
  no, give them the command. The one step you cannot fully automate is the final
  Zotero GUI click for the Better BibTeX add-on — offer to download the `.xpi`
  and walk them through that last step. Never install silently; always ask first.

## Command reference

`init, import-zotero, scan-pdfs, import-doi, external-search, discover, search,
embed, add-note, link, notes, note, screen, list, paper, update, merge, delete, ingest-pdf,
cite-fetch, refs, cited-by, most-cited, export-bib, push-zotero, sync-zotero,
sync-inbox, migrate-to-zotero, missing-refs, projects, prefs, s2-key, onboarded,
status`. Every command supports `--human`; see README.md for the full table.

Papers and notes carry project/topic tags (many-to-many): `scan-pdfs --project`
sets them at folder ingest (ask the user for the name), `add-note --project` /
`--no-project` at note capture (defaults to the cwd name), and `search --project`
filters to one. Manage with `projects list|rename|tag|untag`.

Zotero (source_of_truth=zotero only): `push-zotero [--ids …] [--status S]
[--dry-run] [--force]` adds papers to a running Zotero via its connector API
(items tagged `litdb`); it records `zotero_pushed_at` so re-runs skip already-sent
papers. Requires Zotero running. `sync-zotero` pulls the other direction —
import new Zotero items + ingest their PDFs + embed, incrementally — and is what
the session-start catch-up (step 3 above) runs in zotero mode; it fails soft
(`"synced": false`) when Zotero is closed. `migrate-to-zotero` is the one-shot for a
`litdb`-mode user adopting Zotero: it pushes the whole corpus and, only if the
push fully succeeds, flips `source_of_truth` to `zotero` (then run `import-zotero`
to pull Better BibTeX keys back). Both are local-connector only.

BibTeX: `export-bib [--out FILE] [--status S] [--ids …]` writes BibTeX for the
corpus (or a subset) using each paper's stored `citation_key` (fallback keys are
generated for any without one, and collisions get a/b/c suffixes). This is how a
`source_of_truth=litdb` user gets the `.bib` they cite from — no Zotero needed.

Semantic Scholar key: `s2-key status` reports whether a key is present and its
source (env var or stored file); `s2-key set <KEY>` stores it (`~/.litdb/s2_api_key`,
0600) and records the `has_s2_api_key` preference; `s2-key clear` removes the
stored file. A stored key raises the S2 rate limit so `external-search`/`discover`
with `--source s2`/`both` stop returning HTTP 429.

Fixing records: `update PAPER_ID --doi … --citation-key … --title … --authors …
--year … --venue … --openalex-id …` patches a paper's metadata in place (full
text and embeddings are preserved; the abstract chunk is re-indexed). This is how
you repair the filename-titled records `scan-pdfs --keep-unresolved` creates:
resolve the real record (e.g. `import-doi <doi>` or `external-search`), then
either `update` the existing paper with the correct ids, or — if `import-doi`
created a second record — `merge --keep <good_id> --dupe <other_id>` to combine
metadata + full text into one paper. Setting a paper's `openalex-id` lets the
citation graph recognize it, collapsing false `missing-refs` gaps. `delete
PAPER_ID` removes a paper, its chunks/embeddings, and its links.
