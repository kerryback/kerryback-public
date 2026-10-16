# litdb

litdb is a private, local library-management service for your research papers and
your research notes. It reads your
PDFs in full and indexes them for keyword and semantic search; captures and
organizes your notes — tagged, linked to papers, and searchable right alongside
them; finds and imports new work from the scholarly literature; tracks citations;
and writes your bibliography — all in one SQLite file on your machine. Nothing
leaves your computer unless you ask for an outside lookup.

It runs as a Claude Code plugin. You never type a command, but every action below
is also a plain command you can script (see the reference at the end).

## What it does

- Add papers. Reads each PDF's full text, resolves its metadata from OpenAlex
  (title, authors, venue, year, DOI), splits the text into passages, and embeds
  them into a local vector store. Sources: a folder of PDFs, a Zotero library, a
  single DOI, or a watched inbox folder that ingests on its own.
- Add and organize notes. Write the note however you like — a line in chat, a
  paragraph pasted in, a file — and tell Claude to file it. Claude picks the kind
  (idea/summary/critique/question/todo/quote), finds the paper it's about, and
  anchors it to a page or a verbatim quote. Notes are embedded
  whole and searchable next to your papers; `notes` lists them and `notes --search`
  finds them, and they surface first when you ask what you have on a topic.
- Search your corpus. Hybrid keyword (BM25) + semantic (vector) search over full
  text and abstracts, returning the paper and the page a passage came from. Scope
  by project/topic, publication year, or reading status.
- Find new work. Searches OpenAlex and Semantic Scholar, marks what you already
  own, and imports the details of any paper it finds into the database — searchable
  and citable at once. Full-text PDFs are imported directly when a free copy exists:
  Claude locates and downloads it with its web search and fetch tools. Paywalled
  papers you download through your library login, and litdb ingests them from there.
- Follow citations. A paper's references and who cites it, the works your library
  leans on most, and important works you cite but don't own.
- Write your bibliography. A `.bib` for the whole library or a chosen subset, using
  each paper's stored citation key.
- Stay private. Everything lives in one SQLite file locally; nothing is sent out
  unless you ask for an external lookup, and notes you mark confidential are always
  embedded locally.

## Getting started

Install once:

```
claude plugin marketplace add kerryback/kerryback-public
claude plugin install litdb@kerryback-public
```

On first use, Claude runs a short setup — a couple of questions (see modes below),
then it builds the runtime for you. litdb keeps its data in one place (`~/.litdb`),
independent of any project or folder, so there is nothing else to configure.

For semantic search it will offer to set up a small free tool (Ollama with a local
embedding model) and walk you through it. Skip it and search still works by
wording; add it later and litdb reindexes.

## With or without Zotero

litdb has two modes, chosen once at setup and stored as `source_of_truth`:

- litdb (default). litdb owns your references. You add PDFs; it organizes, indexes,
  and searches them and writes your `.bib`. Zotero is never touched. If you adopt
  Zotero later, one command migrates the whole library in.
- zotero. Your Zotero library is authoritative. litdb imports it — using Better
  BibTeX for your existing citation keys when Zotero is running with that add-on —
  keeps itself current as you save papers there, and pushes papers you add through
  litdb back into Zotero.

Either way, dropping new PDFs into a watched inbox folder ingests them
automatically.

---

## For power users: running commands directly

You never need this section, but every action Claude takes is a plain command you
can run yourself or put in a script. The interpreter lives at
`~/.litdb/.venv/bin/python`; `python3 skills/litdb/setup.py --runtime-path` prints its
path. Commands print machine-readable JSON by default; add `--human` for readable
output.

```bash
PY=$(python3 skills/litdb/setup.py --runtime-path)

$PY -m litdb scan-pdfs ~/Papers --keep-unresolved --embed   # add a folder of PDFs
$PY -m litdb search "momentum crashes" --human              # search your library
$PY -m litdb discover "factor momentum" --human             # your library + new work
$PY -m litdb notes --search "momentum" --human              # search your own notes
$PY -m litdb missing-refs --human                           # cited but not owned
$PY -m litdb export-bib --out refs.bib                      # write your bibliography
```

Getting papers in

