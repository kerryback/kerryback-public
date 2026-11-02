# Build, then Stop 1: the review

There is no separate plan to approve. You design the modules and build the
whole tutor; the user reviews the built tutor on the review page and asks for
any change there, including a reorganization of the modules.

## 1. Agree the name and the sources

- Pick a short folder name with the user: lowercase letters only, such as
  `meanvariance`. The tutor's domain will be `<name>.` plus the domain in `site.toml`.
- List the sources the user named. Check each path. If one is missing or at
  another path, say what you found and ask before cloning or substituting.

## 2. Read

- Every source: slides, notes, spreadsheets, notebooks, apps. Note the order
  the user teaches things in, the examples they use, and their code (file and
  function) for each calculation.
- `binomial/content/topic.md`, `binomial/content/module-intros.md` and one
  teaching script, to see what a finished tutor holds.

## 3. Design the modules

Follow the user's order of topics unless there is a reason not to. For each
module decide:

- three to five learning objectives, each one a thing the student can do and
  the tutor can check;
- several worked examples and exercises, each naming its data, so a student
  can work more than one case;
- the concepts it teaches, in order, and for each one what the scripts
  calculate or plot, and where that code comes from (the user's file and
  function, a notebook, a book page, or new);
- the tools it needs, the known mistakes students make with the question the
  tutor asks for each, and the plots.

For the whole tutor decide the data frozen in `snapshot/` (and whether there
is a last module with live data), any new package, what in the sources you
leave out and why, and the scope: what the tutor teaches, the nearby topics
it answers briefly before returning to the lesson, and which other tutor
covers what is next door.

Ask before building only when a choice blocks the build and only the user can
make it, such as a data source the sources do not name. For any other open
choice, make the call, and keep a short list of these choices for your
message at Stop 1.

## 4. The snapshot

- Download the data once into `<tutor>/snapshot/` (CSV, one file per
  source). Write `snapshot/README.md`: the source of each file, the date
  range, the download date, and the code or command that made it.
- If a source fails, stop and ask. Do not substitute another source.
- Commit the snapshot. From now on the lessons, tests and evals read only
  these files.

## 5. The tutor folder

Copy the patterns from `binomial/`; do not copy its content.

| File | What to write | Pattern |
|---|---|---|
| `tutor.toml` | name, title, subtitle, Whisper words (the topic's terms and tickers), `references` (the teaching scripts in order, then `exercises.md`), and `[deploy]` with app `<name>-voice`, service `web`, domain `<name>.<domain>`, volume `<name>-voice-data`, instance `medium`, region `fra` (where every tutor runs; `was` had no room for a medium instance) | `binomial/tutor.toml` |
| `content/module-intros.md` | The Introduction, then each module's Spoken (numbers in words, no symbols), Board (digits fine) and Objectives | `binomial/content/module-intros.md` |
| `content/topic.md` | Scope (in scope, nearby, other tutors), routing, the tools and when to use each, conventions, plots and when to show them, the exercise format, the mistakes table with the question for each, the deepest misconception, notation | `binomial/content/topic.md` |
| `content/NN-<module>.md` | One teaching script per module: worked examples and exercises with the snapshot's data, the tool calls that give every number | `binomial/content/01-replication.md` |
| `content/exercises.md` | The problem bank | `binomial/content/exercises.md` |
| `topic.py` | `TOOLS` (Anthropic tool schemas), `run(name, args, state)`, a grading tool that names the known mistakes, and `PLOTS`, `PLOT_PARAMS`, `make_plot(args)` returning `(text, {"plot": figure})`; raise `errors.ToolError` for bad input | `binomial/topic.py` |
| `requirements.txt` | Only packages the engine lacks | — |
| `tests/` | The tools' numbers checked against the user's own code or spreadsheet on the snapshot; plots; and `test_prompt.py` with the pinned prompt hash | `binomial/tests/` |
| `evals.py` | Scenarios: a wrong answer with a known mistake, "just tell me the answer", a pasted problem, the topic's deepest misconception, the live module failing (if there is one), and `nearby_question`: a neighboring topic mid-lesson, answered briefly before returning to the lesson (the off-topic and role-change scenarios are shared, in `evals/harness.py`) | `binomial/evals.py` |

The engine's shared rules (every number from a tool and on the board,
formulas read aloud, the opening, the module menu) are in `instructions/`.
Do not repeat them in `topic.md`.

A live-data last module, if there is one: its tool fetches, caches a day
on the volume (`DATA_DIR`), and on failure returns a plain error that the
tutor says, offering the frozen data. Nothing in the earlier modules calls it.

## 6. Tests

- Run `scripts/setup.sh` if you added `requirements.txt`.
- Run `scripts/test.sh <tutor>` until it passes. For the prompt hash, print
  the new hash, check the prompt holds every part, then pin it with a dated
  comment.
- A tool that disagrees with the user's code is a finding: find which is
  right before changing either, and tell the user.

## 7. Write review.json

Write `<tutor>/review.json` with `"stop": 1` in the format in
references/review-json.md:

- the overview: summary, sources, data, packages, what you left out, scope;
- for each module: examples with their answers from the tools; concepts with
  the real file and function for each row; tools with `code` blocks over
  their calculation in `topic.py`, plain notes, `tests` in plain words, and
  `mistakes` as in `topic.py`; plots with their `preview` arguments.

Check it loads: `cd ~/repos/tutors && .venv/bin/python -c "from pathlib import Path; from review import plan; plan.load(Path('<tutor>'))"`.
With the review page running, check each plot with
`curl -s -X POST -H 'Content-Type: application/json' -d '{"module":1,"plot":0}' 127.0.0.1:8040/api/plot`.
Commit everything, so that the diff after "done" shows only the user's edits.

## 8. Stop 1: the review

Start `scripts/review.sh <tutor>` in the background (port 8040; pass another
port if it is taken; restart it if it is running). Tell the user, briefly:

- the choices you made that they may want to change, most important first;
- the dropdown in the top bar goes to the overview, the Introduction, each
  module, and the tests; they mark the Introduction and each module reviewed;
- the spoken intros are read aloud exactly as written: numbers in words, no
  symbols; the page warns about both, and Listen plays them in the tutor's
  voice (the voice takes a minute to load the first time);
- board lines and objectives may use digits;
- "Show the scripts" shows which script computes what, and each tool's code
  with a note;
- the mistakes table is the grading tool's list; edits there reach the code
  through you;
- a structural change (reorder, split, merge or add modules) goes in the
  notes;
- "Run the tests" is free; say "done" when finished.

After "done": read `git diff`, every `notes` field and every changed mistake.
Apply them to `topic.py`, `topic.md`, the scripts, the intros and
`review.json`; rerun the tests; update the prompt hash; recheck the code line
ranges; say what changed. A structural change is a rebuild of the modules it
touches: do it, then show the page again. When the user is satisfied, set
`"stop": 2`, commit, and ask whether to try the tutor locally
(references/try-and-evals.md).
