---
description: Build an HTML status report of the project — executive summary, open issues, and a chronology — from the committed records. Optionally scoped to a date range or one coauthor.
argument-hint: "[optional: since <date>, or a coauthor's name]"
---

Produce a status report for this project as a self-contained HTML page.

Read `CLAUDE.md` if you have not already. Everything below assumes it.

`$ARGUMENTS`, if given, narrows the report: a date or phrase ("since August 1",
"last week") bounds the chronology, and a coauthor's name focuses it on their
work. With no argument, report the whole project to date.

## First: is the record complete?

Run this before anything else:

```bash
python3 -m tools.chronology --gap --human
```

It lists commits that landed with no changelog entry dated after them — work
whose *reason* was never written down. Entries are written by `/handover`, or
whenever Claude asks *update state?*, and those only happen when someone
invokes them, so work that ended any other way leaves exactly this hole. Git has
what changed; nothing has why.

If there is a gap, **deal with it before writing the report, not after.** For
each undocumented commit you can reconstruct the reason for — from this
conversation, from the diff, from `session.md` — offer to add the changelog
entry now. Say plainly which ones you cannot reconstruct; those are lost, and
the report should not invent a reason for them.

A report built on a changelog with a five-commit hole will read as complete and
will not be. If the user declines to fill it, put the gap in the report itself,
in the executive summary, naming the dates and authors.

## What this reads, and what it does not

Everything else the report needs is already written down and committed. There is
no accumulation step to run first and no log to mine: the changelog in
The state directory is the incremental artifact, and `/handover` keeps it current.

Read these, and only these:

| Source | What it gives the report |
|---|---|
| `project/global/state/` | the thesis, settled facts, killed ideas with reasons, open questions, results, and the dated changelog |
| `project/global/method_spec.md` | what is frozen for the current round |
| `project/global/data_manifest.md` | what is canonical and why it is trusted |
| `project/<author>/session.md` | each person's in-flight work, next actions, open threads |
| `project/<author>/analyst.md`, `replicator.md` | where each build stands, if the project is empirical |
| `draft/` | whether the paper exists and what it currently contains |
| `python3 -m tools.chronology` | the assembled timeline |

Do NOT read `logs/debate-*.jsonl`. It is bulky, it is local to one machine, and
it says nothing the changelog does not say better.

Build the timeline with the tool rather than by hand — it merges four sources
and gets the ordering right:

```bash
python3 -m tools.chronology --human                    # everything
python3 -m tools.chronology --since 2026-08-01 --human
python3 -m tools.chronology --author <slug> --human
python3 -m tools.chronology --kinds changelog,commit --human   # decisions only
```

## What goes in the report

### 1. Executive summary

Four or five sentences, written for a coauthor who has been away for a month.
What the project is arguing, where it now stands, what changed most recently,
and the single thing most needing attention. Name the current headline result
with its actual magnitude — a status report that says "results are promising"
has told nobody anything.

If the thesis has moved since the last major entry, say so explicitly and give
the reason. That is usually the most valuable sentence on the page.

### 2. What is settled

The claims that have been through the gate and should not be relitigated, each
with the date it settled. Keep this section short and hard: a fact belongs here
only if `state/core.md` treats it as settled. Where a result is empirical and the
project runs two builds, say whether both builds converged on it.

This section exists so a returning coauthor knows what NOT to reopen. Do not
soften it with maybes.

### 3. Open issues

Everything genuinely unresolved, grouped by kind and each tagged with whose it
is:

- **Blocking** — work that cannot proceed until this is decided. An open round
  lock held by someone who has stopped working belongs here.
- **In flight** — started and unfinished. Pull these from each `session.md`,
  and say what each was waiting on.
- **Open questions** — unsettled, not currently being worked.
- **Deferred** — decided-not-to-do-yet, with the reason. Distinct from killed.

For each, say what would resolve it. An open issue with no route to closure is
either a blocking decision for the humans or it is not really an issue — say
which.

### 4. Chronology

The project's arc, newest first, grouped by date. Lead each day with the
decisions from the changelog — those carry the reason — then the commits and
runs around them as supporting detail. A reader should be able to scan dates
and see the shape of the project without expanding anything.

Where a direction was explored and abandoned, show it. Those are what make this
section worth reading, because "we tried X and here is why we stopped" is the
most expensive knowledge on the project and the easiest to lose. It lives in the
round entries and the killed-ideas section — if a round's entry was never
written, this report cannot recover it, and should say so rather than imply the
project never explored anything.

Collapse the run-level detail behind a disclosure element so the decisions stay
legible; a day with forty script runs should not bury the one decision that made
them happen.

### 5. Who is doing what

One line per coauthor: what they last worked on, what they hold now, and whether
anything is waiting on them.

## Writing it

Self-contained HTML — no external stylesheets, scripts, fonts, or images.
Everything inline. Theme-aware: define the light palette on `:root`, redefine
under `@media (prefers-color-scheme: dark)` guarded as
`:root:not([data-theme="light"])`, and give `body` an explicit background.

If the repo already has an HTML document at its root — a `protocols.html`, an
onboarding brief, an earlier status report — read its `<style>` block and match
it. These accumulate into a set that coauthors read together, and a page in a
different visual language reads as a stray.

Write for the coauthor, not for the record. Ordinary sentences, dates in plain
form, no internal vocabulary from `CLAUDE.md`, no bare finding IDs, no scores.
Where a number matters, give it with its units.

Save to the repo root as `status-<YYYY-MM-DD>.html`. Do not overwrite an earlier
status report — they are a series, and the older ones are how someone sees what
the project looked like before.

## Then

Tell the user in the chat: where the file is, the executive summary in two
sentences, and the top open issue. Someone who reads only your message should
know the state of the project.

Then offer, without doing either unasked:

- **Commit it**, so the other coauthors get it on their next pull. This is
  usually the point of running the command.
- **Publish it as an artifact**, if they want a link to send to someone outside
  the repo. Load the `artifact-design` skill first if so.

If the report surfaced something that belongs in the durable record — an open
issue nobody had written down, a decision made in conversation but never entered
in the changelog — say so and offer to add it. A status report that quietly
discovers missing memory and does not fix it has wasted the discovery.
