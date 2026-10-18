# Problem bank

Every answer here was produced by `scripts/binomial.py`. Still run the script
before you grade — it costs nothing and it protects the student from a confident
wrong correction.

Give one problem at a time and stop. Do not paste a list.

## Making new problems

The bank runs out; the script does not.

```
# the exercise, with one node and its ancestors blanked
python scripts/binomial.py --S 90 --K 95 --r 0.02 --u 1.15 --d 0.9 \
    --n 2 --kind "European call" --blank 1,1 --brief

# the answer key, for you
python scripts/binomial.py --S 90 --K 95 --r 0.02 --u 1.15 --d 0.9 \
    --n 2 --kind "European call"
```

Guidelines that make a problem teach something:

- Change the tree, not just the strike. A student who sees u = 1.1 and d = 0.9
  four times starts pattern-matching on 0.6 instead of computing q.
- Pick u, d, r so that q is not 0.5. A q of 0.5 lets a student who is using the
  real probability get the right answer for the wrong reason.
- Avoid d = 1 − (u − 1). Students assume symmetry; break it sometimes.
- For American problems, put the interesting node where exercise is close either
  way. A node where exercising is obviously right teaches less than one where it
  wins by 0.3.
- Blank a middle-date node rather than a terminal one. Terminal values are just
  payoffs; the interesting work is the recursion.

## Module 1 — replication

1.1 S = 80, one period to 100 or 64, r = 3%, call struck at 80. Find Δ, B, and
the price.
Answer: Δ = 20/36 = 0.5556, B = −34.52, price 9.92.

1.2 Same tree as 1.1, but price the put struck at 80.
Answer: Δ = −0.4444, B = 43.15, price 7.59. Ask why delta is negative.

1.3 S = 50, one period to 65 or 37.50, r = 2%, put struck at 55.
Answer: Δ = −0.6364, B = 40.55, price 8.73.

1.4 S = 100, one period to 120 or 90, r = 1%, call struck at 95.
Answer: Δ = 0.8333, B = −74.26, price 9.08. Worth noting the high delta: the
option is in the money, so it tracks the stock closely.

1.5 Conceptual. In 1.4, suppose you believe the stock will rise with probability
0.9 and your classmate believes 0.3. Which of you is willing to pay more for the
call?
Answer: neither — you both pay 9.08 or you get arbitraged. If the student
answers "me," go back to the replicating portfolio, not to the formula.

## Module 2 — risk-neutral probabilities

2.1 S = 100, one period to 125 or 80, r = 5%, call struck at 100. Find q, then
the price, then check with the replicating portfolio.
Answer: q = 0.5556, price 13.23, Δ = 0.5556, B = −42.33. The coincidence that
q and Δ are both 0.5556 is an artifact of this tree — say so before the student
builds a theory on it.

2.2 S = 200, one period to 220 or 190, r = 4%, put struck at 210.
Answer: q = 0.6, price 7.69.

2.3 Reverse. u = 1.20, r = 3%, and q = 0.40. Find d.
Answer: 0.4(1.20 − d) = 1.03 − d gives d = 0.9167.

2.4 Conceptual. A stock is at 100 and will be at 110 or 90. The risk-free rate
is 12% per period. What is a call struck at 100 worth?
Answer: the question is broken — 1.12 exceeds u = 1.10, so the bond dominates the
stock and there is an arbitrage. Let them try it in the script and read the
refusal. Then ask what the arbitrage trade actually is: short the stock, lend the
proceeds, and you owe at most 110 on a position that grew to 112.

2.5 Conceptual. Two stocks have identical trees, but one has an expected return
of 8% and the other 25%. Their calls, same strike, same expiration — same price
or different?
Answer: same. This is 1.5 in different clothing; use it if 1.5 did not land.

## Module 3 — multi-period

3.1 S = 100, u = 1.20, d = 0.85, r = 2%, two periods, European call struck at
105.
Answer: q = 0.4857. Terminal 39, 0, 0. Up node 18.57, down node 0, price 8.84.

