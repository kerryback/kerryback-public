# kerryback-public

A Claude plugin marketplace.

| Plugin | What it does |
|---|---|
| `critique` | Reviews work Claude produced — a draft, a deck, or code — with parallel reviewer agents, argues against every finding, and publishes an HTML guide with the verdict and the options. |
| `voiceover` | Turns a slide deck (one PDF) into a narrated MP4 plus a transcript. Claude writes the narration; a local app is where you edit it, pick an ElevenLabs voice, and generate. Needs an ElevenLabs API key. |
| `litdb` | A personal literature and notes knowledge base: hybrid keyword and semantic search over your papers and notes, with Zotero and PDF-folder import. |
| `finance-data` | Fetches free financial, market and economic data — Yahoo Finance, FRED, SEC EDGAR, Ken French, FinnHub, Financial Modeling Prep — and saves it as CSV. |
| `wrds` | Empirical asset-pricing data from WRDS (CRSP, Compustat) and Open Source Asset Pricing, as extractable Python builds. Needs a WRDS account. |
| `two-stage-dcf` | Two-stage enterprise valuation. Fetches a company's statements, 10-Ks, press releases and call transcripts, argues for each forecast assumption from them, and writes one page with an editable baseline that revalues the DCF in the browser, plus an Excel workbook. |
| `risk-parity` | The risk parity (equal risk contribution) portfolio, and the covariance matrix it needs, from historical returns. |
| `tutor` | One-on-one tutors that coach a student to the answer instead of giving it: `/tutor:binomial` (binomial option pricing). |

## Install

In Claude Code:

```
/plugin marketplace add kerryback/kerryback-public
/plugin install <plugin>@kerryback-public
```

In the Claude apps (Desktop, Cowork): Customize → Plugins → Add → Add marketplace → `kerryback/kerryback-public`.

Start a new session after installing; a plugin's skills do not load until then.
