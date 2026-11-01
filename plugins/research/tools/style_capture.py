#!/usr/bin/env python3
"""Hook: capture prose corrections, and put the learned house style in context.

One script, three hook events, dispatched on `hook_event_name`:

  UserPromptSubmit  stash the prompt, keyed by prompt_id, in a small ring buffer
  PostToolUse       on an Edit to a prose file, append {instruction, before, after}
  SessionStart      print this project's own rules, extracted from the guide

The point is to close the loop between "Claude, stop doing that" and Claude not
doing that in three months. A correction stated in chat is gone when the session
ends; captured, it becomes a candidate rule that `/style-learn` can promote into
`writing-guide.md`, which is the project's one writing standard.

This is deliberately NOT session-wide logging. It fires on one tool, filtered to
prose files under the draft directory, and what it writes is a staging buffer
that stays local and gitignored. The artifact that survives is the curated rule
file, which a human accepted line by line. Bulk capture is not memory; see the
note in the research skill.

Safe by construction: never raises into the tool loop, writes nothing outside
the project, truncates long passages, and stays silent when it cannot tell where
it is.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# What counts as prose. An Edit outside these is content or code, not style.
PROSE_SUFFIXES = {".tex", ".md", ".txt", ".qmd", ".rmd"}
PROSE_DIRS = ("draft",)

# Prose the writing standard explicitly does not govern: notes between
# coauthors, machine-owned memory, and the style files themselves. Matched
# against the path's parts and stem so it works from any subdirectory.
EXCLUDE_STEMS = {
    "state", "session", "method_spec", "data_manifest", "analyst",
    "replicator", "verifier", "claude", "readme", "protocols",
    "writing-guide", "changelog",
}
EXCLUDE_DIRS = {"project", "archive", ".claude", "node_modules", ".git"}

# A correction is a sentence or a paragraph. Anything much larger is a section
# rewrite, where the style signal is buried in content changes.
MAX_PASSAGE = 1500
MIN_PASSAGE = 12
PROMPT_RING = 40


def project_root() -> Path | None:
    """The repo, found the same way the other tools find it."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and (Path(env) / "project").is_dir():
        return Path(env).resolve()
    here = Path.cwd().resolve()
    for cand in [here, *here.parents]:
        if (cand / "project").is_dir():
            return cand
    if env and Path(env).is_dir():
        return Path(env).resolve()
    return None


def author_slug() -> str:
    """Mirror of runid.user_slug — git's user.name, else the OS login."""
    name = ""
    try:
        name = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        pass
    name = name or os.environ.get("USER") or os.environ.get("USERNAME") or ""
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower() or "anon"


def logs_dir(root: Path) -> Path:
    d = root / "project" / author_slug() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_prose(root: Path, raw_path: str) -> bool:
    """True when an edit to this file is the kind of thing style rules govern."""
    if not raw_path:
        return False
    try:
        p = Path(raw_path)
        if not p.is_absolute():
            p = (root / p).resolve()
        rel = p.relative_to(root)
    except Exception:
        return False
    if p.suffix.lower() not in PROSE_SUFFIXES:
        return False
    parts = set(rel.parts[:-1])
    if parts & EXCLUDE_DIRS:
        return False
    if rel.stem.lower() in EXCLUDE_STEMS:
        return False
    # Confined to the draft tree: that is what the writing standard binds.
    return bool(parts & set(PROSE_DIRS)) or rel.parts[0] in PROSE_DIRS


def stash_prompt(root: Path, payload: dict) -> None:
    """Hold the prompt so the edit it causes can be recorded with its reason."""
    text = payload.get("user_input") or payload.get("prompt") or ""
    if not text.strip():
        return
    pid = payload.get("prompt_id") or payload.get("session_id") or "unknown"
    f = logs_dir(root) / "style-prompts.json"
    try:
        ring = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(ring, list):
            ring = []
    except Exception:
        ring = []
    ring.append({
        "prompt_id": pid,
        "ts": datetime.now(timezone.utc).isoformat(),
        "text": text[:4000],
    })
    f.write_text(json.dumps(ring[-PROMPT_RING:], ensure_ascii=False), encoding="utf-8")


def lookup_prompt(root: Path, pid: str | None) -> str:
    """The instruction behind this edit — by id, else the most recent."""
    f = logs_dir(root) / "style-prompts.json"
    try:
        ring = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not ring:
        return ""
    if pid:
        for rec in reversed(ring):
            if rec.get("prompt_id") == pid:
                return rec.get("text", "")
    return ring[-1].get("text", "")


def edit_pairs(payload: dict) -> list[tuple[str, str]]:
    """Every (before, after) in this tool call. Edit is one; MultiEdit is many."""
    ti = payload.get("tool_input") or {}
    if not isinstance(ti, dict):
        return []
    if isinstance(ti.get("edits"), list):
        return [
            (e.get("old_string", ""), e.get("new_string", ""))
            for e in ti["edits"] if isinstance(e, dict)
        ]
    return [(ti.get("old_string", ""), ti.get("new_string", ""))]


