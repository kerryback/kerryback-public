# Installing litdb

litdb is per-user and local. Each person installs their own copy; there is no
shared server. Works on macOS and Windows.

## Requirements

- Python 3.10 or newer on PATH.
- Optional: [uv](https://docs.astral.sh/uv/) for faster environment setup
  (the installer falls back to the standard library `venv` + `pip`).
- Optional (Phase 2+): [Ollama](https://ollama.com/) for local embeddings.

## Setup

Clone the repo (or download it), then from its directory:

```
python3 skills/litdb/setup.py --check     # report status
python3 skills/litdb/setup.py             # show the plan (changes nothing)
python3 skills/litdb/setup.py --yes       # install everything
```

litdb installs into a fixed per-user home, `~/.litdb`, independent of the repo.
`--yes` creates `~/.litdb/.venv`, installs litdb (non-editable, so the clone is
disposable afterward), initializes the database, and copies the skill into
`~/.claude/skills/`. It never installs Python, uv, or Ollama for you.

To repair or update later, follow the litdb skill's `setup.md` or re-run `setup.py --yes`
— it reinstalls from `git+https://github.com/kerryback/kerryback-public#subdirectory=plugins/litdb`, so you don't need
a checkout.

The managed interpreter is:

- macOS/Linux: `~/.litdb/.venv/bin/python`
- Windows: `~/.litdb/.venv/Scripts/python.exe`

Get it programmatically with `python3 skills/litdb/setup.py --runtime-path`.

## litdb home and data location

Everything litdb owns lives in `~/.litdb`:

- `~/.litdb/.venv` — the runtime
- `~/.litdb/litdb.db` — the database
- `~/.litdb/preferences.json`, `~/.litdb/.onboarded` — per-user settings/marker

Override with environment variables:

- `LITDB_HOME` — the whole home directory (venv + data)
- `LITDB_DB` — just the database file
- `LITDB_CONFIG` — path to a `config.toml` (see `config.example.toml`)

## Importing from Zotero

Two options:

1. Export file (works offline). In Zotero: File → Export Library → format
   "CSL JSON" (or use Better BibTeX). Then:

   ```
   .venv/bin/python -m litdb import-zotero --file library.json
   ```

2. Live from a running Zotero:

   ```
   .venv/bin/python -m litdb import-zotero --local
   ```

   If the Better BibTeX add-on is installed, litdb uses it automatically and
   captures citation keys; otherwise it falls back to the Zotero local API.
   Force Better BibTeX with `--bbt`, or skip it with `--no-bbt`.

Better BibTeX (recommended for LaTeX users) gives stable citation keys. Download
the latest `.xpi` from
https://github.com/retorquere/zotero-better-bibtex/releases/ (right-click the
`.xpi` asset → Save Link As, so the browser doesn't try to open it), then in
Zotero go to Tools → Add-ons → gear → Install Add-on From File, and restart
Zotero.

Re-importing is safe: papers are matched on DOI, Zotero key, OpenAlex/S2 id, then
citekey, and updated in place.

## Windows notes

- Use `py -3` or `python` if `python3` is not on PATH.
- The venv interpreter is under `.venv\Scripts\`, not `.venv/bin/`.
- FTS5: if setup reports FTS5 missing (rare), install a Python build with FTS5,
  or add `pysqlite3-binary` to the venv. Standard python.org builds include it.

## Uninstall

Delete the plugin's `.venv` directory and the litdb data directory. Nothing else
is touched.

## Optional MCP server

The everyday skill uses the CLI and needs no server, so the plugin does not
register one. If you prefer native MCP tools, install the extra into the runtime
and register the server yourself:

```
~/.litdb/.venv/bin/python -m pip install 'mcp>=1.2.0'
```

Then add an entry to your Claude Code MCP config pointing at the runtime:

```json
{ "mcpServers": { "litdb": {
  "command": "~/.litdb/.venv/bin/python", "args": ["-m", "litdb.server"] } } }
```

(Use the absolute path to `~/.litdb/.venv/bin/python`, or the `Scripts\\python.exe`
form on Windows, if your client does not expand `~`.)
