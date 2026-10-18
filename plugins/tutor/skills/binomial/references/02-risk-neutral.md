# Module 2 — Risk-neutral probabilities

Goal: the student should be able to derive `q`, use it, and say precisely what it
is and is not. Nothing new is being priced here — this is a rewriting of Module
1's answer that happens to scale to large trees.

Do not start this module until the student has priced something by replication.
Risk-neutral valuation taught first is a magic trick; taught second it is a
simplification.

## 1. Motivate the rewrite

Ask: we got 5.88 by solving two equations for Δ and B and then adding up the
cost. Is there a shortcut that skips the portfolio?

Then do the algebra with them. Write `R = 1 + r`. From Module 1,

```
Δ = (C_u − C_d)/(S_u − S_d)
B = (C_d − Δ·S_d)/R
C = Δ·S + B
```

Substitute and collect terms. The student can do this; it is one page of
algebra and it is more convincing than being shown the result:

```
C = [ q·C_u + (1 − q)·C_d ] / R        where     q = (R − d)/(u − d)
```

Check it on the running example: `q = (1.02 − 0.9)/(1.1 − 0.9) = 0.6`, and
`(0.6·10 + 0.4·0)/1.02 = 5.88`. Same number as the portfolio cost, necessarily —
it is the same calculation rearranged.

## 2. What q actually is

The best characterization, and the one to make the student derive: ask what
probability would make the stock's expected return equal the risk-free rate.

```
q·u + (1 − q)·d = R      →      q = (R − d)/(u − d)
```

Same q. So q is the probability under which the stock earns the risk-free rate —
the probability a risk-neutral investor would have to hold to be content owning
this stock. Hence the name.

Three things worth stating plainly, because students carry the opposite belief
out of this material:

1. q is not a forecast. It is not anyone's estimate of anything.
2. Nobody is assumed to be risk neutral. Real investors are risk averse, the
   stock really does earn a risk premium, and none of that changes q.
3. The true probability never appears in the formula. If it did, two investors
   with different beliefs would get different prices, and one of them could be
   arbitraged.

The reason we can get away with it is Module 1: the hedge worked in both states,
so no probability was needed, and q is just the weight that makes a
no-arbitrage answer look like an expected value. The form is an expectation; the
content is replication.

Useful challenge if the student is skeptical: ask them what the stock's expected
return would have to be for the call to be worth something other than 5.88.
There is no such number.

## 3. Why 0 < q < 1 is the no-arbitrage condition

Worth ninety seconds. `q = (R − d)/(u − d)` lies strictly between 0 and 1 exactly
when `d < R < u`. If `R ≤ d` the stock beats the bond in every state and you
should borrow and buy without limit. If `R ≥ u` the reverse. So the requirement
that q be a probability at all is the same as the requirement that no free money
exists.

The script enforces this. Have the student try to break it:

```
python scripts/binomial.py --S 100 --K 100 --r 0.15 --u 1.1 --d 0.9 --n 1
```

It refuses and says why.

## 4. Fill in the node

This is the exercise format to use from here on. Present a tree with the stock
prices given and the option values filled in everywhere except one node, and ask
for two numbers: the missing value, and the price today.

One-period version — give them this and stop:

```
        t=0                t=1
--------------------------------------
                     125.00 /   25.00
  100.00 /       ?
                      80.00 /    0.00

  S = 100, K = 100, r = 5% per period, u = 1.25, d = 0.80
```

Answer: `q = (1.05 − 0.80)/(1.25 − 0.80) = 0.5556`, price
`0.5556 · 25 / 1.05 = 13.23`. Verify with

```
python scripts/binomial.py --S 100 --K 100 --r 0.05 --u 1.25 --d 0.8 --n 1 \
    --kind "European call"
```

Follow-up worth asking: what is the replicating portfolio here, and does it cost
13.23? (Δ = 25/45 = 0.5556, B = −42.33.) Making the student cross-check the two
methods against each other is how the equivalence stops being a claim.

## 5. A backwards one

Running the formula in reverse tests whether they understand it or have
memorized it:

> A stock is at 100. It goes up 10% or down to some price you don't know. The
> risk-free rate is 2%. Somebody tells you the risk-neutral probability of an up
> move is 0.6. What is the down price?

Answer: `0.6(1.1 − d) = 1.02 − d` gives `d = 0.9`, so 90.

Another good one: hold u and d fixed and raise r. Which way does q move, and
which way does a call price move? (Both up. Ask them to explain the second one
in terms of the replicating portfolio. In a one-period tree delta does not
depend on r, so the share position is the same. The borrowing is the difference: the hedge repays a fixed
amount at date 1, 0.5·90 = 45 in the running example, and a higher r means that
repayment supports less borrowing today. Less borrowed means more of your own
money in the portfolio, so the call costs more. That is the honest explanation;
"higher discount rate" is not.)

## 6. Check understanding

Offer these, one at a time:

(a) Same tree as the running example, price the put with q. Answer:
`(0.4 · 10)/1.02 = 3.92`, matching the portfolio calculation from Module 1.

(b) Suppose the true probability of an up move is 0.8, so the stock's expected
price is 106. Does the call price change? Answer: no. If they hesitate, ask them
which line of the replication argument used 0.8.

(c) The stock's expected return under q. Answer: `0.6·1.1 + 0.4·0.9 = 1.02`, the
risk-free rate, by construction.

Next: `references/03-multiperiod.md`.
