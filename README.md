# kerryback-public

A Claude plugin marketplace.

| Plugin | What it does |
|---|---|
| `critique` | Reviews work Claude produced — a draft, a deck, or code — with parallel reviewer agents, argues against every finding, and publishes an HTML guide with the verdict and the options. |
| `voiceover` | Turns a slide deck (one PDF) into a narrated MP4 plus a transcript. Claude writes the narration; a local app is where you edit it, pick an ElevenLabs voice, and generate. Needs an ElevenLabs API key. |
| `litdb` | A personal literature and notes knowledge base: hybrid keyword and semantic search over your papers and notes, with Zotero and PDF-folder import. |
| `finance-data` | Fetches free financial, market and economic data — Yahoo Finance, FRED, SEC EDGAR, Ken French, FinnHub, Financial Modeling Prep — and saves it as CSV. |
| `wrds` | Empirical asset-pricing data from WRDS (CRSP, Compustat) and Open Source Asset Pricing, as extractable Python builds. Needs a WRDS account. |
| `risk-parity` | The risk parity (equal risk contribution) portfolio, and the covariance matrix it needs, from historical returns. |
| `research` | Sets up a research repository that several people and their agents can share: per-author folders, portable paths, one canonical dataset, provenance, and a writing guide that learns. |
| `smithers` | An email and calendar desk. A local app holds Gmail, Calendar, tasks, and drafts. Claude writes the briefing and drafts replies; you review and send. |
| `tutor` | Builds voice whiteboard tutors from your slides, notebooks, or code, with a review page, evals, and a deploy step. Uses the [tutor-starter](https://github.com/kerryback/tutor-starter) repo. |
| `binomial-tutor` | A voice whiteboard tutor for binomial option pricing that runs in your own Claude Code: Claude teaches on a whiteboard in your browser, with open-source voice (Kokoro) and speech recognition (Whisper) running in the browser. No API key. Start it with `/binomial-tutor:binomial`. |
| `valuation` | A two-stage DCF valuation of a public company from its SEC filings and earnings calls. Runs unattended and builds a tabbed HTML page, with every judgment call flagged, and an Excel workbook with live formulas. Needs `SEC_USER_AGENT` set to your name and email. |

## Install

In Claude Code:

```
/plugin marketplace add kerryback/kerryback-public
/plugin install <plugin>@kerryback-public
```

In the Claude apps (Desktop, Cowork): Customize → Plugins → Add → Add marketplace → `kerryback/kerryback-public`.

Start a new session after installing; a plugin's skills do not load until then.