3.2 In 3.1, find the replicating portfolio at date 0 and verify it is
self-financing into the date-1 up node.
Answer: Δ = 0.5306, B = −44.22. Up state: 0.5306·120 − 44.22·1.02 = 18.57, the
up-node value exactly.

3.3 S = 40, u = 1.20, d = 0.85, r = 4%, two periods, European put struck at 42.
Blank the date-1 down node.
Answer: q = 0.5429, down node 6.38, price 3.08.

3.4 S = 25, u = 1.10, d = 1/1.10, r = 1%, three periods, European call struck at
25.
Answer: q = 0.5286, price 2.14. Date-1 nodes 3.49 and 0.68; date-2 nodes 5.50,
1.31, 0.

3.5 Conceptual. How many nodes are in a 30-period tree at the final date, and
how many paths lead to it?
Answer: 31 nodes, about a billion paths. Then ask which number determines how
long the computation takes.

3.6 Conceptual. In 3.1, the option is worth 0 at the date-1 down node even though
the stock could still recover to 102. Why is 102 not enough?
Answer: the strike is 105. Both successors of the down node finish out of the
money, so the option is dead there. Useful for students who think a positive
stock price implies a positive option value.

## Module 4 — American

4.1 S = 100, u = 1.15, d = 0.85, r = 5%, two periods, American put struck at 110.
Answer: q = 0.6667. Date-1 down node: hold 19.76, exercise 25, so exercise.
Price 10.41. The European put on the same tree is 8.74, so early exercise is
worth 1.66.

4.2 One period. S = 200, up to 220 or down to 190, r = 4%, American put struck at
210. This one catches almost everybody.
Answer: holding is worth 7.69, but exercising immediately pays 210 − 200 = 10.
The put is worth 10 and should be exercised at once, before the tree does
anything. Students look only at future nodes and forget that date 0 is a node
too.

4.3 S = 60, u = 1.15, d = 0.90, r = 3%, three periods, American put struck at 60.
Blank the date-2 bottom node.
Answer: q = 0.52. That node: hold 9.65, exercise 11.40, so exercise. Date-1 down
node: hold 6.28, exercise 6.00, so hold. Price 3.38. The date-1 node is the one
to discuss — in the money and still not worth exercising.

4.4 Take 4.1 and set r = 0, leaving everything else alone. What happens to the
early exercise decision?
Answer: q becomes 0.5, and holding is worth exactly as much as exercising at the
down node. The American and European puts are then worth the same. Interest on
the strike was the only thing early exercise was ever buying.

4.5 S = 50, u = 1.10, d = 1/1.10, r = 1%, three periods, American call struck at
50. Compare with the European call.
Answer: both 4.29, and no node is ever exercised early. Have them explain it
before you do.

4.6 Conceptual. Your classmate says an American option must be worth strictly
more than the European one, since it can do everything the European one can do
and more. Where does the argument go wrong?
Answer: "weakly more," not "strictly." The extra rights are worth something only
if there is a node where using them beats holding. For a call on a
non-dividend-paying stock there never is.

## Mixed and diagnostic

M.1 Price a call and a put on the same two-period tree and check put-call parity:
`C − P = S − K/(1+r)^n`. Any tree works; use 3.1 (C = 8.84, P = 9.77, and
S − K/1.02² = 100 − 100.92 = −0.92, matching 8.84 − 9.77). Ask whether parity
should also hold for American options.
Answer: no, it holds with an inequality instead, precisely because early exercise
breaks the static arbitrage that proves parity.

M.2 Give a student a completed tree with one value deliberately wrong and ask
them to find the error. Generate a correct tree with the script, then change one
number by 15%. This tests the recursion harder than filling in a blank does,
because they have to check every node rather than compute one.

M.3 Ask the student to price the same European option with n = 1, 2, 5, 20, 100
periods, holding u = e^(σ√Δt), d = 1/u, and the per-period rate fixed as
`e^(rate·Δt) − 1`. Ask what the sequence of prices is doing.
Answer: converging, to the Black-Scholes price. Good closing exercise for a
student who has seen Black-Scholes and thinks it is a separate model.
