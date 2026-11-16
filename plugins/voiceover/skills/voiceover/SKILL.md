---
name: voiceover
description: >-
  Turn a slide deck into a narrated MP4 video plus a transcript, and write the
  narration for it. Use when someone wants to narrate/voice a deck, "make a
  narrated video from these slides", "add AI voiceover to this deck", "write
  narration for this presentation", "turn this lecture into a video", "voice
  over this Quarto deck with the animations", or "narrate these reveal.js
  slides" — and when they invoke /voiceover with a deck, or bare with no deck
  at all. Takes one file, named on the command line or uploaded in the app:
  the PDF exported from the slides (each page becomes a still image), or a
  reveal.js deck — the .html Quarto renders for a revealjs presentation (a .qmd
  is resolved to its rendered .html) — which is recorded in headless Chrome
  with its fragments and animations. You (Claude Code) draft the narration
  immediately, through the app's narration API; a local app
  (http://127.0.0.1:8010) shows each slide beside its script, where the author
  edits it, picks a voice, and generates. The finished .mp4 and .txt are saved
  to the author's working directory. Speaks with Kokoro (free, open source,
  runs on the author's computer) or ElevenLabs (needs an API key); the author
  chooses once, at first use.
---

# voiceover

Two roles, don't conflate them:
- The author runs this local app on their own machine to make the video.
  You, Claude Code, write the narration; the author reads it, edits anything
  that sounds wrong, picks a voice, and generates. The port and the voice
  engine matter here.
- Viewers run nothing. They receive two files — `<name>.mp4` (the narrated
  video) and `<name>.txt` (the transcript) — and view/read them like any other
  file. No app, no server, no localhost, no login.

## A deck is one file: a PDF or a reveal.js deck

The file type picks how the video is made. Never ask the author which.

- A PDF (`deck-3.pdf`), exported from whatever the slides were built in. The
  app copies it into its own folder and renders a page image per slide. In the
  video, each page is a still image shown while its narration plays.
- A reveal.js deck: usually the `.html` Quarto writes when it renders a
  `format: revealjs` deck, with its `<name>_files/` folder beside it. Any page
  that starts reveal.js works. The app opens it by path, in place, so the
  `_files` folder comes along. Chrome plays the deck while the app records it,
  so fragments, transitions and animations are in the video. See "reveal.js
  decks" below before narrating one.

A deck with animations the author wants to keep should be given as reveal.js,
not as a PDF of it. A PDF of a reveal.js deck works too, as still pages.

The narration lives in the app, not in a source deck: a PDF has nowhere to put
it, and a rendered reveal.js file is rewritten on every render. Both of you
write to that one copy: the author types on the Narration text screen
(autosaved), and you write through the narration API.

## Two ways in — either way, draft immediately

- With a deck: `/voiceover deck-3.pdf`, `/voiceover lecture-3.html` (or the
  `.qmd`), "run voiceover on deck 3", "narrate this deck". Launch on that file
  (step 2) and draft.
- With nothing: a bare `/voiceover`. Launch with no deck; the app opens on its
  Upload screen and the author drops a PDF there, or a reveal.js deck (a `.zip`
  of the deck folder, or a self-contained `.html`). Poll
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

- The voice engine, chosen once. Check whether one is recorded:
  `printenv TTS_ENGINE; grep '^TTS_ENGINE=' ~/.voiceover/.env`. If either prints
  `kokoro` or `elevenlabs`, it is chosen: don't ask again. If neither does,
  ask the author which engine to use before the first launch, and describe both
  evenly:

  - Kokoro: free and open source (Apache 2.0). It runs on their own computer,
    needs no account or key, and the narration never leaves the machine. The
    first Generate downloads its model, about 340 MB, once. It has 28 English
    voices (American and British), plainer and less expressive than
    ElevenLabs', and no voice cloning. A long deck takes a few minutes, because
    it speaks one slide at a time on the computer's processor.
  - ElevenLabs: a cloud service. It needs an account and an API key, and the
    free tier has a monthly quota that covers a trial but not a full deck. Its
    voices are more natural and expressive, it has thousands of voices to choose
    from, and it can clone the author's own voice. The narration text is sent
    to ElevenLabs.

  Record the answer by adding `--engine kokoro` or `--engine elevenlabs` to the
  launch command in step 2, once. It writes `TTS_ENGINE` to
  `~/.voiceover/.env`. Tell them they can switch at any time under Audio settings
  in the app, where each deck keeps its settings for both engines. If an
  existing install already has an ElevenLabs key and no `TTS_ENGINE`, it keeps
  using ElevenLabs: tell them Kokoro now exists and ask, but don't switch
  without their answer.

- `ELEVENLABS_API_KEY` — needed only when the engine is ElevenLabs, and only to
  generate. Check with `printenv ELEVENLABS_API_KEY` and
  `grep -c '^ELEVENLABS_API_KEY=.' ~/.voiceover/.env`. Writing and reviewing
  narration need no key, so a missing one is never a reason to delay launching.
  If ElevenLabs is the engine and there is no key, say so up front and walk them
  through it — don't just say "you'll need a key":

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
- A browser, for a reveal.js deck only. The installed Google Chrome is used.
  Without it, the first reveal.js deck downloads a headless Chromium (about
  150 MB), once. A PDF deck needs no browser, so don't mention this for one.
- Python is already present (it runs the launcher), and the first launch sets up
  a small Python environment automatically. Quarto is NOT required by the app
  (the author renders a reveal.js deck), and neither is ffmpeg — it ships with
  the Python dependencies. The frontend ships prebuilt, so Node is not required.

## What to do

`<skill-dir>` below is the "Base directory for this skill" reported when the
skill is invoked; use that absolute path. `<port>` defaults to 8010.

1. Find the deck, if one was named.
   - A `.pdf` or a reveal.js `.html` is used as is.
   - A `.qmd` is resolved by the launcher to its rendered `.html` (beside it, or
     under `docs/` or `_site/`). If none exists, ask the author to render it, or
     run `quarto render <file>.qmd` yourself if they agree.
   - A `.pptx` or `.key`: look for a PDF of the same name next to it and use
     that. If there isn't one, ask them to export it — PowerPoint: File ▸
     Export ▸ Create PDF/XPS; Keynote: File ▸ Export To ▸ PDF.
   Named no deck at all, skip straight to launching without one.

2. Launch the app in the background from the author's current directory (so
   the finished files save there):

   ```
   python3 "<skill-dir>/scripts/skill_launch.py" "<absolute path to the .pdf or .html>"
   python3 "<skill-dir>/scripts/skill_launch.py"      # no deck: they upload one
   ```

   On the first launch after the author chose an engine (Prerequisites), add
   `--engine kokoro` or `--engine elevenlabs` to the command.

   Run it in the background — it starts a long-lived local server. The first
   launch sets up the app environment, so it takes a little longer. Given a deck
   it prints `Open: http://127.0.0.1:<port>/?project=<deck>`; note the deck id.
   Given none, find the id from `GET /api/projects` once they have uploaded.