| Command | Purpose |
|---|---|
| `scan-pdfs DIR [--project NAME] [--keep-unresolved] [--embed]` | add a folder of PDFs (look up metadata, read full text; tag with a project/topic) |
| `sync-inbox` | add new PDFs from your inbox folder (skips ones already added) |
| `import-doi DOI [--source]` | add one paper by DOI |
| `import-zotero --file F \| --local \| --bbt` | import from Zotero |
| `ingest-pdf --paper ID (--file F \| --auto) \| --all` | read a PDF's full text into an existing paper |

Searching and reading

| Command | Purpose |
|---|---|
| `search "Q" [--mode] [--type] [--status] [--year-min/max] [--project NAME]` | search full text + abstracts by wording, meaning, or both (optionally scoped to a project) |
| `screen --paper P --status … [--note] [--priority]` | mark reading status / triage |
| `list [--status]` | list papers (your reading queue) |
| `paper ID` | show a paper with its notes, keywords, and citekey |

Finding new work (searches your library first)

| Command | Purpose |
|---|---|
| `external-search "Q" [--source] [--import]` | search OpenAlex / Semantic Scholar (marks what you own; optional import) |
| `discover "Q"` | your library's hits plus new outside candidates in one view |

Citations

| Command | Purpose |
|---|---|
| `cite-fetch --paper ID \| --all` | fetch a paper's references and citers |
| `refs --paper ID` / `cited-by --paper ID` | what a paper cites / who cites it |
| `most-cited` | works your library cites most |
| `missing-refs` | works you cite a lot but don't own |

Fixing up records

| Command | Purpose |
|---|---|
| `update ID [--doi] [--citation-key] [--title] [--authors] [--year] [--venue] …` | correct a paper's details in place (keeps its full text) |
| `merge --keep K --dupe D` | combine two records for the same paper into one |
| `delete ID` | remove a paper and everything attached to it |

Citing and Zotero

| Command | Purpose |
|---|---|
| `export-bib [--out FILE] [--status S] [--ids …]` | write a `.bib` bibliography for the library or a subset |
| `sync-zotero` | pull new papers from Zotero (import + read PDFs + index) |
| `push-zotero [--ids …] [--dry-run] [--force]` | add papers to Zotero (skips ones already sent) |
| `migrate-to-zotero [--dry-run]` | move your whole library into Zotero and switch to Zotero mode |

Notes, indexing, and admin

| Command | Purpose |
|---|---|
| `add-note --body … [--title] [--kind K] [--link ID] [--relation R] [--page N] [--quote …] [--confidential] [--project NAME \| --no-project]` | attach a note, optionally kind-tagged and anchored to a page/quote of a linked paper (auto-tags with the working-folder name) |
| `link --note N --paper P [--relation] [--page N] [--quote …]` | link an existing note to a paper |
| `notes [--search Q] [--paper ID] [--kind K] [--project NAME] [--since DATE] [--confidential] [-k N]` | list notes, or `--search` notes only (hybrid); returns full note bodies |
| `note ID` | show one note with its links (full body) |
| `projects list \| rename OLD NEW \| tag NAME --paper/--note ID \| untag …` | manage the project/topic tags on papers and notes |
| `embed [--provider] [--model] [--force]` | build/refresh the "search by meaning" index |
| `prefs [set KEY VALUE \| get KEY]` | view/change settings (see Settings) |
| `s2-key [status \| set KEY \| clear]` | store your Semantic Scholar key |
| `status` | library statistics |
| `init` / `onboarded [--mark \| --reset]` | create the database / manage first-run setup |

### Settings

Changed with `litdb prefs set KEY VALUE`, stored in `~/.litdb/preferences.json`:

| Setting | Meaning |
|---|---|
| `source_of_truth` | `litdb` (default) or `zotero` — who's in charge of your references |
| `inbox` | a folder whose new PDFs are added automatically each session |
| `uses_tex` | you write in LaTeX (litdb surfaces citation keys) |
| `use_better_bibtex` | use Better BibTeX citation keys when importing from Zotero |

---

## For developers: how it works

- Storage. One SQLite file, `~/.litdb/litdb.db`, in a fixed per-user home (with the
  venv, `preferences.json`, and the `.onboarded` marker). `LITDB_HOME` / `LITDB_DB`
  override the locations.
