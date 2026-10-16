# Add papers to the library

Read and follow this when the user wants to add a folder of PDFs or import a
Zotero library. `LITDB_PY` is resolved in SKILL.md. Always `embed` after adding
papers so they become semantically searchable.

## A folder of loose PDFs on disk

Goal: every PDF ends up as one record with full text, embeddings, and proper
OpenAlex metadata (title, authors, year, venue, DOI, `openalex_id`). Run the whole
pipeline in the background so the user can keep chatting while it works: ask for
the folder path synchronously, then hand every long step to a background command
or subagent and let each stage's completion drive the next. Never block waiting —
if the user says something mid-ingest, just answer; the pipeline advances on its
own via completion notifications.

DOIs embedded in PDFs are missing or wrong for most older/scanned papers, so do
not rely on them; resolve metadata from OpenAlex by title/author with subagents
that verify each match against the PDF.

1. Ask for the folder path and the project/topic these papers belong to — the only
   synchronous steps. For the project, ask what research project or topic this
   folder is for; offer the folder's name only as a suggestion, never as a silent
   default (folder names like `Downloads` or `refs` make poor topic tags). If the
   user says the papers span several projects, collect each name. Only skip the tag
   if the user explicitly declines. Pass each name with a `--project "<name>"` flag
   (repeatable) on the `scan-pdfs` call below; every paper the scan adds is tagged,
   and `search --project "<name>"` then scopes retrieval to this set.

2. Start ingestion in the background and return control to the user immediately.
   Run as a background command (one `--project` per project name from step 1):
   `"$LITDB_PY" -m litdb scan-pdfs "<folder>" --project "<name>" --keep-unresolved --embed`
   Tell the user ingestion is running in the background and they can keep working;
   you will report when it's done. Do not wait on it.
   - It adds every PDF with full text (embedded), resolving metadata via OpenAlex
     where a DOI is confidently found and adding the rest as filename-titled
     stubs. Each `unresolved` entry in the JSON carries the stub's `paper_id` and
     `file` — that list is the work for step 3.

3. When scan-pdfs finishes (its completion re-invokes you), resolve the stubs with
   background subagent(s). If there are no `unresolved` stubs, skip to step 4.
   Otherwise split the stub list (`paper_id` + `file`) across one or more subagents
   — parallelize for large folders; subagents run in the background, so the user
   stays free. Give each this per-record protocol (use `"$LITDB_PY"` for litdb
   calls):
     a. Read the PDF's first 1–2 pages (the `file`) for the true title, authors,
        and year — filenames and embedded years are often wrong.
     b. `"$LITDB_PY" -m litdb external-search "<title> <first-author-surname>" --source openalex`.
     c. Verify before trusting: publication year within ±1, at least one author
        surname in common, and a close title match. Never accept the top hit
        blindly.
     d. If verified, patch the record in place (preserves the attached full text
        and embeddings, no duplicate):
        `"$LITDB_PY" -m litdb update <paper_id> --doi <doi> --openalex-id <oaid> --title "<title>" --authors "<authors>" --year <year> --venue "<venue>"`
        (add `--citation-key <key>` when `uses_tex`).
     e. No confident match (working papers, unindexed pieces): set a clean title
        and flag it — `"$LITDB_PY" -m litdb update <paper_id> --title "<clean title>"`.
     f. Return a per-file summary: resolved (title + DOI) or needs-review (reason).

4. When the subagent(s) finish, rebuild the citation graph as a background command:
   `"$LITDB_PY" -m litdb cite-fetch --all`.

5. When that finishes, post the final report: counts resolved / needs-review, new
   citation edges, and the needs-review list; then `"$LITDB_PY" -m litdb missing-refs`
   for gaps. Confirm with `status` and a sample `search --human`.

Notes:
- If `source_of_truth=zotero`, add one more background step after step 3: push the
  freshly resolved papers into Zotero with `push-zotero`, then re-run
  `import-zotero` so Better BibTeX keys flow back into litdb. (In `litdb` mode,
  skip this — litdb owns the records and `export-bib` owns the `.bib`.)
- The subagents resolve what the DOI pass could not (usually the bulk of an older
  collection). To verify every record including DOI-resolved ones, widen step 3 to
  all `paper_id`s, at higher cost.
- Semantic Scholar can supplement OpenAlex in step 3 (`--source s2`/`both`) when a
  key is stored (`has_s2_api_key`); default to `openalex` (no key, no rate limit).
- `--limit N` on `scan-pdfs` processes a first batch for a quick trial.

## An existing Zotero library

1. Preferences: `import-zotero` already honors `use_better_bibtex`; you don't need
   to pass flags unless the user overrides (`--bbt` / `--no-bbt`).
2. Run: `"$LITDB_PY" -m litdb import-zotero --local`
   - Uses Better BibTeX automatically when available (capturing citation keys),
     else the Zotero local API.
   - The result reports `source` and `with_citation_key`; relay those.
3. If Zotero isn't running or has no papers, guide the user: open Zotero, install
   the Zotero Connector browser extension, and add papers (click the connector on
   a paper's page, or use "Add Item by Identifier" with a DOI).
4. Embed: `"$LITDB_PY" -m litdb embed`.

## After importing

Offer to build the citation graph for the new papers (`cite-fetch --all`) and, if
useful, show `missing-refs` — papers the collection references but doesn't own.
