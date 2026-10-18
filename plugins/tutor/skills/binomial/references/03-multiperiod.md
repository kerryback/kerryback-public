# Module 3 — Two periods and n periods

Goal: the student should see that nothing new happens after Module 1. A
multi-period tree is a one-period tree glued to itself, and backward induction is
the glue.

## 1. Ask before you show

Extend the running example to two periods: from 110 the stock goes to 121 or 99;
from 90 it goes to 99 or 81. Same 2% per period, same strike of 100.

```
        t=0                t=1                t=2
---------------------------------------------------------
                                        121.00
                     110.00
  100.00                                 99.00
                      90.00
                                         81.00
```

Ask two questions before teaching anything, and wait for both:

1. Why is there one node at 99 instead of two? (Up-then-down and
   down-then-up land in the same place, because `u·d = d·u`. The tree
   recombines. This is worth flagging now because it is what makes large trees
   computable.)
2. We know how to price an option that expires next period. Here the option has
   two periods to go. Where could we stand in this tree such that the problem
   looks like the one we already solved?

Question 2 is the module. If the student says "at date 1," they have discovered
backward induction and the rest is arithmetic. If they don't, narrow it: "suppose
it's date 1 and the stock is at 110 — how many periods are left?"

## 2. Work backward

Terminal payoffs first — ask for them: 21, 0, 0.

Now the up node at date 1. The stock is at 110 and goes to 121 or 99. That is
exactly a one-period problem, and `q = 0.6` still, because q depends only on u,
d, and r:

```
C_u = (0.6 · 21 + 0.4 · 0)/1.02 = 12.35
```

Ask for the down node yourself before giving it (0, since the option is worthless
in both successor states). Then date 0, treating the date-1 values as the
payoffs:

```
C_0 = (0.6 · 12.35 + 0.4 · 0)/1.02 = 7.27
```

```
        t=0                t=1                t=2
---------------------------------------------------------
                                        121.00 /   21.00
                     110.00 /   12.35
  100.00 /    7.27                       99.00 /    0.00
                      90.00 /    0.00
                                         81.00 /    0.00
```

The step students skip past: at date 0 we discounted 12.35, which is not a cash
flow. Nobody receives 12.35. Ask why we may treat it as one. (Because it is the
market value of the option at that node — you could sell it for exactly that,
and a value you can convert to cash is as good as cash.)

## 3. The hedge is dynamic — this is the real content

Most students take backward induction on faith. Don't let them; the replication
argument still has to work, and seeing it work is what makes multi-period pricing
believable.

At date 0, `Δ = (12.35 − 0)/(110 − 90) = 0.6176` and `B = 7.27 − 0.6176·100 =
−54.50`.

Now the question to ask, and it is the good one:

> Hold that portfolio for one period. If the stock goes up to 110, what is it
> worth?

```
0.6176 · 110 − 54.50 · 1.02 = 67.94 − 55.59 = 12.35
```

Exactly `C_u`. And in the down state it is worth exactly 0. So the date-0
portfolio, left alone, always turns into precisely enough to fund the date-1
portfolio — no money added, none taken out. That property is called
self-financing, and it is what licenses the whole recursion: the option is
replicated not by one static portfolio but by a trading strategy that rebalances
at each node.

Have them compute the new delta at the up node: `(21 − 0)/(121 − 99) = 0.9545`.
The hedge got heavier as the option moved into the money. That is delta hedging,
and the student has now done it.

```
python scripts/binomial.py --S 100 --K 100 --r 0.02 --u 1.1 --d 0.9 --n 2 \
    --kind "European call"
```

The `delta` and `bond` columns let them check the self-financing property at
every node.

## 4. Fill in the node

Give them this and stop:

```
        t=0                t=1                t=2
---------------------------------------------------------
                                         57.60 /    0.00
                      48.00 /    0.53
   40.00 /       ?                       40.80 /    1.20
                      34.00 /       ?
                                         28.90 /   13.10

  European put, S = 40, K = 42, r = 4% per period, u = 1.20, d = 0.85
```

Answers: `q = (1.04 − 0.85)/(1.20 − 0.85) = 0.5429`; down node
`(0.5429·1.20 + 0.4571·13.10)/1.04 = 6.38`; price
`(0.5429·0.53 + 0.4571·6.38)/1.04 = 3.08`.

Generate more of these — see `references/exercises.md`, or:

```
python scripts/binomial.py --S 40 --K 42 --r 0.04 --u 1.2 --d 0.85 --n 2 \
    --kind "European put" --blank 1,1 --brief
```

A worthwhile follow-up on this particular tree: the exercise value at the date-1
down node is 42 − 34 = 8, which is more than the 6.38 we just computed. Ask what
that means. It means nothing yet for a European put — the holder cannot act on it
— and it is the entire subject of Module 4. This is a good place to end if the
student wants a break.

## 5. n periods

Two moves generalize the recursion; ask the student to supply both.

Number of nodes. At date t there are t+1 nodes, not 2^t, because the tree
recombines. Ask them to count paths versus nodes at date 3: eight paths, four
nodes. A 50-period tree has 2^50 paths — about a quadrillion — and 51 nodes.
That gap is why this model is practical.

The recursion. At every node with time left,

```
V = [ q·V_up + (1 − q)·V_down ] / (1 + r)
```

applied from the terminal date backward. No new idea; the same one-period
argument at every node, with a self-financing strategy that rebalances each
period.

For a European option only, the recursion collapses into a formula, because a
node at date n with k up moves is reached by C(n,k) paths each of q-probability
`q^k (1−q)^(n−k)`:

```
C_0 = (1 + r)^(−n) · Σ_k C(n,k) · q^k (1 − q)^(n−k) · max(S·u^k·d^(n−k) − K, 0)
```

Check it against the two-period answer: only k = 2 pays, so
`0.36 · 21/1.02² = 7.27`. Same number. Emphasize why this shortcut exists only
for European options: it assumes we never do anything before the terminal date.
Module 4 breaks that assumption, and the formula goes with it.

## 6. Calibration and where this is going

Only if the student asks or has seen Black-Scholes. The periods are not
economically meaningful — they are a discretization. With T years and n steps,
`Δt = T/n`, the standard (Cox-Ross-Rubinstein) choice is

```
u = e^(σ√Δt)        d = 1/u        1 + r = e^(rate·Δt)
```

so u and d are pinned to the stock's volatility, and d = 1/u is what makes the
tree recombine symmetrically. As n grows the tree's terminal distribution
converges to lognormal and the European price converges to Black-Scholes. The
binomial model is not an approximation to reality that Black-Scholes improves on;
they are the same model at different resolutions.

Nice demonstration if they want it: price the same option with n = 1, 5, 25, 100
and watch it settle down.

Next: `references/04-american.md`.
