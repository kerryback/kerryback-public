# Module intros and learning objectives

The app plays each module's intro the same way every time, however the student
arrives: from the module menu, or when the tutor moves on to the next module.
The spoken part is read aloud. The board part goes on the intro page of the
whiteboard. The objectives are shown on that page and given to the tutor as the
targets for the module.

Write spoken text with numbers in words. The board keeps digits.

The Introduction plays once, at the start of a new student's first session in
the voice version, before the tutor's opening questions.

## Introduction

Spoken:
Welcome to the binomial tutor. I'll teach you how to price options with
binomial trees, in four modules. First, you'll price an option by copying it
with the stock and a bond. Second, you'll learn a shortcut called risk-neutral
probabilities. Third, you'll work with trees that have many periods and fit
them to a stock's volatility. And fourth, you'll price American options, which
can be exercised early. The whole course takes about forty to sixty minutes,
and you can stop between modules. To answer me, just talk. You can also press Type to type an answer,
press Pause to stop me, or use the menu to jump to any module.

Board:
- Module 1: One period: replication and no arbitrage
- Module 2: Risk-neutral probabilities
- Module 3: Many periods and calibration
- Module 4: American options and early exercise
- About 40 to 60 minutes in all; stop between modules whenever you like
- Talk to answer, or press Type; Pause stops the tutor; the menu jumps to a module

## Module 1 — One period: replication and no arbitrage

Spoken:
In this module you'll price your first option. We'll take a stock that can go
either up or down over one period, and we'll build a portfolio of the stock and
a bond that pays exactly what the option pays in both cases. Since the two pay
the same, they must cost the same, and that gives the option's price. This idea,
copying an option with assets you already know how to price, is the foundation
for everything else in the course.

Board:
- One period: the stock goes up or down
- Copy the option with the stock and a bond
- Same payoffs, so the same price

Objectives:
- Compute the option's payoff in the up state and in the down state.
- Find the replicating portfolio: the number of shares, delta, and the amount in the bond.
- Price the option as the cost of the replicating portfolio.
- Explain why any other price allows an arbitrage.

## Module 2 — Risk-neutral probabilities

Spoken:
In this module you'll learn a shortcut to the price you found by replication.
First you'll find the probability that makes the stock's expected value,
discounted at the risk-free rate, equal its price today. Then you'll use that
same probability to price the option, and you'll see that you always get the
Module 1 answer. The shortcut matters because it scales: on a big tree you
don't need to build a new portfolio at every node.

Board:
- Find the probability q that prices the stock
- Use q to price the option
- Same answer as replication, every time

Objectives:
- Find q from the stock's prices: the probability that makes the expected stock price, discounted at the risk-free rate, equal today's price.
- Price an option as its expected payoff under q, discounted at the risk-free rate.
- Show that this gives the same price as the replicating portfolio, and explain why.
- Say what q is not: not a forecast, and not an assumption that investors are risk neutral.

## Module 3 — Many periods and calibration

Spoken:
In this module you'll price options on trees with more than one period. The key
idea is that a big tree is just one-period trees joined together. You start at
the end, where you know the payoffs, and work backward one step at a time,
using exactly what you learned in the first two modules. You'll also see that
the replicating portfolio changes as the stock moves, which is how options are
hedged in practice. Finally, you'll learn where the up and down moves come
from: you'll fit the tree to the stock's volatility, and see that as the
periods get shorter, the stock's continuously compounded return becomes
normally distributed.

Board:
- A big tree is one-period trees joined together: work backward
- The hedge changes at every node
- Fit u and d to volatility; returns become normal

Objectives:
- Build a two-period stock tree and explain why an up then down move lands on the same price as a down then up move.
- Compute the option's payoffs at the last date.
- Work backward one node at a time to price the option today.
- Find the replicating portfolio at each node, and explain why it changes as the stock moves.
- Extend the method to a tree with many periods.
- Estimate annual volatility from daily returns: the standard deviation of daily log returns times the square root of 252.
- Calibrate a tree by the Cox-Ross-Rubinstein rule (Δt = T/n, u = e^(σ√Δt), d = 1/u, 1 + r = e^(rate·Δt)), find q, and price an option on it.
- Explain why, as the number of periods grows over a fixed time, the continuously compounded return converges to a normal distribution.

## Module 4 — American options and early exercise

Spoken:
In this module you'll price American options, which can be exercised at any
time, not just at the end. There is only one change to the method: at every
node, you compare the value of holding the option with the value of exercising
it now, and you take the larger. You'll find where it pays to exercise a put
early, and you'll see why an American call on a stock with no dividends is
never exercised early.

Board:
- American options can be exercised at any date
- At each node: the larger of holding and exercising
- When early exercise pays, and when it never does

Objectives:
- State the one change to backward induction for an American option.
- Price an American put on a tree, marking the nodes where early exercise is best.
- Explain why exercising a put early can be worth it.
- Explain why an American call on a stock with no dividends is worth the same as a European call.
