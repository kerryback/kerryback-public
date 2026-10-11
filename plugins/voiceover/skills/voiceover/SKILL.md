---
name: voiceover
description: >-
  Turn a slide deck into a narrated MP4 video plus a transcript, and write the
  narration for it. Use when someone wants to narrate/voice a deck, "make a
  narrated video from these slides", "add AI voiceover to this deck", "write
  narration for this presentation", or "turn this lecture into a video" — and
  when they invoke /voiceover with a deck, or bare with no deck at all. Takes
  one file: the PDF exported from the slides, named on the command line or
  uploaded in the app. You (Claude Code) draft the narration immediately, through
  the app's narration API; a local app (http://127.0.0.1:8010) shows each slide
  beside its script, where the author edits it, picks a voice, and generates.
  The finished .mp4 and .txt are saved to the author's working directory.
  Requires an ElevenLabs API key.
---

# voiceover

Two roles, don't conflate them:
- The author runs this local app on their own machine to make the video.
  You, Claude Code, write the narration; the author reads it, edits anything
  that sounds wrong, picks a voice, and generates. The port and the ElevenLabs
  key matter here.
- Viewers run nothing. They receive two files — `<name>.mp4` (the narrated
  video) and `<name>.txt` (the transcript) — and view/read them like any other
  file. No app, no server, no localhost, no login.

## A deck is one PDF

The deck is one file: `deck-3.pdf`, exported from whatever the slides were
built in. The app copies it into its own folder, renders a page image per slide,
and holds the narration itself.

The narration lives in the app, not in a source deck — a PDF has nowhere to put
it. Both of you write to that one copy: the author types on the Narration
text screen (autosaved), and you write through the narration API. There is no
`.qmd` or `.pptx` in the picture, and nothing to keep in sync.

## Two ways in — either way, draft immediately

- With a deck: `/voiceover deck-3.pdf`, "run voiceover on deck 3", "narrate
  this deck". Launch on that PDF (step 2) and draft.
- With nothing: a bare `/voiceover`. Launch with no deck; the app opens on its
  Upload screen and the author drops a PDF there. Poll
  `GET http://127.0.0.1:<port>/api/projects` every few seconds until a deck shows
  up in state `ready`, then draft that one. Tell them you're waiting for the
  upload, and don't ask them anything else in the meantime.

Once slides are readable, write the narration without being asked again — that is
the thing they came for. Don't offer to draft it, don't ask what style they want,
and don't wait for them to look at the app first: draft it, then say it's there
and can be changed.

The exception is a deck that already has narration (reopened, or written by the
author): leave what is there alone, and fill in only the slides that are
empty.

## Prerequisites — check first, offer to fix

- `ELEVENLABS_API_KEY` — the text-to-speech voice, needed only to generate.
  Check with `printenv ELEVENLABS_API_KEY`. Writing and reviewing narration need
  no key, so a missing one is never a reason to delay launching. If it's empty,
  say so up front and walk them through it — don't just say "you'll need a key":

  1. Sign up (free) at https://elevenlabs.io.
  2. Profile menu, bottom left → API Keys → Create API Key. Copy it; it starts
     with `sk_` and is shown once.
  3. Paste it into the amber banner at the top of the app and press Save key.
     The app validates it against ElevenLabs before accepting, stores it in
     `~/.voiceover/.env` (outside the skill, so a plugin update can't wipe it),
     and enables generation with no restart.

  Offer the alternative if they'd rather have it in the environment for other
  tools too: help them export `ELEVENLABS_API_KEY` in their shell profile. An
  exported variable takes precedence over the stored one.

  Mention the quota once, when they first generate rather than at signup: the
  free tier is measured in minutes of audio per month, which covers trying this
  out but not voicing a full deck. If a build fails partway with a quota
  error, that is what happened — the already-synthesized slides are cached, so
  resuming after an upgrade re-voices only what's left.

  A different failure looks similar and is not the quota: ElevenLabs also caps
  how many requests may run **at once**, and the cap rises with the plan (Free
  allows 2). Over it, the extra requests come back 429 and the build stops. The
  app requests 2 at a time out of the box, which every plan can serve; the
  author raises it on the Voice screen under "ElevenLabs plan" once they
  know their limit. Their API reports the plan tier but not its concurrency
  number, so this cannot be detected for them. A clip that comes back 429 is
  retried with backoff, so brushing the cap costs seconds rather than the run;
  if a build still dies with a concurrency or "too many requests" error, the
  setting is genuinely too high — or a second copy of the app is running on the
  same key.
- Python is already present (it runs the launcher), and the first launch sets up
  a small Python environment automatically. Quarto is NOT required, and neither
  is ffmpeg — it ships with the Python dependencies. The frontend ships prebuilt,
  so Node is not required.

## What to do

`<skill-dir>` below is the "Base directory for this skill" reported when the
skill is invoked; use that absolute path. `<port>` defaults to 8010.

1. Find the PDF, if one was named. If the author names a `.qmd`, `.pptx` or
   `.key`, look for a PDF of the same name next to it and use that. If there
   isn't one, ask them to export it — PowerPoint: File ▸ Export ▸ Create PDF/XPS;
   Quarto: render, then print to PDF with `pdf-separate-fragments: false` so a
   fragment build doesn't become five pages; Keynote: File ▸ Export To ▸ PDF.
   Named no deck at all, skip straight to launching without one.

2. Launch the app in the background from the author's current directory (so
   the finished files save there):

   ```
   python3 "<skill-dir>/scripts/skill_launch.py" "<absolute path to the .pdf>"
   python3 "<skill-dir>/scripts/skill_launch.py"      # no deck: they upload one
   ```

   Run it in the background — it starts a long-lived local server. The first
   launch sets up the app environment, so it takes a little longer. Given a deck
   it prints `Open: http://127.0.0.1:<port>/?project=<deck>`; note the deck id.
   Given none, find the id from `GET /api/projects` once they have uploaded.

