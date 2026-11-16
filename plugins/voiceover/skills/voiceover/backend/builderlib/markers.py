"""Step markers: where in a slide's script the deck advances to its next fragment.

A slide keeps one continuous script. The author (or Claude) types `[next]` at
the point where the next fragment should appear:

    Demand slopes down because of substitution. [next] Supply slopes up ...

Markers are stripped before the text goes to ElevenLabs, so they cost nothing
and never reach the voice. `split` returns the spoken text plus the character
offset, in that spoken text, of each marker; the build turns each offset into a
time using the clip's character timestamps.

ElevenLabs v3 also uses square brackets, for audio tags like `[excited]`. Only
the exact word `next` (any case, optional inner spaces) is a marker; every other
bracketed tag passes through to the voice untouched.
"""
import re

MARKER_RE = re.compile(r"\[\s*next\s*\]", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def split(narration: str) -> tuple[str, list[int]]:
    """(spoken_text, marker_offsets).

    The spoken text is the narration with every marker removed and the
    whitespace around each marker collapsed to one space. Each offset is the
    index in the spoken text of the first character spoken after that marker,
    so a marker at the very end has offset len(spoken_text).
    """
    text = narration or ""
    parts = MARKER_RE.split(text)
    spoken = ""
    offsets = []
    for i, part in enumerate(parts):
        piece = _WS_RE.sub(" ", part)
        if i == 0:
            piece = piece.lstrip()
        else:
            # Join the pieces with exactly one space, never two, never none
            # between words.
            piece = piece.lstrip()
            if spoken and piece and not spoken.endswith(" "):
                spoken += " "
            offsets.append(len(spoken))
        spoken += piece
    spoken = spoken.rstrip()
    offsets = [min(o, len(spoken)) for o in offsets]
    return spoken, offsets


def spoken(narration: str) -> str:
    return split(narration)[0]


def count(narration: str) -> int:
    return len(MARKER_RE.findall(narration or ""))


def times(offsets: list[int], alignment: dict | None, text_len: int,
          duration: float) -> list[float]:
    """Seconds into the clip at which each marker falls.

    Uses the character start times ElevenLabs returned with the clip. When they
    are missing, or do not line up with the text that was sent, falls back to a
    position proportional to the character offset: rougher, but never wrong by
    more than a sentence on a normal slide.
    """
    starts = (alignment or {}).get("character_start_times_seconds") or []
    exact = len(starts) == text_len and text_len > 0
    out = []
    for off in offsets:
        if off >= text_len:
            out.append(duration)
        elif exact:
            out.append(float(starts[off]))
        else:
            out.append(duration * off / max(text_len, 1))
    return out
