"""Run a script and record what it actually read and wrote.

The static pass in `provenance.py` infers the graph from the code and is a good
first draft, but it cannot see a path assembled at runtime. This does: it
installs a PEP-578 audit hook, which fires on every file open *below* pandas,
pyarrow, numpy and matplotlib, so the record is what happened rather than what
the source appeared to say.

This is a record of RUNS, not a log of everything that happens. One line per
script execution: what it read, what it wrote, how long it took, and at which
commit. That is the thing you want a year later when a number needs defending.

    python tools/runlog.py workspaces/logmult/code/04_eval.py 2001 2025 mytag

One JSON line per run is appended to

    project/<author>/logs/runs.jsonl

which is COMMITTED — that is the point. It sits with the author's other run
records, so there is one place to look for "what happened", and nobody else
writes there: three people recording runs never touch the same path. A run records the script, its arguments, the git commit, the
inputs it opened and the outputs it wrote, so "what produced this file" has an
answer that does not depend on anyone remembering.

Reads and writes are recorded only for paths under $@@DATA_ENV@@ or the repo's
workspaces/ — the interpreter opens hundreds of .py and .so files that are noise
here.
"""
from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO))
from tools.runid import user_slug  # noqa: E402

# Set by the research skill to <PROJECT>_DATA; every script reads the same variable.
DATA_ENV = "@@DATA_ENV@@"

IGNORE_SUFFIX = (".py", ".pyc", ".pyo", ".so", ".dylib", ".pth", ".json.lock")
WRITE_MODES = set("wax+")


def _roots(data_root: str) -> list[str]:
    """Both spellings of the data root.

    ~/Dropbox is a symlink into ~/Library/CloudStorage, so a path that has been
    through Path.resolve() no longer starts with $@@DATA_ENV@@. Comparing
    against only the declared form silently discards every data read.
    """
    out = [data_root, str(REPO / "workspaces")]
    try:
        r = str(Path(data_root).resolve())
        if r != data_root:
            out.append(r)
    except Exception:
        pass
    return out


def _interesting(path: str, roots: list[str]) -> bool:
    if any(path.endswith(s) for s in IGNORE_SUFFIX) or "__pycache__" in path:
        return False
    if "/site-packages/" in path or "/.venv/" in path:
        return False
    return any(path.startswith(r) for r in roots)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        print("usage: python tools/runlog.py <script.py> [args...]", file=sys.stderr)
        return 2

    data_root = os.environ.get(DATA_ENV)
    if not data_root:
        print(f"{DATA_ENV} is not set — see CLAUDE.md", file=sys.stderr)
        return 2

    roots = _roots(data_root)
    script = Path(sys.argv[1]).resolve()
    args = sys.argv[2:]
    if not script.exists():
        print(f"no such script: {script}", file=sys.stderr)
        return 2

    reads: dict[str, None] = {}
    writes: dict[str, None] = {}

    def hook(event, event_args):
        # `open` fires for every file the process opens, at the C level.
        if event != "open":
            return
        path, mode, flags = (list(event_args) + [None, None])[:3]
        if not isinstance(path, str):
            return
        try:
            path = str(Path(path).resolve())
        except Exception:
            return
        if not _interesting(path, roots):
            return
        writing = bool(mode and WRITE_MODES & set(mode))
        if not writing and isinstance(flags, int):
            writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND))
        (writes if writing else reads)[path] = None

    def commit() -> str | None:
        try:
            r = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                               capture_output=True, text=True, timeout=5)
            return r.stdout.strip() or None
        except Exception:
            return None

    def note(path, writing):
        """Record a path seen through a patched library call."""
        if not isinstance(path, (str, Path)):
            return                      # a buffer or file object, not a path
        try:
            p = str(Path(path).resolve())
        except Exception:
            return
        if _interesting(p, roots):
            (writes if writing else reads)[p] = None

    def patch_libraries():
        """Wrap the library calls that bypass the audit hook.

        pyarrow reads parquet with its own C++ file I/O, so `open` never fires
        and a parquet READ is invisible to the hook — which is exactly the
        pipeline's main input. Writes came through fine because pandas' CSV
        writer goes via Python `open`. Patch the readers and writers by name.
        """
        try:
            import pandas as pd
        except ImportError:
            return

        def wrap_fn(mod, name, writing):
            fn = getattr(mod, name, None)
            if fn is None:
                return
            def inner(*a, **k):
                if a:
                    note(a[0], writing)
                return fn(*a, **k)
            inner.__name__ = name
            setattr(mod, name, inner)

        def wrap_method(cls, name, writing):
            fn = getattr(cls, name, None)
            if fn is None:
                return
            def inner(self, *a, **k):
                if a:
                    note(a[0], writing)
                return fn(self, *a, **k)
            inner.__name__ = name
            setattr(cls, name, inner)

        for n in ("read_parquet", "read_csv", "read_feather", "read_pickle",
                  "read_stata", "read_excel", "read_json", "read_table"):
            wrap_fn(pd, n, False)
        for cls in (pd.DataFrame, pd.Series):
            for n in ("to_parquet", "to_csv", "to_feather", "to_pickle",
                      "to_stata", "to_excel", "to_json"):
                wrap_method(cls, n, True)
        try:
            import numpy as np
            for n in ("load",):
                wrap_fn(np, n, False)
            for n in ("save", "savez", "savez_compressed", "savetxt"):
                wrap_fn(np, n, True)
        except ImportError:
            pass
        try:
            import pyarrow.parquet as pq
            wrap_fn(pq, "read_table", False)
            wrap_fn(pq, "write_table", True)
        except ImportError:
            pass

    patch_libraries()
    head = commit()
    started = datetime.now(timezone.utc)
    t0 = time.time()
    sys.argv = [str(script)] + args

    status, err = "ok", None
    sys.addaudithook(hook)          # after our own setup, before the script runs
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as e:
        if e.code not in (0, None):
            status, err = "exit", f"SystemExit({e.code})"
    except BaseException as e:       # noqa: BLE001 - record the failure, then re-raise
        status, err = "error", f"{type(e).__name__}: {e}"
        raise
    finally:
        def rel(p: str) -> str:
            for r in sorted(_roots(data_root), key=len, reverse=True):
                if r.endswith("workspaces"):
                    continue
                if p.startswith(r + "/"):
                    return "$DATA/" + p[len(r) + 1:]
            return p.replace(str(REPO) + "/", "")

        # which author tree did this script come from
        tree = next((q.name for q in script.parents if q.parent.name == "workspaces"), None)
        # a file both read and written (append, or read-then-overwrite) is an output
        for w in writes:
            reads.pop(w, None)
        record = {
            "ts": started.isoformat(timespec="seconds"),
            "author": user_slug(),
            "tree": tree,
            "script": str(script.relative_to(REPO)) if script.is_relative_to(REPO) else str(script),
            "args": args,
            "commit": head,
            "seconds": round(time.time() - t0, 1),
            "status": status,
            "error": err,
            "inputs": sorted(rel(p) for p in reads),
            "outputs": sorted(rel(p) for p in writes),
        }
        out = REPO / "project" / user_slug() / "logs"
        out.mkdir(parents=True, exist_ok=True)
        with (out / "runs.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        print(f"\n[runlog] {status}: {len(record['inputs'])} inputs, "
              f"{len(record['outputs'])} outputs -> project/{user_slug()}/logs/runs.jsonl",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
