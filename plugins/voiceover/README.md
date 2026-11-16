# voiceover

Turn a slide deck into a narrated MP4 video plus a transcript — and get the
narration written for you.

Give it the PDF of your slides, or a reveal.js deck (such as the `.html` Quarto
renders for a revealjs presentation). Claude drafts the narration slide by
slide; a local app shows each slide beside its script, where you edit anything
that sounds wrong, pick a voice, and press Generate. The finished `.mp4` and
`.txt` land in your working directory.

The file type decides how the video is made:

| You give it | The video |
| --- | --- |
| a PDF of your slides | each page is a still image, shown while its narration plays |
| a reveal.js deck | the deck is played and recorded in Chrome, with its fragments, transitions and animations, each fragment appearing at the word where the narration says `[next]` |

## Install

```
/plugin marketplace add kerryback/kerryback-public
/plugin install voiceover@kerryback-public
```

Then `/voiceover deck-3.pdf` or `/voiceover lecture-3.html` (or the `.qmd`), or
just `/voiceover` and upload the deck in the app. "Narrate these slides" works
too.

## What you provide

| | |
| --- | --- |
| a PDF of your slides | exported from PowerPoint, Quarto, Keynote — anything |
| or a reveal.js deck | the rendered `.html`, with its `_files` folder beside it |
| a voice engine | Kokoro or ElevenLabs, chosen the first time (below) |

That's the lot. The app runs no Quarto, and needs no ffmpeg or Node. A
reveal.js deck uses your installed Google Chrome; without it, the first
reveal.js deck downloads a headless Chromium (about 150 MB) once. A PDF needs
no browser.

## Choosing a voice engine

The first time, Claude asks which engine should speak your narration. You can
switch at any time under Audio settings in the app.

| | Kokoro | ElevenLabs |
| --- | --- | --- |
| Cost | Free, open source (Apache 2.0) | Free tier with a monthly quota; paid plans above it |
| Runs | On your computer; the narration never leaves it | In ElevenLabs' cloud; the narration is sent there |
| Setup | Nothing. The first Generate downloads a 340 MB model once | An account and an `ELEVENLABS_API_KEY` |
| Voices | 28 English voices, American and British; plainer | Thousands, more natural and expressive; voice cloning |
| Speed | One slide at a time on your processor; a long deck takes minutes | Several slides at once |

With ElevenLabs, Claude checks for the key before launching and offers to help
set it, rather than letting it fail halfway through. Writing narration needs no
engine at all; only generating the video does.

## How it goes

The app opens at <http://127.0.0.1:8010>, with one row of buttons:

`Upload · Narration text · Audio settings · [Generate] · Preview`

Claude reads the deck and writes the narration straight away; you read it in
Narration text, change anything that sounds wrong (it autosaves), or tell Claude
what you'd actually say and let it rewrite the passage. Then a voice, then
Generate, then the video is on Preview and the files are in your folder.

## Nothing here starts over

The two things people hesitate to press are both incremental:

- Upload (or "Read it again"), after you've edited the slides: each new slide is
  matched against the old deck by content, so a slide that didn't change keeps
  its narration and the audio already spoken for it. Only slides that changed,
  or are new, come back flagged.
- Generate, after you've edited some narration: only the slides whose text changed
  are spoken again. A one-slide fix costs one slide of synthesis. (Change the
  voice, though, and the whole deck is re-spoken — every clip is cached under the
  voice that made it.)

## reveal.js decks

Chrome plays the deck in real time while the app records it, so a 20-minute
deck takes a little over 20 minutes to record. A slide with fragments needs one
`[next]` in its script for each fragment step, placed before the words about
what appears; Claude places them, and the editor shows the count and has an
"Insert [next]" button. Not recorded: sound from a video on a slide (its
picture is), and anything that needs a click.

## Getting good narration

The narration is drafted to be spoken, not read — a different register from the
text on your slides. It doesn't read the bullets aloud, because a listener can
already see them; it says the thing the bullets are shorthand for.

If a slide's narration is wrong, the fastest fix is usually to tell Claude what
you'd actually say and let it rewrite the passage.

## Your own voice

If you'd rather the video sounded like you than like a stock voice, use the
ElevenLabs engine and clone your voice there — a cloned voice shows up in this app's voice list alongside
the stock ones, labelled as yours.
