# Voiceover — API & Data Contract

Single source of truth for the backend and frontend. Both build to this.

This app turns a slide deck into a narrated MP4 video plus a transcript. It is an
author-only authoring tool that runs locally as a skill: the author
invokes it on a deck, the app opens on http://127.0.0.1:8010, and the finished
`.mp4` and `.txt` are written to the author's working directory. Viewers run
nothing — they only receive those two files. There is no viewer-facing app, no
chatbot, no hosting, and no in-app download.

## What a deck is

One file, arriving either as a path (the launcher, when the skill was invoked
on a deck) or as a browser upload (the Upload screen, when it wasn't). Its type
picks the deck's format, kept as `source_type` in `meta.json`:

- `pdf`: the PDF the author exported from their slides. The app copies it into
  the deck folder (`deck.pdf`) and renders one page image per slide.
- `revealjs`: a rendered reveal.js presentation, usually the `.html` Quarto
  writes for a `format: revealjs` deck, with its `<stem>_files/` folder beside
  it. By path it is read where it is and never copied, because its HTML leans
  on `_files/` and sometimes on images above it. By upload it is a `.zip` of
  the deck's folder or a self-contained `.html`, unpacked into the deck folder
  (`upload/`). Headless Chrome (Playwright; the installed Google Chrome when
  present) loads the deck and reads, per slide in reading order with vertical
  stacks flattened: its `h`/`v` indices, number of fragment `steps`, `title`,
  `slide_text`, speaker `notes`, and a thumbnail with every fragment shown.

A deck whose meta has no `source_type`, or `"pdf"`, is a PDF deck. Any other
file type (`.pptx`, `.key`, …) is refused with an instruction to export to PDF.

The narration is the app's own — `narration.json` in the deck folder — because a
PDF has nowhere to keep it and a rendered reveal.js file is rebuilt on every
render. Two authors write to that one copy: the author, in the Narration text
screen (autosaved per slide), and Claude Code, through the narration API. On a
reveal.js deck, a `[next]` marker in a slide's script is where the recording
advances one fragment step (see "Markers").

## Auth model

- None. The app runs locally, launched per-deck by the author.

## Directory layout

```
backend/            FastAPI app (this contract's server)
frontend/           React + Vite + Tailwind SPA -> builds to frontend/dist
scripts/            skill_launch.py (start the app)

{project}/                    the author's project folder (VOICEOVER_OUTPUT_DIR)
  <deck>.pdf                  a PDF deck the author exported (read, never written)
  <deck>.html + <deck>_files/ or a rendered reveal.js deck (read, never written)
  <deck>.mp4                  finished narrated video (build output — the deliverable)
  <deck>.txt                  finished narration transcript (build output)
  .voiceover/                 per-project app data (DATA_DIR); no database
    decks/<deck>/             one folder per deck, named after it (the deck id)
      deck.pdf                PDF: the app's copy of the ingested PDF
      upload/                 reveal.js: an uploaded deck, unpacked (absent when
                              opened by path)
      slides/slide-NNN.png    per-slide images (1-based): PDF pages, or reveal.js
                              thumbnails 720 high
      narration.json          {"slides":[{index,title,slide_text,narration,change?}]}
                              plus, on reveal.js, h, v, steps and notes
      fingerprints.json       {"slides":[{index,image_sha,text_sha}]} — last ingest
      config.json             {voice_id, model, stability, similarity_boost,
                              style, use_speaker_boost, speed}
      audio/<sha>.mp3 + manifest.json, and on reveal.js a <sha>.json
                              (character timestamps) beside each clip
      meta.json               {id,name,state,source_type,source_path,upload_name,
                              upload_html,source_mtime,deck_sha,deck_size,
                              build_sig,review,log,timestamps}
```
The deck folders under `.voiceover/decks` ARE the registry — the app lists decks
by scanning them and reading each `meta.json`. There is no database.

## Deck states

`loading → ready → building → built`, plus `load_failed | building_failed`, each
carrying a `log`. `ready` means the slide images (and on reveal.js the step
counts) and the narration are in hand.
`built` means the MP4 is ready. A stopped build is not a state: the deck goes
back to the one it had before (see "Stopping a build").

Staleness is computed, not stored: `store.build_signature` shas every slide's
narration plus the voice settings, and on reveal.js the sha of the deck's HTML
as last read (a PDF deck's signature is unchanged from before reveal.js decks
existed); `_build` stamps it into `build_sig`;
`is_stale` compares. So an edit or a settings change makes a built video stale
with no edit bookkeeping.

## Carrying the script across a new upload or re-read

A re-uploaded or re-read deck is aligned against the previous ingest by
content, never by index — insert one slide and every later slide would otherwise inherit its
neighbour's script. `slidematch.align` runs a cascade of image sha → text sha →
text similarity → position (see its module docstring), and `jobs._carry_over`
moves each surviving slide's narration onto its new index, flagging what moved:

- `change: "new"` — nothing matched it; it has no narration yet.
- `change: "edited"` — matched on weaker evidence than an identical render; it
  keeps the old script as a starting point.
- `review` (on the deck) — `{total, unchanged, edited, new, removed,
  suspect_rerender}`. `suspect_rerender` means most matches were same-words /
  different-pixels, i.e. a re-export or re-render rather than a rewrite.

Flags clear when the slide is edited (`PUT …/narration…`) or waved through
(`POST …/review/clear`); the review disappears when no flag is left.

Audio needs no equivalent: clips are named for the text they speak, so a script
that lands on a different slide brings its audio with it.

## REST API (all JSON; all under /api; no auth — local app)

- `GET  /api/projects` → `[{id,name,state,stale,files,updated_at}]`
- `POST /api/projects` `{deck, name?, project?}` → deck summary; starts an
  ingest. `deck` is a path to a `.pdf` or a rendered reveal.js `.html`/`.htm`
  already on disk (the launcher's route); `pdf` and `html` are accepted as
  older names for it. 400 if it is missing or another type. Re-opening the same
  file reopens the same deck (id = slug of the filename stem); `project`
  re-reads into a named deck instead, for a re-export saved under a different
  filename.
- `POST /api/projects/upload` (multipart `file`: `.pdf`, `.html` or `.zip`) →
  202; start a new deck from a file chosen in the browser — the Upload screen
  with no deck open, which is how a bare launch (no deck named) gets its slides.
  A zip is unpacked (paths that climb out are refused) and the presentation is
  the shallowest `.html`, preferring one with a sibling `<stem>_files/`. Deck id
  = slug of the filename stem, so the same deck reopens rather than
  duplicating. 400 for any other file type; a failed new reveal.js deck leaves
  no folder behind.
- `POST /api/projects/{id}/deck` (multipart `file`) → 202; upload into an
  existing deck. Same deck, same settings, script carried across. `…/pdf` is
  the same route under its older name.
- `POST /api/projects/{id}/reload` → 202; re-read the deck from the path it was
  opened with. 409 for a deck that arrived by upload (no path to go back to) or
  whose path is gone.
- `GET  /api/projects/{id}` → `{id,name,state,stale,files,
  format,slides:[{index,title,narration,steps,change,image_url}],config,review,
  log,updated_at}` — `format` is `pdf` or `revealjs`; `steps` is 0 on a PDF.
- `GET  /api/projects/{id}/narration` → `{format,slides:[{index,title,
  slide_text,narration,change?}],review}` — what Claude Code reads before
  drafting. A reveal.js slide also has `h`, `v`, `steps`, `notes` and
  `markers` (the number of `[next]` in its script now).
- `PUT  /api/projects/{id}/narration/{index}` `{narration}` → 200; one slide (the
  editor's autosave). 404 for an index this deck doesn't have.
- `PUT  /api/projects/{id}/narration` `{slides:[{index,narration}]}` → `{written}`;
  several at once (how Claude delivers a draft — in batches of ~5 as it writes,
  not one call at the end, so the deck visibly fills in). Slides not named are
  untouched.
- `POST /api/projects/{id}/review/clear` `{indexes?}` → `{cleared}`; drop change
  flags without editing ("keep as is"). Omit `indexes` to clear all.
- `PUT  /api/projects/{id}/config` `{voice_id,model,stability,similarity_boost,style,use_speaker_boost,speed,kokoro_voice,kokoro_speed}` → 200 (all fields optional; 400 on an unknown Kokoro voice; `kokoro_speed` clamped to 0.7–1.3)
- `GET  /api/tts/status` → `{engine,engine_chosen,configured,ready,kokoro_downloaded,concurrency}`. `configured`: is an ElevenLabs key set. `ready`: can Generate run with the engine in force (always true for Kokoro).
- `GET  /api/tts/engine` → `{engine,chosen}`; `POST /api/tts/engine` `{engine}` (`kokoro` | `elevenlabs`) → saves `TTS_ENGINE` to `~/.voiceover/.env` and switches live; 400 on anything else. Account-wide, not per deck. Unset, the engine is `elevenlabs` when a key is configured, else `kokoro`; an exported `TTS_ENGINE` wins.
- `GET  /api/tts/kokoro/voices` → `{voices:[{id,name,grade,group}],default,speed_range,downloaded}` — the 28 English voices with Kokoro's own grades
- `GET  /api/tts/kokoro/preview/{voice}?speed=` → MP3 sample of the voice, synthesized once and cached in `~/.voiceover/kokoro-previews`; 404 for an unknown voice, 502 if the model download fails
- `POST /api/tts/key` `{api_key}` → validates against ElevenLabs, persists to `~/.voiceover/.env` (outside the skill dir, so a plugin update can't wipe it), updates the live value
- `GET  /api/tts/voices` → `{configured, voices:[{voice_id,name,category}]}`
- `GET  /api/tts/voices/{voice_id}` → `{voice_id,name,category,preview_url,labels[]}` (resolve one id — the account first, then the Voice Library; 404 when no such voice)
- `POST /api/projects/{id}/build` → 202; TTS + video (PDF) or recording
  (reveal.js). 409 while loading, after a failed load, or while a build is running.
- `POST /api/projects/{id}/build/cancel` → 202 `{stopping}`; Stop. 409 when no build is running. The job ends with a `cancelled` event and the deck returns to `built` (if it had a video) or `ready`.
- `GET  /api/projects/{id}/events` → SSE stream of `{stage,state,done,total,message}` for the active job
- `GET  /api/projects/{id}/slides/{file}` → PNG (slide image)
- `GET  /api/projects/{id}/video` → the rendered MP4 (served inline, Range-aware; 404 until built) — for the in-app player only

`files` (on a deck) is `{format, deck, pdf, source_path, source_dir, missing,
changed, uploaded}` (`pdf` repeats `deck`, for older clients): `changed` means
the file on disk has moved on since the app read it (the author re-exported or
re-rendered in place), which is what `POST …/reload` is for. On a reveal.js
deck a build refuses to start while `changed` is true, so the recording never
plays slides the narration was not written for.

## Markers (reveal.js)

`[next]` (any case, spaces allowed inside the brackets) in a slide's script is
one fragment step. `markers.split` strips them and collapses the whitespace
around each to one space, giving the spoken text and the character offset of
each marker in it. Only `[next]` is a marker; other bracketed text (ElevenLabs
v3 audio tags) is spoken as written. The frontend counts markers with the same
pattern (`constants.MARKER_RE`).

At record time each offset becomes a time: the start time ElevenLabs reported
for that character, or, when the timestamps are missing or don't line up with
the text, a time proportional to the offset. Fewer markers than steps: the
leftover steps are shown 0.5 s apart when the audio ends. More: the extras are
ignored.

## Audio cache

`audio_gen` names each MP3 `sha(narration + voice signature).mp3` and writes
`manifest.json` mapping slide index → filename. On a reveal.js deck it
synthesizes through ElevenLabs' `with-timestamps` endpoint, the spoken text has
its markers stripped (so moving a marker re-voices nothing), and the character
timestamps are saved beside each clip as `<sha>.json`; such a clip counts as
cached only when both files exist. Nothing is keyed by slide
position, so inserting or reordering slides re-synthesizes nothing, and two
slides with identical narration share a clip. Unreferenced clips are pruned after
each build.

## Output delivery (no in-app download)

On each finished build the `<deck>.mp4` and `<deck>.txt` (transcript) are
rendered directly into the author's project folder (`VOICEOVER_OUTPUT_DIR`,
set by the launcher to the cwd; see `store.video_path` / `store.transcript_path`).
The app plays `GET /api/projects/{id}/video` in a `<video>` tag; there is no
download button.

## Engines

Two text-to-speech engines; the account's engine (`TTS_ENGINE`) decides which one
a build uses. Each deck's `config.json` holds settings for both, so switching and
back loses nothing.

- Kokoro (`builderlib/kokoro.py`): Kokoro-82M through `kokoro-onnx`, run locally.
  Model files (`kokoro-v1.0.onnx`, `voices-v1.0.bin`, about 340 MB) download once
  to `~/.voiceover/models`. `espeakng-loader`, a kokoro-onnx dependency, ships
  espeak-ng, so nothing else is installed. Deck settings `kokoro_voice` (default
  `af_heart`) and `kokoro_speed` (default 1.0, 0.7–1.3). British voices (`bf_`,
  `bm_`) use `en-gb`. Clips are encoded to MP3 with the bundled ffmpeg and run one
  at a time. No key. On a reveal.js deck Kokoro gives no timestamps, so each
  clip is spoken in pieces cut at the `[next]` markers and joined; the timing
  file beside it has the same `alignment.character_start_times_seconds` shape as
  ElevenLabs', exact at each marker and spread evenly between them, and the
  clip's name covers the marker offsets as well as the text.
- ElevenLabs: everything below.

The audio cache keys a Kokoro clip by `kokoro|<voice>|speed=<speed>` and an
ElevenLabs clip by its voice signature, so neither engine's clips are ever served
for the other. `build_signature` covers only the engine in force (Kokoro adds
`engine=kokoro`; ElevenLabs is unchanged from before engines existed).

## Voices & models (frontend picker; backend passes through to audio_gen)

- Voices: fetched live from the account via `GET /api/tts/voices` (ElevenLabs),
  so account + cloned voices appear. Default `voice_id` is `J9NvviOEdVm6E7Hwdpdj`
  ("Jerry B."). When no `ELEVENLABS_API_KEY` is set the picker prompts for one.
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
    when the deck's file on disk changed since the app read it.
  - Narration text — thumbnail strip (amber dot = no narration, coloured tag =
    changed in the last upload), the slide on the left, its script in an
    autosaving textarea on the right (on a reveal.js slide with fragments, a
    marker bar above it: steps vs markers, amber when they differ, and an
    "Insert [next]" button that puts one at the cursor), and the review banner
    above when an upload
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
- The header also carries the deck name, the deck's filename and the state pill.
  Build progress (SSE, with per-slide ticks) renders under it on whichever screen
  is showing; a failed build keeps its reason on screen until the next run.
- Opening `/` with no `?project=` is the Upload screen alone. Uploading there
  stamps `?project=<id>` into the URL, so a reload — or handing the link to
  Claude — reopens the same deck.

## Build job (backend)

1. Synthesize audio for every slide with narration: with Kokoro,
   `config.kokoro_voice` + `config.kokoro_speed`, one clip at a time; with
   ElevenLabs, `config.voice_id` + `config.model` + voice settings. Clips are content-addressed, so
   only text that is new in this voice is sent.
2. Make the video. PDF — render `video.mp4` (`video_gen.generate`): each
   slide's PNG shown for its narration length + a 1.5s pause (silent slides
   dwell 4s), segments normalized to 1920×1080/25fps and concatenated.
   reveal.js — record `<deck>.mp4` (`reveal_video.generate`): headless Chrome
   plays the deck in real time at 1080 pixels high (width from the deck's own aspect), with
   reveal's controls, progress bar, keyboard, hash and autoSlide turned off and
   Quarto's menu buttons hidden. Each slide is shown with fragments hidden, its
   audio starts 0.6 s later, fragments advance at marker times, and the slide
   holds 1.5 s after the audio (silent slides: fragments 1.2 s apart, then 4 s).
   Chrome's screencast (CDP) frames, stamped with paint time, are turned into a
   constant 30 fps stream piped to ffmpeg (libx264, TV range). Every slide
   change is logged at the time it happened, the audio track is assembled from
   that log, and video + audio + cover art are muxed.
   Both use ffmpeg from the `imageio-ffmpeg` wheel — no system ffmpeg.
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
backoff. A PDF video checks between segments and before the final concat; a
reveal.js recording checks at least every 0.25 s. The MP4 is written only at
the end (the concat, or the final rename); so a stopped run leaves the previous video,
manifest and transcript untouched. In the UI, Generate turns into Stop while a
run is going.

Nothing is rendered from source — no Quarto, no LibreOffice. A PDF deck's
images come from the author's PDF; a reveal.js deck is the HTML the author
rendered, played in headless Chrome. A PDF deck never starts a browser.

## Env (backend)

`TTS_ENGINE` (`kokoro` | `elevenlabs`; see Engines). `ELEVENLABS_API_KEY` is the
only key, needed only with ElevenLabs — the app makes no LLM calls, so there is
no `ANTHROPIC_API_KEY`. `DATA_DIR` (per-project deck folders + working files;
the launcher sets `{project}/.voiceover`). Optional: `TTS_CONCURRENCY` (default
2, capped by your ElevenLabs account's concurrency limit), `VIDEO_CONCURRENCY`
(default 4), `VOICEOVER_OUTPUT_DIR` (finished MP4 + transcript destination; the
launcher sets it to the cwd).
