# litdb onboarding (first run)

Read and follow this only when `litdb onboarded` reports `false`. Keep it brief
and interactive — do steps for the user where you can, ask where their judgment
is needed, and never do the whole thing silently. Record answers as preferences
and mark onboarding complete at the end. `LITDB_PY` and `PLUGIN_ROOT` are as
resolved in SKILL.md.

## Steps

1. Runtime and database. Confirm `"$LITDB_PY" -m litdb status` works (invoke the
   follow `SKILL_DIR/setup.md` first if the runtime isn't ready).

2. One or two sentences on what litdb is: a private, local, searchable library of
   the user's papers and notes, with semantic search, discovery, and citations.

3. Source of truth — do you use Zotero? Ask plainly whether the user uses Zotero
   as their reference manager. This picks one of two paths; do not blur them.
   - Yes → `prefs set source_of_truth zotero`. Zotero is authoritative. Ingest
     from Zotero with `import-zotero`; when papers enter via litdb instead (a
     local-PDF folder or external discovery), push them into Zotero with
     `push-zotero` and re-`import-zotero` so Better BibTeX keys flow back. litdb is
     a derived index. (Local connector only; Zotero must be running.)
   - No (default) → `prefs set source_of_truth litdb`. Bypass Zotero entirely:
     ingest folders straight into litdb and use `export-bib` for the `.bib` they
     cite from. Reassure them this needs no Zotero at all, and that if they ever
     adopt Zotero later, `migrate-to-zotero` pushes the whole litdb library into
     Zotero and switches modes — so choosing "no" now costs nothing.
     Then set up an inbox: ask for a folder to drop new PDF downloads into (they
     can point their browser's download location there, or move papers in). Record
     it — `prefs set inbox <folder>` — and tell them it can be changed anytime with
     the same command. Each litdb session will ingest new PDFs from it
     automatically (`sync-inbox`, idempotent by content hash). If they'd rather not
     use an inbox, leave it unset and they can run `scan-pdfs <folder>` on demand.

4. TeX / Better BibTeX.
   - Ask: "Do you write your papers in TeX / LaTeX?"
   - Record it: `"$LITDB_PY" -m litdb prefs set uses_tex true|false`.
   - If yes, explain that the Better BibTeX add-on for Zotero gives every paper a
     stable citation key so litdb can hand you `\cite{key}`. Offer two choices:
     1. use Better BibTeX
     2. do not use Better BibTeX
     Record: `"$LITDB_PY" -m litdb prefs set use_better_bibtex true|false`.
     If they choose (1) and it isn't installed, offer to install it for them:
     with consent, download the latest `.xpi` from
     https://github.com/retorquere/zotero-better-bibtex/releases/ to a known
     location (e.g. `~/Downloads`), then walk them through the final GUI step
     (Zotero → Tools → Add-ons → gear → Install Add-on From File → pick the
     `.xpi` → restart). That last click is the only part you can't do for them.
   - If they don't use TeX, set `use_better_bibtex false` (citekeys aren't needed)
     unless they say otherwise.

5. Get papers in. Ask which fits, then follow the matching task file:
   - Loose PDFs scattered on disk → follow `add-folder.md`.
   - An existing Zotero library → follow `add-folder.md` (Zotero section).
   - Nothing yet / start fresh → seed by topic or DOI:
     `"$LITDB_PY" -m litdb external-search "<topic>" --import` or
     `"$LITDB_PY" -m litdb import-doi <doi>`.
   For a mixed situation (common), do the PDF folder first, then Zotero for the
   DOI-less stragglers.

6. Make it searchable and show it working: `"$LITDB_PY" -m litdb embed`, then a
   sample `"$LITDB_PY" -m litdb search "<their topic>" --human`.
   If `embed` reports an Ollama error (not running, or the model isn't pulled),
   offer to set it up for them: with consent, install Ollama (macOS:
   `brew install ollama`; Windows: `winget install Ollama.Ollama`; or the
   installer from https://ollama.com), start it, and run
   `ollama pull nomic-embed-text`, then retry `embed`. If they decline, note that
   search still works in keyword mode.

7. Optional (offer, don't force): build the citation graph and reveal gaps —
   `"$LITDB_PY" -m litdb cite-fetch --all` then `"$LITDB_PY" -m litdb missing-refs`.

8. Semantic Scholar API key (optional, for external discovery). litdb can search
   Semantic Scholar for related work and novelty checks (`external-search`,
   `discover`, with `--source s2` or `both`). Without a key, S2 is rate-limited
   across all anonymous users and often returns HTTP 429; a free key removes that.
   Ask whether the user already has a key or wants one:
   - Has one → store it: `"$LITDB_PY" -m litdb s2-key set <KEY>` (writes
     `~/.litdb/s2_api_key`, mode 0600, and records `has_s2_api_key`). Verify with
     `"$LITDB_PY" -m litdb s2-key status`.
   - Wants one → point them to https://www.semanticscholar.org/product/api. They
     need the Academic Graph API (a single key covers all of Semantic Scholar's
     APIs). When it arrives, store it as above.
   - Not now → record it so the skill knows:
     `"$LITDB_PY" -m litdb prefs set has_s2_api_key false`. Corpus-first search and
     OpenAlex discovery still work; only S2-sourced discovery is unavailable.
   A user who prefers an environment variable can instead export `S2_API_KEY`;
   litdb honors it over the stored file. Never print the full key back — the CLI
   already masks it.

9. Finish: `"$LITDB_PY" -m litdb onboarded --mark`. Preferences were already
   recorded via `prefs` in the steps above.

To re-run onboarding later, the user can run `litdb onboarded --reset`.
