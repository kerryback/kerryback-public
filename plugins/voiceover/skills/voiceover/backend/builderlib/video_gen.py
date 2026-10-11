"""Compose a downloadable narrated MP4 from the per-slide PNGs and per-slide TTS
audio the build already produced.

No screen-recording of the reveal player is involved: each slide image is shown
for the length of its narration (plus a short inter-slide pause), silent slides
dwell for a fixed beat, and the segments are concatenated into one video.mp4.

ffmpeg is provided by the `imageio-ffmpeg` pip package (a bundled static binary),
so there is no system ffmpeg dependency — it works the same locally and in the
container.
"""
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import imageio_ffmpeg

from . import config, store

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# Every slide is scaled and padded to one canvas, so the segments concat cleanly.
# The canvas follows the deck's own page shape rather than a fixed 16:9: a 16:10
# or 4:3 deck forced into 1920x1080 picks up black pillarbox bars that then show
# on every page the finished video is embedded in.
CANVAS_H = 1080             # target height; width follows the deck's aspect
CANVAS_W_MAX = 2560         # guard against a freakishly wide page
FPS = 25
INTER_SLIDE_PAUSE_S = 1.5   # trailing silence after each narration
SILENT_DWELL_S = 4.0        # how long a slide with no narration is shown

_VENC = ["-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
         "-r", str(FPS)]
# The TTS clips are mono speech. Encoding them as 192k stereo duplicates one
# identical channel and dominates the file — audio ran ~4x the size of the video.
_AENC = ["-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-ac", "1"]


def _png_size(path: Path):
    """(width, height) from a PNG's IHDR, without pulling in an image library."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def _canvas(png: Path) -> tuple:
    """Canvas for the whole video, taken from the deck's own page shape.

    Height is fixed at CANVAS_H and width follows the page aspect, both rounded
    to even numbers (libx264 with yuv420p requires it). A deck whose pages are
    all one shape — the normal case — therefore renders with no padding at all.
    """
    size = _png_size(png)
    if not size or size[0] <= 0 or size[1] <= 0:
        return 1920, CANVAS_H
    w = int(round(CANVAS_H * size[0] / size[1]))
    w = min(max(w, 2), CANVAS_W_MAX)
    return w - (w % 2), CANVAS_H - (CANVAS_H % 2)


def _vscale(cw: int, ch: int) -> str:
    """Fit a slide into the canvas. The pad is a safety net for a deck with a
    stray odd-sized page; with a uniform deck it is a no-op."""
    return (f"scale={cw}:{ch}:force_original_aspect_ratio=decrease,"
            f"pad={cw}:{ch}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1,format=yuv420p")

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def _probe_duration(path: Path) -> float:
    """Seconds of an audio/video file, via ffmpeg's stderr banner."""
    out = subprocess.run([FFMPEG, "-i", str(path)],
                         capture_output=True, text=True).stderr
    m = _DURATION_RE.search(out)
    if not m:
        return 0.0
    h, mm, ss = m.groups()
    return int(h) * 3600 + int(mm) * 60 + float(ss)


def _encode_narrated(png: Path, mp3: Path, out: Path, vscale: str) -> None:
    total = _probe_duration(mp3) + INTER_SLIDE_PAUSE_S
    cmd = [
        FFMPEG, "-y", "-loop", "1", "-i", str(png), "-i", str(mp3),
        "-filter_complex",
        f"[0:v]{vscale}[v];[1:a]apad=pad_dur={INTER_SLIDE_PAUSE_S}[a]",
        "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
        *_VENC, *_AENC, str(out),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def _encode_silent(png: Path, out: Path, vscale: str) -> None:
    cmd = [
        FFMPEG, "-y", "-loop", "1", "-i", str(png),
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-filter_complex", f"[0:v]{vscale}[v]",
        "-map", "[v]", "-map", "1:a", "-t", f"{SILENT_DWELL_S:.3f}",
        *_VENC, *_AENC, str(out),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def generate(pid: str, progress=None) -> Path:
    """Render <project>/video.mp4 and return its path.

    Slide index i uses slides/slide-{i+1:03d}.png and the audio file the manifest
    maps to index i (silent if none). Raises if there are no slide images.
    """
    slides = sorted(store.read_narration(pid)["slides"], key=lambda s: s["index"])
    slides_dir = store.slides_dir(pid)
    audio_dir = store.audio_dir(pid)

    manifest = {}
    man_path = audio_dir / "manifest.json"
    if man_path.exists():
        for e in json.loads(man_path.read_text(encoding="utf-8")):
            if e.get("file"):
                manifest[e["index"]] = e["file"]

    work = store.pdir(pid) / "video_work"
    if work.exists():
        import shutil
        shutil.rmtree(work)
    work.mkdir(parents=True)

    # Build the (index, png, mp3-or-None) work list, skipping missing images.
    jobs = []
    for s in slides:
        i = s["index"]
        png = slides_dir / f"slide-{i + 1:03d}.png"
        if not png.exists():
            continue
        mp3_name = manifest.get(i)
        mp3 = audio_dir / mp3_name if mp3_name else None
        jobs.append((i, png, mp3 if (mp3 and mp3.exists()) else None))

    if not jobs:
        raise RuntimeError("no slide images to render into a video")

    total = len(jobs)
    done = 0

    # One canvas for the whole video, from the first slide's page shape.
    vscale = _vscale(*_canvas(jobs[0][1]))

    def _one(item):
        i, png, mp3 = item
        seg = work / f"seg-{i:03d}.mp4"
        if mp3:
            _encode_narrated(png, mp3, seg, vscale)
        else:
            _encode_silent(png, seg, vscale)
        return i, seg

    segs = {}
    workers = max(1, min(config.VIDEO_CONCURRENCY, total))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, item) for item in jobs]
        for fut in as_completed(futures):
            i, seg = fut.result()
            segs[i] = seg
            done += 1
            if progress:
                progress(done, total, "Rendering video")

    # Concatenate in slide order (identical codecs/params -> stream copy).
    ordered = [segs[i] for i, _, _ in jobs]
    list_file = work / "segments.txt"
    list_file.write_text(
        "".join(f"file '{seg.as_posix()}'\n" for seg in ordered), encoding="utf-8")

    out = store.video_path(pid)
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c", "copy", "-movflags", "+faststart", str(out)],
        capture_output=True, text=True, check=True)

    import shutil
    shutil.rmtree(work, ignore_errors=True)
    return out
