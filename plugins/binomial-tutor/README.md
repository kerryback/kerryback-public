# Binomial Tutor (Claude Code plugin)

A voice whiteboard tutor that runs in your own Claude Code. Claude is the
tutor: it talks, writes on a whiteboard in your browser, draws trees and
plots, and checks your answers with exact tools. You answer by speaking or
typing on the whiteboard.

## Install

```
/plugin install binomial-tutor --marketplace kerryback/kerryback-public
```

On Claude Code older than 2.1.275, use two steps:

```
/plugin marketplace add kerryback/kerryback-public
/plugin install binomial-tutor@kerryback-public
```

Restart Claude Code after installing.

## Use

```
/binomial-tutor:binomial
```

Claude opens the whiteboard in your browser. Press Start there and allow the
microphone. Keep the Claude Code window open while you work; you do not need
to look at it.

The first time, the browser downloads the voice models (about 170 MB) from
Hugging Face, so Start takes a minute or two to come on. After that they load
from the browser's cache.

## What runs where

- Claude, in your Claude Code session, does the teaching. It uses your Claude
  plan; there is no separate API key.
- The voice is Kokoro (82M, Apache 2.0) and the speech recognition is Whisper
  base.en, both running in the browser through Transformers.js. Your
  recordings never leave your computer. The text of what you say goes to
  Claude, like anything you type in Claude Code.
- A small local server (Python 3.9 or later, standard library only) serves the
  whiteboard on 127.0.0.1 and gives Claude the tutor's tools. Every number the
  tutor uses comes from these tools.
- Your progress (modules done, where you stopped) is kept in the plugin's data
  folder and picked up next session.

## Requirements

- Claude Code.
- `python3` on your PATH (macOS has it with the command line tools; on Windows,
  install Python from python.org).
- A current Chrome, Edge, Firefox or Safari.

## Settings

Environment variables, set before starting Claude Code:

| Variable | Default | Meaning |
|---|---|---|
| `TUTOR_PORT` | `8030` | First port to try for the whiteboard |
| `KOKORO_VOICE` | `af_heart` | Kokoro voice |
| `KOKORO_SPEED` | `0.9` | Speaking speed (1.0 is normal) |
| `VOICE_IDLE_SECONDS` | `45` | Silence before the tutor asks whether to continue |

This plugin is built from the voice tutors at github.com/kerryback/tutors by
`scripts/build-plugin.sh binomial`. Do not edit it here.
