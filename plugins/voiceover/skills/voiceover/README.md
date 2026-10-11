# Voiceover Builder

Turn a slide deck into a narrated MP4 video plus a transcript, with the narration
written and edited in the app.

## A deck is one PDF

| file | supplies |
| --- | --- |
| `deck-3.pdf`, exported from your slides | the slide images used in the video |

That is the whole input. PDF is what every slide tool exports faithfully — export
from PowerPoint, Quarto, Keynote, Beamer, anything.

The narration is the app's, held slide by slide alongside the page images. Claude
Code drafts it; you edit it in the app, where it autosaves as you type.

## Requirements

One thing you provide; everything else is handled for you.

- An ElevenLabs API key — the text-to-speech voice. Get a free key at
  https://elevenlabs.io and either export `ELEVENLABS_API_KEY` or paste it into
  the app's banner. Needed only to generate; writing narration works without it.

Handled for you: Python (the first launch builds a small virtual environment),
ffmpeg (ships with the Python dependencies), and the web UI (ships prebuilt, so
Node is not required). Quarto is not required — the app renders nothing. No
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

Invoke `/voiceover deck-3.pdf`, or `/voiceover` on its own and upload the PDF
in the app. Directly:

```
python3 scripts/skill_launch.py /path/to/deck-3.pdf
python3 scripts/skill_launch.py                        # upload one in the app
```

The launcher builds the app environment (first run only), starts the app on port
8010, reads the PDF, and opens the browser on it. If port 8010 is in use, pass
`--port 8011`. Stop with Ctrl-C.

## The screens

One row of buttons, in the order things happen for a new deck:

`Upload · Narration text · Audio settings · [Generate] · Preview`

Nothing is gated on anything else — go straight to whichever one you need.

## The edit cycle

- Narration wrong? Edit it in Narration text (it autosaves), or tell Claude —
  "tighten slide 3", "warmer on the intro" — and it rewrites that slide.
- Slides changed? Export the PDF again and drop it on Upload. Each new page is
  matched against the old deck by content, so a page that didn't change keeps its
  narration and the audio already spoken for it; only pages that changed, or are
  new, come back flagged for another look.
- Then Generate. Only the slides whose narration changed are spoken again, so
  fixing one slide costs one slide of audio. Changing a voice or a read setting is
  the exception — every clip is cached under the voice that made it, so the deck
  is re-spoken.

## Storage and outputs

No database. Each deck is a folder under `{project}/.voiceover/decks/<deck-name>`
holding its copy of the PDF, its page images, its narration, audio and settings.
The finished `<deck-name>.mp4` and `<deck-name>.txt` are written to the project
folder, so they are easy to find. Delete a deck by deleting its folder. The shared
Python environment lives once in `~/.voiceover/venv`.

## Structure

```
SKILL.md            the Claude Code skill definition (installs as /voiceover)
backend/            FastAPI backend + builderlib (deck, slidematch, jobs, audio, video)
frontend/           React + Vite + Tailwind SPA (four screens); dist/ ships prebuilt
scripts/            skill_launch.py — the launcher
CONTRACT.md         API and data contract
CLAUDE.md           orientation and design decisions
```

## Environment

| Variable | Purpose |
| --- | --- |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS — voiceover audio (account + cloned voices) |
| `DATA_DIR` | Per-project deck folders + working files (launcher sets `{project}/.voiceover`) |
| `TTS_CONCURRENCY` | Parallel TTS requests per build (default 5; at or below your ElevenLabs account's limit) |
| `VIDEO_CONCURRENCY` | Parallel ffmpeg segment encodes per build (default 4) |
| `VOICEOVER_OUTPUT_DIR` | Where the finished MP4 + transcript are written (launcher sets it to the project folder) |
