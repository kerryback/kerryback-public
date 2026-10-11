"""Folder-backed project registry — the deck folders under DATA_DIR/decks ARE the
source of truth. Each deck folder holds a meta.json with the deck's state; there is
no database. A deck exists iff its folder (with a meta.json) exists, so deleting a
deck is just deleting its folder.

Public API mirrors the old SQLite module so callers are unchanged:
create_project / get_project / list_projects / update_project / delete_project.
"""
import json
import shutil
import time
from typing import Optional

from . import config


def _meta_path(pid: str):
    return config.project_dir(pid) / "meta.json"


def _normalize(meta: dict) -> dict:
    """Fill in defaults so every project dict has a stable shape."""
    meta.setdefault("log", "")
    meta.setdefault("source_type", None)
    # Where the ingested PDF came from on disk, when it was opened by path
    # rather than uploaded through the browser. Empty for an upload.
    meta.setdefault("source_path", "")
    return meta


def _read(pid: str) -> Optional[dict]:
    p = _meta_path(pid)
    if not p.exists():
        return None
    try:
        return _normalize(json.loads(p.read_text(encoding="utf-8")))
    except (ValueError, OSError):
        return None


def _write(pid: str, meta: dict) -> None:
    config.project_dir(pid).mkdir(parents=True, exist_ok=True)
    _meta_path(pid).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def init() -> None:
    # Folder-backed: nothing to migrate. DATA_DIR/decks is created by config.
    config.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def create_project(pid: str, name: str, source_type: Optional[str], state: str) -> dict:
    now = time.time()
    meta = _normalize({
        "id": pid, "name": name, "state": state, "source_type": source_type,
        "created_at": now, "updated_at": now,
    })
    _write(pid, meta)
    return meta


def get_project(pid: str) -> Optional[dict]:
    return _read(pid)


def list_projects() -> list:
    root = config.PROJECTS_DIR
    if not root.exists():
        return []
    out = []
    for d in root.iterdir():
        if not d.is_dir():
            continue
        meta = _read(d.name)
        if meta is not None:
            out.append(meta)
    out.sort(key=lambda m: m.get("updated_at", 0), reverse=True)
    return out


def update_project(pid: str, **fields) -> None:
    meta = _read(pid)
    if meta is None:
        return
    meta.update(fields)
    meta["updated_at"] = time.time()
    _write(pid, meta)


def delete_project(pid: str) -> None:
    shutil.rmtree(config.project_dir(pid), ignore_errors=True)
