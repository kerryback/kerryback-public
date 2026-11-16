"""Record the narrated MP4: play the deck in headless Chrome in real time, with
each slide's audio, and capture the screen.

Why real time: a reveal.js deck moves on its own clock — slide transitions,
auto-animate, CSS animations, embedded video, JavaScript charts. Playing it and
recording what the browser paints captures all of it with no special handling.
The cost is that a build takes as long as the video.

How it runs:
1. Open the deck at 1080 pixels high, presenter furniture off (browser.py).
2. Start Chrome's screencast (CDP Page.startScreencast). Chrome sends a JPEG
   each time the page repaints, stamped with the time it was painted, and none
   while nothing moves. A writer thread turns that variable stream into a
   constant 30 fps one — repeating the last frame until the next arrives — and
   pipes it to ffmpeg. Nothing is buffered on disk but the encoded video.
   (Playwright's built-in recorder was not used: it encodes VP8 at a fixed low
   bitrate, which blurs slide text.)
3. For each slide: show it with every fragment hidden, start its audio LEAD_S
   later, and call Reveal.nextFragment() at the time of each `[next]` marker,
   taken from the clip's character timestamps (markers.py). Steps left over
   when the audio ends are shown then, so nothing stays hidden. Hold
   INTER_SLIDE_PAUSE_S, then move on.
4. Every slide change is logged at the time it actually happened, and the audio
   track is assembled from that log, so a slow step never pulls the voice out
   of sync with the picture — it only lengthens the pause.
5. Mux video + audio + cover art into the MP4.

Waiting is done with page.wait_for_timeout, never time.sleep: Playwright's sync
API delivers screencast frames only while it is inside one of its own calls,
and a frame left unacknowledged stops the screencast.

ffmpeg is provided by the `imageio-ffmpeg` pip package (a bundled static
binary), so there is no system ffmpeg dependency.
"""
import base64
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import wave
from pathlib import Path

import imageio_ffmpeg

from . import audio_gen, browser, markers, store

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

FPS = 30
CANVAS_H = 1080
LEAD_S = 0.6                # slide shown, transition plays, then the voice starts
INTER_SLIDE_PAUSE_S = 1.5   # after a slide's narration ends
SILENT_DWELL_S = 4.0        # a slide with no narration
SILENT_STEP_S = 1.2         # between fragments on a slide with no narration
LEFTOVER_STEP_S = 0.5       # between steps shown after the audio ran out
SETTLE_S = 1.5              # fonts, MathJax and images before recording starts
SAMPLE_RATE = 44100
JPEG_QUALITY = 92


