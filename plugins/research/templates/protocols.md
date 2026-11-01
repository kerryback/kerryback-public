# Writing `protocols.html`

This is the spec for the human-facing guide you write to the repo root during
setup. `CLAUDE.md` is the operating manual for you; this is the one document a
coauthor actually reads. Write it once at setup, and update it whenever a rule
in `CLAUDE.md` changes — the two are a pair, and a stale `protocols.html` is
worse than none, because people believe it.

Write it LAST, after the repo is built and verified. It describes what is
actually there, not what was planned: if the interview said no to the debate
panel, the guide has no debate section.

## Who it is for

One person, on their first day, who did not run setup and was not in the
conversation. They know the field and their own research; they may not know git
beyond `commit` and `push`, and they have never seen this layout. They want to
do one afternoon's work without breaking anything or asking a question they feel
they should already know the answer to.

Write for that person, in ordinary sentences. This is the one place in the repo
where the audience is not Claude.

## What it must cover

**1. What this project is.** The one-line description, then two or three
sentences of context. Who is on it, and what stage it is at.

**2. Your first twenty minutes.** The literal steps, in order, with the commands
spelled out: clone, set the data environment variable, create the venv, install
requirements, open Claude Code in the repo and say "get me set up." Say that
Claude runs `tools/onboard.py` itself and will walk them through what is
missing — they do not have to memorize any of this.

Include the one thing that fails silently: their `git config user.name` decides
the slug that names every folder they own. Show them how to check it and what it
will produce.

**3. Where things live, and the one rule.** A short tree, then the rule stated
plainly: `project/global/` is shared and is the project; `project/<you>/` is
yours and nobody else writes in it; data lives outside the repo and is never
committed. Say where the data actually is, by name — the Dropbox or Box folder,
not just an environment variable.

**4. Working at the same time.** This is the section that most needs to exist,
because it is the piece a newcomer will assume works the way it does everywhere
else. Cover, in this order:

- **Everyone works at once.** Nobody claims anything, nobody waits, and there is
  nothing to release. Say it plainly and early — a collaborator who has used a
  locked repository before will otherwise go looking for the lock.
- **Why it works: the state is a directory, not a file.** One `state.md` holding
  everything cannot be merged, and the only fix on one file is to let one person
  write at a time. Instead, `python3 -m tools.state new "what changed"` creates
  one file. Two people running it at the same moment create two different files,
  and git merges file additions without a conflict.
- **How to read it:** `python3 -m tools.state show`. It prints and writes
  nothing — there is no assembled `state.md` on disk, on purpose, because a
  generated shared file is exactly what two people at once would collide on.
- **The two rules.** Never edit another author's entry or block; they are
  append-only, and if one is wrong you write a new one saying so. And `core.md`
  — thesis, settled facts, open questions, killed ideas — is the one shared
  file, short enough that two people editing it the same day is a small readable
  conflict rather than two rewrites of a thousand lines.
- **Claude raises it, you do not have to remember.** When a result changed, when
  something was settled or killed, at a gate, or before committing work someone
  else would need explained, Claude asks *update state?* rather than waiting to
  be told.

**5. What the project remembers.** The two committed records — the state
entries, and the run records — and the fact that there is no session log, on
purpose. Then the part that asks something of them: a stretch of work ends with
an entry saying what it took up and what came of it, written *even when nothing
settled*. That is what answers "did we ever try X" a year later, and it
is the entry people skip, because a round that changed nothing feels like
nothing worth recording. It leaves no diff and no artifact, so if the entry is
not written the exploration is gone. Killed ideas also go in the killed-ideas
section with the reason.

**6. Why Claude runs your scripts oddly.** They will notice Claude typing
`python3 tools/runlog.py my_script.py` instead of `python3 my_script.py`, and
should know why rather than assuming it is a quirk: the wrapper runs the script
normally and appends one line recording the script, the commit, and the files it
actually read and wrote. That line is what answers "where did this number come
from" when a referee asks. Tell them to do the same when they run something
themselves, and that a script run directly still works — it just leaves no
record, and nothing warns them.

**7. Writing.** `writing-guide.md` in the repo root governs everything in
`draft/`. Say that it is binding rather than advisory, that it does not apply to
notes between coauthors, and that Claude reads it before drafting.

**8. The commands.** A short table: `/handover`, `/report`, and anything else
the project got. One line each, in plain language. There are deliberately few —
the state is kept current by Claude asking, not by a command somebody has to
remember to run.

**9. Who to ask.** Names, and what each person owns.

Include only the sections that apply. If the project got Overleaf, add how the
mirror works and the rule that you always pull before you push. If it got the
debate panel, add what it costs — their own OpenRouter key, their own calls —
and that the briefs stay on their machine while the decision goes in the
changelog.

## What to leave out

- The internals of `tools/`. If they need provenance, they will ask Claude.
- Anything addressed to Claude. Do not paste `CLAUDE.md` sections in; rewrite
  them for a person or leave them out.
- Rationale for choices they cannot change. Say what the rule is and the one
  sentence of why that makes it stick; skip the design argument.
- Aspirations. Document the repo that exists.

## How to write it

Self-contained HTML — no external stylesheets, scripts, fonts, or images.
Everything inline. Theme-aware: define the light palette on `:root`, redefine
under `@media (prefers-color-scheme: dark)` guarded as
`:root:not([data-theme="light"])`, and give `body` an explicit background.

Readable on a laptop without zooming: a max-width around 70 characters of text,
generous line height, and commands in a monospace block that can be copied in
one selection. Any wide block scrolls inside its own container rather than
making the page scroll sideways.

`/report` writes its report to the same repo root and matches whatever style it
finds here, so this file sets the visual language for the project's documents.
Keep it plain and typographic — it is a reference someone opens on their second
day, not a landing page.

Every command in it must be one you actually ran or verified during setup. A
guide with a command that does not work teaches the reader that the guide is not
to be trusted, and they will stop reading it at that point.