3. Read the deck. `GET http://127.0.0.1:<port>/api/projects/<deck>/narration`
   returns `{ "slides": [ { "index": 0, "title": "…", "slide_text": "…",
   "narration": "…", "change": … }, … ] }` — indexes 0-based, one per page.
   Draft from `slide_text`; it is far cheaper than reading images. Only when a
   slide's `slide_text` is empty or clearly misses the visual content (a chart, a
   diagram, an all-image slide) read that one page's image at
   `GET …/api/projects/<deck>/slides/slide-<NNN>.png` (1-based, zero-padded).

4. Write the narration back in batches as you go — about five slides per call,
   in slide order, starting as soon as the first few are written:

   ```
   PUT http://127.0.0.1:<port>/api/projects/<deck>/narration
   {"slides": [{"index": 0, "narration": "…"}, {"index": 1, "narration": "…"}]}
   ```

   Do not save the whole deck for one PUT at the end. The app polls every few
   seconds, so a batch appears in the thumbnail strip within moments of being
   sent: batching is what turns a silent two-minute wait into a screen visibly
   filling in, and it lets the author start reading slide 1 while you are
   still on slide 20. On a deck of ten or fewer, two batches are enough.

   Slides you leave out are untouched, so a partial redraft never blanks the
   rest. Narration already there is the author's — leave it alone unless
   asked. It appears in the app within a few seconds; no reload needed.

5. Hand off with a clear invitation. Tell the author, in your own words: the
   narration is in the app at the URL, slide by slide. They can edit any of it
   right there — it autosaves — or tell you: "tighten slide 3", "warmer on the
   intro", "add a worked example on the Gordon-growth slide". When it reads well
   they open Audio settings, pick a voice, and press Generate; the video appears
   on the Preview screen and `<deck>.mp4` + `<deck>.txt` are written to their
   folder.

   You don't need to warn them off generating early — the app does that itself.
   While slides are still arriving it shows a count above the editor, and
   Generate stops on a deck with empty slides rather than rendering silence,
   with "Generate anyway" there for a deliberately part-narrated deck.

   Say too that neither Upload nor Generate starts over, because that is the
   thing people are most likely to fear and avoid:
   - Changed the slides? Export the PDF again and drop it on Upload. Each new
     page is matched against the old deck by content, so a page that didn't
     change keeps its narration and the audio already spoken for it; only pages
     that changed or are new come back flagged.
   - Changed some narration? Generate again. Only the slides whose text changed
     are spoken again — a one-slide fix costs one slide of synthesis. (Changing a
     voice or a read setting is the exception: the whole deck is re-spoken,
     because every clip is cached under the voice that made it.)

6. Revisions come to you, in chat. Read the slide, rewrite it, PUT it back, say
   what changed. Keep the style rules below. Editing one slide's narration
   changes only that slide's audio: everything else is reused from the last run,
   so a one-slide fix costs one slide of synthesis.

7. After they upload a new PDF, redraft what moved. `GET …/narration` marks slides
   `"change": "new"` (no narration yet) or `"change": "edited"` (the script shown
   is the one the old slide had). Deal with those and leave the rest alone. A
   slide whose old script still fits needs nothing — the author can press
   "Keep as is" in the app, or you can `POST …/review/clear` with its index.

8. If the server does not come up (port already in use), rerun with a different
   port, e.g. `--port 8011`, and use that port in the API calls.

## Narration style rules

Write what a good speaker would say aloud, not slide captions.
- Spoken prose only: no markdown, bullets, headings, or stage directions.
- Roughly 60–130 words per slide; teach the content, don't just describe it.
- One continuous talk: each slide picks up mid-thought from the previous one.
  Lead with the substance. Do not open slides with throat-clearing transitions
  like "Let's", "Now", "Next", "So", "Moving on", or "Let's look at".
- Never say "this slide" or "welcome"; narrate the content directly.
- Stay faithful to what each slide actually shows.
