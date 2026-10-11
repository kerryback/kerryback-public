# voiceover

Turn a slide deck into a narrated MP4 video plus a transcript — and get the
narration written for you.

Give it the PDF of your slides. Claude drafts the narration slide by slide; a
local app shows each slide beside its script, where you edit anything that sounds
wrong, pick a voice, and press Generate. The finished `.mp4` and `.txt` land in
your working directory.

## Install

```
/plugin marketplace add kerryback/kerryback-public
/plugin install voiceover@kerryback-public
```

Then `/voiceover deck-3.pdf`, or just `/voiceover` and upload the PDF in the
app. "Narrate these slides" works too.

## What you provide

| | |
| --- | --- |
| a PDF of your slides | exported from PowerPoint, Quarto, Keynote — anything |
| `ELEVENLABS_API_KEY` | text to speech. A free key works to start |

That's the lot. Quarto is not required; neither is ffmpeg or Node. Claude checks
for the key before launching and offers to help set it, rather than letting it
fail halfway through — and writing narration needs no key at all, only generating
the video does.

## How it goes

The app opens at <http://127.0.0.1:8010>, with one row of buttons:

`Upload · Narration text · Audio settings · [Generate] · Preview`

Claude reads the deck and writes the narration straight away; you read it in
Narration text, change anything that sounds wrong (it autosaves), or tell Claude
what you'd actually say and let it rewrite the passage. Then a voice, then
Generate, then the video is on Preview and the files are in your folder.

## Nothing here starts over

The two things people hesitate to press are both incremental:

- Upload, after you've edited the slides: each new page is matched against the old
  deck by content, so a page that didn't change keeps its narration and the audio
  already spoken for it. Only pages that changed, or are new, come back flagged.
- Generate, after you've edited some narration: only the slides whose text changed
  are spoken again. A one-slide fix costs one slide of synthesis. (Change the
  voice, though, and the whole deck is re-spoken — every clip is cached under the
  voice that made it.)

## Getting good narration

The narration is drafted to be spoken, not read — a different register from the
text on your slides. It doesn't read the bullets aloud, because a listener can
already see them; it says the thing the bullets are shorthand for.

If a slide's narration is wrong, the fastest fix is usually to tell Claude what
you'd actually say and let it rewrite the passage.

## Your own voice

If you'd rather the video sounded like you than like a stock voice, clone your
voice on ElevenLabs — a cloned voice shows up in this app's voice list alongside
the stock ones, labelled as yours.
