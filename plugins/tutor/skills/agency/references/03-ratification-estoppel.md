# Module 3 — Ratification and estoppel

Goal: the student should be able to handle the case where both rungs of the
ladder failed and the principal is bound anyway — and should be able to say what
each of these two doctrines needs that the other does not.

Open by naming the situation, because it is what unifies the module: no actual
authority, no apparent authority, and yet.

## 1. Ratification, from the fact pattern

Run scenario 8:

```
python scripts/agency.py --scenario 8
```

Novak, a floor associate with no instructions of any kind, tells Reyes "I have
full authority" and sells the $22,000 print with a guarantee. Module 2 already
disposed of that: the gallery is not bound. But a week later the gallery learns
the full terms, says nothing to Reyes, and accepts and uses two deliveries under
the deal.

Ask:

> Nothing has changed about what happened on March 14. Can something the gallery
> did in April change whether it is bound to a contract made in March?

Let them answer before you confirm. Yes — a principal can ratify, and
ratification relates back: the act is treated as authorized from the moment it
was done, not from the moment of affirmance. Secs. 4.01, 4.02.

Then the question that gets at why anyone would care about "relates back":

> Why does the timing matter, if the gallery ends up bound either way?

Because it is not a new contract. The terms are the ones Novak agreed to, and
everything that happened in between — the deliveries, the risk of loss, Novak's
own exposure — is reordered as if the authority had been there all along.

## 2. What counts as ratifying

Ask what the gallery actually did, in the language of the rule. It never said
"we ratify." It took deliveries. Sec. 4.01(2) reaches both a manifestation of
assent and conduct justifying a reasonable assumption of consent, and taking the
benefit of a deal you know about is the standard example.

Then push on silence:

> Would silence alone be enough? The gallery learns the terms, says nothing, and
> takes nothing.

Generally no. Silence is not assent unless the circumstances make speaking up
the natural thing — and the circumstances usually involve having taken something.
Worth flagging that this is fact-bound and that courts differ, which is a good
place to remind the student what the script does not model.

## 3. The knowledge element

Run scenario 9 against scenario 8. This is the pair to spend time on:

```
python scripts/agency.py --scenario 8 --key
python scripts/agency.py --scenario 9 --key
```

Scenario 9 is identical except that when the gallery accepted the two
deliveries, nobody there had seen the contract or knew what it committed them
to. Ask whether that is still ratification.

No. Ratification requires knowledge of the material facts. Sec. 4.06. You cannot
accidentally assent to terms you have never learned.

Two follow-ups worth asking:

> The gallery has had the use of two deliveries. Do they just keep those?

No — restitution is a separate track from ratification. Failing to ratify is not
a license to keep the benefit.

> The gallery reads the contract in May and then affirms. Ratified?

Yes, at that point, and it still relates back to March. The knowledge has to
precede the affirmance, not the receipt.

## 4. Timing, and the third party's escape

Run scenario 10:

```
python scripts/agency.py --scenario 10
```

Harbor's billing clerk signs the $60,000 ultrasound lease with Vantage on the
clerk's own say-so. Vantage writes to Harbor withdrawing from the deal. Only
after that does Harbor write back affirming it.

Ask who wins, and make them explain the sequence rather than just name a rule.

Vantage. Ratification is not effective after the third party has withdrawn.
Sec. 4.05. The reason is the one students find satisfying once they see it:

> While Harbor sits on an unauthorized contract deciding whether to affirm, what
> does Harbor have?

A free option. Harbor can watch the market and ratify only if the deal turns out
well, at Vantage's expense. Withdrawal is what closes the option. The same logic
runs through the rest of sec. 4.05 — ratification also fails if circumstances
have changed enough to make it inequitable.

## 5. No partial ratification

Ask, without a script run:

> Harbor affirms the price in the ultrasound lease but says the five-year
> service commitment was never authorized and it will not honor that part. Can
> it?

No. Ratification is all or nothing. Sec. 4.07. A principal who wants only part
of the deal has to negotiate for it like anyone else, because what is on offer
is the transaction the agent made, not a menu.

This one is a reliable catch — students reason term by term because that is how
they read contracts.

## 6. Estoppel

Run scenario 11:

```
python scripts/agency.py --scenario 11
```

A Bowman bookkeeper is holding themselves out to customers as able to sign
supply contracts. Bowman knows it is happening and does nothing. Dunn, relying
on the arrangement, turns down other business and buys inventory to fill the
order.

Ask first whether apparent authority works here. It does not: the manifestation
was the agent's, and a bookkeeper's position does not reach supply contracts. So
rung 2 fails on both counts.

Then ask:

> Bowman watched this happen and said nothing. Does that matter?

It does. A principal who has notice that third parties are being misled, and
that they may change position as a result, and who takes no reasonable steps to
say otherwise, is estopped to deny the authority. Sec. 2.05.

Now make them distinguish it from apparent authority, which is the point of
teaching it:

| | Apparent authority | Estoppel |
|---|---|---|
| Needs a manifestation by the principal | Yes | No — carelessness or silence with notice will do |
| Needs detrimental reliance | No | Yes |
| Runs both ways | Yes — the principal can enforce the contract too | No — it is a shield for the third party, not a sword for the principal |

The last row is the one to dwell on. Ask:

> The market moves and the deal is now great for Bowman. Bowman sues Dunn to
> enforce it. Under estoppel, can it?

No. Estoppel prevents Bowman from denying the authority; it does not manufacture
a contract Bowman can sue on. That asymmetry is why the doctrines are separate
and why it is worth knowing which one you are standing on.

## 7. Check understanding

Offer one:

(a) Exercise 3.4 in the bank.

(b) Conceptual: a promoter signs a lease "on behalf of" a corporation that has
not been formed yet. The corporation forms two months later and moves in. Is
that ratification?
Answer: no, at least not classically — there was no principal in existence to
have authorized the act when it was done, so the corporation is generally said
to adopt rather than ratify, and adoption does not relate back. Sec. 4.04. Good
for a business-law student because promoter liability is next door.

(c) Diagnostic: give them scenario 8 and ask them to identify, in order, which
rung of the ladder each fact bears on. Tests the structure rather than the
rules, and reveals students who are pattern-matching on keywords.

## Where students get stuck

Treating any acceptance of a benefit as ratification. The most common error in
the module. Diagnostic question: "What did they know when they accepted?"

Reading ratification as forgiveness of the agent. It is not. The principal who
ratifies is bound to the third party and may still have a claim against the
agent for exceeding authority, though ratification will often make the loss zero.

Missing that ratification needs the agent to have purported to act for the
principal. Sec. 4.03. Someone acting purely on their own account leaves nothing
to ratify — which is exactly the trap in module 4.

Using estoppel as a catch-all when they cannot find apparent authority. Make
them name the detrimental change in position. No reliance, no estoppel.

Next: `references/04-liability.md`.
