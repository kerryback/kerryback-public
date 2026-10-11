# Voiceover Builder — orientation for Claude

Read this first when working on this repo. It describes what the app is, how it
is structured, and the design decisions behind it (with the reasoning, so you
don't undo them by accident).

## What it is

A local app, launched as a Claude Code skill, that turns a slide deck into a
narrated MP4 video plus a transcript.

A deck is one file: the PDF the author exported from their slides. It arrives
either as a path (the launcher was given a deck) or as a browser upload (it
wasn't, so the app opens on Upload and waits). The app copies it into the deck
folder, renders a page image per slide, and owns the narration in
`narration.json`.

Two roles — keep them straight:
- The author runs this app on their own machine to author the video. The
  server, the port (8010), and the ElevenLabs key all live here.
- Viewers run nothing. They receive `<name>.mp4` and `<name>.txt` and view them
  like any other file. There is no viewer-facing app or URL.

## Architecture

1. Backend — `backend/`, FastAPI. Owns decks, runs the two long jobs (ingest,
   build) in background threads, reports progress over an event stream, and
   serves the SPA + the rendered video. No auth, no LLM calls.
2. Frontend — `frontend/`, React + Vite + Tailwind. Four screens in one top bar
   with Generate among them: Upload · Narration text · Audio settings ·
   [Generate] · Preview. The launcher opens `/?project=<id>`, or bare `/`.

Key backend modules (`backend/builderlib/`):
- `deck.py` — ingest a PDF: page PNGs, per-page text/title, content fingerprints.
- `slidematch.py` — align a new ingest against the previous one (see below).
- `store.py` / `db.py` — folder-backed registry (no database: each deck folder's
  `meta.json` is the source of truth) and per-deck file I/O, including the
  narration store.
- `jobs.py` — two jobs, `_ingest` and `_build`, each run in a thread via `_run_bg`.
- `audio_gen.py` — content-addressed per-slide TTS.
- `video_gen.py` — composes the PNGs + MP3s into the MP4 with ffmpeg (from the
  `imageio-ffmpeg` pip wheel — no system ffmpeg).

## Deck lifecycle (states)

`loading → ready → building → built`, with `load_failed` and `building_failed`.
`ready` means page images and narration are in hand. Staleness is computed, not
tracked: `store.build_signature` shas every slide's narration plus the voice
settings, `_build` stamps it, and `store.is_stale` compares. There is no edit
bookkeeping to get wrong.

## Design choices (and why)

Input is a PDF, and only a PDF.
It is the one thing every slide tool exports faithfully. Reading `.pptx` or `.qmd`
directly was tried in both directions — LibreOffice mangles PowerPoint (cropped
table cells, animation builds), and Quarto needs a render step and a Quarto
install — and the PDF avoids all of it. A deck the author names as `.pptx` or
`.qmd` is answered with "export it first", not silently converted.

The narration lives in the app, and both authors write to the same copy.
A PDF has nowhere to keep speaker notes, so `narration.json` in the deck folder is
the single copy. The author types into an autosaving textarea; Claude writes
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
No Quarto, no LibreOffice, no headless browser: page images come from the
author's PDF. Do not add a render step back.

The deliverables are files on disk, not a hosted app or an in-app download.
`_build` renders the MP4 and transcript directly to the author's project
folder (`VOICEOVER_OUTPUT_DIR`). `GET /api/projects/{id}/video` serves that MP4
inline for the in-app player only. There is no download endpoint, no deploy path,
no login.

The video is composed from images + audio, not screen-recorded.
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

The ElevenLabs key lives in ~/.voiceover/.env, never in the skill directory.
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

## Gotchas / operational notes

- The local dev backend runs without `--reload`, so code changes need a manual
  restart to take effect.
- Frontend changes need `npm run build` in `frontend/`; FastAPI serves the built
  `frontend/dist`, which is committed, so an unbuilt edit will not show up.
- `skill_launch.py` reinstalls requirements when `requirements.txt` changes (it
  stamps a sha in the venv), so a skill update that adds a dependency doesn't
  need the user to blow away `~/.voiceover/venv`.
- `backend/tests/test_slidematch.py` runs with plain `python3` — no pytest, no
  fixtures — and covers the alignment cascade shape by shape. Run it after any
  change to `slidematch.py`.
- A deck opened by path remembers that path, so the app can notice a re-export
  (`store.file_status().changed`) and offer to re-read it. A deck that arrived by
  upload deliberately forgets any earlier path: the file on disk is no longer
  what the deck is narrating, so nagging about it would be wrong.
- A build that dies partway (an ElevenLabs quota error is the usual way) leaves
  the clips it finished on disk under their content-addressed names, so retrying
  after an upgrade re-synthesizes only what's left. The manifest and the prune
  both run after synthesis, so a failed run changes nothing else.
- The skill drafts narration as soon as slides are readable — including after a
  bare launch, where it polls `GET /api/projects` waiting for the upload. Don't
  add a confirmation step in front of that; it is what the author invoked the
  skill for.
- Global preference for this user: avoid boldface in generated prose.
