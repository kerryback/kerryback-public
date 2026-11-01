"""Which script produced this file, what did it depend on, and what is downstream.

Reads the dependency graph out of the code rather than asking anyone to declare
it. That is possible because every path in `workspaces/` now goes through
`DATA_ROOT` or `REPO_ROOT` in one uniform form, so a static pass can tell what
each script reads and writes.

    python -m tools.provenance --file logmult/data/preds.parquet   # who made it, from what
    python -m tools.provenance --script logmult/code/02_estimator.py  # what to re-run
    python -m tools.provenance --graph                              # the whole DAG
    python -m tools.provenance --orphans                            # files nothing produces

WHAT IT CANNOT SEE. A path assembled at runtime — a loop variable, an argv value,
a glob — is invisible to a static pass. Those show up as gaps: a file with no
producer, or a script with no inputs. `--orphans` lists them so the gaps are
visible rather than silently missing. Treat the graph as a strong first draft of
provenance, not a proof.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())

# method/function names that mean "this argument is a path being read / written"
READ_FNS = {"read_parquet", "read_csv", "read_table", "read_pickle", "read_stata",
            "read_feather", "read_json", "load", "read_excel",
            # a glob IS a read — this pipeline concatenates partial_*.parquet
            "glob", "iglob"}
WRITE_FNS = {"to_parquet", "to_csv", "to_pickle", "to_feather", "to_json", "to_excel",
             "savefig", "savez", "savez_compressed", "save", "write_text", "write_bytes"}


def _fn_name(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


class Resolver(ast.NodeVisitor):
    """Fold module-level string constants so f-strings built from them resolve.

    The house style is `DATA = f"{DATA_ROOT}/logmult/data"` and then
    `f"{DATA}/preds.parquet"`, so without this almost nothing would resolve.
    """

    def __init__(self):
        self.env: dict[str, str] = {"DATA_ROOT": "$DATA", "REPO_ROOT": "$REPO",
                                    "WORK_ROOT": "$WORK"}

    def visit_Assign(self, node: ast.Assign):
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            v = self.value(node.value)
            if v is not None:
                self.env[node.targets[0].id] = v
        self.generic_visit(node)

    def value(self, node) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return self.env.get(node.id)
        if isinstance(node, ast.JoinedStr):
            out = []
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    out.append(part.value)
                elif isinstance(part, ast.FormattedValue):
                    v = self.value(part.value)
                    # A part fixed only at runtime (a TAG from argv, a loop year)
                    # becomes a wildcard, so the edge is still recorded — as a
                    # pattern. Losing the edge entirely would be worse than
                    # recording it imprecisely.
                    out.append("*" if v is None else v)
                else:
                    out.append("*")
            return "".join(out)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            a, b = self.value(node.left), self.value(node.right)
            return None if a is None or b is None else a + b
        if isinstance(node, ast.Call) and _fn_name(node) == "join":
            parts = [self.value(a) for a in node.args]
            if all(p is not None for p in parts):
                return "/".join(p.strip("/") for p in parts)
        return None


def scan(path: Path) -> tuple[set[str], set[str]]:
    """Return (reads, writes) as normalized $DATA/... or $REPO/... strings."""
    try:
        tree = ast.parse(path.read_text(errors="ignore"))
    except SyntaxError:
        return set(), set()
    r = Resolver()
    r.visit(tree)
    reads, writes = set(), set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _fn_name(node)
        args = list(node.args)
        if name == "open":
            if not args:
                continue
            mode = ""
            if len(args) > 1:
                mode = r.value(args[1]) or ""
            for kw in node.keywords:
                if kw.arg == "mode":
                    mode = r.value(kw.value) or mode
            target = writes if any(c in mode for c in "wax") else reads
            v = r.value(args[0])
            if v:
                target.add(v)
            continue
        if name in READ_FNS or name in WRITE_FNS:
            # pandas writers are methods: df.to_parquet(path) -> path is arg 0
            v = r.value(args[0]) if args else None
            if v is None:
                continue
            (writes if name in WRITE_FNS else reads).add(v)
    keep = lambda s: {p for p in s if p.startswith(("$DATA", "$REPO", "$WORK"))}
    return keep(reads), keep(writes)


def authors() -> list[str]:
    """Author trees only — `global/` is shared, not a person."""
    ws = REPO / "workspaces"
    return sorted(d.name for d in ws.iterdir()
                  if d.is_dir() and not d.name.startswith(".") and d.name != "global")


def build(author: str) -> dict:
    """One DAG per author. Each keeps their own code and their own data, so a
    shared graph would imply dependencies across builds that must stay
    independent."""
    reads: dict[str, set[str]] = {}
    writes: dict[str, set[str]] = {}
    root = REPO / "workspaces" / author
    if not root.is_dir():
        raise SystemExit(f"no such author tree: workspaces/{author}  (have: {', '.join(authors())})")
    for f in sorted(root.rglob("*.py")):
        rel = str(f.relative_to(root))
        rd, wr = scan(f)
        if rd or wr:
            reads[rel], writes[rel] = rd, wr
    produced_by: dict[str, list[str]] = defaultdict(list)
    for s, ws in writes.items():
        for w in ws:
            produced_by[w].append(s)
    return {"reads": reads, "writes": writes, "produced_by": dict(produced_by)}


def short(p: str) -> str:
    return (p.replace("$DATA/", "").replace("$WORK/", "")
             .replace("$REPO/workspaces/", ""))


def matches(a: str, b: str) -> bool:
    """Do two path expressions refer to the same artifact?

    Either side may be a pattern: a reader globs `partial_*.parquet`, a writer
    emits `partial_{tag}.parquet`. Compare in both directions so the edge is
    found regardless of which end carries the wildcard.
    """
    from fnmatch import fnmatch
    return a == b or fnmatch(a, b) or fnmatch(b, a)


def producers_of(g, path: str) -> list[str]:
    exact = g["produced_by"].get(path)
    if exact:
        return exact
    return sorted({s for written, ss in g["produced_by"].items()
                   if matches(path, written) for s in ss})



def _nid(counter, cache, label):
    """A stable id derived from the label, not from encounter order.

    Sequential ids renumber every downstream node when one artifact is added, so
    an unrelated edit rewrites whole diagrams and the diff is unreadable. Hashing
    the label keeps a node's id fixed for as long as its name is.
    """
    if label not in cache:
        cache[label] = "n" + hashlib.sha1(label.encode()).hexdigest()[:8]
    return cache[label]


def mermaid(g, scope=None, direction="LR") -> str:
    """Render the DAG as a Mermaid flowchart.

    Mermaid because it needs nothing installed: GitHub renders it inside a
    markdown file, so the picture lives in the repo next to what it describes.

    Scripts are boxes, data files are cylinders, and edges run
    input -> script -> output. `scope` keeps it to one subproject; the whole
    graph is 200+ nodes and unreadable as a single picture.
    """
    cache = {}
    lines = [f"flowchart {direction}"]
    edges, nodes = [], {}

    # Two spellings of one artifact must become ONE node, or the picture shows a
    # break where the pipeline is actually connected: the writer emits
    # `lampreds_{a}_{b}.parquet` and the reader globs `lampreds_*.parquet`.
    all_art = {short(x) for s in g["reads"] for x in g["reads"][s]}
    all_art |= {short(x) for s in g["writes"] for x in g["writes"][s]}
    canon = {}
    for a in sorted(all_art, key=len):
        canon[a] = next((c for c in canon.values() if matches(a, c)), a)

    def art(label):
        return canon.get(label, label)

    def keep(s):
        return scope is None or s.startswith(scope + "/") or f"/{scope}/" in s

    for script, rd in g["reads"].items():
        ws = g["writes"].get(script, set())
        if not keep(script) and not any(keep(short(x)) for x in rd | ws):
            continue
        sid = _nid(None, cache, script)
        nodes[sid] = f'{sid}["{Path(script).name}"]'
        for r in sorted(rd):
            lbl = art(short(r))
            rid = _nid(None, cache, lbl)
            nodes[rid] = f'{rid}[("{Path(lbl).name}")]'
            edges.append(f"    {rid} --> {sid}")
        for w in sorted(ws):
            lbl = art(short(w))
            wid = _nid(None, cache, lbl)
            nodes[wid] = f'{wid}[("{Path(lbl).name}")]'
            edges.append(f"    {sid} --> {wid}")

    lines += [f"    {v}" for v in nodes.values()]
    lines += sorted(set(edges))
    lines.append("    classDef script fill:#e8eef7,stroke:#3b6ef6,stroke-width:1px;")
    scripts = [i for lbl, i in cache.items() if lbl.endswith(".py")]
    if scripts:
        lines.append("    class " + ",".join(sorted(scripts)) + " script;")
    return "\n".join(lines)


def upstream(g, target: str, depth=0, seen=None, out=None):
    """Everything that had to run for `target` to exist."""
    seen = seen if seen is not None else set()
    out = out if out is not None else []
    for producer in producers_of(g, target):
        if (target, producer) in seen:
            continue
        seen.add((target, producer))
        out.append((depth, producer, target))
        for src in sorted(g["reads"].get(producer, ())):
            upstream(g, src, depth + 1, seen, out)
    return out


def downstream(g, script: str):
    """Scripts that must be re-run if `script` changes, in wave order."""
    waves, frontier, seen = [], {script}, {script}
    while frontier:
        files = {w for s in frontier for w in g["writes"].get(s, ())}
        nxt = {s for s, rd in g["reads"].items()
               if s not in seen and any(matches(r, f) for r in rd for f in files)}
        if not nxt:
            break
        waves.append((sorted(files), sorted(nxt)))
        seen |= nxt
        frontier = nxt
    return waves


def independence(g) -> list[tuple[str, str, str]]:
    """Edges that cross the analyst/replicator boundary.

    The two-build protocol only means something if the two builds are actually
    independent. A Replicator script reading an Analyst artifact (or the reverse)
    couples them, and the convergence check silently stops being evidence.

    NOT a violation: reading `$GLOBAL/...`. That is the confirmed, collapsed
    panel both estimators are TOLD to share — protocol step 4. Its authority
    comes from the two-build gate having already fired on it.
    """
    def side(script):
        parts = script.split("/")
        if parts[0] == "archive":
            return None                     # superseded; not a live claim
        return parts[0] if parts[0] in ("analyst", "replicator") else None

    out = []
    for s, rd in g["reads"].items():
        for r in sorted(rd):
            if r.startswith("$GLOBAL"):
                continue                      # canonical shared data, by design
            for prod in producers_of(g, r):
                a, b = side(s), side(prod)
                if a and b and a != b:
                    out.append((prod, short(r), s))
    return sorted(set(out))


def write_dag(author: str, g: dict) -> list[Path]:
    """Regenerate the committed diagrams for one author, into their own tree.

    Lives at workspaces/<author>/dag/ rather than anywhere shared: it is derived
    from that author's code, so it is theirs. project/global/ is only for what
    all three of us jointly own.

    One markdown file per subproject, each holding a Mermaid block that GitHub
    renders inline — so the picture is visible in the repo, next to the code it
    describes, with nothing to install. Plus an index with counts and the
    unproduced inputs.

    Written by the pre-commit hook, so it cannot drift: a commit that changes a
    script updates that script's diagram in the same commit.
    """
    out = REPO / "workspaces" / author / "dag"
    out.mkdir(parents=True, exist_ok=True)
    def subkey(s):
        parts = s.split("/")
        n = 3 if parts[0] == "archive" else 2      # archive/<role>/<sub> | <role>/<sub>
        return "/".join(parts[:n])
    subs = sorted({subkey(s) for s in g["reads"]})
    written, rows = [], []

    for sub in subs:
        scripts = [s for s in g["reads"] if subkey(s) == sub]
        arts = {short(x) for s in scripts for x in g["reads"][s] | g["writes"].get(s, set())}
        body = mermaid(g, scope=sub)
        n_edges = sum(1 for line in body.splitlines() if "-->" in line)
        f = out / (sub.replace("/", "__") + ".md")
        f.write_text(
            f"# {author} / {sub}\n\n"
            f"{len(scripts)} scripts, {len(arts)} artifacts, {n_edges} edges. "
            f"Generated by `tools/provenance.py --write`; do not edit.\n\n"
            f"```mermaid\n{body}\n```\n", encoding="utf-8")
        written.append(f)
        rows.append((sub, len(scripts), len(arts), n_edges))

    read_all = {q for rd in g["reads"].values() for q in rd}
    orphans = sorted(q for q in read_all if not producers_of(g, q))
    lines = [f"# Provenance — {author}", "",
             "Which script produced each file, inferred from the code. Regenerated by",
             "the pre-commit hook; do not edit by hand.", "",
             "| subproject | scripts | artifacts | edges |", "|---|---:|---:|---:|"]
    lines += [f"| [{s}]({s.replace(chr(47), '__')}.md) | {a} | {b} | {c} |" for s, a, b, c in rows]
    lines += ["", f"## Inputs nothing produces ({len(orphans)})", "",
              "Raw pulls and downloads — or a path built at runtime that static",
              "analysis cannot see. Both look the same from here.", ""]
    lines += [f"- `{short(q)}`" for q in orphans]
    idx = out / "index.md"
    idx.write_text("\n".join(lines) + "\n", encoding="utf-8")
    written.append(idx)
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="a data file, e.g. logmult/data/preds.parquet")
    ap.add_argument("--script", help="a script, e.g. logmult/code/02_estimator.py")
    ap.add_argument("--graph", action="store_true", help="dump the whole graph as JSON")
    ap.add_argument("--orphans", action="store_true", help="files read but never produced")
    ap.add_argument("--runs", action="store_true",
                    help="recorded runs (runtime truth, from tools/runlog.py)")
    ap.add_argument("--author", default=None,
                    help="whose DAG (default: yours, from git config user.name)")
    ap.add_argument("--authors", action="store_true", help="list author trees")
    ap.add_argument("--mermaid", metavar="SUBPROJECT", nargs="?", const="",
                    help="draw the DAG as Mermaid (optionally scoped to one subproject)")
    ap.add_argument("--independence", action="store_true",
                    help="edges crossing the analyst/replicator boundary")
    ap.add_argument("--write", action="store_true",
                    help="regenerate the committed diagrams under workspaces/<author>/dag/")
    args = ap.parse_args()

    if args.authors:
        for a in authors():
            n = sum(1 for _ in (REPO / "workspaces" / a).rglob("*.py"))
            print(f"  {a:<16} {n:>4} scripts")
        return

    if args.author is None:
        sys.path.insert(0, str(REPO))
        from tools.runid import user_slug
        args.author = user_slug()
    g = build(args.author) if not args.runs else {"reads": {}, "writes": {}, "produced_by": {}}

    if args.runs:
        import json as _json
        recs = []
        for f in sorted((REPO / "project").glob("*/logs/runs.jsonl")):
            for line in f.read_text().splitlines():
                if line.strip():
                    recs.append(_json.loads(line))
        if not recs:
            print("no runs recorded yet — run scripts via tools/runlog.py")
            return
        print(f"{len(recs)} recorded run(s):\n")
        for r in sorted(recs, key=lambda r: r["ts"]):
            print(f"  {r['ts']}  {r['author']}  {r['status']}  {r['seconds']}s  @{r['commit']}")
            print(f"    {r['script']} {' '.join(r['args'])}")
            for i in r["inputs"]:
                print(f"      in  {short(i.replace('$DATA/', ''))}")
            for o in r["outputs"]:
                print(f"      out {short(o)}")
        return

    if args.independence:
        v = independence(g)
        if not v:
            print("no edges cross the analyst/replicator boundary.")
            return
        print(f"{len(v)} edge(s) cross the analyst/replicator boundary.\n"
              "Each is either a deliberate cross-test or an accidental coupling —\n"
              "the tool cannot tell. Reads of $GLOBAL are excluded (shared by design).\n")
        for prod, art, s in v:
            print(f"  {prod}\n     writes {art}\n     which {s} reads")
        return

    if args.write:
        files = write_dag(args.author, g)
        print(f"wrote {len(files)} files under workspaces/{args.author}/dag/")
        return

    if args.mermaid is not None:
        scope = args.mermaid or None
        print(mermaid(g, scope=scope))
        return

    if args.graph:
        print(json.dumps({k: {kk: sorted(vv) for kk, vv in v.items()} if k != "produced_by"
                          else v for k, v in g.items()}, indent=2, default=list))
        return

    if args.orphans:
        read_all = {p for rd in g["reads"].values() for p in rd}
        missing = sorted(p for p in read_all if not producers_of(g, p))
        print(f"read by some script, produced by none ({len(missing)}):")
        print("  these are raw inputs (a WRDS pull, a download) or a gap in what")
        print("  static analysis can see — a path built at runtime.\n")
        for p in missing:
            who = sorted(s for s, rd in g["reads"].items() if p in rd)[:3]
            print(f"  {short(p)}\n      read by: {', '.join(who)}")
        return

    if args.file:
        key = args.file if args.file.startswith("$") else "$DATA/" + args.file
        if not producers_of(g, key):
            alt = "$REPO/workspaces/" + args.file
            key = alt if producers_of(g, alt) else key
        chain = upstream(g, key)
        if not chain:
            print(f"no producer found for {args.file}")
            print("  either a raw input, or its path is built at runtime (see --orphans)")
            return
        print(f"{short(key)}\n")
        for depth, producer, target in chain:
            print("  " * depth + f"<- {producer}   produces {short(target)}")
        return

    if args.script:
        waves = downstream(g, args.script)
        if not waves:
            print(f"{args.script} writes nothing that another script reads — nothing downstream.")
            return
        print(f"if {args.script} changes, re-run in this order:\n")
        for i, (files, scripts) in enumerate(waves, 1):
            print(f"  wave {i}  (via {', '.join(short(f) for f in files[:3])}"
                  f"{' ...' if len(files) > 3 else ''})")
            for s in scripts:
                print(f"      {s}")
        return

    ap.print_help()


if __name__ == "__main__":
    main()
