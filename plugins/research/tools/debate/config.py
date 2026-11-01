"""Find the project root and load the debate-voice roster.

Vendored into this repo so the project depends on nothing installed elsewhere:
a coauthor needs a clone and an OpenRouter key, nothing more.

The project root is the directory holding `project/`. The roster — which
OpenRouter model backs each debate seat — is `project/global/config.toml`, shared and
committed so every coauthor's debate runs against the same panel. Roster is
config, not code: swapping a voice is a one-line edit there.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

CHARTERS_DIR = Path(__file__).resolve().parent / "charters"


def find_project_root(start: str | Path | None = None) -> Path:
    """Walk up from `start` (default: cwd) to the nearest dir containing a
    `project/` folder — that is where coauthor is active."""
    p = Path(start or Path.cwd()).resolve()
    for cand in [p, *p.parents]:
        if (cand / "project").is_dir():
            return cand
    # Fall back to cwd so logging still works before init during dev.
    return Path.cwd().resolve()


def load_roster(project_root: str | Path | None = None) -> dict:
    root = Path(project_root) if project_root else find_project_root()
    cfg = root / "project" / "global" / "config.toml"
    if not cfg.exists():
        raise FileNotFoundError(
            f"No debate roster at {cfg}. It is committed — if it is missing you are "
            "not at the project root, or the checkout is incomplete."
        )
    with cfg.open("rb") as fh:
        return tomllib.load(fh)


def charter_text(role: str) -> str:
    f = CHARTERS_DIR / f"{role}.md"
    if not f.exists():
        raise FileNotFoundError(f"No charter for role '{role}' at {f}")
    return f.read_text(encoding="utf-8")
