# Voiceover

Turn a slide deck into a narrated MP4 video plus a transcript, with the narration
written and edited in the app.

## A deck is one file: a PDF or a reveal.js deck

| file | the video |
| --- | --- |
| `deck-3.pdf`, exported from your slides | each page a still image, shown while its narration plays |
| `lecture-3.html`, a rendered reveal.js deck | the deck played and recorded in Chrome, with its animations |

The file type decides; you are never asked. PDF is what every slide tool
exports faithfully — export from PowerPoint, Quarto, Keynote, Beamer, anything.
A reveal.js deck is usually the `.html` Quarto renders for a revealjs
presentation, with its `_files` folder beside it; it is read in place. In its
script, `[next]` marks where the next fragment appears.

The narration is the app's, held slide by slide alongside the slide images. Claude
Code drafts it; you edit it in the app, where it autosaves as you type.

## Requirements

One thing you provide; everything else is handled for you.

- A voice engine, chosen at first use and switchable under Audio settings:
  Kokoro (free, open source, runs on your computer, no key; downloads a 340 MB
  model the first time) or ElevenLabs (an API key from https://elevenlabs.io,
  exported as `ELEVENLABS_API_KEY` or pasted into the app's banner; more natural
  voices and voice cloning). Writing narration needs neither.

Handled for you: Python (the first launch builds a small virtual environment),
ffmpeg (ships with the Python dependencies), and the web UI (ships prebuilt, so
Node is not required). Quarto is not required — the app renders nothing. A
reveal.js deck uses the installed Google Chrome, or a headless Chromium
downloaded once (about 150 MB) when there is none; a PDF needs no browser. No
Anthropic API key is needed; the narration is written by Claude Code, not by the
app.

## Two roles

- Author — runs this app locally (a Claude Code skill) to author the video.
  Claude Code drafts the narration; the author edits it, picks a voice, and
  generates. The app opens at http://127.0.0.1:8010.
- Viewers — run nothing. They receive `<name>.mp4` (the narrated video) and
  `<name>.txt` (the transcript) and view them like any other file.

## Install

From the kerryback/kerryback-public plugin marketplace:

```
/plugin marketplace add kerryback/kerryback-public
/plugin install voiceover@kerryback-public
```

or with the `skills` CLI:

```
npx skills@latest add kerryback/kerryback-public
```

or manually — clone and symlink the skill into your Claude Code skills directory:

```
git clone https://github.com/kerryback/kerryback-public.git
ln -s "$(pwd)/skills/plugins/voiceover/skills/voiceover" ~/.claude/skills/voiceover
```

## Run

Invoke `/voiceover deck-3.pdf` or `/voiceover lecture-3.html` (a `.qmd` is
resolved to its rendered `.html`), or `/voiceover` on its own and upload the
deck in the app (a PDF, or for reveal.js a `.zip` of the deck folder or a
self-contained `.html`). Directly:

```
python3 scripts/skill_launch.py /path/to/deck-3.pdf
python3 scripts/skill_launch.py /path/to/lecture-3.html
python3 scripts/skill_launch.py                        # upload one in the app
```

The launcher builds the app environment (first run only), starts the app on port
8010, reads the deck, and opens the browser on it. If port 8010 is in use, pass
`--port 8011`. Stop with Ctrl-C.

## The screens

One row of buttons, in the order things happen for a new deck:

`Upload · Narration text · Audio settings · [Generate] · Preview`

Nothing is gated on anything else — go straight to whichever one you need.

## The edit cycle

- Narration wrong? Edit it in Narration text (it autosaves), or tell Claude —
  "tighten slide 3", "warmer on the intro" — and it rewrites that slide.
- Slides changed? Export the PDF (or render the reveal.js deck) again and drop it
  on Upload, or press "Read it again" for a deck opened by path. Each new slide
  is matched against the old deck by content, so a slide that didn't change
  keeps its narration and the audio already spoken for it; only slides that
  changed, or are new, come back flagged for another look. A reveal.js deck must
  be read again before Generate once its file has changed.
- Then Generate. Only the slides whose narration changed are spoken again, so
  fixing one slide costs one slide of audio. Changing a voice or a read setting is
  the exception — every clip is cached under the voice that made it, so the deck
  is re-spoken.

## Storage and outputs

No database. Each deck is a folder under `{project}/.voiceover/decks/<deck-name>`
holding its copy of the PDF (a reveal.js deck is read in place, or kept unpacked
there when uploaded), its slide images, its narration, audio and settings.
The finished `<deck-name>.mp4` and `<deck-name>.txt` are written to the project
folder, so they are easy to find. Delete a deck by deleting its folder. The shared
Python environment lives once in `~/.voiceover/venv`.

## Structure

```
SKILL.md            the Claude Code skill definition (installs as /voiceover)
backend/            FastAPI backend + builderlib (PDF: deck, video_gen; reveal.js:
                    reveal_deck, reveal_video, browser, markers; shared: slidematch,
                    jobs, audio_gen, kokoro, store)
frontend/           React + Vite + Tailwind SPA (four screens); dist/ ships prebuilt
scripts/            skill_launch.py — the launcher
CONTRACT.md         API and data contract
CLAUDE.md           orientation and design decisions
```

## Environment

| Variable | Purpose |
| --- | --- |
| `TTS_ENGINE` | `kokoro` or `elevenlabs`; stored in `~/.voiceover/.env` (default: ElevenLabs if a key is set, else Kokoro) |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS — voiceover audio (account + cloned voices); only with ElevenLabs |
| `DATA_DIR` | Per-project deck folders + working files (launcher sets `{project}/.voiceover`) |
| `TTS_CONCURRENCY` | Parallel TTS requests per build (default 2; at or below your ElevenLabs account's limit) |
| `VIDEO_CONCURRENCY` | Parallel ffmpeg segment encodes per PDF build (default 4) |
| `VOICEOVER_OUTPUT_DIR` | Where the finished MP4 + transcript are written (launcher sets it to the project folder) |
