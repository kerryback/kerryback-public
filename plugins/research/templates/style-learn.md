---
description: Turn captured prose corrections into rules in writing-guide.md — review the backlog, propose rules, write the ones the author accepts into the section they belong in.
argument-hint: "[optional: --since <rev> to also harvest committed rewrites]"
---

Curate the backlog of prose corrections into `writing-guide.md`.

That file is the project's one writing standard. You are adding to it, in the
section the rule bears on — not starting a file of conventions beside it, and
not appending a rules section at the end. If a rule about prose is worth
keeping, it belongs where someone reading about that topic will meet it.

You are not summarizing a log. You are deciding which corrections generalize,
and every rule you propose has to survive the question *would this have caught
the correction, and would it be right the next time?*

## 1. Gather

```bash
python3 tools/style.py harvest          # or: --since <rev> from "$ARGUMENTS"
python3 tools/style.py pending
```

`harvest` picks up prose the author rewrote themselves, which the hook cannot
see. Run it first or you will curate half the evidence.

If nothing is pending, say so in one line and stop. Do not invent rules to have
something to show.

## 2. Read the guide

Read `writing-guide.md` in full before proposing anything — all of it, not the
section you expect to land in. You need the whole thing to avoid the three
failure modes that would degrade it:

- **Duplication.** If the guide already says it, there is no rule to add. The
  correction happened because the guide was not followed, not because it was
  silent. Say so and add nothing.
- **Contradiction.** If the correction cuts against a line already in the guide,
  do not add a rule beside it. Rewrite that line, and show the author both the
  old and the new wording — you are changing the standard, which is a bigger
  thing than adding to it, and they should see it as such.
- **Fragmentation.** If a marked rule already covers it, bump its `hits` and
  update `last` rather than adding a second. Widen its wording only if the new
  evidence genuinely shows it was too narrow.

## 3. Cluster and propose

Group the observations by what the correction was really about. The `before` and
`after` are the evidence; the `instruction` says what the author wanted, and is
usually a better guide to the rule than the diff.

Discard, without proposing:

- content changes — a corrected number, a new citation, a changed claim
- edits where you rewrote your own draft mid-thought
- one-offs specific to a passage, with nothing that would transfer
- anything you cannot state as an instruction someone could follow

Propose a rule only when it clears one of these bars:

- two or more independent corrections point the same way, or
- one correction states a general instruction outright ("never say X", "always
  give the units first")

For each candidate show the author: the rule as one imperative sentence, which
section of the guide it goes in, the number of observations behind it, the
single most convincing before/after pair, and any existing line it would
replace. Nothing longer.

Also flag, separately, any correction you dropped and why, one line each. The
author needs to see what you judged to be noise; that call is the one most
likely to be wrong.

## 4. Get a decision on each

Put the candidates to the author with `AskUserQuestion` where there are few, in
prose where there are many. Accept, reject, or reword — their wording wins over
yours without argument.

Nothing enters the guide that the author did not accept. It is committed and
shared with coauthors who do not have identical taste, and that is exactly why
the promotion step is a person rather than a heuristic.

## 5. Write it into the guide

Edit `writing-guide.md`. Each accepted rule is a single line, placed in the
section it belongs to, carrying a marker:

```
- Say "median-fit," never "pinball."  <!-- learned: no-pinball | hits: 3 | added: 2026-08-17 | last: 2026-08-17 -->
```

One line each — a rule needing a paragraph has not been decided yet. An example
may go on an indented line beneath it, and the extractor will carry it along.
Set `added` and `last` to today; `hits` is the number of observations behind the
rule, incremented when later evidence lands on an existing rule.

The marker is what puts the rule in context at the start of a session, so a rule
written without one is a rule nobody will see.

## 6. Close out

```bash
python3 tools/style.py accept
python3 tools/style.py check
```

`accept` advances the watermark so the same observations are not re-proposed.
`check` counts the marked rules and their injected size against the cap, and
lists any that have gone stale.

If `check` reports over cap, fix it now rather than deferring: merge related
rules into one general statement, or retire the stale ones it names. The cap is
on the marked rules only — the guide itself is a manual and is meant to be long
— and it exists because those lines go into context every session. A rule list
too long to read is a rule list nobody follows, including you.

Then commit `writing-guide.md` with a one-line message naming what was learned,
and tell the author in two or three sentences what changed, what you dropped,
and any existing line you rewrote.