- Data model. `paper`, `note`, `note_paper`, `chunk` (the retrieval unit — one
  abstract chunk plus any full-text chunks), `keyword` / `paper_keyword` (with
  provenance), `embedding` (vectors, namespaced by model), `citation` (edges), and
  `ingested_file` (a content-hash ledger that makes inbox scans idempotent). Schema
  migrations are additive and automatic.
- Search. FTS5 BM25 (keyword) and brute-force cosine similarity over float32
  vectors (numpy-accelerated when present), fused with Reciprocal Rank Fusion and
  deduplicated to one hit per paper. No native extension required, so it stays
  portable; a vector engine like sqlite-vec can drop in later.
- Embeddings. One provider interface; vectors are namespaced by `model_id` so
  several models coexist and switching is a config edit plus a reindex. Local by
  default (Ollama `nomic-embed-text`); Voyage / OpenAI / fastembed optional; a
  zero-dependency `hash` provider works before setup. Confidential notes are always
  embedded locally.
- Two modes. `source_of_truth` selects whether litdb or Zotero is authoritative. In
  litdb mode nothing touches Zotero. In Zotero mode litdb is a derived index kept
  current with `sync-zotero` / `push-zotero`; the Zotero integration uses the local
  connector only and never leaves the machine.
- Notes are paper-anchored raw material for synthesis, not an editor. A note carries
  a kind, links to papers (each with an optional page/quote), and project tags; it's
  embedded whole — one vector per note, not chunked — and retrieved as a separate,
  higher-priority track from papers (`notes` / `notes --search`, read in full). The
  structure is Claude's job, not the user's: you write the note in whatever form
  suits you and Claude fills in kind, links, anchors, and tags. Rich editing still
  lives in your own note app (Obsidian, Markdown, Zotero); litdb complements it and can export
  to it later. Deliberately deferred (revisit before building): synthesis commands,
  Markdown/Obsidian export, Zotero note push, note-to-note links.
- Surface. The CLI is primary and drives everything; `litdb.server` optionally
  exposes the same operations as MCP tools.

### Install from source

```bash
git clone https://github.com/kerryback/kerryback-public && cd kerryback-public/plugins/litdb
python3 skills/litdb/setup.py --check     # report what's present/missing
python3 skills/litdb/setup.py             # dry-run plan (changes nothing)
python3 skills/litdb/setup.py --yes       # build the runtime into ~/.litdb
```

`setup.py` only builds the runtime (venv + package; `--editable` for dev) and
never installs system software for you. Requires Python 3.10+.

### Configuration file

Behavioral choices live in Settings (above). `config.toml` is only for lower-level
defaults — copy `config.example.toml` into the data directory, or point
`LITDB_CONFIG` at it:

```toml
[embedding]
provider = "ollama"          # ollama | fastembed | voyage | openai | hash
model    = "nomic-embed-text"

[policy]
confidential_stay_local = true
local_provider = "ollama:nomic-embed-text"

[external]
openalex_mailto = ""         # your email joins OpenAlex's faster "polite pool"
s2_api_key_env  = "S2_API_KEY"

[zotero]
connector = "http://localhost:23119"
```

### Skills

One self-contained skill ships in the plugin: `litdb`. Its SKILL.md is a lean
router — it resolves the runtime, runs first-run onboarding, loads preferences,
does the session-start catch-up sync, and routes each request to a task file that
lives beside it: `setup.md` (one-time runtime bootstrap via the bundled
`setup.py`: check → consent → install), `onboarding.md`, `add-folder.md`,
`add-note.md`, or `search.md`. Keeping everything in one skill directory means a
single-skill install (e.g. `npx skills add`) is fully self-contained.

### Design principles

Local-first and private by construction; self-contained (Zotero, OpenAlex,
Semantic Scholar, and Better BibTeX are reached with small in-house `urllib`
clients, so a colleague installs just one plugin); programmatic (every step is a
scriptable command with JSON output); and human-in-the-loop (external results and
links are proposed, not written silently).

Possible future refinements: section-aware PDF chunking, a cross-encoder
reranker, a Zotero Web API transport for headless sync, and a real notes
integration. The schema accommodates them without migration.

## License

MIT.