class _Encoder:
    """Variable-rate screencast frames in, constant-rate H.264 out."""

    def __init__(self, out: Path):
        self.proc = subprocess.Popen(
            [FFMPEG, "-y", "-loglevel", "error",
             "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", str(FPS), "-i", "-",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
             "-pix_fmt", "yuv420p", "-r", str(FPS),
             # Even dimensions for yuv420p, whatever size the frames come in.
             # Screencast JPEGs are full-range; convert to the TV range every
             # player expects, or some show the slides washed out.
             "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2:in_range=full:out_range=tv,"
                    "format=yuv420p",
             "-color_range", "tv",
             str(out)],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        self.q: queue.Queue = queue.Queue()
        self.t0 = None          # timestamp of the first frame = video time 0
        self.ticks = 0          # frames written so far
        self.last = None
        self.error = None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def push(self, ts: float, jpeg: bytes) -> None:
        self.q.put((ts, jpeg))

    def finish(self, end_ts: float) -> None:
        self.q.put(("end", end_ts))
        self.thread.join()
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        err = self.proc.stderr.read().decode("utf-8", "replace")
        if self.proc.wait() != 0 or self.error:
            raise RuntimeError(f"Video encode failed: {self.error or err[-500:]}")

    def kill(self) -> None:
        self.q.put(("end", None))
        try:
            self.proc.kill()
        except OSError:
            pass

    def _emit_until(self, ts: float) -> None:
        while self.t0 + self.ticks / FPS < ts:
            self.proc.stdin.write(self.last)
            self.ticks += 1

    def _run(self) -> None:
        try:
            while True:
                ts, jpeg = self.q.get()
                if ts == "end":
                    if jpeg is not None and self.last is not None:
                        self._emit_until(jpeg)
                    return
                if self.t0 is None:
                    self.t0 = ts
                elif self.last is not None:
                    self._emit_until(ts)
                self.last = jpeg
        except (BrokenPipeError, OSError) as e:
            self.error = str(e)


def _plan(pid: str) -> list:
    """Per slide, in order: where it is, how many steps, its clip and the times
    of its markers within that clip."""
    slides = sorted(store.read_narration(pid)["slides"], key=lambda s: s["index"])
    audio_dir = store.audio_dir(pid)
    manifest = {}
    man_path = audio_dir / "manifest.json"
    if man_path.exists():
        for e in json.loads(man_path.read_text(encoding="utf-8")):
            if e.get("file"):
                manifest[e["index"]] = e["file"]
    plan = []
    for s in slides:
        clip = None
        duration = 0.0
        times = []
        name = manifest.get(s["index"])
        if name and (audio_dir / name).exists():
            clip = audio_dir / name
            duration = probe_duration(clip)
            text, offsets = markers.split(s.get("narration") or "")
            timing = audio_gen.read_timing(clip)
            times = markers.times(offsets, timing.get("alignment"), len(text),
                                  duration)
        plan.append({"index": s["index"], "h": s.get("h", s["index"]),
                     "v": s.get("v", 0), "steps": int(s.get("steps") or 0),
                     "clip": clip, "duration": duration, "times": times})
    return plan


def schedule(item: dict) -> tuple[list, float]:
    """(fragment times, slide length), in seconds from the moment the slide is
    shown. Pure, so the timing rules can be tested without a browser."""
    steps = item["steps"]
    if item["clip"] is None:
        fr = [SILENT_STEP_S * (k + 1) for k in range(steps)]
        return fr, (fr[-1] if fr else 0.0) + SILENT_DWELL_S
    marked = [LEAD_S + t for t in item["times"][:steps]]
    end = LEAD_S + item["duration"]
    leftover = [end + LEFTOVER_STEP_S * k for k in range(steps - len(marked))]
    fr = marked + leftover
    tail = max([end] + fr)
    return fr, tail + INTER_SLIDE_PAUSE_S


def probe_duration(path: Path) -> float:
    """Seconds of an audio file, from its decoded length."""
    pcm = _decode(path)
    return len(pcm) / 2 / SAMPLE_RATE


def _decode(path: Path) -> bytes:
    out = subprocess.run(
        [FFMPEG, "-loglevel", "error", "-i", str(path), "-f", "s16le",
         "-ac", "1", "-ar", str(SAMPLE_RATE), "-"],
        capture_output=True, check=True)
    return out.stdout


def _write_audio(placements: list, length_s: float, out: Path) -> None:
    """One mono WAV: silence, with each clip at the second it was started."""
    total = int(length_s * SAMPLE_RATE) + SAMPLE_RATE
    buf = bytearray(total * 2)
    for start_s, clip in placements:
        pcm = _decode(clip)
        at = max(0, int(round(start_s * SAMPLE_RATE))) * 2
        end = min(len(buf), at + len(pcm))
        buf[at:end] = pcm[:end - at]
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(buf))


