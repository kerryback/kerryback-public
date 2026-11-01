#!/usr/bin/env python3
"""Curation backend for the learned house style.

`style_capture.py` (the hook) fills a local buffer with corrections. This is
what `/style-learn` drives to turn that buffer into rules:

    python3 tools/style.py pending            what has been captured, uncurated
    python3 tools/style.py harvest            add your own uncommitted rewrites
    python3 tools/style.py accept             mark the backlog curated
    python3 tools/style.py check              rule count, size, and stale rules
    python3 tools/style.py stats              where the corrections came from
    python3 tools/style.py rules              the project rules now in the guide

Rules live in `writing-guide.md`, which is the project's single writing
standard. There is no separate file of conventions and there should never be
one: a rule about prose goes into the section of the guide it bears on, and a
rule that contradicts what is already there replaces it rather than sitting
next to it.

The division of labour is deliberate. This file does storage, deduplication,
diff parsing and the size cap — everything with a right answer. Deciding that
six corrections are one rule, what that rule says, and which existing line it
has to rewrite is judgment, so it lives in the slash command and ends at a
human saying yes.

The buffer is per author and gitignored; the guide is committed. That is the
whole reason coauthors with different taste can share one standard: what you
were corrected on stays yours until someone promotes it deliberately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from style_capture import (  # noqa: E402
    GUIDE, MAX_PASSAGE, MIN_PASSAGE, author_slug, extract_learned, is_prose,
    logs_dir, project_root,
)

# The cap is on rules this project added, not on the guide, which is a manual
# and is meant to be long. These are what gets put in context every session, so
# the ceiling is what a person will actually read before writing a paragraph.
MAX_RULES = 40
MAX_CHARS = 6000
STALE_DAYS = 400


def root_or_die() -> Path:
    root = project_root()
    if root is None:
        sys.exit("no project root here (looked for a project/ directory)")
    return root


def obs_path(root: Path) -> Path:
    return logs_dir(root) / "style-observations.jsonl"


def mark_path(root: Path) -> Path:
    return logs_dir(root) / "style-watermark"


def rules_path(root: Path) -> Path:
    return root / GUIDE


def load_obs(root: Path) -> list[dict]:
    f = obs_path(root)
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def fingerprint(rec: dict) -> str:
    key = f"{rec.get('file','')}|{rec.get('before','')}|{rec.get('after','')}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def watermark(root: Path) -> str:
    f = mark_path(root)
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


def pending(root: Path) -> list[dict]:
    mark = watermark(root)
    return [r for r in load_obs(root) if r.get("ts", "") > mark]


# ---------------------------------------------------------------- harvest


def diff_hunks(root: Path, since: str) -> list[tuple[str, str, str]]:
    """(file, before, after) for each changed hunk in the draft tree.

    Your own rewrites of Claude's prose are the strongest signal there is — you
    are showing the fix rather than describing it — and no hook can see them,
    because you made them in your editor.
    """
    try:
        raw = subprocess.run(
            ["git", "diff", "--unified=0", "--no-color", since, "--", "."],
            capture_output=True, text=True, cwd=root, timeout=60,
        ).stdout
    except Exception:
        return []
    hunks: list[tuple[str, str, str]] = []
    cur_file = ""
    before: list[str] = []
    after: list[str] = []

    def flush() -> None:
        b, a = "\n".join(before).strip(), "\n".join(after).strip()
        if cur_file and b and a and b != a and len(b) >= MIN_PASSAGE:
            hunks.append((cur_file, b[:MAX_PASSAGE], a[:MAX_PASSAGE]))
        before.clear()
        after.clear()

    for line in raw.splitlines():
        if line.startswith("+++ b/"):
            flush()
            cur_file = line[6:].strip()
        elif line.startswith("@@"):
            flush()
        elif line.startswith("-") and not line.startswith("---"):
            before.append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            after.append(line[1:])
    flush()
    return [(f, b, a) for f, b, a in hunks if is_prose(root, f)]


def harvest(root: Path, since: str) -> int:
    """Append your own edits to the buffer, skipping anything already there.

    Exact duplicates of Claude's own recorded edits are dropped, so a hunk that
    is simply Claude's uncommitted work is not re-read as your correction of it.
    A hunk where you edited on top of Claude's edit is not an exact match and
    will show up — curation is where that gets judged, which is why curation is
    a human step.
    """
    seen = {fingerprint(r) for r in load_obs(root)}
    rows = []
    for f, b, a in diff_hunks(root, since):
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "author": author_slug(),
            "source": "self-edit",
            "file": f,
            "instruction": "",
            "before": b,
            "after": a,
            "truncated": False,
        }
        if fingerprint(rec) in seen:
            continue
        seen.add(fingerprint(rec))
        rows.append(rec)
    if rows:
        with obs_path(root).open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


# ------------------------------------------------------------------ rules


def check(root: Path) -> int:
    if not rules_path(root).exists():
        sys.exit(f"no {GUIDE} at the repo root — the guide is where rules live")
    rules = extract_learned(root)
    total = sum(len(r["text"]) + sum(len(e) for e in r["extra"]) for r in rules)
    print(f"project rules   {len(rules)} / {MAX_RULES}")
    print(f"injected size   {total} / {MAX_CHARS} chars")
    today = datetime.now(timezone.utc).date()
    stale = []
    for r in rules:
        try:
            age = (today - datetime.strptime(r["last"], "%Y-%m-%d").date()).days
        except Exception:
            continue
        if age > STALE_DAYS and r["hits"] <= 1:
            stale.append((r["text"], age))
    over = len(rules) > MAX_RULES or total > MAX_CHARS
    if over:
        print("\nOVER CAP — merge or retire before adding. The cap is the point:")
        print("these lines go into context every session, so they stay short")
        print("enough to be read. Prefer one general rule to three specific ones.")
    if stale:
        print(f"\nstale ({STALE_DAYS}+ days, rarely triggered) — candidates to retire:")
        for t, age in stale:
            print(f"  {age:>4}d  {t[:70]}")
    if not over and not stale:
        print("\nwithin cap, nothing stale")
    return 1 if over else 0


# ------------------------------------------------------------------- cli


def cmd_pending(root: Path, args) -> int:
    rows = pending(root)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    if not rows:
        print("nothing pending — the backlog is curated")
        return 0
    print(f"{len(rows)} uncurated observation(s) since {watermark(root) or 'the beginning'}\n")
    for i, r in enumerate(rows, 1):
        print(f"--- {i}. {r.get('file')}  [{r.get('source')}]  {r.get('ts','')[:19]}")
        if r.get("instruction"):
            print(f"    asked: {r['instruction'].strip()[:400]}")
        print(f"    before: {r.get('before','').strip()[:600]}")
        print(f"    after:  {r.get('after','').strip()[:600]}")
        print()
    return 0


def cmd_harvest(root: Path, args) -> int:
    n = harvest(root, args.since)
    print(f"harvested {n} new hunk(s) from `git diff {args.since}`")
    return 0


def cmd_accept(root: Path, args) -> int:
    rows = load_obs(root)
    if not rows:
        print("nothing to mark")
        return 0
    latest = max(r.get("ts", "") for r in rows)
    mark_path(root).write_text(latest + "\n", encoding="utf-8")
    print(f"watermark set to {latest} — {len(pending(root))} pending after this")
    return 0


def cmd_stats(root: Path, args) -> int:
    rows = load_obs(root)
    by_src: dict[str, int] = {}
    by_file: dict[str, int] = {}
    for r in rows:
        by_src[r.get("source", "?")] = by_src.get(r.get("source", "?"), 0) + 1
        by_file[r.get("file", "?")] = by_file.get(r.get("file", "?"), 0) + 1
    print(f"{len(rows)} observation(s) captured, {len(pending(root))} uncurated")
    for k, v in sorted(by_src.items(), key=lambda x: -x[1]):
        print(f"  {v:>4}  {k}")
    print()
    for k, v in sorted(by_file.items(), key=lambda x: -x[1])[:10]:
        print(f"  {v:>4}  {k}")
    return 0


def cmd_rules(root: Path, args) -> int:
    rules = extract_learned(root)
    if not rules:
        print(f"no project rules in {GUIDE} yet — the guide is all published craft")
        return 0
    for r in rules:
        hits = f"{r['hits']}x" if r["hits"] else "—"
        print(f"{GUIDE}:{r['line']:<5} [{hits:>4}] {r['section']}")
        print(f"    {r['text']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pending", help="uncurated observations")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_pending)

    p = sub.add_parser("harvest", help="add your own rewrites from git")
    p.add_argument("--since", default="HEAD", help="revision to diff against (default HEAD)")
    p.set_defaults(fn=cmd_harvest)

    p = sub.add_parser("accept", help="mark the backlog curated")
    p.set_defaults(fn=cmd_accept)

    p = sub.add_parser("check", help="cap and staleness")
    p.set_defaults(fn=lambda root, args: check(root))

    p = sub.add_parser("stats", help="what has been captured")
    p.set_defaults(fn=cmd_stats)

    p = sub.add_parser("rules", help="the project rules now in the guide")
    p.set_defaults(fn=cmd_rules)

    args = ap.parse_args()
    return args.fn(root_or_die(), args)


if __name__ == "__main__":
    sys.exit(main())
