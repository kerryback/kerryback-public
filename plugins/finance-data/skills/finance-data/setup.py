#!/usr/bin/env python3
"""finance-data runtime setup — build/repair the dedicated fetch environment.

finance-data fetches data with third-party libraries (yfinance, pandas-datareader,
finnhub-python, requests, pandas). Installing those into "the user's Python" is
unreliable on machines with several Python environments — `pip` and `python` can
disagree about what's installed. So the skill uses a FIXED, private virtualenv:

  ~/.finance-data/venv        (override the home with FINANCE_DATA_HOME)

Every fetch runs through this venv's interpreter, never the system Python. The
fetched data is written to a CSV in the user's project, which their own analysis
environment reads back — that file is the hand-off between the two environments.

Modes:
  --check         report what's present/missing (add --json for machine output)
  --runtime-path  print the venv's python if usable, else exit 1
  (default)       show the plan (dry run) without changing anything
  --yes           execute: create the venv and install the libraries

Never installs system software (Python itself). Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Libraries the fetch recipes import. Transitive deps (lxml, numpy, …) come along.
LIBS = ["pandas", "yfinance", "pandas-datareader", "finnhub-python", "requests"]
# Import names to verify after install (finnhub-python imports as `finnhub`).
IMPORTS = ["pandas", "yfinance", "pandas_datareader", "finnhub", "requests"]
MIN_PY = (3, 9)


def home() -> Path:
    override = os.environ.get("FINANCE_DATA_HOME")
    return Path(override).expanduser() if override else Path.home() / ".finance-data"


def venv_dir() -> Path:
    return home() / "venv"


def venv_python(venv: Path | None = None) -> Path:
    venv = venv or venv_dir()
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def _imports_ok(python: Path) -> bool:
    return _run([str(python), "-c", "import " + ", ".join(IMPORTS)]).returncode == 0


def gather() -> dict:
    vpy = venv_python()
    venv_ok = vpy.exists()
    return {
        "os": os.name,
        "python": sys.version.split()[0],
        "python_ok": sys.version_info[:2] >= MIN_PY,
        "uv": shutil.which("uv"),
        "home": str(home()),
        "venv": str(venv_dir()),
        "venv_exists": venv_ok,
        "imports_ok": _imports_ok(vpy) if venv_ok else False,
        "ready": bool(venv_ok and _imports_ok(vpy)),
    }


def cmd_check(as_json: bool) -> int:
    st = gather()
    if as_json:
        print(json.dumps(st, indent=2))
        return 0
    print("finance-data setup — status")
    print(f"  python          {st['python']} ({'ok' if st['python_ok'] else f'need >= {MIN_PY[0]}.{MIN_PY[1]}'})")
    print(f"  uv              {st['uv'] or 'not found (optional; speeds install)'}")
    print(f"  home            {st['home']}")
    print(f"  venv            {'present' if st['venv_exists'] else 'missing'}  [{st['venv']}]")
    print(f"  libraries       {'import ok' if st['imports_ok'] else 'missing/incomplete'}")
    print(f"  READY           {'yes' if st['ready'] else 'no — run: python3 setup.py --yes'}")
    return 0


def cmd_runtime_path() -> int:
    vpy = venv_python()
    if vpy.exists() and _imports_ok(vpy):
        print(str(vpy))
        return 0
    return 1


def show_plan() -> int:
    st = gather()
    print("finance-data setup — plan (dry run; nothing changed)")
    if sys.version_info[:2] < MIN_PY:
        print(f"  ! Python {MIN_PY[0]}.{MIN_PY[1]}+ required (found {st['python']}); install it first.")
    if st["ready"]:
        print("  Runtime already installed. Nothing to do.")
        return 0
    tool = "uv" if st["uv"] else "python -m venv + pip"
    print(f"  1. create venv at {venv_dir()}  (using {tool})")
    print(f"  2. install: {', '.join(LIBS)}")
    print("\nRun again with --yes to proceed. The system Python is never modified.")
    return 0


def do_install() -> int:
    if sys.version_info[:2] < MIN_PY:
        print(f"ERROR: Python {MIN_PY[0]}.{MIN_PY[1]}+ required (found {sys.version.split()[0]}).", file=sys.stderr)
        return 2

    home().mkdir(parents=True, exist_ok=True)
    have_uv = bool(shutil.which("uv"))
    vpy = venv_python()

    if not vpy.exists():
        r = _run(["uv", "venv", str(venv_dir())]) if have_uv else _run([sys.executable, "-m", "venv", str(venv_dir())])
        if r.returncode != 0:
            print("ERROR: failed to create venv:\n" + r.stderr, file=sys.stderr)
            return 1

    if have_uv:
        r = _run(["uv", "pip", "install", "--python", str(vpy), "--upgrade", *LIBS])
    else:
        _run([str(vpy), "-m", "pip", "install", "--upgrade", "pip"])
        r = _run([str(vpy), "-m", "pip", "install", "--upgrade", *LIBS])
    if r.returncode != 0:
        print("ERROR: failed to install libraries:\n" + r.stderr, file=sys.stderr)
        return 1

    if not _imports_ok(vpy):
        print("ERROR: libraries did not import after install.", file=sys.stderr)
        return 1

    print("Done. The finance-data runtime is installed.")
    print(f"  home:    {home()}")
    print(f"  runtime: {vpy}")
    print("Run every fetch with that interpreter; save results as CSV for your analysis environment.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="finance-data runtime setup")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--runtime-path", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)

    if args.runtime_path:
        return cmd_runtime_path()
    if args.check:
        return cmd_check(args.json)
    if args.yes:
        return do_install()
    return show_plan()


if __name__ == "__main__":
    raise SystemExit(main())
