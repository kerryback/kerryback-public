# Voiceover — orientation for Claude

Read this first when working on this repo. It describes what the app is, how it
is structured, and the design decisions behind it (with the reasoning, so you
don't undo them by accident).

## What it is

A local app, launched as a Claude Code skill, that turns a slide deck into a
narrated MP4 video plus a transcript.

A deck is one file, and its type picks one of two ways to make the video:

- A PDF the author exported from their slides. The app copies it into the deck
  folder and renders a page image per slide; the video shows each image for
  the length of its narration.
- A reveal.js deck: the rendered `.html` (Quarto's revealjs output, or any page
  that starts reveal.js). The app reads it in place in headless Chrome, and the
  video is recorded from the browser in real time, with its fragments,
  transitions and animations, each fragment timed to a `[next]` marker in the
  script.

Either way the app owns the narration in `narration.json`. A deck arrives as a
path (the launcher was given one) or as a browser upload (it wasn't, so the app
opens on Upload and waits): a PDF, or for reveal.js a `.zip` of the deck's
folder or a self-contained `.html`. The format is kept per deck as
`source_type` in `meta.json` (`store.deck_format`: `"pdf"`, or `"revealjs"`; a
deck with neither is a PDF deck from before reveal.js decks were supported).

The reveal.js half began as a separate plugin, voiceover-html, copied from
this one, and was merged back in at 4.0.0 so a change is made once. Both
halves share the narration store, the editor, the audio cache, slidematch,
the event stream and the voice picker; the format-specific code is in its own
modules, listed below.

Two roles — keep them straight:
- The author runs this app on their own machine to author the video. The
  server, the port (8010), and the ElevenLabs key all live here.
- Viewers run nothing. They receive `<name>.mp4` and `<name>.txt` and view them
  like any other file. There is no viewer-facing app or URL.

## Architecture

1. Backend — `backend/`, FastAPI. Owns decks, runs the two long jobs (ingest,
   build) in background threads, reports progress over an event stream, and
   serves the SPA + the rendered video. No auth, no LLM calls. For a reveal.js
   deck, both jobs launch headless Chrome; a PDF deck never does.
2. Frontend — `frontend/`, React + Vite + Tailwind. Four screens in one top bar
   with Generate among them: Upload · Narration text · Audio settings ·
   [Generate] · Preview. The launcher opens `/?project=<id>`, or bare `/`.

Key backend modules (`backend/builderlib/`):
- `deck.py` — ingest a PDF: page PNGs, per-page text/title, content fingerprints.
  Also `deck_kind`, the one place a file type is mapped to a format.
- `reveal_deck.py` — ingest a reveal.js deck: per-slide indices, fragment step
  count, text, notes, thumbnail, fingerprints; unpack uploads.
- `browser.py` — launch headless Chrome (the installed Chrome, else
  Playwright's Chromium, installed once on first need), load a deck, turn off
  presenter furniture.
- `markers.py` — parse `[next]` markers; turn their offsets into times.
- `slidematch.py` — align a new ingest against the previous one (see below).
- `store.py` / `db.py` — folder-backed registry (no database: each deck folder's
  `meta.json` is the source of truth) and per-deck file I/O, including the
  narration store.
- `jobs.py` — two jobs, `_ingest` and `_build`, each run in a thread via `_run_bg`.
- `audio_gen.py` — content-addressed per-slide TTS. With `timed=True` (a
  reveal.js deck) it strips markers and saves character timestamps per clip.
- `video_gen.py` — PDF: composes the PNGs + MP3s into the MP4 with ffmpeg (from
  the `imageio-ffmpeg` pip wheel — no system ffmpeg).
- `reveal_video.py` — reveal.js: play and record the deck, assemble the audio
  from the log of slide changes, mux the MP4.

## Deck lifecycle (states)

`loading → ready → building → built`, with `load_failed` and `building_failed`.
`ready` means page images and narration are in hand. Staleness is computed, not
tracked: `store.build_signature` shas every slide's narration plus the voice
settings (and, for a reveal.js deck, the deck file's sha as last read), `_build`
stamps it, and `store.is_stale` compares. A PDF deck's signature has no format
line, so it is byte-identical to the signature before reveal.js decks existed;
keep it that way, or every built PDF deck turns stale on upgrade. There is no edit
bookkeeping to get wrong.

## Design choices (and why)

Input is a PDF or a rendered reveal.js deck, and the file type decides.
A PDF is the one thing every slide tool exports faithfully. Reading `.pptx`
directly was tried — LibreOffice mangles PowerPoint (cropped table cells,
animation builds) — so a `.pptx` or `.key` is answered with "export it to PDF
first", not silently converted. A reveal.js deck is the exception worth its
cost: its animations are the point, and a PDF loses them. The author is never
asked which path to take; `deck.deck_kind` maps the extension.

The narration lives in the app, and both authors write to the same copy.
A PDF has nowhere to keep speaker notes, and a rendered reveal.js file is
rebuilt on every render, so `narration.json` in the deck folder is the single
copy. A reveal.js deck's own speaker notes are read and handed to Claude as
drafting context, never written back. The author types into an autosaving textarea; Claude writes
through `PUT …/narration` (bulk) and `PUT …/narration/{index}` (one slide). The
editor keeps a `pending` map of unflushed edits and layers it over every poll, so
narration arriving from Claude never overwrites something being typed. Version 2.x
instead kept the notes in the author's own `.qmd`/`.pptx` and had no editor at
all; that removed the two-copy problem but also removed the screen people
actually worked on, and made a PDF-only deck impossible to narrate.

The wait for Claude's draft is visible, and Generate will not render silence.
Nothing connects the browser to the Claude Code session — the app only ever sees
slides appear through the narration API — so the minute or two after an upload
looked exactly like nothing happening, and the obvious move was to press
Generate. That spends ElevenLabs quota on a video of silence and says so only in
a transcript full of "(silent)" afterwards. Two halves fix it and depend on each
other: the skill writes narration in batches of about five slides instead of one
PUT at the end, and `DraftStatus` turns those arrivals into "Claude Code is
writing — 12 of 41". Drop the batching and the status has nothing to show until
the whole deck lands at once. When nothing has arrived recently the same panel
says so plainly and points at the Claude Code window, because the app genuinely
cannot tell a Claude that is thinking from one that was never asked — do not
make it assert either. `App.NothingToSay` is the second half: Generate stops on
any empty slide, keeps "Generate anyway" for a deliberately part-narrated deck,
and is a banner rather than a modal because the fix lives on another screen.

An upload does not start over, and neither does Generate.
These are the two things a user will avoid pressing if they doubt them, so both
are incremental and both say so on screen. An upload aligns the new pages against
the old ones by content (`slidematch.align`: image sha → text sha → text
similarity → position) and carries each surviving slide's narration onto its new
index, flagging `new`/`edited` and summarizing in `review`. Generate re-synthesizes
only text that is new in the current voice, because the audio cache is keyed by
content. Do not "simplify" the alignment to carry by index: inserting one page
would shift every later script by one, and it would look correctly matched.

Audio is a content-addressed cache, not an indexed one.
`audio_gen` names each MP3 `sha(narration + voice signature).mp3` and writes a
manifest of index → filename. Nothing is keyed by slide position, so a script that
moves to another slide keeps its audio, and two slides with identical narration
share one clip. This is also why the re-upload path needs no audio remapping — an
earlier version had `store.remap_audio` shuffling files whenever the deck changed
shape, and a whole class of bug with it. Clips no slide points at are pruned after
each build, because a clip's name encodes text that nothing says any more.

Nothing is rendered from source.
No Quarto, no LibreOffice: page images come from the author's PDF, and a
reveal.js deck is the HTML the author rendered. A `.qmd` named to the launcher
is resolved to its rendered `.html` (beside it, or under `docs/` or `_site/`),
never rendered. Do not add a render step.

The deliverables are files on disk, not a hosted app or an in-app download.
`_build` renders the MP4 and transcript directly to the author's project
folder (`VOICEOVER_OUTPUT_DIR`). `GET /api/projects/{id}/video` serves that MP4
inline for the in-app player only. There is no download endpoint, no deploy path,
no login.

A PDF video is composed from images + audio, not screen-recorded.
`video_gen` shows each slide's PNG for the length of its narration MP3 (plus a
1.5s inter-slide pause), silent slides dwell 4s, and the per-slide segments are
concatenated. Every segment is normalized to a 1920×1080 / 25fps / yuv420p / aac
canvas so the concat is a clean stream-copy.

ffmpeg comes from pip, not the system.
`imageio-ffmpeg` ships a bundled static binary; `video_gen.FFMPEG` is its path.
Do not add a system ffmpeg requirement.

Expression is a model + settings choice, not an account tier.
The most common complaint about the output is that the voice sounds flat, and
the instinct is to blame the ElevenLabs plan. It is not the plan. It is the
model: `eleven_multilingual_v2` is deliberately even-toned — fine for a short
clip, monotonous over a ten-minute deck. The default is `eleven_v3` with
honest labels. Before suggesting a plan upgrade anywhere, check the model.

Be careful not to overstate the settings half of this. All five settings
(`audio_gen.VOICE_SETTING_KEYS`) go on every request and appear in Audio
settings, but `style` and `use_speaker_boost` already defaulted server-side to
what we now send — exposing them made the knobs reachable; it did not by itself
make the audio less flat. `style`'s effect on v3 is unverified: an A/B at 0.0 vs
0.7 was inconclusive because generation is non-deterministic and the run-to-run
spread exceeded the between-setting difference.

Voice settings travel as one dict, and the whole dict is in the hash.
`_voice_sig` names every field in `VOICE_SETTING_KEYS`, so adding a field
invalidates old clip names and forces a re-render instead of quietly serving
audio built with different settings. Add a sixth setting to `VOICE_SETTING_KEYS`
and `DEFAULT_VOICE_SETTINGS` and it flows through naming, the API payload, and
staleness automatically. `_merged_settings` only substitutes defaults for `None`,
so an explicit `false` (speaker boost off) survives.

The ElevenLabs key and the engine choice (`TTS_ENGINE`) live in ~/.voiceover/.env,
and Kokoro's model files in ~/.voiceover/models, never in the skill directory.
The skill directory is package content — installing or updating the plugin
replaces it. Version 1.x wrote a pasted key to `backend/.env`, inside that
directory, so an update silently deleted it and dropped the user back at the key
banner with no explanation. It hit exactly the people who used the paste-in-app
path rather than exporting a shell variable. `config.py` now resolves the key
from, strongest first: a real environment variable, `~/.voiceover/.env`, then a
legacy `backend/.env` whose key is copied out on first run. The old file is read
but never written and never deleted — the skill directory may be read-only, and
a stale copy is harmless once the home file wins. Do not move it back, and do not
put anything else durable under the skill directory.


## reveal.js decks: design choices (and why)

Everything above applies to both formats. These apply only to a reveal.js
deck (`store.is_revealjs`).

A reveal.js deck is the rendered HTML, opened in place.
Not the `.qmd`: rendering needs Quarto and the author's project setup, and the
author renders anyway to look at the deck. Not a copy: a Quarto deck leans on
its `_files/` folder and sometimes on images above it, so only the original
location reliably has everything. The cost is that the file can change under
the app. `file_status().changed` catches that, and Generate refuses to record
until the deck is read again, because the narration would no longer match the
slides that play. Uploads (zip or self-contained html) exist for a bare launch.

Narration says when fragments appear, with `[next]` markers in one script.
The author chose this over two alternatives: one script box per fragment step
(exact, but the narration reads in pieces), and no sync (fragments spread
evenly through the audio). A marker sits before the words that introduce its
fragment. Markers are stripped before TTS, and an ElevenLabs clip (from the
with-timestamps endpoint, `audio_gen.synthesize_timed`) is named for the spoken
text, so moving a marker re-voices nothing. Kokoro returns no timestamps, so a
Kokoro clip is spoken in pieces cut at the markers and joined
(`audio_gen.synthesize_kokoro_timed`); each marker is then exact, and its name
covers the marker positions, so moving one re-speaks that slide. The cost: a marker in
the middle of a sentence can put a small pause and a falling tone there. The
alternative, one Kokoro call per slide with markers placed by character
position (markers.times' fallback), keeps the read smooth but can miss a
fragment by a few words. ElevenLabs v3 audio tags also use
square brackets, so only `[next]` is a marker; do not widen the pattern. The
frontend's `MARKER_RE` must match `markers.MARKER_RE`.

The video is recorded in real time, not rendered frame by frame.
Also the author's choice. Playing the deck captures whatever the browser
paints — JS charts, canvas, embedded video, transitions — with no per-library
handling. The cost is a build as long as the video. Frame-by-frame (pause the
clock, step it, screenshot) would never drop a frame on a slow machine, but it
needs every animation source brought under a virtual clock.

Recording uses Chrome's screencast, not Playwright's recorder.
Playwright's `record_video_dir` encodes VP8 at a fixed low bitrate, which blurs
slide text. The CDP screencast hands over a JPEG per repaint, stamped with
paint time (measured: 60 per second during continuous animation, none while
the page is still). `_Encoder` repeats the last frame up to each new timestamp
to make a constant 30 fps stream and pipes it to ffmpeg; only the encoded
video touches disk. Two traps: (1) wait with `page.wait_for_timeout`, never
`time.sleep` — Playwright's sync API dispatches frame events only inside its
own calls, and an unacknowledged frame stops the screencast; (2) screencast
JPEGs are full range, so the encode converts to TV range, or some players show
the slides washed out.

Audio is placed from what happened, not from the plan.
Each slide change is logged at the wall-clock time it ran, and the audio track
is built from that log; video time 0 is the first frame's paint time, on the
same clock (`on_frame` guards against a different one). A slow step lengthens
a pause; it never pulls the voice off the picture. On the test deck each slide
appeared 0.6–0.7 s before its speech, as designed (`LEAD_S` is 0.6).

Chrome is needed only for a reveal.js deck.
The launcher checks for it only when it is handed an `.html`, and
`browser.chrome()` installs Playwright's Chromium itself, once, when no browser
starts (a reveal.js deck uploaded after a bare launch). A PDF-only author never
downloads a browser. Playwright is still a Python requirement for everyone; it
is small without its browser.

A reveal.js clip carries its timings.
`audio_gen` keeps each reveal.js clip's character timestamps beside it as
`<sha>.json`, and such a clip counts as cached only when both files exist. PDF
clips have no timing file and are named exactly as before.

## Gotchas / operational notes

- The local dev backend runs without `--reload`, so code changes need a manual
  restart to take effect.
- Frontend changes need `npm run build` in `frontend/`; FastAPI serves the built
  `frontend/dist`, which is committed, so an unbuilt edit will not show up.
- `skill_launch.py` reinstalls requirements when `requirements.txt` changes (it
  stamps a sha in the venv), so a skill update that adds a dependency doesn't
  need the user to blow away `~/.voiceover/venv`. It downloads Playwright's
  Chromium only for a reveal.js deck, and only when no Google Chrome is
  installed.
- Tests run with plain `python3` — no pytest, no fixtures:
  `backend/tests/test_slidematch.py` (the alignment cascade, shape by shape;
  run it after any change to `slidematch.py`), `backend/tests/test_engine.py`
  (engine choice, cache separation, unchanged PDF signatures and clip names,
  Kokoro marker timing) and `backend/tests/test_markers.py` (marker parsing,
  marker timing, and — in the app venv — the per-slide schedule).
- A deck opened by path remembers that path, so the app can notice a re-export
  (`store.file_status().changed`) and offer to re-read it. For a reveal.js deck
  Generate refuses until it is re-read, because the recording plays the file. A deck that arrived by
  upload deliberately forgets any earlier path: the file on disk is no longer
  what the deck is narrating, so nagging about it would be wrong.
- A build that dies partway (an ElevenLabs quota error is the usual way) leaves
  the clips it finished on disk under their content-addressed names, so retrying
  after an upgrade re-synthesizes only what's left. The manifest and the prune
  both run after synthesis, so a failed run changes nothing else.
- Not recorded from a reveal.js deck: sound from audio or video elements on a
  slide (only the narration), and interaction other than advancing fragments.
  `autoSlide` is turned off; the narration drives timing.
- The skill drafts narration as soon as slides are readable — including after a
  bare launch, where it polls `GET /api/projects` waiting for the upload. Don't
  add a confirmation step in front of that; it is what the author invoked the
  skill for.
- Global preference for this user: avoid boldface in generated prose.
