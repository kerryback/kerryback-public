#!/usr/bin/env python3
"""litdb bootstrap — install/repair the runtime and (optionally) the skill.

The litdb runtime lives in a FIXED per-user home, ``~/.litdb`` (override with the
LITDB_HOME env var):

  ~/.litdb/.venv          managed virtualenv with the litdb package installed
  ~/.litdb/litdb.db       the database
  ~/.litdb/preferences.json, ~/.litdb/.onboarded

Because the home is fixed, nothing depends on a project/repo folder that a user
might delete. The package is installed non-editable (copied into the venv) from a
local checkout when present, otherwise straight from GitHub — so after install
the source checkout is disposable.

This handles only the RUNTIME. The skill itself is distributed as a Claude Code
plugin (or copied into ~/.claude/skills); Claude Code discovers it and, on first
use, reads the litdb skill's setup.md, which runs this bundled script to build the
runtime.

Modes:
  --check         report what is present/missing (add --json for machine output)
  --runtime-path  print the venv's Python if usable, else exit 1
  (default)       show the plan (dry run) without changing anything
  --yes           execute: create ~/.litdb/.venv, install litdb, init the DB

Options:
  --editable      install the local checkout editable (development)
  --dev           alias for --editable

Never installs system software (Python, uv). Everything here is standard library.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

GIT_URL = "git+https://github.com/kerryback/kerryback-public#subdirectory=plugins/litdb"
EXTRAS = "[embeddings,pdf]"

THIS = Path(__file__).resolve()
# Local source root = the nearest ancestor directory containing litdb's own
# pyproject.toml, if we're running from a checkout. This works whether the script
# lives at scripts/setup.py or bundled inside skills/litdb/. It is None when
# running from an installed skill (no checkout above it), so we install from
# GitHub. The name check avoids matching an unrelated project's pyproject.toml.
def _find_source_root(start: Path):
    for d in (start, *start.parents):
        pp = d / "pyproject.toml"
        try:
            if pp.is_file() and 'name = "litdb"' in pp.read_text(encoding="utf-8"):
                return d
        except OSError:
            pass
    return None


SOURCE_ROOT = _find_source_root(THIS.parent)

MIN_PY = (3, 10)


def litdb_home() -> Path:
    override = os.environ.get("LITDB_HOME")
    return Path(override).expanduser() if override else Path.home() / ".litdb"


def venv_dir() -> Path:
    return litdb_home() / ".venv"


def venv_python(venv: Path | None = None) -> Path:
    venv = venv or venv_dir()
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def _fts5_ok(python: Path) -> bool:
    probe = "import sqlite3;sqlite3.connect(':memory:').execute('CREATE VIRTUAL TABLE t USING fts5(x)')"
    return _run([str(python), "-c", probe]).returncode == 0


def gather() -> dict:
    vpy = venv_python()
    venv_ok = vpy.exists()
    installed = _run([str(vpy), "-c", "import litdb"]).returncode == 0 if venv_ok else False
    return {
        "os": os.name,
        "python": sys.version.split()[0],
        "python_ok": sys.version_info[:2] >= MIN_PY,
        "uv": shutil.which("uv"),
        "litdb_home": str(litdb_home()),
        "venv": str(venv_dir()),
        "venv_exists": venv_ok,
        "litdb_installed": installed,
        "fts5_ok": _fts5_ok(vpy) if venv_ok else False,
        "source": "local checkout" if SOURCE_ROOT else "github",
        "ready": bool(venv_ok and installed),
    }


def install_spec(editable: bool) -> tuple[list[str], str]:
    """Return (pip-args-for-source, human description)."""
    if SOURCE_ROOT is not None:
        if editable:
            return (["-e", f"{SOURCE_ROOT}{EXTRAS}"], f"editable from {SOURCE_ROOT}")
        return ([f"{SOURCE_ROOT}{EXTRAS}"], f"from {SOURCE_ROOT}")
    return ([f"litdb{EXTRAS} @ {GIT_URL}"], f"from {GIT_URL}")


def cmd_check(as_json: bool) -> int:
    st = gather()
    if as_json:
        print(json.dumps(st, indent=2))
        return 0
    print("litdb setup — status")
    print(f"  python           {st['python']} ({'ok' if st['python_ok'] else f'need >= {MIN_PY[0]}.{MIN_PY[1]}'})")
    print(f"  uv               {st['uv'] or 'not found (optional; speeds install)'}")
    print(f"  litdb home       {st['litdb_home']}")
    print(f"  venv             {'present' if st['venv_exists'] else 'missing'}  [{st['venv']}]")
    print(f"  litdb installed  {'yes' if st['litdb_installed'] else 'no'}")
    print(f"  sqlite FTS5      {'ok' if st['fts5_ok'] else 'unknown'}")
    print(f"  install source   {st['source']}")
    print(f"  READY            {'yes' if st['ready'] else 'no — run: python3 setup.py --yes'}")
    return 0


def cmd_runtime_path() -> int:
    vpy = venv_python()
    if vpy.exists() and _run([str(vpy), "-c", "import litdb"]).returncode == 0:
        print(str(vpy))
        return 0
    return 1


def show_plan(editable: bool) -> int:
    st = gather()
    _, desc = install_spec(editable)
    print("litdb setup — plan (dry run; nothing changed)")
    if sys.version_info[:2] < MIN_PY:
        print(f"  ! Python {MIN_PY[0]}.{MIN_PY[1]}+ required (found {st['python']}); install it first.")
    if st["ready"]:
        print("  Runtime already installed. Nothing to do.")
        return 0
    tool = "uv" if st["uv"] else "python -m venv + pip"
    print(f"  1. create venv at {venv_dir()}  (using {tool})")
    print(f"  2. install litdb {desc}")
    print("  3. verify FTS5 and initialize the database")
    print("\nRun again with --yes to proceed. System software is never installed for you.")
    return 0


def do_install(editable: bool) -> int:
    if sys.version_info[:2] < MIN_PY:
        print(f"ERROR: Python {MIN_PY[0]}.{MIN_PY[1]}+ required (found {sys.version.split()[0]}).", file=sys.stderr)
        return 2

    home = litdb_home()
    home.mkdir(parents=True, exist_ok=True)
    have_uv = bool(shutil.which("uv"))
    vpy = venv_python()

    # 1) venv
    if not vpy.exists():
        r = _run(["uv", "venv", str(venv_dir())]) if have_uv else _run([sys.executable, "-m", "venv", str(venv_dir())])
        if r.returncode != 0:
            print("ERROR: failed to create venv:\n" + r.stderr, file=sys.stderr)
            return 1

    # 2) install package (non-editable by default -> checkout becomes disposable)
    src_args, desc = install_spec(editable)
    if have_uv:
        r = _run(["uv", "pip", "install", "--python", str(vpy), *src_args])
    else:
        r = _run([str(vpy), "-m", "pip", "install", *src_args])
    if r.returncode != 0:
        print(f"ERROR: failed to install litdb ({desc}):\n" + r.stderr, file=sys.stderr)
        return 1

    # 3) verify + init
    if not _fts5_ok(vpy):
        print("ERROR: this Python's sqlite3 lacks FTS5.", file=sys.stderr)
        return 1
    r = _run([str(vpy), "-m", "litdb", "init"])
    if r.returncode != 0:
        print("ERROR: failed to initialize the database:\n" + r.stderr, file=sys.stderr)
        return 1

    print("Done. The litdb runtime is installed.")
    print(f"  home:    {home}")
    print(f"  runtime: {vpy}")
    print(f"  {r.stdout.strip()}")
    print("The runtime lives in ~/.litdb; any source checkout is disposable.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="litdb bootstrap / dependency setup")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--runtime-path", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--editable", "--dev", dest="editable", action="store_true")
    args = ap.parse_args(argv)

    if args.runtime_path:
        return cmd_runtime_path()
    if args.check:
        return cmd_check(args.json)
    if args.yes:
        return do_install(args.editable)
    return show_plan(args.editable)


if __name__ == "__main__":
    raise SystemExit(main())
