# kerryback-public

A Claude plugin marketplace with two plugins.

| Plugin | What it does |
|---|---|
| `critique` | Reviews work Claude produced — a draft, a deck, or code — with parallel reviewer agents, argues against every finding, and publishes an HTML guide with the verdict and the options. |
| `voiceover` | Turns a slide deck (one PDF) into a narrated MP4 plus a transcript. Claude writes the narration; a local app is where you edit it, pick an ElevenLabs voice, and generate. Needs an ElevenLabs API key. |

## Install

In Claude Code:

```
/plugin marketplace add kerryback/kerryback-public
/plugin install critique@kerryback-public
/plugin install voiceover@kerryback-public
```

In the Claude apps (Desktop, Cowork): Customize → Plugins → Add → Add marketplace → `kerryback/kerryback-public`.

Start a new session after installing; a plugin's skills do not load until then.
