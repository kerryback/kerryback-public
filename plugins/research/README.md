# research

Sets up a research repository that several people — and their Claudes — can work
in without tripping over each other, then writes the `CLAUDE.md` that keeps it
that way.

```
/plugin marketplace add kerryback/kerryback-public
/plugin install research@kerryback-public
```

Then, in the repository:

```
/research
```

Claude interviews you, scaffolds the structure, wires the tooling, verifies it
works, and explains it in two minutes.

## What it prevents

Research repos fail in the same few ways, and each one is cheap to prevent and
expensive to fix later:

- **Paths that name one person's home directory**, so nobody else can run the
  code. Four roots, all derived — from an env var, from the script's own
  location, from walking up to `CLAUDE.md` — and no absolute path anywhere.
- **The shared dataset living in whoever built it's folder.** One canonical
  store, read-only, with promotion recorded: hash, shape, who, and why it is
  trusted.
- **Two people rewriting the same prose file.** The round is claimed through git,
  which makes a push an atomic mutex, so exactly one claim wins and the loser
  finds out immediately rather than at merge time.
- **Nobody knowing which script produced a number.** The dependency graph is read
  out of the code — who wrote each file, what it read, what breaks if it changes
  — and runs are recorded as they happen.
- **A structure only its author understands.** The generated `CLAUDE.md` states
  the rules, and a session-start check tells Claude whether the person in front
  of it is set up, so onboarding is something Claude performs rather than a
  README nobody reads.
- **Prose drifting into machine default.** `writing-guide.md` is vendored into
  the repo and binding for everything in `draft/` — economics section formulas
  and style rules on one side, the tells and rhythms that make AI prose
  recognizable on the other. It is read before writing, not after, and it works
  for a coauthor who has installed nothing.
- **Giving the same note for the third time.** The guide learns. When you tell
  Claude to change how a passage reads — or rewrite its prose yourself — a hook
  keeps the passage and what you asked for, and `/style-learn` turns that
  backlog into rules you accept one at a time. They are written into the guide
  itself, in the section each one bears on, so there is still exactly one
  standard and no second file to disagree with it. The guide is a manual and too
  long to put in context, so the rules your project added are marked, extracted,
  and put in context at the start of every session — capped, because a list too
  long to read is a list nobody follows. Captures stay local to whoever produced
  them; only an accepted rule is committed, so coauthors with different taste
  still share one standard.

## What you choose

- **Empirical or not.** If empirical, it scaffolds an analyst/replicator split
  and the two-build protocol: independent builds, reconcile, confirm before
  analysis, collapse to one, never average a disagreement. A theory project skips
  all of it rather than getting two empty directories.
- **A debate panel or not.** Independent model voices that propose and attack
  ideas through OpenRouter. Each coauthor needs their own key and pays for their
  own calls, so it is off unless you ask.
- **Overleaf or not.** For teams where some coauthors write in Overleaf and some
  do not. It mirrors `draft/` — and only `draft/` — into an Overleaf project
  through the git bridge, so the Overleaf people get a normal Overleaf project,
  everyone else keeps a normal git repo, and one person holds both. Claude does
  the syncing, so nobody has to learn `git subtree` to write a paper.

## What gets written down

Two committed records, small enough to live in git forever.

- **The state** in `project/global/state/`, one file per entry. One at the end of every
  round — what it took up, and what came of it — plus any substantive change as
  it happens. Newest first, append only. Killed ideas go in with the reason.
  The round entry is written even when the round settled nothing, which is what
  makes *did we ever explore X* answerable: a round that chased something and
  dropped it leaves no diff and no artifact, only its entry.
- **The runs** — `project/<author>/logs/runs.jsonl`. One line per script
  execution: arguments, commit, duration, status, and the files it actually
  opened and wrote, caught by an audit hook below pandas and pyarrow so paths
  built at runtime are recorded too.

There is deliberately **no session-wide activity log**. Capturing every prompt
and every tool call reaches tens of megabytes a project, will not go in git, and
answers none of the questions coauthors ask. "What did they do last week", "why
did we change that", "did we ever explore X" are questions about *decisions*; a
tool-call log records *actions* and never says why. It can tell you a file was
edited at 2:14pm. It cannot tell you the exhibit was dropped because a coauthor
did not like where it sat — the changelog can, because someone wrote it there
when they decided it.

So the decision gets written at the moment it is made, and the generated
`CLAUDE.md` tells Claude to do that rather than to trust that a log will
reconstruct it later. Underneath all three, `git log --since` answers "last
week" directly.

Everything else in `logs/` stays local: the briefs sent to each debate seat and
`logs/debate-<run>.jsonl`, the full model responses. Both are the input to a
decision rather than the decision, and the changelog carries what a coauthor
needs. Raw material nobody curated reads as a record and is not one.

## Reading it back

`/report` writes an HTML report to the repo root — executive summary, what is
settled and should not be reopened, open issues tagged by whose they are, and a
chronology. It reads the three records above plus each `session.md` and git; it
never touches a log.

Underneath it, `tools/chronology.py` merges the changelog, `git log`, and the
run records into one timeline, newest first, decisions before the artifacts
around them:

```bash
python3 -m tools.chronology --human
python3 -m tools.chronology --author jane-doe --since "last week" --human
python3 -m tools.chronology --kinds changelog --human        # decisions only
```

That is also the direct answer to the questions people actually ask. *What did
my coauthors do last week* is `--author <slug> --since "last week"`. *Why did we
change that* is `--kinds changelog`, since every entry carries its reason.
*Did we ever explore X* is the round entries, since every round names what it
took up whether or not it changed anything.

No accumulation step runs first, and none is needed: the changelog is the
incremental artifact, and `/handover` is what keeps it current. If the record
is stale the report says so rather than papering over it.

## Existing projects

It adapts one too, in an order chosen so a mistake surfaces before more moves are
stacked on it: paths first, verified by re-running something whose answer is
already known; then data out of the repo; then the per-author split; then
archiving what is superseded. Commit between steps.