3. Read the deck. `GET http://127.0.0.1:<port>/api/projects/<deck>/narration`
   returns `{ "format": "pdf" | "revealjs", "slides": [ { "index": 0,
   "title": "…", "slide_text": "…", "narration": "…", "change": … }, … ] }` —
   indexes 0-based, one per slide. A reveal.js deck's slides also have
   `notes` (speaker notes), `steps` and `markers`; see "reveal.js decks".
   Draft from `slide_text` (and `notes`, often the best guide to what the author
   means to say); it is far cheaper than reading images. Only when a slide's
   text is empty or clearly misses the visual content (a chart, a diagram, an
   all-image slide) read that one slide's image at
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
   folder. For a reveal.js deck, also say what "reveal.js decks" asks you to.

   You don't need to warn them off generating early — the app does that itself.
   While slides are still arriving it shows a count above the editor, and
   Generate stops on a deck with empty slides rather than rendering silence,
   with "Generate anyway" there for a deliberately part-narrated deck.

   Say too that neither Upload nor Generate starts over, because that is the
   thing people are most likely to fear and avoid:
   - Changed the slides? Export the PDF again (or render the reveal.js deck
     again) and drop it on Upload, or press "Read it again" there for a deck
     opened by path. Each slide is matched against the old deck by content, so
     a slide that didn't change keeps its narration and the audio already
     spoken for it; only slides that changed or are new come back flagged.
   - Changed some narration? Generate again. Only the slides whose text changed
     are spoken again — a one-slide fix costs one slide of synthesis. (Changing a
     voice or a read setting is the exception: the whole deck is re-spoken,
     because every clip is cached under the voice that made it.)

