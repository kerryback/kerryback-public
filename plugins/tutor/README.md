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

You can also just say what you want — "teach me the binomial model", "quiz me
on early exercise" — and Claude will pick the right tutor. Each one asks what you want to cover and
where you are starting from before it teaches anything.

Binomial runs 30 to 45 minutes end to end. It can be stopped between modules
and picked up later.

## What's inside

```
plugins/tutor/
├── .claude-plugin/plugin.json
└── skills/
    └── binomial/
        ├── SKILL.md                        tutoring protocol Claude follows
        ├── references/
        │   ├── 01-replication.md           one period: replication and no arbitrage
        │   ├── 02-risk-neutral.md          where q comes from and what it means
        │   ├── 03-multiperiod.md           two periods, dynamic hedging, n periods
        │   ├── 04-american.md              early exercise
        │   └── exercises.md                problem bank with answers
        └── scripts/
            └── binomial.py                 prices trees, generates exercises, plots
```

## The script on its own

The binomial script is usable without Claude.

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

## Adding a tutor

Add a folder under `skills/`. It needs a `SKILL.md` with `name` and
`description` in the frontmatter; references and scripts are optional. The
folder name becomes the command, so `skills/capm/` is `/tutor:capm`. Add a row
to the table above with your name in the contributed-by column, and bump the
version in `.claude-plugin/plugin.json`.

Nothing else changes — no new plugin, no marketplace entry, and everyone who
has already installed `tutor` gets your tutor on their next update.
