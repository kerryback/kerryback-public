"""Match a re-ingested deck against the previous ingest.

The author edits the deck and re-uploads the PDF, so slides can be added,
removed, or revised in place. Narration cannot be carried over by index:
inserting one page would shift every later slide's script onto the wrong
picture, while every slide still *looked* correctly matched. This module aligns
the two ingests on per-slide content and reports, for each new slide, which old
slide it came from and whether its content changed.

Audio needs no equivalent: clips are content-addressed by the text they speak
(see audio_gen), so once the narration lands on the right slide its audio
follows for free.

Alignment is a cascade of progressively weaker evidence. Each level matches what
it can; the runs left between those matches are handed down to the next level,
so a strong match never gets crossed by a weak one:

1. `image_sha` — the rendered page is byte-identical. The slide is unchanged.
2. `text_sha` — the words are identical but the pixels are not: a chart or
   diagram edit (or a re-export that re-rasterized). Matched, flagged `edited`.
3. text similarity — the words are merely close: a slide revised in place. This
   level is what keeps a reworded slide from being paired with a deleted
   neighbour just because it landed in the same position.
4. position — nothing left to go on. Within a run bounded by matched slides,
   the k-th old slide is the k-th new one, revised. Surplus new slides are
   insertions, surplus old ones deletions.

Two shas rather than one because either alone has a blind spot: the image misses
nothing but drifts when a re-export renders identical content differently, and
the text is stable but blind to a graphics-only edit. Fingerprints are computed
in `convert._fingerprints`; the `text` used by level 3 is the page text the
caller carries over from narration.json.
"""
from difflib import SequenceMatcher

EDITED = "edited"
NEW = "new"

# How alike two slides' text must be to read as the same slide, revised. Set by
# what it has to separate: a reworded version of a slide (which keeps its title,
# its structure, and most of its words) against an unrelated neighbouring slide.
SIMILAR_ENOUGH = 0.6

# Slide text is short, but ratio() is quadratic — bound it rather than trust that.
MAX_TEXT = 600


def _keys(slides: list, lo: int, hi: int, key: str, side: str) -> list:
    """Fingerprints for slides[lo:hi], with blanks made unmatchable.

    An all-graphic slide has no extractable text, so its text_sha is empty. Left
    as-is, every such slide would compare equal to every other one and the text
    level would confidently match unrelated slides. Each blank gets a unique
    sentinel instead, so blanks fall through to the levels below.
    """
    out = []
    for i in range(lo, hi):
        fp = slides[i].get(key) or ""
        out.append(fp if fp else f"\x00{side}{i}")
    return out


def _exact(key: str):
    """A level that matches slides whose `key` is identical, in order."""
    def match(old, new, i1, i2, j1, j2):
        sm = SequenceMatcher(None, _keys(old, i1, i2, key, "o"),
                             _keys(new, j1, j2, key, "n"), autojunk=False)
        pairs = []
        for a, b, size in sm.get_matching_blocks():
            for k in range(size):
                pairs.append((i1 + a + k, j1 + b + k))
        return pairs
    return match


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a[:MAX_TEXT], b[:MAX_TEXT], autojunk=False).ratio()


def _similar(old, new, i1, i2, j1, j2):
    """Match slides whose text is close but not identical.

    Greedy left to right, never looking back past a match already made, so the
    pairs it returns stay in order and cannot cross.
    """
    pairs = []
    lo = i1
    for j in range(j1, j2):
        best, best_score = None, SIMILAR_ENOUGH
        for i in range(lo, i2):
            score = _ratio(old[i].get("text", ""), new[j].get("text", ""))
            if score > best_score:
                best, best_score = i, score
        if best is not None:
            pairs.append((best, j))
            lo = best + 1
    return pairs


_LEVELS = (_exact("image_sha"), _exact("text_sha"), _similar)
_TEXT_LEVEL = 1  # the level whose matches mean "same words, different pixels"


def _align_range(old, new, i1, i2, j1, j2, level, pairs, edited, text_matched):
    """Align old[i1:i2] against new[j1:j2], recursing into the gaps one level down."""
    if i1 >= i2 or j1 >= j2:
        return  # a pure insertion or deletion — nothing on the other side to pair

    if level >= len(_LEVELS):
        for k in range(min(i2 - i1, j2 - j1)):
            pairs[j1 + k] = i1 + k
            edited.add(j1 + k)
        return

    matches = _LEVELS[level](old, new, i1, i2, j1, j2)
    prev_i, prev_j = i1, j1
    for oi, nj in matches:
        _align_range(old, new, prev_i, oi, prev_j, nj,
                     level + 1, pairs, edited, text_matched)
        pairs[nj] = oi
        if level > 0:
            # Matched on weaker evidence than an identical render: it moved.
            edited.add(nj)
            if level == _TEXT_LEVEL:
                text_matched.add(nj)
        prev_i, prev_j = oi + 1, nj + 1
    _align_range(old, new, prev_i, i2, prev_j, j2,
                 level + 1, pairs, edited, text_matched)


def align(old: list, new: list) -> dict:
    """Align two ingests of the same deck.

    old/new: per-slide records in slide order, `{index, image_sha, text_sha}` plus
    an optional `text` (the page's extracted text) for the similarity level.

    Returns:
      pairs   {new_index: old_index} for every new slide carried over
      status  {new_index: "edited" | "new" | None}, None meaning unchanged
      removed [old_index] that no new slide claims
      summary counts + `suspect_rerender` (see below)
    """
    pairs: dict = {}
    edited: set = set()
    text_matched: set = set()
    _align_range(old, new, 0, len(old), 0, len(new), 0, pairs, edited, text_matched)

    status = {}
    for j in range(len(new)):
        if j not in pairs:
            status[j] = NEW
        elif j in edited:
            status[j] = EDITED
        else:
            status[j] = None

    removed = sorted(set(range(len(old))) - set(pairs.values()))
    n_edited = sum(1 for v in status.values() if v == EDITED)
    n_new = sum(1 for v in status.values() if v == NEW)

    # A deck where most matched slides came back "same words, different pixels"
    # is far more likely to have been re-exported (fonts or rasterization
    # drifted) than genuinely rewritten slide by slide. Say so, rather than
    # silently inviting a full redraft and a full re-synthesis.
    suspect = (len(text_matched) >= 3
               and len(pairs) > 0
               and len(text_matched) >= 0.6 * len(pairs))

    return {
        "pairs": pairs,
        "status": status,
        "removed": removed,
        "summary": {
            "total": len(new),
            "unchanged": len(new) - n_edited - n_new,
            "edited": n_edited,
            "new": n_new,
            "removed": len(removed),
            "suspect_rerender": suspect,
        },
    }
