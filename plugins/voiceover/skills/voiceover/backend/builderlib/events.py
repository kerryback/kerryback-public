"""In-memory per-project job progress, consumed by the SSE endpoint.

Jobs run in background threads and push events here; the async SSE endpoint
polls for events appended since the last one it saw. Simple and thread-safe.
"""
import threading
from typing import Optional

_lock = threading.Lock()
# project_id -> {"events": [ {stage,state,done,total,message}, ... ], "active": bool}
_store: dict = {}


def start(project_id: str) -> None:
    with _lock:
        _store[project_id] = {"events": [], "active": True}


def emit(project_id: str, stage: str, state: str, done: int = 0, total: int = 0,
         message: str = "") -> None:
    evt = {"stage": stage, "state": state, "done": done, "total": total, "message": message}
    with _lock:
        entry = _store.setdefault(project_id, {"events": [], "active": True})
        entry["events"].append(evt)


def finish(project_id: str) -> None:
    with _lock:
        entry = _store.get(project_id)
        if entry:
            entry["active"] = False


def snapshot(project_id: str, since: int):
    """Return (new_events, next_index, active) for events after `since`."""
    with _lock:
        entry = _store.get(project_id)
        if not entry:
            return [], since, False
        events = entry["events"]
        new = events[since:]
        return list(new), len(events), entry["active"]
