# tutor

The tutoring skills themselves. Each subdirectory of `skills/` is one tutor: a
protocol Claude follows, the reference material it teaches from, and usually a
script that generates problems and verifies answers.

Every tutor works the same way. The student produces the answers and Claude
diagnoses the wrong ones, rather than presenting worked solutions.

## Installing it

```
claude plugin marketplace add kerryback/kerryback-public
claude plugin install tutor@kerryback-public
```

Inside a running session, `/plugin marketplace add kerryback/kerryback-public` and
`/plugin install tutor@kerryback-public`.

One install brings every tutor in the collection, and new ones arrive when you
update.

## The tutors

| Command | Subject | Contributed by |
|---|---|---|
| `/tutor:binomial` | Binomial option pricing: replicating portfolios and no arbitrage, risk-neutral probabilities, multi-period backward induction, American options and early exercise | Kerry Back |
| `/tutor:agency` | Agency and authority in business law: actual authority, apparent authority, ratification and estoppel, and who is liable on the contract | Kerry Back |

You can also just say what you want — "teach me the binomial model", "when is a
company bound by what its manager signed", "quiz me on early exercise" — and
Claude will pick the right tutor. Each one asks what you want to cover and
where you are starting from before it teaches anything.

Binomial runs 30 to 45 minutes end to end, agency 40 to 50. Both can be stopped
between modules and picked up later.

## What's inside

```
plugins/tutor/
├── .claude-plugin/plugin.json
└── skills/
    ├── binomial/
    │   ├── SKILL.md                        tutoring protocol Claude follows
    │   ├── references/
    │   │   ├── 01-replication.md           one period: replication and no arbitrage
    │   │   ├── 02-risk-neutral.md          where q comes from and what it means
    │   │   ├── 03-multiperiod.md           two periods, dynamic hedging, n periods
    │   │   ├── 04-american.md              early exercise
    │   │   └── exercises.md                problem bank with answers
    │   └── scripts/
    │       └── binomial.py                 prices trees, generates exercises, plots
    └── agency/
        ├── SKILL.md                        tutoring protocol Claude follows
        ├── references/
        │   ├── 01-actual-authority.md      express and implied, the agent's lens
        │   ├── 02-apparent-authority.md    the third party's lens, and traceability
        │   ├── 03-ratification-estoppel.md what saves a deal with no authority
        │   ├── 04-liability.md             disclosed, unidentified, undisclosed
        │   ├── exercises.md                problem bank with verified answers
        │   └── authorities.md              what may be cited, and what may not
        └── scripts/
            └── agency.py                   generates fact patterns and answer keys
```

## The scripts on their own

Both are usable without Claude.

`skills/binomial/scripts/binomial.py` prices European and American calls and
puts on a recombining tree and prints the tree, the risk-neutral probability,
and the replicating portfolio at every node.

```
python skills/binomial/scripts/binomial.py --S 100 --K 100 --r 0.02 \
    --u 1.1 --d 0.9 --n 2 --kind "American put"
```

`u` and `d` are gross returns (1.1 means +10%), `r` is per period, and `--d`
defaults to `1/u`. Add `--plot trees.html` for interactive figures of the stock
and option trees, or `--blank 1,0` to hide a node and its ancestors so the tree
becomes a problem to solve. Requires numpy, and plotly only if you use
`--plot`.

The pricing functions and the tree figure come from the binomial trees notebook
at [learn-investments.rice-business.org](https://learn-investments.rice-business.org)
by Kerry Back and Kevin Crotty, extended here to allow a down factor other than
`1/u` and to report the replicating portfolio and early-exercise nodes.

`skills/agency/scripts/agency.py` builds a fact pattern from a set of
parameters and derives the answer from those same parameters, so the key is
right by construction rather than by reasoning about the story.

```
python skills/agency/scripts/agency.py --list
python skills/agency/scripts/agency.py --scenario 2
python skills/agency/scripts/agency.py --scenario 2 --key
```

Without `--key` it prints the fact pattern alone, which is what you hand a
student. With `--key` it adds the analysis rung by rung — actual authority,
apparent authority, estoppel, ratification, the undisclosed principal, the
bottom line, and the agent's own exposure — each with the Restatement section.

Build a targeted problem with `--build` and change one variable at a time:

```
python skills/agency/scripts/agency.py --build --context 3 \
    --grant capped --act 2 --position general_manager --belief position --key
```

The settings that carry the doctrine are `--grant` (what the principal told the
agent), `--belief` (where the third party's belief came from), `--act` (how big
the transaction is), `--position`, `--terminated`, `--after`, and `--status`.
Running a pair that differs in exactly one setting is the most useful thing the
script does. `--random --seed N` builds a fresh coherent problem.

Combinations that cannot describe a real situation are refused with an
explanation rather than answered.

## Adding a tutor

Add a folder under `skills/`. It needs a `SKILL.md` with `name` and
`description` in the frontmatter; references and scripts are optional. The
folder name becomes the command, so `skills/capm/` is `/tutor:capm`. Add a row
to the table above with your name in the contributed-by column, and bump the
version in `.claude-plugin/plugin.json`.

Nothing else changes — no new plugin, no marketplace entry, and everyone who
has already installed `tutor` gets your tutor on their next update.
