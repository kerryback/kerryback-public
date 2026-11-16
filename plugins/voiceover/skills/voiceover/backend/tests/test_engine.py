"""The text-to-speech engine choice. No network, no model:

    python3 backend/tests/test_engine.py

Covers how the engine is resolved, that the two engines never share a cached
clip, that an ElevenLabs PDF deck keeps the build signature it had before
engines (and reveal.js decks) existed, and that a reveal.js deck's Kokoro clips
are timed at their [next] markers. Runs against a throwaway VOICEOVER_HOME and DATA_DIR.
"""
import hashlib
import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp())
os.environ["VOICEOVER_HOME"] = str(TMP / "home")
os.environ["DATA_DIR"] = str(TMP / "data")
os.environ.pop("TTS_ENGINE", None)
os.environ.pop("ELEVENLABS_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from builderlib import audio_gen, config, db, kokoro, store  # noqa: E402

FAILED = []


def check(name, ok, detail=""):
    print(f"{'ok ' if ok else 'BAD'} {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILED.append(name)


# --- resolving the engine ----------------------------------------------------
config.TTS_ENGINE = ""
config.ELEVENLABS_API_KEY = ""
check("unset, no key -> kokoro", config.tts_engine() == "kokoro")
check("unset is not a choice", not config.tts_engine_chosen())
config.ELEVENLABS_API_KEY = "sk_test"
check("unset, key -> elevenlabs (existing installs unchanged)",
      config.tts_engine() == "elevenlabs")
config.set_tts_engine("kokoro")
check("chosen kokoro wins over a key", config.tts_engine() == "kokoro")
check("choice saved to the home .env",
      "TTS_ENGINE=kokoro" in config.ENV_FILE.read_text())
try:
    config.set_tts_engine("espeak")
    check("unknown engine rejected", False)
except ValueError:
    check("unknown engine rejected", True)

# --- the audio cache keeps the engines apart -----------------------------------
eleven = audio_gen._voice_sig("J9NvviOEdVm6E7Hwdpdj", "eleven_v3",
                              audio_gen._merged_settings(None))
koko = audio_gen._kokoro_sig(audio_gen._kokoro_settings({"voice": "af_heart",
                                                         "speed": 1.0}))
check("signatures differ by engine", eleven != koko, koko)
check("kokoro speed is in the signature",
      koko != audio_gen._kokoro_sig(audio_gen._kokoro_settings(
          {"voice": "af_heart", "speed": 0.9})))
check("speed clamped", kokoro.clamp_speed(5) == kokoro.SPEED_RANGE[1])
check("28 English voices", len(kokoro.voice_list()) == 28)
check("British voices use en-gb", kokoro.lang("bf_emma") == "en-gb"
      and kokoro.lang("af_heart") == "en-us")

# --- build signature ----------------------------------------------------------
db.init()
pid = "sigtest"
store.pdir(pid).mkdir(parents=True, exist_ok=True)
store.narration_path(pid).write_text(
    '{"slides": [{"index": 0, "narration": "Hello."}]}', encoding="utf-8")
cfg = store.read_config(pid)
old_parts = ["0:Hello."] + [f"{k}={cfg.get(k)}" for k in sorted(store.ELEVEN_KEYS)]
old_sig = hashlib.sha256("\x00".join(old_parts).encode("utf-8")).hexdigest()

config.set_tts_engine("elevenlabs")
check("elevenlabs signature same as before engines existed",
      store.build_signature(pid) == old_sig)
store.write_config(pid, {"kokoro_voice": "bm_george"})
check("idle engine's settings do not mark the video stale",
      store.build_signature(pid) == old_sig)
config.set_tts_engine("kokoro")
k1 = store.build_signature(pid)
check("switching engine changes the signature", k1 != old_sig)
store.write_config(pid, {"kokoro_voice": "af_bella"})
check("kokoro voice change changes the signature", store.build_signature(pid) != k1)

# --- PDF and reveal.js decks ------------------------------------------------------
config.set_tts_engine("elevenlabs")
check("a deck with no format is a PDF deck", store.deck_format(pid) == store.PDF)
if db.get_project(pid) is None:
    db.create_project(pid, pid, None, "ready")
db.update_project(pid, source_type="pdf")
check("a PDF deck's signature is unchanged", store.build_signature(pid) == old_sig)
db.update_project(pid, source_type=store.REVEALJS, deck_sha="abc")
check("a reveal.js deck's signature covers the deck as read",
      store.build_signature(pid) != old_sig)
check("file type picks the format",
      [__import__("builderlib.deck", fromlist=["x"]).deck_kind(Path(n))
       for n in ("a.pdf", "a.html", "a.zip", "a.pptx")]
      == ["pdf", "revealjs", "revealjs", None])

# A PDF build names its clips exactly as before: sha(text + NUL + signature),
# with the text stripped but [next] left alone.
spoken = []
audio_gen.synthesize = lambda text, out, *a, **k: (spoken.append(text), out.write_bytes(b"mp3"))
adir = TMP / "audio_pdf"
audio_gen.generate([{"index": 0, "narration": " Hi [next] there. "}], adir,
                   "J9NvviOEdVm6E7Hwdpdj", "eleven_v3")
want = hashlib.sha256(("Hi [next] there." + chr(0) + eleven).encode()).hexdigest()[:32] + ".mp3"
check("PDF clip name unchanged", (adir / want).exists(), str(sorted(p.name for p in adir.iterdir())))
check("PDF text spoken as written", spoken == ["Hi [next] there."], str(spoken))

# --- Kokoro timings at the markers ---------------------------------------------
# Stand in for the model: each piece takes 0.1 s per character.
from builderlib import markers  # noqa: E402

def fake_segments(pieces, out_path, voice, speed):
    out_path.write_bytes(b"mp3")
    at, t = [], 0.0
    for p in pieces:
        at.append(t)
        t += 0.1 * len(p)
    return at + [t]

kokoro.synthesize_segments = fake_segments
narr = "Demand slopes down. [next] Supply slopes up. [next] They cross."
text, offsets = markers.split(narr)
clip = TMP / "clip.mp3"
audio_gen.synthesize_kokoro_timed(text, offsets, clip, {"voice": "af_heart", "speed": 1.0})
timing = audio_gen.read_timing(clip)
got = markers.times(offsets, timing.get("alignment"), len(text), 0.1 * len(text))
want = [round(0.1 * o, 6) for o in offsets]
check("one timestamp per character",
      len(timing["alignment"]["character_start_times_seconds"]) == len(text))
check("each marker fires where its piece starts",
      [round(t, 6) for t in got] == want, f"{got} vs {want}")

print()
print("FAILED:", ", ".join(FAILED) or "none")
sys.exit(1 if FAILED else 0)
