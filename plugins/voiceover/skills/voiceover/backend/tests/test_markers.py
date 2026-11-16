"""Marker parsing and recording schedule. Runs with plain python3, no pytest:
    python3 tests/test_markers.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from builderlib import markers  # noqa: E402


def check(label, got, want):
    assert got == want, f"{label}: got {got!r}, want {want!r}"


def test_split():
    check("middle", markers.split("Demand first. [next] Then supply."),
          ("Demand first. Then supply.", [14]))
    check("no space", markers.split("A.[next]B."), ("A. B.", [3]))
    check("start", markers.split("[next] A b"), ("A b", [0]))
    check("end", markers.split("A b [next]"), ("A b", [3]))
    check("two", markers.split("A [next] B [NEXT] C"), ("A B C", [2, 4]))
    check("spaces inside", markers.split("A [ next ] B"), ("A B", [2]))
    check("v3 tag kept", markers.split("[excited] A [next] B"),
          ("[excited] A B", [12]))
    check("none", markers.split("  plain   text "), ("plain text", []))
    check("count", markers.count("a [next] b [next]"), 2)


def test_times():
    al = {"character_start_times_seconds": [0.0, 0.1, 0.2, 0.3, 0.4]}
    check("exact", markers.times([2], al, 5, 1.0), [0.2])
    check("end", markers.times([5], al, 5, 1.0), [1.0])
    check("fallback", markers.times([2], {}, 4, 2.0), [1.0])
    check("mismatch", markers.times([1], al, 10, 10.0), [1.0])


def test_schedule():
    # Imported here: reveal_video pulls in imageio_ffmpeg, which only the app
    # environment has.
    from builderlib import reveal_video as vg
    silent = {"clip": None, "steps": 2, "duration": 0, "times": []}
    fr, length = vg.schedule(silent)
    check("silent frags", fr, [vg.SILENT_STEP_S, 2 * vg.SILENT_STEP_S])
    check("silent len", length, 2 * vg.SILENT_STEP_S + vg.SILENT_DWELL_S)
    voiced = {"clip": "x", "steps": 3, "duration": 10.0, "times": [2.0]}
    fr, length = vg.schedule(voiced)
    end = vg.LEAD_S + 10.0
    check("voiced frags", fr, [vg.LEAD_S + 2.0, end, end + vg.LEFTOVER_STEP_S])
    check("voiced len", length, end + vg.LEFTOVER_STEP_S + vg.INTER_SLIDE_PAUSE_S)
    extra = {"clip": "x", "steps": 1, "duration": 5.0, "times": [1.0, 2.0]}
    fr, _ = vg.schedule(extra)
    check("extra markers ignored", fr, [vg.LEAD_S + 1.0])


if __name__ == "__main__":
    test_split()
    test_times()
    try:
        test_schedule()
    except ImportError as e:
        print(f"skipped schedule tests ({e})")
    print("ok")
