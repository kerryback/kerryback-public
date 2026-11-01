"""Project state as a directory of small files, so several people can write at once.

The obvious design is one `state.md` holding the thesis, the settled facts and a
changelog. It fails the moment two people work the same day: it is long prose
that each round rewrites, git cannot merge two rewrites of long prose, and the
only fix that works on one file is to let one person write at a time. That is a
lock, and a lock means your collaborators wait.

So the state is a DIRECTORY:

    project/global/state/
      core.md                     thesis, settled facts, open questions, killed
                                  ideas — curated, short, rewritten freely
      entries/<date>-<author>-<slug>.md    one dated entry per file
      blocks/<date>-<author>-<slug>.md     one topic block per file

Adding an entry adds a NEW FILE. Two people adding entries at the same moment
add two different files, and git merges file additions with no conflict and no
conversation. Nobody claims anything and nobody waits.

    python3 -m tools.state show                  the whole state, newest first
    python3 -m tools.state show --kind entries   just the dated entries
    python3 -m tools.state new "what changed"    start an entry, correctly named
    python3 -m tools.state check                 front matter parses, names sort

`show` reads and prints. It writes no file, commits nothing, pushes nothing —
there is deliberately no assembled `state.md` on disk, because a generated
shared file is exactly what two people working at once would collide on. The
sequencing happens at read time, so there is nothing to keep in sync.

The one file two people can still collide on is `core.md`, and that is the
trade: it is short and changes rarely, so a collision there is a few readable
lines rather than two rewrites of a thousand.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date as _date
from pathlib import Path

from .runid import user_slug

STATE_REL = Path("project") / "global" / "state"
KINDS = ("blocks", "entries")

FM = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)


def _repo_root(start: Path) -> Path:
    for p in [start.resolve(), *start.resolve().parents]:
        if (p / "CLAUDE.md").exists() or (p / ".git").exists():
            return p
    return start.resolve()


def _parse(path: Path) -> dict:
    """One entry file -> {date, author, kind, title, body, path}."""
    text = path.read_text(encoding="utf-8")
    m = FM.match(text)
    if not m:
        raise ValueError(f"{path.name}: no front matter")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    missing = {"date", "author", "title"} - set(meta)
    if missing:
        raise ValueError(f"{path.name}: front matter missing {sorted(missing)}")
    meta["body"] = m.group(2).strip("\n")
    meta["path"] = path
    meta.setdefault("kind", path.parent.name)
    return meta


def load(root: Path, kind: str | None = None) -> list[dict]:
    """Every entry, newest first. Ties break on filename, which is stable."""
    out = []
    for k in KINDS if kind is None else (kind,):
        d = root / STATE_REL / k
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            out.append(_parse(f))
    out.sort(key=lambda e: (e["date"], e["path"].name), reverse=True)
    return out


def slugify(text: str, words: int = 6) -> str:
    s = re.sub(r"[^a-z0-9\s-]", "", text.lower())
    return "-".join(s.split()[:words]) or "entry"


def cmd_show(root: Path, args) -> int:
    core = root / STATE_REL / "core.md"
    if core.exists() and args.kind is None:
        print(core.read_text(encoding="utf-8").rstrip("\n"))
        print()
    for e in load(root, args.kind):
        if args.author and e["author"] != args.author:
            continue
        if args.since and e["date"] < args.since:
            continue
        print(f"## {e['title']}")
        print(f"*{e['date']} — {e['author']}*")
        print()
        print(e["body"])
        print()
    return 0


def cmd_new(root: Path, args) -> int:
    kind = "blocks" if args.block else "entries"
    d = root / STATE_REL / kind
    d.mkdir(parents=True, exist_ok=True)
    today = _date.today().isoformat()
    author = user_slug()
    stem = f"{today.replace('-', '')}-{author}-{slugify(args.title)}"
    path = d / f"{stem}.md"
    n = 2
    while path.exists():                      # same author, same day, same words
        path = d / f"{stem}-{n}.md"
        n += 1
    path.write_text(
        f"---\ndate: {today}\nauthor: {author}\nkind: {kind}\n"
        f"title: {args.title}\n---\n\n\n", encoding="utf-8")
    print(path.relative_to(root))
    return 0


def cmd_check(root: Path, args) -> int:
    bad = 0
    for k in KINDS:
        d = root / STATE_REL / k
        for f in sorted(d.glob("*.md")) if d.is_dir() else []:
            try:
                e = _parse(f)
            except ValueError as exc:
                print(f"FAIL {exc}", file=sys.stderr)
                bad += 1
                continue
            if not f.name.startswith(e["date"].replace("-", "")):
                print(f"WARN {f.name}: filename date != front matter {e['date']}",
                      file=sys.stderr)
    n = len(load(root))
    print(f"{n} entr{'y' if n == 1 else 'ies'}, {bad} malformed")
    return 1 if bad else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m tools.state",
                                description=__doc__.split("\n")[0])
    p.add_argument("--project", default=".", help="project root")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("show", help="render the state, newest first")
    s.add_argument("--kind", choices=KINDS, default=None)
    s.add_argument("--author", default=None)
    s.add_argument("--since", default=None, metavar="YYYY-MM-DD")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("new", help="create a correctly named entry file")
    s.add_argument("title")
    s.add_argument("--block", action="store_true",
                   help="a topic block rather than a dated entry")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("check", help="front matter parses and names sort")
    s.set_defaults(fn=cmd_check)

    args = p.parse_args(argv)
    return args.fn(_repo_root(Path(args.project)), args)


if __name__ == "__main__":
    raise SystemExit(main())
