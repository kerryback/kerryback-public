"""The debate log: append-only JSONL, secret-redacted, one file per run.

One writer feeds it: `tools/debate/debate.py`, which appends a record per voice
call — the seat, the model, the messages sent, and the response returned. That
is the whole of it. There is no session-wide hook and no tool-call capture: an
exhaustive record of every prompt and every tool call runs to tens of megabytes
a project, cannot go in git, and answers none of the questions people actually
ask. What answers those is a decision written down with its reason, which is
the state entries.

Read a slice when a specific question needs one:

    python3 -m tools.logging_ --seat adversary --limit 5

What IS shared with coauthors, and deliberately:

- `project/<author>/logs/runs.jsonl` — the run records. Committed.
- `project/global/state/` — the curated truth, one file per entry. When a
  debate resolves, the question, the decision, and the reason go here.

This file's own output stays local, and so are the briefs. Both are the input to
a decision rather than the decision, and the changelog carries the part a
coauthor needs.

Logs are named by RUN, not by round: a round counter is per-machine, so two
coauthors in a shared clone each have a "round 3", while
`<author>-<date>-<time>` says who ran it and when and cannot collide.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .runid import author_dir, current_run_id

# Redaction happens in one place, for every writer, so no seat can leak a key to
# disk by forgetting. Patterns are deliberately broad: a false positive costs a
# line of log, a false negative costs a credential.
_REDACTIONS = [
    (re.compile(r"sk-or-[A-Za-z0-9_\-]{16,}"), "sk-or-<redacted>"),
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "sk-<redacted>"),
    (re.compile(r"(?i)(api[_-]?key|secret|token|authorization|bearer)\s*[:=]\s*\S+",),
     r"\1=<redacted>"),
    (re.compile(r"postgres(?:ql)?://[^\s\"']+"), "postgresql://<redacted>"),
    # .pgpass-style host:port:db:user:password
    (re.compile(r"(?m)^([^:\s]+:\d+:[^:]+:[^:]+):[^:\s]+$"), r"\1:<redacted>"),
]


def redact(text: str) -> str:
    if not isinstance(text, str):
        text = json.dumps(text, default=str)
    for pat, repl in _REDACTIONS:
        text = pat.sub(repl, text)
    return text


def redact_obj(obj):
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    return obj


def append_event(project_dir: str | Path, event: dict) -> None:
    """Append one fully-formed record (it carries its own timestamp and ids).

    The run stamp goes into the record as well as the filename, so records stay
    attributable if the files are later concatenated or renamed.
    """
    run = event.get("run_id") or current_run_id(project_dir)
    record = redact_obj({"run_id": run, **event})
    path = author_dir(project_dir) / "logs" / f"debate-{run}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def read_events(project_dir: str | Path, run: str | None = None):
    """Yield the records of one run (default: the current one), in order."""
    run = run or current_run_id(project_dir)
    path = author_dir(project_dir) / "logs" / f"debate-{run}.jsonl"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue  # a truncated last line beats losing the file


def main() -> None:
    """`python3 -m tools.logging_ [--run <id>] [--seat adversary] [--limit N]`"""
    import argparse

    ap = argparse.ArgumentParser(description="read a slice of the debate log")
    ap.add_argument("--project", default=".", help="project root")
    ap.add_argument("--run", help="run id (default: the current run)")
    ap.add_argument("--seat", help="filter by debate seat, e.g. adversary")
    ap.add_argument("--limit", type=int, default=0, help="last N matching records")
    args = ap.parse_args()

    rows = [
        e for e in read_events(args.project, args.run)
        if not args.seat or e.get("seat") == args.seat
    ]
    if args.limit:
        rows = rows[-args.limit:]
    for e in rows:
        print(json.dumps(e, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
