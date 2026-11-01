"""Promote a confirmed artifact to the shared canonical store.

`<data root>/global/` is the single source of truth for core data:
the panel every author estimates on. Its authority comes entirely from the fact
that getting in is hard, so this is the only way in.

    python tools/promote.py ~/Dropbox/the project/data/kerry-back/extend2000/data/panel_nonmicro.parquet \\
        --note "two-build reconciled: N within 0.24%, medians to the digit"

What it does: copies the file to global/, makes it READ-ONLY, and appends a row
to project/global/data_manifest.md recording the hash, the shape, who promoted
it, when, from where, and why it is trusted.

WHEN YOU MAY PROMOTE
--------------------
Only after the two-build gate: two independent builds of the same spec,
reconciled on observation counts and summary statistics. Promoting an
unreconciled file silently converts one person's build into everyone's ground
truth, which is the failure the protocol exists to prevent.

If the panel is later rebuilt, extended, or has a column redefined, the gate
applies again. A confirmation does not carry over to a different file.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(REPO))
from tools.runid import user_slug  # noqa: E402

# Set by the research skill to <PROJECT>_DATA.
DATA_ENV = "@@DATA_ENV@@"

MANIFEST = REPO / "project" / "global" / "data_manifest.md"
HEADER = """# Canonical data manifest

Everything in `<data root>/global/` — the shared, confirmed data
every author estimates on. Written by `tools/promote.py`; do not edit by hand.

A row here is a claim that the artifact passed the two-build gate. If you cannot
point at the reconciliation, it does not belong in global.

| file | promoted | by | rows x cols | sha256 (12) | basis |
|---|---|---|---|---|---|
"""


def describe(path: Path) -> str:
    try:
        import pandas as pd
        df = pd.read_parquet(path) if path.suffix == ".parquet" else None
        if df is not None:
            return f"{len(df):,} x {df.shape[1]}"
    except Exception:
        pass
    return f"{path.stat().st_size // 1024:,} KB"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="the file to promote")
    ap.add_argument("--note", required=True,
                    help="why this is trusted — the reconciliation, in one line")
    ap.add_argument("--force", action="store_true", help="replace an existing canonical file")
    args = ap.parse_args()

    src = Path(args.path).expanduser().resolve()
    if not src.is_file():
        print(f"no such file: {src}", file=sys.stderr)
        return 2

    data_root = os.environ.get(DATA_ENV)
    if not data_root:
        print("@@DATA_ENV@@ is not set — see CLAUDE.md", file=sys.stderr)
        return 2
    glob_dir = Path(data_root).parent / "global"
    glob_dir.mkdir(parents=True, exist_ok=True)
    dst = glob_dir / src.name

    if dst.exists() and not args.force:
        print(f"{dst.name} is already canonical. Replacing it needs --force, and needs\n"
              f"the two-build gate to have fired again on the NEW file.", file=sys.stderr)
        return 1

    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    shape = describe(src)

    if dst.exists():
        dst.chmod(0o644)
    shutil.copy2(src, dst)
    dst.chmod(0o444)                       # read-only: nobody edits canon in place

    try:
        rel = str(src.relative_to(Path(data_root)))
    except ValueError:
        rel = str(src)
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True).stdout.strip()

    if not MANIFEST.exists():
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(HEADER, encoding="utf-8")
    row = (f"| `{dst.name}` | {datetime.now(timezone.utc):%Y-%m-%d} | {user_slug()} "
           f"| {shape} | `{digest[:12]}` | {args.note} (from `{rel}`, repo @{head}) |\n")
    with MANIFEST.open("a", encoding="utf-8") as fh:
        fh.write(row)

    print(f"promoted {dst.name} -> {glob_dir}")
    print(f"  {shape}   sha256 {digest[:12]}   read-only")
    print(f"  recorded in {MANIFEST.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