def record_edit(root: Path, payload: dict) -> None:
    if payload.get("tool_name") not in ("Edit", "MultiEdit"):
        return
    ti = payload.get("tool_input") or {}
    path = ti.get("file_path", "") if isinstance(ti, dict) else ""
    if not is_prose(root, path):
        return
    instruction = lookup_prompt(root, payload.get("prompt_id"))
    try:
        rel = str(Path(path).resolve().relative_to(root))
    except Exception:
        rel = path
    rows = []
    for before, after in edit_pairs(payload):
        # A pure insertion has no objectionable text, so it carries no
        # correction. A one-word change is usually a typo, not a style rule.
        if len(before.strip()) < MIN_PASSAGE or before.strip() == after.strip():
            continue
        rows.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "author": author_slug(),
            "source": "instruction",
            "file": rel,
            "instruction": instruction[:2000],
            "before": before[:MAX_PASSAGE],
            "after": after[:MAX_PASSAGE],
            "truncated": len(before) > MAX_PASSAGE or len(after) > MAX_PASSAGE,
        })
    if not rows:
        return
    with (logs_dir(root) / "style-observations.jsonl").open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


GUIDE = "writing-guide.md"
LEARNED = re.compile(r"^(?P<text>.*?)\s*<!--\s*learned:\s*(?P<meta>.*?)\s*-->\s*$")


def extract_learned(root: Path) -> list[dict]:
    """The project-added rules in the guide, in document order.

    A learned rule is one line carrying a `<!-- learned: ... -->` marker,
    interleaved into whichever section of the guide it belongs to, plus any
    indented lines immediately under it. One line is the format and also the
    discipline: a rule that needs a paragraph has not been decided yet.
    """
    f = root / GUIDE
    if not f.exists():
        return []
    lines = f.read_text(encoding="utf-8").splitlines()
    out: list[dict] = []
    section = ""
    fenced = False
    for i, line in enumerate(lines):
        # The guide documents the marker format inside a fenced block. Without
        # this, that example is extracted as a live rule and the guide's own
        # instructions become part of the house style.
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if line.startswith("## "):
            section = line[3:].strip()
        m = LEARNED.match(line)
        if not m:
            continue
        meta = {}
        for part in m.group("meta").split("|"):
            if ":" in part:
                k, v = part.split(":", 1)
                meta[k.strip()] = v.strip()
            elif part.strip():
                meta["id"] = part.strip()
        text = re.sub(r"^\s*[-*]\s+", "", m.group("text")).strip()
        extra = []
        for nxt in lines[i + 1:]:
            if nxt.strip() and nxt[:1] in " \t":
                extra.append(nxt.strip())
            else:
                break
        out.append({
            "text": text,
            "extra": extra,
            "section": section,
            "line": i + 1,
            "id": meta.get("id", ""),
            "hits": int(meta.get("hits", 0) or 0),
            "added": meta.get("added", ""),
            "last": meta.get("last", ""),
        })
    return out


def emit_rules(root: Path) -> None:
    """Put the project's own rules in context.

    This is an excerpt, regenerated every session and never edited by hand.
    `writing-guide.md` is the one definitive standard; it is too long to put in
    context whole, and these are the rules least likely to survive a skim,
    because they are this project's arbitrary conventions rather than craft the
    model already half-knows. Plain stdout is added as context by SessionStart,
    so printing is the whole mechanism.
    """
    rules = extract_learned(root)
    if not rules:
        return
    by_section: dict[str, list[dict]] = {}
    for r in rules:
        by_section.setdefault(r["section"] or "General", []).append(r)
    lines = [
        f"This project's own writing rules — {len(rules)} of them, excerpted from "
        f"{GUIDE} at the lines noted. That file is the single definitive standard "
        "for the project's writing; this is a view of the part of it this project "
        "added, not a second standard, and it is regenerated each session rather "
        "than maintained. Read the full guide before writing prose — it holds the "
        "craft these rules sit inside. The guide governs draft/ by default, so "
        "these do too, except where a rule states its own wider scope — a few do, "
        "and they mean it.",
        "",
    ]
    for section, rs in by_section.items():
        lines.append(f"{section}:")
        for r in rs:
            lines.append(f"  - {r['text']}  [{GUIDE}:{r['line']}]")
            lines.extend(f"      {e}" for e in r["extra"])
        lines.append("")
    print("\n".join(lines).rstrip())


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    root = project_root()
    if root is None:
        return  # not in a project set up for this; stay silent
    event = payload.get("hook_event_name")
    if event == "UserPromptSubmit":
        stash_prompt(root, payload)
    elif event == "PostToolUse":
        record_edit(root, payload)
    elif event == "SessionStart":
        emit_rules(root)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # never break the tool loop
