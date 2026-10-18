# Module 4 — American options and early exercise

Goal: the student should be able to price an American option in a tree, say at
which nodes exercise is optimal and why, and explain why an American call on a
non-dividend-paying stock is worth the same as a European one.

## 1. One change to the recursion

State the difference: an American option can be exercised at any date up to
expiration, not just at expiration. Then ask what that does to the backward
induction — the student can usually get there.

At every node the holder chooses between two things they actually have:

```
V = max( exercise value ,  [ q·V_up + (1 − q)·V_down ] / (1 + r) )
```

Exercise value is `S − K` for a call and `K − S` for a put. The second term is
what the option is worth if kept, computed exactly as before. Take the larger.
That is the whole modification, applied at every node, working backward.

Ask why the option is worth the max rather than something in between. (Because
the holder chooses, and chooses after seeing where the stock went. An option is
never worth less than what you can convert it into right now.)

Also worth flagging: the closed-form sum from Module 3 is now useless, since it
presumed we hold to expiration. American options have to be walked node by node.
This is why trees remain the standard tool for them.

## 2. Worked example — an American put

Same running tree: S = 100, u = 1.1, d = 0.9, r = 2%, two periods, K = 100, so
q = 0.6. Terminal payoffs: 0 at 121, 1 at 99, 19 at 81. Ask for those first.

Now walk backward, and at each node ask for both numbers before revealing
either.

Up node, stock at 110. Holding is worth `(0.6·0 + 0.4·1)/1.02 = 0.39`. Exercising
pays `100 − 110 = −10`, i.e. nothing, since you would not exercise. Value 0.39.

Down node, stock at 90. Holding is worth `(0.6·1 + 0.4·19)/1.02 = 8.04`.
Exercising pays `100 − 90 = 10`. Ten beats 8.04, so exercise. Value 10.

Date 0. Holding is worth `(0.6·0.39 + 0.4·10)/1.02 = 4.15`. Exercising pays 0.
Value 4.15.

```
        t=0                t=1                t=2
---------------------------------------------------------
                                        121.00 /    0.00
                     110.00 /    0.39
  100.00 /    4.15                       99.00 /    1.00
                      90.00 /   10.00*
                                         81.00 /   19.00

  * = exercise here
```

The comparison worth drawing out: the same put with European terms is worth
3.38. The right to exercise early is worth 0.77, and every cent of it comes from
that one node.

```
python scripts/binomial.py --S 100 --K 100 --r 0.02 --u 1.1 --d 0.9 --n 2 \
    --kind "American put"
python scripts/binomial.py --S 100 --K 100 --r 0.02 --u 1.1 --d 0.9 --n 2 \
    --kind "European put" --brief
```

The `hold` and `exercise` columns in the full output are precisely the two
numbers being compared at each node.

## 3. Why would anyone exercise early?

Ask before explaining. The student has just computed a node where exercising
beats holding — ask them what they got by exercising and what they gave up.

Got: the strike, 100, in hand a period early, where it earns interest.
Gave up: the chance that the stock falls further, and the protection of not
having to sell if it rises. Exercise is irreversible; holding keeps the choice.

So early exercise of a put is a trade of optionality for interest, and it wins
when there is little optionality left to give up — deep in the money, where the
put is nearly certain to finish in the money and behaves like a short stock
position plus a receivable. Higher interest rates make early exercise more
attractive; more volatility makes it less attractive, because the abandoned
optionality is worth more.

Good check, and a trap worth letting them fall into: ask what happens at that
node if r drops to 0. Most students recompute the continuation value and forget
that q changes too. It becomes `q = (1 − 0.9)/0.2 = 0.5`, so holding is worth
`0.5·1 + 0.5·19 = 10` — exactly what exercising pays. The advantage disappears.

That is not a coincidence. With no interest and no dividends the American put is
worth exactly the European put, because interest on the strike was the only thing
early exercise ever bought. Confirm it in front of them:

```
python scripts/binomial.py --S 100 --K 100 --r 0.0 --u 1.1 --d 0.9 --n 2 \
    --kind "American put" --brief
```

Both styles come to 5.25. Then put r back and watch the premium reappear.

## 4. The American call result

Set this up as a puzzle rather than a theorem. Run:

```
python scripts/binomial.py --S 50 --K 50 --r 0.01 --u 1.1 --n 3 \
    --kind "American call" --brief
python scripts/binomial.py --S 50 --K 50 --r 0.01 --u 1.1 --n 3 \
    --kind "European call" --brief
```

Both give 4.29, and no node is ever marked for exercise. Ask why the extra right
turned out to be worthless.

The reasoning, which they should assemble rather than receive: exercising a call
early means paying K sooner than necessary, forfeiting the interest on it, and
throwing away the protection against the stock falling below K. Both effects
point the same way, so holding always weakly dominates. If you want out of the
position, sell the call — the market price is at least the exercise value, and
generally more.

Note the asymmetry with the put explicitly, since students expect symmetry: for
a call, the interest on K argues against early exercise; for a put, it argues
for. That single sign difference is the whole story.

Then the caveat: this holds for a non-dividend-paying stock. A large dividend can
make early exercise of a call optimal just before the ex-dividend date, because
the stock price drops and the call holder does not receive the dividend. Mention
it; do not develop it unless asked.

## 5. Fill in the node

Give them this and stop. Three values are missing and one of them is an early
exercise node — do not hint at which.

```
        t=0                t=1                t=2                t=3
----------------------------------------------------------------------------
                                                            91.25 /    0.00
                                         79.35 /    0.00
                      69.00 /    0.89                       71.41 /    0.00
   60.00 /       ?                       62.10 /    1.92
                      54.00 /       ?                       55.89 /    4.11
                                         48.60 /       ?
                                                            43.74 /   16.26

  American put, S = 60, K = 60, r = 3% per period, u = 1.15, d = 0.90
```

Answers: `q = 0.52`. Node at 48.60: holding is
`(0.52·4.11 + 0.48·16.26)/1.03 = 9.65`, exercising pays `60 − 48.60 = 11.40`, so
exercise, value 11.40. Node at 54.00: holding is
`(0.52·1.92 + 0.48·11.40)/1.03 = 6.28`, exercising pays 6.00, so hold, value
6.28. Date 0: `(0.52·0.89 + 0.48·6.28)/1.03 = 3.38`, exercise pays 0, hold.

The node at 54 is the instructive one and worth returning to: exercising pays
6.00 and holding is worth 6.28, so it is close, and a student who exercised there
made a defensible mistake. Ask what the 0.28 is buying.

Verify with:

```
python scripts/binomial.py --S 60 --K 60 --r 0.03 --u 1.15 --d 0.9 --n 3 \
    --kind "American put"
```

## Where students get stuck

Comparing exercise value against the wrong thing. The comparison is exercise
value now versus discounted continuation value, both measured at that node. A
student comparing the exercise value at date 1 against the option's date-0 price,
or against the terminal payoff, will get nonsense.

Forgetting to propagate the exercise decision. Once a node is set to its exercise
value, that number — not the continuation value — is what gets discounted into
the previous node. Missing this is the most common arithmetic error in American
trees, and it always makes the option look too cheap.

Assuming exercise is optimal whenever the option is in the money. It is in the
money at 54.00 and holding still wins. Being in the money is necessary, not
sufficient.

Expecting a formula. There isn't one. If they push, that is the honest answer:
the exercise boundary is what makes American options a numerical problem.
