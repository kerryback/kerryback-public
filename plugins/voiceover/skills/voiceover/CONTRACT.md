# Voiceover Builder — API & Data Contract

Single source of truth for the backend and frontend. Both build to this.

This app turns a slide deck into a narrated MP4 video plus a transcript. It is an
author-only authoring tool that runs locally as a skill: the author
invokes it on a deck, the app opens on http://127.0.0.1:8010, and the finished
`.mp4` and `.txt` are written to the author's working directory. Viewers run
nothing — they only receive those two files. There is no viewer-facing app, no
chatbot, no hosting, and no in-app download.

## What a deck is

One file: the PDF the author exported from their slides, arriving either as a
path (the launcher, when the skill was invoked on a deck) or as a browser upload
(the Upload screen, when it wasn't). The app copies it into the deck folder
(`deck.pdf`) and renders one page image per slide.

The narration is the app's own — `narration.json` in the deck folder — because a
PDF has nowhere to keep it. Two authors write to that one copy: the author,
in the Narration text screen (autosaved per slide), and Claude Code, through the
narration API. Non-PDF input is refused with an instruction to export first.

## Auth model

- None. The app runs locally, launched per-deck by the author.

## Directory layout

```
backend/            FastAPI app (this contract's server)
frontend/           React + Vite + Tailwind SPA -> builds to frontend/dist
scripts/            skill_launch.py (start the app)

{project}/                    the author's project folder (VOICEOVER_OUTPUT_DIR)
  <deck>.pdf                  the deck the author exported (read, never written)
  <deck>.mp4                  finished narrated video (build output — the deliverable)
  <deck>.txt                  finished narration transcript (build output)
  .voiceover/                 per-project app data (DATA_DIR); no database
    decks/<deck>/             one folder per deck, named after it (the deck id)
      deck.pdf                the app's copy of the ingested PDF
      slides/slide-NNN.png    per-slide images rendered from it (1-based)
      narration.json          {"slides":[{index,title,slide_text,narration,change?}]}
      fingerprints.json       {"slides":[{index,image_sha,text_sha}]} — last ingest
      config.json             {voice_id, model, stability, similarity_boost,
                              style, use_speaker_boost, speed}
      audio/<sha>.mp3 + manifest.json
      meta.json               {id,name,state,source_type,source_path,upload_name,
                              source_mtime,build_sig,review,log,timestamps}
```
The deck folders under `.voiceover/decks` ARE the registry — the app lists decks
by scanning them and reading each `meta.json`. There is no database.

## Deck states

`loading → ready → building → built`, plus `load_failed | building_failed`, each
carrying a `log`. `ready` means the page images and the narration are in hand.
`built` means the MP4 is ready. A stopped build is not a state: the deck goes
back to the one it had before (see "Stopping a build").

Staleness is computed, not stored: `store.build_signature` shas every slide's
narration plus the voice settings; `_build` stamps it into `build_sig`;
`is_stale` compares. So an edit or a settings change makes a built video stale
with no edit bookkeeping.

## Carrying the script across a new upload

A re-uploaded PDF is aligned against the previous ingest by content, never by
index — insert one page and every later slide would otherwise inherit its
neighbour's script. `slidematch.align` runs a cascade of image sha → text sha →
text similarity → position (see its module docstring), and `jobs._carry_over`
moves each surviving slide's narration onto its new index, flagging what moved:

- `change: "new"` — nothing matched it; it has no narration yet.
- `change: "edited"` — matched on weaker evidence than an identical render; it
  keeps the old script as a starting point.
- `review` (on the deck) — `{total, unchanged, edited, new, removed,
  suspect_rerender}`. `suspect_rerender` means most matches were same-words /
  different-pixels, i.e. a re-export rather than a rewrite.

Flags clear when the slide is edited (`PUT …/narration…`) or waved through
(`POST …/review/clear`); the review disappears when no flag is left.

Audio needs no equivalent: clips are named for the text they speak, so a script
that lands on a different slide brings its audio with it.

## REST API (all JSON; all under /api; no auth — local app)

- `GET  /api/projects` → `[{id,name,state,stale,files,updated_at}]`
- `POST /api/projects` `{pdf, name?, project?}` → deck summary; starts an ingest.
  `pdf` is a path to a PDF already on disk (the launcher's route). 400 if it is
  missing or not a PDF. Re-opening the same PDF reopens the same deck (id = slug
  of the filename stem); `project` re-reads into a named deck instead, for a
  re-export saved under a different filename.
- `POST /api/projects/upload` (multipart `file`) → 202; start a new deck from a
  PDF chosen in the browser — the Upload screen with no deck open, which is how a
  bare launch (no deck named) gets its slides. Deck id = slug of the filename
  stem, so the same deck reopens rather than duplicating.
- `POST /api/projects/{id}/pdf` (multipart `file`) → 202; upload into an existing
  deck. Same deck, same settings, script carried across.
- `POST /api/projects/{id}/reload` → 202; re-read the PDF from the path the deck
  was opened with. 409 for a deck whose PDF arrived by upload (no path to go back
  to) or whose path is gone.
- `GET  /api/projects/{id}` → `{id,name,state,stale,files,
  slides:[{index,title,narration,change,image_url}],config,review,log,updated_at}`
- `GET  /api/projects/{id}/narration` → `{slides:[{index,title,slide_text,
  narration,change?}],review}` — what Claude Code reads before drafting.
- `PUT  /api/projects/{id}/narration/{index}` `{narration}` → 200; one slide (the
  editor's autosave). 404 for an index this deck doesn't have.
- `PUT  /api/projects/{id}/narration` `{slides:[{index,narration}]}` → `{written}`;
  several at once (how Claude delivers a draft — in batches of ~5 as it writes,
  not one call at the end, so the deck visibly fills in). Slides not named are
  untouched.
- `POST /api/projects/{id}/review/clear` `{indexes?}` → `{cleared}`; drop change
  flags without editing ("keep as is"). Omit `indexes` to clear all.
- `PUT  /api/projects/{id}/config` `{voice_id,model,stability,similarity_boost,style,use_speaker_boost,speed}` → 200 (all fields optional)
- `GET  /api/tts/status` → `{configured}` (is an ElevenLabs key set)
- `POST /api/tts/key` `{api_key}` → validates against ElevenLabs, persists to `~/.voiceover/.env` (outside the skill dir, so a plugin update can't wipe it), updates the live value
- `GET  /api/tts/voices` → `{configured, voices:[{voice_id,name,category}]}`
- `GET  /api/tts/voices/{voice_id}` → `{voice_id,name,category,preview_url,labels[]}` (resolve one id — the account first, then the Voice Library; 404 when no such voice)
- `POST /api/projects/{id}/build` → 202; TTS + video. 409 while loading, after a failed load, or while a build is running.
- `POST /api/projects/{id}/build/cancel` → 202 `{stopping}`; Stop. 409 when no build is running. The job ends with a `cancelled` event and the deck returns to `built` (if it had a video) or `ready`.
- `GET  /api/projects/{id}/events` → SSE stream of `{stage,state,done,total,message}` for the active job
- `GET  /api/projects/{id}/slides/{file}` → PNG (slide image)
- `GET  /api/projects/{id}/video` → the rendered MP4 (served inline, Range-aware; 404 until built) — for the in-app player only

`files` (on a deck) is `{pdf, source_path, source_dir, missing, changed,
uploaded}`: `changed` means the PDF on disk has moved on since the app read it
(the author re-exported in place), which is what `POST …/reload` is for.

## Audio cache

`audio_gen` names each MP3 `sha(narration + voice signature).mp3` and writes
`manifest.json` mapping slide index → filename. Nothing is keyed by slide
position, so inserting or reordering slides re-synthesizes nothing, and two
slides with identical narration share a clip. Unreferenced clips are pruned after
each build.

## Output delivery (no in-app download)

On each finished build the `<deck>.mp4` and `<deck>.txt` (transcript) are
rendered directly into the author's project folder (`VOICEOVER_OUTPUT_DIR`,
set by the launcher to the cwd; see `store.video_path` / `store.transcript_path`).
The app plays `GET /api/projects/{id}/video` in a `<video>` tag; there is no
download button.

## Voices & models (frontend picker; backend passes through to audio_gen)

- Voices: fetched live from the account via `GET /api/tts/voices` (ElevenLabs),
  so account + cloned voices appear. Default `voice_id` is `EXAVITQu4vr4xnSDxMaL`
  ("Sarah"). When no `ELEVENLABS_API_KEY` is set the picker prompts for one.
- The rest of ElevenLabs' Voice Library (~15k voices) is not listed — it is only
  browsable and auditionable on their site. The picker takes a pasted id instead
  and resolves it through `GET /api/tts/voices/{voice_id}`, showing the name,
  labels and preview clip before the author commits to it. Text-to-speech
  accepts a library voice directly, with no add-to-my-voices step; ElevenLabs
  files it under the account on first use, so afterwards it is in the dropdown.
- Models (`model_id`): `eleven_v4` (newest, expressive), `eleven_v4_turbo`
  (faster v4), `eleven_v3` (default, most expressive),
  `eleven_multilingual_v2` (even, understated), `eleven_turbo_v2_5` (faster),
  `eleven_flash_v2_5` (fastest). v3 is the default because the v2 family's even
  delivery reads as flat over a full narrated deck — a model property, not an
  account-tier limit.
- Voice settings, all sent on every request (`audio_gen.VOICE_SETTING_KEYS`):
  `stability`, `similarity_boost`, `style`, `use_speaker_boost`, `speed`.
  Defaults 0.5 / 0.75 / 0.0 / true / 1.0. Ranges are 0–1 except `speed` (0.7–1.2).
- Stability is model-shaped: v3 defines three levels (0.0 Creative, 0.5 Natural,
  1.0 Robust) and the picker offers exactly those; the v2 family and v4 take a
  continuous 0–1 slider (ElevenLabs documents no named levels for v4).
  The API does not reject in-between values on v3, so the backend
  passes settings through unmodified rather than snapping them.

## Frontend

- React + Vite + Tailwind. Builds to `frontend/dist`; FastAPI serves it at `/`
  (SPA fallback). API calls use RELATIVE paths (`api/...`) so it works behind a
  proxy/sub-path.
- Four screens plus Generate, all in one row in the top bar, in the order things
  happen for a new deck: `Upload · Narration text · Audio settings · [Generate] ·
  Preview`. They are places, not steps: nothing is gated on anything else, and the
  app routes the author only twice — after an upload (→ Narration text) and on
  pressing Generate (→ Preview).
  - Upload — drop zone / picker. With a deck open it uploads into that deck and
    says what survives; with none open (a bare launch) it starts a new deck and
    also lists the decks this folder already knows. Shows a "read it again" offer
    when the PDF on disk changed since the app read it.
  - Narration text — thumbnail strip (amber dot = no narration, coloured tag =
    changed in the last upload), the slide on the left, its script in an
    autosaving textarea on the right, and the review banner above when an upload
    left flags. Above those, `DraftStatus` says what is happening to the
    narration: slides arriving in the last 30s reads as "Claude Code is writing"
    with an n-of-total bar; a quiet deck with empty slides says so and points at
    the Claude Code window. It infers from arrivals — the app has no channel to
    Claude and never claims to know more than it sees.
  - Audio settings — voice, Voice Library lookup, model, and the read settings.
    Autosaved, debounced; no apply step.
  - Preview — the finished video, or an empty state with a Generate button.
- Generate stops on a deck with any empty slide and shows what is missing,
  rather than rendering a video of silence. The warning carries "Generate
  anyway", because a part-narrated deck is a legitimate thing to build.
- Both incremental paths are stated where they are used, because "will this throw
  away my work?" is the question that stops people using either: the Upload
  screen says a page that didn't change keeps its narration and its audio, and
  Generate says only slides whose narration changed are spoken again.
- The header also carries the deck name, the PDF's filename and the state pill.
  Build progress (SSE, with per-slide ticks) renders under it on whichever screen
  is showing; a failed build keeps its reason on screen until the next run.
- Opening `/` with no `?project=` is the Upload screen alone. Uploading there
  stamps `?project=<id>` into the URL, so a reload — or handing the link to
  Claude — reopens the same deck.

## Build job (backend)

1. Synthesize audio for every slide with narration, using `config.voice_id` +
   `config.model` + voice settings (ElevenLabs). Clips are content-addressed, so
   only text that is new in this voice is sent.
2. Render `video.mp4` (`video_gen.generate`): each slide's PNG shown for its
   narration length + a 1.5s pause (silent slides dwell 4s), segments normalized
   to 1920×1080/25fps and concatenated. Uses ffmpeg from the `imageio-ffmpeg`
   wheel — no system ffmpeg.
3. Write the transcript (`jobs._write_transcript`): the per-slide narration,
   snapshotted so it matches this build.
4. Outputs are already in place: both were rendered straight to
   `VOICEOVER_OUTPUT_DIR`; `jobs._announce_outputs` just reports where.
5. Stamp `build_sig` so later edits show as stale.

### Stopping a build

Stop (`POST …/build/cancel`) sets a per-build flag that both steps check. Audio
starts no new clip once it is set, but a clip already sent to ElevenLabs is
allowed to finish and land in the cache — it is billed either way, and the next
build then reuses it. Retry backoff waits on the flag, so Stop never sits out a
backoff. Video checks between segments and before the final concat, which is
the only step that writes the MP4; so a stopped run leaves the previous video,
manifest and transcript untouched. In the UI, Generate turns into Stop while a
run is going.

Nothing is rendered from source — no Quarto, no LibreOffice, no headless browser.
The slide images come from the author's PDF.

## Env (backend)

`ELEVENLABS_API_KEY` (TTS) is the only key — the app makes no LLM calls, so there
is no `ANTHROPIC_API_KEY`. `DATA_DIR` (per-project deck folders + working files;
the launcher sets `{project}/.voiceover`). Optional: `TTS_CONCURRENCY` (default
5, capped by your ElevenLabs account's concurrency limit), `VIDEO_CONCURRENCY`
(default 4), `VOICEOVER_OUTPUT_DIR` (finished MP4 + transcript destination; the
launcher sets it to the cwd).
