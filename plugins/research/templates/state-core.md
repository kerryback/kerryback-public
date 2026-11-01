# State — @@PROJECT@@

The single source of truth for this project's direction — and it is a DIRECTORY,
not a file, so that several people can write to it at the same time:

    project/global/state/
      core.md      this file — thesis, settled facts, open questions, killed
                   ideas. Curated and short. Rewrite it freely; it is the one
                   shared file here, and it changes rarely enough that two
                   people editing it at once is a small, readable conflict.
      entries/     one file per dated entry. NEVER edit someone else's.
      blocks/      one file per topic block: a decision recorded, a status
                   frozen, a program written down. Append; do not rewrite.

Read the whole thing with

    python3 -m tools.state show

Add to it with

    python3 -m tools.state new "what changed"            # a dated entry
    python3 -m tools.state new --block "RULE E ADOPTED"  # a topic block

which creates a correctly named file with its front matter filled in. Two people
running that at the same moment create two different files, and git merges them
with no conflict. That is the whole point: there is no lock, and nobody waits for
anybody.

**An entry gets written even when nothing settled.** "We took up X and dropped
it, because Y" is the answer to *did we ever explore X*, and it is the only place
that answer exists — work that changed nothing leaves no diff, no artifact and no
trace. An attempt that failed is a result, and it is the easiest one to lose.

## Thesis

<One paragraph: the claim, and the test that would kill it. Empty until the first
round settles something.>

## Settled facts

<Things established and not to be relitigated, each with what settled it.>

## Open questions

<What is genuinely unresolved, most important first.>

## Killed ideas

<What was tried and abandoned, WITH the reason. This section earns its keep the
day someone proposes one of them again.>
