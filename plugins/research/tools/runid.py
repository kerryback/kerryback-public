"""Who is working, and which run: `<author>-<YYYYMMDD>-<HHMMSS>`.

Coauthors share this repo, so anything a run produces carries who made it and
when. Nothing two people generate can collide, and a directory listing says who
did what without opening anything.

The author slug also picks the directory: `project/<author>/` and
`workspaces/<author>/` are yours, and no one else writes there. The slug comes
from `git config user.name`, so it needs no configuration — but it must be right,
because everything you own is named from it.

Usage (the Coordinator runs this via Bash):
    python -m tools.runid --project . --new   # start a run, print its id
    python -m tools.runid --project .         # print the current id
    python -m tools.runid --stamp             # a fresh stamp, nothing written
    python -m tools.runid --author            # just the author slug

`--stamp` is for artifacts written SEVERAL times within one round — the briefs,
which are rewritten each pass of the debate loop. They cannot share the round's
run id or each pass would overwrite the last, so each takes the time it was
written. Everything logged by the run itself uses the run id instead.
"""
from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path


def user_slug() -> str:
    """Filename-safe identity: git's `user.name`, else the OS login, else `anon`.

    git first because in a shared repo that is the name the collaborators already
    know each other by — the same string that shows up in `git log`.
    """
    name = ""
    try:
        name = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        pass
    name = name or os.environ.get("USER") or os.environ.get("USERNAME") or ""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return slug or "anon"


def new_run_id() -> str:
    # Local time, not UTC: this is a label a human reads against their own clock.
    return f"{user_slug()}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def author_dir(project_dir: str | Path) -> Path:
    """This author's own folder: `project/<author>/`. Created if absent.

    Every coauthor writes only here. Nothing outside `project/global/` is shared,
    which is what keeps one person's Analyst from reading another's working notes.
    """
    d = Path(project_dir) / "project" / user_slug()
    (d / "logs").mkdir(parents=True, exist_ok=True)
    return d


def stamp_run(project_dir: str | Path) -> str:
    """Begin a new run and record it. Called at the top of each round."""
    rid = new_run_id()
    (author_dir(project_dir) / "run").write_text(rid + "\n", encoding="utf-8")
    return rid


def current_run_id(project_dir: str | Path) -> str:
    """The run anything logged right now belongs to; created if absent."""
    f = author_dir(project_dir) / "run"
    if f.exists():
        rid = f.read_text(encoding="utf-8").strip()
        if rid:
            return rid
    return stamp_run(project_dir)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--project", help="project root (not needed with --stamp)")
    ap.add_argument("--new", action="store_true", help="start a new run")
    ap.add_argument("--stamp", action="store_true",
                    help="print a fresh <author>-<date>-<time>; writes nothing")
    ap.add_argument("--author", action="store_true", help="print just the author slug")
    args = ap.parse_args()
    if args.author:
        print(user_slug())
        return
    if args.stamp:
        print(new_run_id())
        return
    if not args.project:
        ap.error("--project is required unless you pass --stamp")
    root = Path(args.project).resolve()
    print(stamp_run(root) if args.new else current_run_id(root))


if __name__ == "__main__":
    main()