6. Revisions come to you, in chat. Read the slide, rewrite it, PUT it back, say
   what changed. Keep the style rules below. Editing one slide's narration
   changes only that slide's audio: everything else is reused from the last run,
   so a one-slide fix costs one slide of synthesis.

7. After the deck is uploaded or read again, redraft what moved.
   `GET …/narration` marks slides `"change": "new"` (no narration yet) or
   `"change": "edited"` (the script shown is the one the old slide had). Deal
   with those and leave the rest alone. A slide whose old script still fits
   needs nothing — the author can press "Keep as is" in the app, or you can
   `POST …/review/clear` with `{"indexes": [i]}`. On a reveal.js deck, check an
   edited slide's `steps` too: it may have gained or lost a fragment.

8. If the server does not come up (port already in use), rerun with a different
   port, e.g. `--port 8011`, and use that port in the API calls.

## reveal.js decks

This section applies only when `format` is `"revealjs"`. A PDF deck has no
markers and no fragments.

How the video is made: Chrome plays the deck in real time while the app
records the screen. Each slide is shown with its fragments hidden, its audio
starts, and the deck advances one fragment at each `[next]` marker in the
script, timed to the word. Transitions, auto-animate, CSS animations, embedded
video and JavaScript charts are all captured as they play. A build therefore
takes about as long as the video it makes, plus the audio synthesis: tell the
author that a 20-minute deck takes a little over 20 minutes to record.

### [next] markers

A slide with fragments needs one `[next]` per fragment step in its script, put
immediately before the words that talk about what appears:

```
Three forces set the price. [next] The first is demand, which falls as the
price rises. [next] The second is supply ... [next] And the third ...
```

- `steps` in `GET …/narration` is how many the slide needs; `markers` is how
  many its script has now. Make them equal.
- A marker is stripped before speech. It costs no quota and is never spoken.
  With ElevenLabs, moving a marker changes no audio; only the recording
  changes. With Kokoro, the slide is spoken in pieces cut at its markers, so
  moving a marker re-speaks that slide (free, a few seconds).
- Too few markers is not fatal: steps left over appear one after another when
  the slide's audio ends. Extra markers are ignored. The editor shows the
  count in amber when they differ, and its "Insert [next]" button puts one at
  the cursor. Tell the author about both in the hand-off.
- Only `[next]` is a marker. Other bracketed words, such as ElevenLabs v3 audio
  tags like `[excited]`, pass through to the voice. (Kokoro has no audio tags.)
- A slide with no fragments needs no markers, even if it animates: entrance
  animations, auto-animate and transitions play as the slide arrives, about
  0.6 s before the voice starts.

Before writing a slide with steps, look at what each fragment shows: the
thumbnail has every fragment visible, and `slide_text` lists them in order.
Narrate the slide so each marker sits where the listener should first see the
new item, and don't talk about a fragment before its marker.

### Reading the deck again

Generate refuses to record a reveal.js deck whose file changed since the app
read it, so the script always lines up with what plays. After the author
renders again, the deck must be read again (Upload screen, "Read it again")
before Generate.

### What the recording cannot do

- Sound from a video or audio element on a slide is not recorded; only the
  narration is. The picture of the video is recorded.
- Interaction is not replayed: anything that needs a click, hover or typing
  (other than advancing fragments) stays in its initial state.
- A deck that moves itself with reveal.js `autoSlide` is held still; the
  narration drives the timing.

## Narration style rules

Write what a good speaker would say aloud, not slide captions.
- Spoken prose only: no markdown, bullets, headings, or stage directions. The
  only bracketed text is `[next]`, on a reveal.js deck (and an ElevenLabs v3
  audio tag if the author asks).
- Roughly 60–130 words per slide; teach the content, don't just describe it.
- One continuous talk: each slide picks up mid-thought from the previous one.
  Lead with the substance. Do not open slides with throat-clearing transitions
  like "Let's", "Now", "Next", "So", "Moving on", or "Let's look at".
- Never say "this slide" or "welcome"; narrate the content directly.
- Stay faithful to what each slide actually shows.