def _record(html: Path, plan: list, video_out: Path, progress, cancel) -> tuple:
    """Play the deck and record it. Returns (audio placements, length in s)."""
    placements = []
    with browser.chrome() as b:
        w, h = browser.deck_size(b, html)
        vp = browser.viewport_for(w, h, CANVAS_H)
        page = browser.open_deck(b, html, vp)
        try:
            first = plan[0]
            page.evaluate(f"() => Reveal.slide({first['h']}, {first['v']}, -1)")
            page.evaluate("() => document.fonts && document.fonts.ready")
            page.wait_for_timeout(int(SETTLE_S * 1000))

            enc = _Encoder(video_out)
            cdp = page.context.new_cdp_session(page)
            clock = {"skew": None}

            def on_frame(evt):
                ts = evt["metadata"].get("timestamp") or time.time()
                # Chrome stamps frames in wall-clock seconds; guard against a
                # build that ever stamps on another clock.
                if clock["skew"] is None:
                    clock["skew"] = 0.0 if abs(ts - time.time()) < 5 else time.time() - ts
                enc.push(ts + clock["skew"], base64.b64decode(evt["data"]))
                try:
                    cdp.send("Page.screencastFrameAck",
                             {"sessionId": evt["sessionId"]})
                except Exception:
                    pass

            cdp.on("Page.screencastFrame", on_frame)
            cdp.send("Page.startScreencast", {
                "format": "jpeg", "quality": JPEG_QUALITY,
                "maxWidth": vp["width"], "maxHeight": vp["height"],
                "everyNthFrame": 1})

            def wait_until(t: float) -> None:
                while True:
                    if cancel is not None and cancel.is_set():
                        raise audio_gen.Cancelled()
                    left = t - time.time()
                    if left <= 0:
                        return
                    page.wait_for_timeout(min(left, 0.25) * 1000)

            # Wait for the first frame, which fixes video time 0.
            deadline = time.time() + 5
            while enc.t0 is None and time.time() < deadline:
                page.wait_for_timeout(20)
            if enc.t0 is None:
                enc.kill()
                raise RuntimeError("Chrome sent no frames to record.")
            # A static page repaints only when something changes, so nudge one
            # repaint to be sure the opening frame is the opening slide.
            page.wait_for_timeout(300)

            try:
                total = len(plan)
                for n, item in enumerate(plan):
                    if progress:
                        progress(n, total, f"Recording slide {n + 1} of {total} "
                                 "(plays in real time)")
                    shown = time.time()
                    if n > 0:
                        page.evaluate(
                            f"() => Reveal.slide({item['h']}, {item['v']}, -1)")
                        shown = time.time()
                    frags, length = schedule(item)
                    if item["clip"] is not None:
                        placements.append((shown + LEAD_S - enc.t0, item["clip"]))
                    for t in frags:
                        wait_until(shown + t)
                        page.evaluate("() => Reveal.nextFragment()")
                    wait_until(shown + length)
                end = time.time()
                cdp.send("Page.stopScreencast")
                page.wait_for_timeout(100)
            except BaseException:
                enc.kill()
                raise
            enc.finish(end)
            length_s = end - enc.t0
        finally:
            page.close()
    if progress:
        progress(len(plan), len(plan), "Recorded")
    return placements, length_s


def generate(pid: str, progress=None, cancel=None) -> Path:
    """Record <deck>.mp4 and return its path.

    `cancel` (a threading.Event) is checked throughout the recording. The
    previous video is replaced only by the final rename, so a stopped or failed
    run leaves it untouched.
    """
    plan = _plan(pid)
    if not plan:
        raise RuntimeError("This deck has no slides to record.")
    html = store.deck_html(pid)
    if not html or not html.is_file():
        raise RuntimeError("The deck's .html file is no longer where the app "
                           "read it. Open it again.")

    work = store.pdir(pid) / "video_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    try:
        video = work / "video.mp4"
        placements, length_s = _record(html, plan, video, progress, cancel)
        audio_gen._check(cancel)

        audio = work / "audio.wav"
        _write_audio(placements, length_s, audio)

        # The first slide doubles as the file's cover art, so Finder and
        # QuickTime show the title slide as the thumbnail.
        cover = work / "cover.jpg"
        first_png = store.slides_dir(pid) / "slide-001.png"
        have_cover = first_png.exists()
        if have_cover:
            subprocess.run(
                [FFMPEG, "-y", "-loglevel", "error", "-i", str(first_png),
                 "-vf", f"scale=-2:{CANVAS_H},format=yuvj420p",
                 "-frames:v", "1", "-q:v", "2", str(cover)],
                capture_output=True, check=True)

        out = store.video_path(pid)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(out.stem + ".part.mp4")
        cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", str(video),
               "-i", str(audio)]
        if have_cover:
            cmd += ["-i", str(cover)]
        cmd += ["-map", "0:v", "-map", "1:a"]
        if have_cover:
            cmd += ["-map", "2:v", "-disposition:v:1", "attached_pic"]
        cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-ac", "1",
                "-ar", str(SAMPLE_RATE), "-t", f"{length_s:.3f}",
                "-movflags", "+faststart", str(tmp)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"Muxing the video failed: {r.stderr[-500:]}")
        os.replace(tmp, out)
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True)
