"""Slide alignment across a reattached deck. No dependencies, no fixtures:

    python3 backend/tests/test_slidematch.py

Exits non-zero on the first shape it gets wrong. The fingerprints here are
stand-in strings, not real shas — what is under test is the cascade, not the
hashing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from builderlib import slidematch  # noqa: E402

FAILED = []


def fp(*specs):
    """spec 'a' -> image sha img-a, text sha txt-a. 'a/b' -> img-a, txt-b.
    'a/-' -> blank text (all-graphic slide). 'a|some words' -> also sets text."""
    out = []
    for i, s in enumerate(specs):
        head, _, text = s.partition("|")
        img, _, txt = head.partition("/")
        txt = txt or img
        out.append({"index": i, "image_sha": f"img-{img}",
                    "text_sha": f"txt-{txt}" if txt != "-" else "",
                    "text": text})
    return out


def check(name, old, new, pairs=None, status=None, removed=None, suspect=None):
    r = slidematch.align(old, new)
    st = {j: (v or "same") for j, v in r["status"].items()}
    ok = True
    for label, got, want in (("pairs", r["pairs"], pairs),
                             ("status", r["status"], status),
                             ("removed", r["removed"], removed),
                             ("suspect", r["summary"]["suspect_rerender"], suspect)):
        if want is not None and got != want:
            ok = False
            print(f"  ! {label}: got {got}, want {want}")
    print(f"{'ok ' if ok else 'FAIL'} {name:24} pairs={r['pairs']} status={st} "
          f"removed={r['removed']} rerender={r['summary']['suspect_rerender']}")
    if not ok:
        FAILED.append(name)
    return r


check("identical", fp("a", "b", "c"), fp("a", "b", "c"),
      pairs={0: 0, 1: 1, 2: 2}, status={0: None, 1: None, 2: None}, removed=[])

check("insert at 1", fp("a", "b", "c"), fp("a", "x", "b", "c"),
      pairs={0: 0, 2: 1, 3: 2}, status={0: None, 1: "new", 2: None, 3: None})

check("delete slide 1", fp("a", "b", "c"), fp("a", "c"),
      pairs={0: 0, 1: 2}, removed=[1], status={0: None, 1: None})

check("edit slide 1", fp("a", "b", "c"), fp("a", "b2", "c"),
      pairs={0: 0, 1: 1, 2: 2}, status={0: None, 1: "edited", 2: None})

check("chart edit (text same)", fp("a", "b", "c"), fp("a", "b2/b", "c"),
      pairs={0: 0, 1: 1, 2: 2}, status={0: None, 1: "edited", 2: None})

check("re-export drift", fp("a", "b", "c", "d"), fp("a2/a", "b2/b", "c2/c", "d2/d"),
      pairs={0: 0, 1: 1, 2: 2, 3: 3}, suspect=True,
      status={0: "edited", 1: "edited", 2: "edited", 3: "edited"})

# The case that broke positional-only pairing: slide "c" is deleted AND slide "d"
# is reworded, so "d2" lands where "c" used to be. Similarity must claim it for
# "d", not for "c".
old = fp("a|Introduction to duration",
         "b|Macaulay duration definition and formula",
         "c|A worked example on a five year bond",
         "d|Convexity corrects the duration approximation",
         "e|Summary and further reading")
new = fp("a|Introduction to duration",
         "x|New slide on yield curves",
         "b|Macaulay duration definition and formula",
         "d2|Convexity corrects the duration approximation for large moves",
         "e|Summary and further reading")
check("insert + edit + delete", old, new,
      pairs={0: 0, 2: 1, 3: 3, 4: 4}, removed=[2],
      status={0: None, 1: "new", 2: None, 3: "edited", 4: None})

# Same shape, but the reworded slide is genuinely unrelated to anything left —
# similarity must decline and let it read as new content in place.
old2 = fp("a|Introduction to duration", "c|A worked example on a five year bond",
          "e|Summary")
new2 = fp("a|Introduction to duration", "z|Monte Carlo simulation of interest rates",
          "e|Summary")
check("unrelated replacement", old2, new2,
      pairs={0: 0, 1: 1, 2: 2}, status={0: None, 1: "edited", 2: None})

check("blank-text slides", fp("a", "b/-", "c/-"), fp("a", "b2/-", "c2/-"),
      pairs={0: 0, 1: 1, 2: 2}, suspect=False,
      status={0: None, 1: "edited", 2: "edited"})

check("all new", fp(), fp("a", "b"), pairs={}, status={0: "new", 1: "new"})
check("all removed", fp("a", "b"), fp(), pairs={}, removed=[0, 1], status={})
check("append", fp("a", "b"), fp("a", "b", "c"),
      pairs={0: 0, 1: 1}, status={0: None, 1: None, 2: "new"})
check("prepend", fp("a", "b"), fp("z", "a", "b"),
      pairs={1: 0, 2: 1}, status={0: "new", 1: None, 2: None})
check("move to end", fp("a", "b", "c"), fp("a", "c", "b"))
# Three identical slides: which one is "the new one" is arbitrary, and any answer
# carries the same narration. Only require one insertion and no false edits.
r = check("duplicate slides", fp("a", "a", "b"), fp("a", "a", "a", "b"), removed=[])
assert sorted(r["status"].values(), key=str) == [None, None, None, "new"], r["status"]

# Every pair must be one-to-one and order-preserving, whatever the input.
for name, (o, n) in {
    "insert + edit + delete": (old, new),
    "move to end": (fp("a", "b", "c"), fp("a", "c", "b")),
    "re-export drift": (fp("a", "b", "c", "d"), fp("a2/a", "b2/b", "c2/c", "d2/d")),
}.items():
    r = slidematch.align(o, n)
    olds = list(r["pairs"].values())
    assert len(olds) == len(set(olds)), f"{name}: an old slide was claimed twice"
    ordered = [r["pairs"][j] for j in sorted(r["pairs"])]
    assert ordered == sorted(ordered), f"{name}: pairs cross"
    assert all(0 <= i < len(o) for i in olds), f"{name}: old index out of range"
print("ok  one-to-one and order-preserving on all shapes")

print("\nFAILED:", FAILED or "none")
sys.exit(1 if FAILED else 0)
