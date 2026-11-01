"""Assemble the project's timeline from the records that already exist.

Three sources, all committed, none of them a transcript:

  changelog  `project/global/state/` — one file per entry (see tools/state.py),
             an author and the reason a thing changed. This is the spine: it is
             the only source that says WHY.
  commit     `git log` — what landed and when.
  run        `project/<author>/logs/runs.jsonl` — a script execution that
             produced a reportable result.

Debate briefs are deliberately not a source. They are the input to a decision,
not the decision, they are gitignored, and a timeline assembled from prompts
answers a question nobody asked.

Nothing here reads a session log, and nothing needs to: a timeline is a sequence
of decisions and the artifacts around them, and those are all written down at the
moment they happen.

Usage:
    python3 -m tools.chronology --since 2026-08-01 --human
    python3 -m tools.chronology --since "last week" --kinds changelog,commit
    python3 -m tools.chronology --author jane-doe --limit 40

`--since` takes an ISO date or anything `git log --since` understands; for the
non-git sources a relative phrase is resolved by asking git to date it, so one
flag means the same thing everywhere. JSON on stdout by default, newest first.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

KINDS = ("changelog", "commit", "run")

def _repo_root(start: Path) -> Path:
    for p in [start.resolve(), *start.resolve().parents]:
        if (p / "CLAUDE.md").exists() or (p / ".git").exists():
            return p
    return start.resolve()


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except Exception:
        return ""


def resolve_since(root: Path, since: str | None) -> str | None:
    """Normalize --since to an ISO date so every source filters identically.

    git understands "last week" and "3 days ago"; the JSONL and filename sources
    do not, so let git do the parsing once and hand the answer to everyone.
    """
    if not since:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", since):
        return since
    out = _git(root, "log", "-1", "--format=%cs", f"--since={since}", "--reverse")
    first = out.strip().splitlines()
    return first[0] if first else None


# --------------------------------------------------------------------------- #
# sources
# --------------------------------------------------------------------------- #

def changelog_entries(root: Path) -> list[dict]:
    """Read `project/global/state/` — one file per entry, front matter on each.

    The state used to be a single `state.md` whose top block this function
    parsed. It is a directory now, so that several people can add entries at the
    same time without git having to merge one file; see `tools/state.py`.
    """
    try:
        from .state import load
    except ImportError:                       # running as a loose script
        return []
    out: list[dict] = []
    for e in load(root):
        out.append({"kind": "changelog", "date": e["date"], "author": e["author"],
                    "summary": e["title"], "body": " ".join(e["body"].split())})
    return out


def _slug(name: str) -> str:
    """Same normalization `tools.runid` applies to `git config user.name`.

    Git records a commit author as a display name ("Jane Doe") while the
    state entries and run records carry the slug ("jane-doe"). One author
    filter has to match all three, so slugify here rather than making the caller
    know which source spells a person which way.
    """
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower() or "anon"


def commits(root: Path, since: str | None) -> list[dict]:
    fmt = "%H%x1f%cs%x1f%an%x1f%s"
    args = ["log", f"--format={fmt}", "--no-merges"]
    if since:
        args.append(f"--since={since}")
    rows = []
    for line in _git(root, *args).splitlines():
        parts = line.split("\x1f")
        if len(parts) == 4:
            sha, date, name, subject = parts
            rows.append({"kind": "commit", "date": date, "author": _slug(name),
                         "author_name": name, "summary": subject, "ref": sha[:7]})
    return rows



def runs(root: Path) -> list[dict]:
    rows = []
    for f in sorted((root / "project").glob("*/logs/runs.jsonl")):
        author = f.parent.parent.name
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = str(r.get("ts") or "")
            script = str(r.get("script") or "").replace("\\", "/").split("/")[-1]
            rows.append({
                "kind": "run", "date": ts[:10], "time": ts[11:16],
                "author": r.get("author") or author,
                "summary": f"ran {script}" + ("" if r.get("status") == "ok"
                                              else f" [{r.get('status')}]"),
                "ref": r.get("commit"),
                "outputs": r.get("outputs") or [],
            })
    return rows


# --------------------------------------------------------------------------- #
# the gap check
# --------------------------------------------------------------------------- #

# Commits the tooling makes on its own. Work landed under these is not a
# decision anybody failed to write down.
_MECHANICAL = re.compile(
    r"^(round (lock|unlock):|Refresh checkpoint\b|Merge\b|Initial commit\b)", re.I
)


def gaps(root: Path, since: str | None = None) -> dict:
    """Commits that landed with no changelog entry dated at or after them.

    Entries are written by `/handover`, which only runs when somebody
    invokes it. Work that ends without it leaves the commits in place
    and the REASON unrecorded — which is invisible, because the
    commits look fine. This makes it visible.

    Reported per author, because the person who can still remember why is the
    one who did it.
    """
    entries = changelog_entries(root)
    newest = max((e["date"] for e in entries), default=None)
    if since:
        newest = max(newest or "", since) or None

    undocumented = [
        c for c in commits(root, None)
        if (newest is None or c["date"] > newest)
        and not _MECHANICAL.match(c["summary"])
    ]
    by_author: dict[str, int] = {}
    for c in undocumented:
        by_author[c["author"]] = by_author.get(c["author"], 0) + 1
    return {
        "newest_changelog_entry": newest,
        "undocumented_commits": undocumented,
        "count": len(undocumented),
        "by_author": by_author,
    }


def report_gaps(root: Path, since: str | None = None) -> int:
    """Print the gap in human form. Returns the number of undocumented commits."""
    g = gaps(root, since)
    if not g["count"]:
        last = g["newest_changelog_entry"]
        print(f"changelog is current (newest entry {last})" if last
              else "no changelog entries yet, and no commits to document")
        return 0

    last = g["newest_changelog_entry"] or "never"
    print(f"{g['count']} commit(s) since the last changelog entry ({last}) "
          f"with no recorded reason:\n")
    for c in g["undocumented_commits"][:15]:
        print(f"  {c['date']}  {c['author']:<16} {c['summary']}")
    if g["count"] > 15:
        print(f"  … and {g['count'] - 15} more")
    print("\nWhat changed is in git; WHY is not written anywhere. Add an entry to\n"
          "project/global/state/ — `python3 -m tools.state new \"…\"` writes one — while\n"
          "somebody still remembers the reason.")
    return g["count"]


# --------------------------------------------------------------------------- #

def build(root: Path, *, since=None, kinds=KINDS, author=None) -> list[dict]:
    since = resolve_since(root, since)
    rows: list[dict] = []
    if "changelog" in kinds:
        rows += changelog_entries(root)
    if "commit" in kinds:
        rows += commits(root, since)
    if "run" in kinds:
        rows += runs(root)
    if since:
        rows = [r for r in rows if (r.get("date") or "") >= since]
    if author:
        want = _slug(author)
        rows = [r for r in rows if r.get("author") == want]
    # Newest first; within a day, decisions before the artifacts around them.
    order = {"changelog": 0, "commit": 1, "run": 2}
    rows.sort(key=lambda r: (r.get("date") or "", -order.get(r["kind"], 9)),
              reverse=True)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="assemble the project timeline")
    ap.add_argument("--project", default=".", help="project root")
    ap.add_argument("--since", help="ISO date, or anything git --since takes")
    ap.add_argument("--author", help="filter to one author slug")
    ap.add_argument("--kinds", default=",".join(KINDS),
                    help=f"comma-separated subset of {','.join(KINDS)}")
    ap.add_argument("--limit", type=int, default=0, help="newest N entries")
    ap.add_argument("--human", action="store_true", help="readable, not JSON")
    ap.add_argument("--gap", action="store_true",
                    help="show commits that landed with no changelog entry after them")
    args = ap.parse_args()

    root = _repo_root(Path(args.project))
    if args.gap:
        if args.human:
            report_gaps(root, args.since)
        else:
            json.dump(gaps(root, args.since), __import__("sys").stdout,
                      ensure_ascii=False, indent=2)
            print()
        return

    kinds = tuple(k.strip() for k in args.kinds.split(",") if k.strip())
    rows = build(root, since=args.since, kinds=kinds, author=args.author)
    if args.limit:
        rows = rows[: args.limit]

    if not args.human:
        json.dump(rows, __import__("sys").stdout, ensure_ascii=False, indent=2)
        print()
        return

    day = None
    for r in rows:
        if r["date"] != day:
            day = r["date"]
            print(f"\n{day}")
        who = r.get("author") or "?"
        print(f"  [{r['kind']:<9}] {who:<16} {r['summary']}")
        if r["kind"] == "changelog" and r.get("body"):
            body = r["body"]
            print(f"                                 {body[:240]}"
                  f"{'…' if len(body) > 240 else ''}")


if __name__ == "__main__":
    main()
