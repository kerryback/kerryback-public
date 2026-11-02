# The review.json format

`<tutor>/review.json` holds what the review page shows that is not in the
tutor's own files: the overview, the examples, the mistakes, the plots'
preview settings and the explanations of the code. You write it after you
build the tutor; the page saves the user's edits into it.

```json
{
  "tutor": "meanvariance",
  "title": "Mean-Variance Tutor",
  "stop": 1,
  "intro_status": "open",
  "overview": {
    "summary": "One paragraph: what the tutor teaches and to whom.",
    "sources": [{"path": "~/teaching/slides/portfolios.qmd"}],
    "data": [{"name": "SPY", "what": "US stocks", "source": "Yahoo, monthly adjusted close", "range": "2006-01 to 2025-12"}],
    "packages": ["yfinance"],
    "left_out": [{"what": "Black-Litterman", "why": "Not in the course slides"}],
    "scope": {"teaches": "What the modules teach.",
              "nearby": "Prerequisites and neighboring topics the tutor answers briefly, then returns to the lesson.",
              "elsewhere": "Which other tutor covers what is next door."}
  },
  "modules": [{
    "n": 2,
    "title": "Two funds",
    "examples": [{"label": "Worked example", "data": "IEF, SPY", "asks": "Tangency weights", "answer": "IEF 38.2%, SPY 61.8%"}],
    "concepts": [{
      "name": "The tangency portfolio",
      "scripts": [
        {"computes": "Tangency weights, mean, sd and Sharpe ratio", "script": "topic.py: tangency",
         "origin": "~/repos/demos/tangency/server.py: compute"},
        {"computes": "Plot: the frontier with the tangency line", "script": "plots.py: frontier",
         "origin": "~/repos/learn-investments-notebooks/portfolios/frontier.ipynb"}
      ]
    }],
    "tools": [{
      "name": "portfolio_stats",
      "source": "~/repos/demos/tangency/server.py: portfolio_stats",
      "does": "...", "inputs": "...", "returns": "...", "tests": "...",
      "file": "topic.py",
      "code": [{"lines": "40-44", "note": "Plain note for this block."}],
      "mistakes": [{"did": "Forgot the covariance term", "ask": "Do the two funds move together?"}]
    }],
    "plots": [{"name": "frontier", "shows": "...", "preview": {"plot": "frontier", "funds": ["IEF", "SPY"]}}],
    "status": "open",
    "notes": ""
  }],
  "notes": ""
}
```

## Required and defaults

Required: `tutor` (the folder name), `title`, `stop` (1 while the user
reviews, 2 once they approve and try it), `modules`, and in each module `n` and
`title`; in each tool and plot, `name`. Everything else may be left out and
defaults to empty (`""`, `[]`, `null`), with `status` and `intro_status`
`"open"`, a tool's `source` `"new"` and its `file` `"topic.py"`.

The spoken intros, board lines and objectives are not in review.json: the page
reads and writes them in `content/module-intros.md`. Older files may hold a
module's `teaches`, `why` or `objectives`; the page ignores them.

## What each part is for

- `overview`: the page's "Overview and data". `sources` lists the files you read
  (paths only: what each is used for goes in the modules' `concepts`);
  `data` is the frozen snapshot (one row per series); `left_out` is what you
  chose not to teach, with the reason; `scope` is the subject's boundary, as in
  the "Scope" section of `topic.md`.
- `intro_status` and `modules[].status`: `"open"` or `"reviewed"`, set by the
  user on the page.
- `modules[].examples`: one row per worked example or exercise, with the
  tools' answer.
- `modules[].concepts`: shown under "Show the scripts", a table for
  each concept the module teaches, in teaching order. One row for each number
  or plot a script produces: `computes` (the quantity, or "Plot: ..."),
  `script` (the file and function in the tutor folder that holds the code,
  such as `"topic.py: market_model"`) and
  `origin` (the user's file and function or notebook cell the code comes from,
  a page of a book for a formula, or `"new"`). Every tool and plot appears in
  at least one row. Required: `name`; `origin` defaults to `"new"`.
- `tools[].source`: the user's file and function (`"~/repos/demos/tangency/server.py: portfolio_stats"`), or `"new"`, optionally followed by a note (`"new (from the slide on leverage)"`).
- `tools[].code`: each block is a line range in `file` (relative
  to the tutor folder, 1-based, inclusive, such as `"40-44"`) and a plain note
  saying what those lines do, for a teacher who does not read Python. Cover
  the tool's whole calculation in blocks of a few lines each. After any edit
  to the file, check the line ranges again: a range past the end shows as
  missing.
- `tools[].tests`: which tests check the tool, against which of the
  user's files, in plain words.
- `tools[].mistakes`: the known mistakes and the tutor's question for each.
  The page shows them for every tool that has any. The user may edit them;
  you then put the edits into `topic.py` and `topic.md`.
- `plots[].preview`: the arguments `topic.make_plot` gets to draw the plot on
  the page when the module opens, such as `{"plot": "frontier", "funds": ["IEF", "SPY"]}`.
  A plot without them shows a warning instead.
- `status` and `notes`: the user's. Read every `notes` field when the user
  says the review is done.

## What the page may change

`notes` and `intro_status`, and in each module `examples`, each tool's
`mistakes`, `status` and `notes`. It also writes the spoken intros, board
lines and objectives in `content/module-intros.md`. It never touches anything
else.

Before you edit review.json while the page is open, tell the user to save
first: the page refuses a save when the file changed on disk.
