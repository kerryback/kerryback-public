"""Is this person set up to work here? Run at the start of every session.

    python3 tools/onboard.py            # human-readable report
    python3 tools/onboard.py --json     # same, machine-readable
    python3 tools/onboard.py --mark     # record that onboarding completed

Checks the preconditions rather than trusting a flag, because a flag goes stale:
a second machine, a new shell, a fresh clone all look "onboarded" to a marker
file and are not. The marker only records that the WALKTHROUGH happened; the
checks below decide whether the setup actually works right now.

Exit code is 0 when everything required passes, 1 otherwise, so a hook or a
script can gate on it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())

# Set by the research skill to <PROJECT>_DATA.
DATA_ENV = "@@DATA_ENV@@"


def sh(*args) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def slug_of(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()


def checks() -> list[dict]:
    out: list[dict] = []

    def add(key, ok, detail, fix=None, required=True):
        out.append({"key": key, "ok": bool(ok), "detail": detail, "fix": fix,
                    "required": required})

    # 1. identity — everything you own is named from this
    name = sh("git", "-C", str(REPO), "config", "user.name")
    slug = slug_of(name) if name else ""
    add("git.name", bool(name) and slug not in ("", "anon"),
        f"user.name = {name!r} -> slug {slug!r}" if name else "user.name is not set",
        'git config user.name "Your Name"')

    email = sh("git", "-C", str(REPO), "config", "user.email")
    add("git.email", bool(email), email or "user.email is not set",
        'git config user.email "you@example.edu"')

    # 2. data
    data = os.environ.get(DATA_ENV, "")
    add(f"env.{DATA_ENV}", bool(data) and Path(data).is_dir(),
        data or "not set",
        f'add to ~/.zshrc:  export {DATA_ENV}="@@DATA_ROOT@@/<slug>"')

    if data:
        g = Path(data).parent / "global"
        add("data.global", g.is_dir() and any(g.glob("*.parquet")),
            f"{g} ({len(list(g.glob('*.parquet'))) if g.is_dir() else 0} canonical files)",
            "ask for access to the shared data folder, and wait for it to sync")
    else:
        add("data.global", False, f"cannot check until {DATA_ENV} is set", None)

    # 3. your own folders
    if slug:
        for d in (REPO / "project" / slug, REPO / "workspaces" / slug):
            add(f"dir.{d.parent.name}", d.is_dir(), str(d.relative_to(REPO)),
                f"mkdir -p {d.relative_to(REPO)}")

    # 4. hooks — git only runs hooks it is told to
    hp = sh("git", "-C", str(REPO), "config", "core.hooksPath")
    add("git.hooksPath", hp == "tools/githooks", hp or "not set",
        "git config core.hooksPath tools/githooks")

    # 5. the debate team (only if this project has one)
    if (REPO / "project" / "global" / "config.toml").exists():
        add("env.OPENROUTER_API_KEY", bool(os.environ.get("OPENROUTER_API_KEY")),
            "set" if os.environ.get("OPENROUTER_API_KEY") else "not set",
            "get a key at openrouter.ai, then add to ~/.zshrc: export OPENROUTER_API_KEY=...")

    # 6. python
    venv = REPO / ".venv" / "bin" / "python"
    add("python.venv", venv.exists(), str(venv.relative_to(REPO)) if venv.exists() else "no .venv",
        "python3 -m venv .venv && .venv/bin/pip install -r requirements.txt")
    if venv.exists():
        # read the requirement names from requirements.txt rather than repeating
        # them here — a second hardcoded list is a second thing to drift.
        IMPORT_NAME = {"beautifulsoup4": "bs4", "scikit-learn": "sklearn",
                       "psycopg2-binary": "psycopg2", "ipython": "IPython",
                       "pyarrow": "pyarrow", "sqlalchemy": "sqlalchemy"}
        req = REPO / "requirements.txt"
        names = []
        if req.exists():
            for line in req.read_text().splitlines():
                line = line.split("#")[0].strip()
                if line:
                    pkg = re.split(r"[<>=!~]", line)[0].strip()
                    names.append(IMPORT_NAME.get(pkg, pkg.replace("-", "_")))
        missing = [m for m in names
                   if subprocess.run([str(venv), "-c", f"import {m}"],
                                     capture_output=True).returncode]
        add("python.packages", not missing,
            f"all {len(names)} present" if not missing else f"missing: {', '.join(missing)}",
            ".venv/bin/pip install -r requirements.txt" if missing else None)

    add("tool.latex", bool(shutil.which("pdflatex")),
        shutil.which("pdflatex") or "pdflatex not found (only needed to build the paper)",
        "brew install --cask mactex-no-gui", required=False)

    return out


def marker(slug: str) -> Path:
    return REPO / "project" / slug / "onboarded"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--mark", action="store_true", help="record that onboarding completed")
    args = ap.parse_args()

    res = checks()
    name = sh("git", "-C", str(REPO), "config", "user.name")
    slug = slug_of(name) if name else ""
    required_ok = all(c["ok"] for c in res if c["required"])

    if args.mark:
        if not slug:
            print("cannot mark: git user.name is not set", file=sys.stderr)
            return 1
        if not required_ok:
            print("cannot mark: required checks still failing", file=sys.stderr)
            return 1
        m = marker(slug)
        m.parent.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        m.write_text(f"{slug}\n{datetime.now().astimezone().isoformat(timespec='seconds')}\n",
                     encoding="utf-8")
        print(f"marked onboarded: {m.relative_to(REPO)}")
        return 0

    done = slug and marker(slug).exists()
    payload = {"slug": slug, "onboarded": bool(done), "ready": required_ok, "checks": res}

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0 if required_ok else 1

    print(f"author : {slug or '(unknown — git user.name not set)'}")
    print(f"status : {'ready' if required_ok else 'NOT READY'}"
          f"{'' if done else '   (no onboarding marker — first time here)'}\n")
    for c in res:
        mark = "ok  " if c["ok"] else ("FAIL" if c["required"] else "warn")
        print(f"  [{mark}] {c['key']:<24} {c['detail']}")
        if not c["ok"] and c["fix"]:
            print(f"         fix: {c['fix']}")
    if not required_ok:
        print("\nNot ready. See the onboarding section of CLAUDE.md.")
    return 0 if required_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
