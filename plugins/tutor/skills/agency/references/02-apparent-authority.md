# Module 2 — Apparent authority

Goal: the student should be able to say why a company is bound by a contract it
forbade, and should be unable to answer "because the agent said so."

This is the module. If a student takes one thing from the whole session, it is
the traceability requirement.

## 1. Set up the collision

Run scenario 2 and paste the fact pattern:

```
python scripts/agency.py --scenario 2
```

Perez is general manager of the Westheimer store. The written instructions cap
Perez at $10,000 for supply contracts. The cap is internal — Dunn has never heard
of it. Perez signs a $40,000 contract with Dunn, who has dealt with Perez as general
manager before.

Module 1 already settled rung 1: no actual authority. Say so, then ask the
question and wait:

> So Perez did something expressly forbidden. Is Bowman stuck with
> the $40,000 contract?

Take their answer before you take their reasoning. Both answers are common and
the reasoning matters more than the vote.

## 2. Ask the better question

Whatever they said, redirect:

> Two people here did nothing wrong: Bowman and Dunn. Perez is the one who
> misbehaved, and Perez has no money. Somebody is going to eat $40,000. Which of
> the two innocent parties should it be, and why?

Let them argue. This is the most valuable ninety seconds in the module, because
students who have reasoned to the allocation themselves never afterward think
the subject is about what the agent was allowed to do.

The answer the law gives: Bowman. Bowman chose Perez, put Perez in the job, gave
Perez the title, and could have told Dunn about the cap with one sentence on an
order form. Dunn could have done nothing except decline to deal with a general
manager, which is not a workable rule for commerce. The loss goes to the party
who was in a position to prevent it cheaply.

Now give them the doctrine, and they will recognize it. Apparent authority is
the power to affect a principal's legal relations when a third party reasonably
believes the actor has authority, and that belief is traceable to the
principal's manifestations. Sec. 2.03.

## 3. Take the rule apart

Three elements. Make them name all three before you move on, and make them say
which one is doing the work in scenario 2.

Belief by the third party. Not the agent. The lens has flipped from module 1 —
say so explicitly and ask them to state module 1's rule and module 2's rule back
to back.

Reasonable. Beliefs held in the face of contrary knowledge are not protected.

Traceable to the principal. The one that carries everything. Ask:

> What did Bowman ever say to Dunn? Reread the facts.

Nothing. Bowman never spoke to Dunn about Perez's authority at all. So where is
the manifestation? Let them find it: Bowman put Perez in the position of general
manager and let Dunn deal with Perez in it. Placing someone in a position is
itself a manifestation to everyone who deals with the business that the person
may do what people in that position ordinarily do. Sec. 1.03 cmt. b, sec. 2.03
cmt. d.

That is why the cap fails. A secret limitation cannot make a third party's
belief unreasonable, because the third party never had it to reason from. It
binds Perez. It does not reach Dunn.

## 4. Kill the error

This is the error the module exists for, so provoke it deliberately rather than
waiting for it. Run scenario 4:

```
python scripts/agency.py --scenario 4
```

Iris Novak, a floor associate at the Alcott Gallery, with no instructions of any
kind about sales of this size, tells Marta Reyes "I have full authority to sign
this" and sells a $22,000 print with a written authenticity guarantee. Reyes has
never dealt with the gallery before and knows nothing else about Novak.

Ask whether the gallery is bound.

A meaningful share of students say yes. The answer is no, and the question that
fixes it is:

> Apparent authority needs a manifestation traceable to the principal. Trace
> that sentence. Who said it?

The agent said it. An agent cannot confer authority on themselves by claiming
it — if they could, the requirement would be empty, and every fraud would bind the
company it was committed against. Secs. 1.03, 2.03.

Then the move that makes it stick. Change one fact and ask again:

> Same facts, except that before Reyes ever walked in, the gallery's owner had
> told Reyes: "Novak handles the twentieth-century prints — deal with Novak."
> Now?

Now the gallery is bound. The sentence is nearly the same; the speaker is not.
Run the pair to show it:

```
python scripts/agency.py --scenario 4 --key
python scripts/agency.py --build --context 2 --grant none --act 2 \
    --position sales_rep --belief principal_said --key
```

## 5. Reasonable, and the ceiling on position

A title is not a blank check. Run scenario 5:

```
python scripts/agency.py --scenario 5
```

Harbor's practice administrator signs a $1.8 million ten-year MRI lease for all
six clinics. Vantage knows Iverson as practice administrator. Ask whether that is
enough.

It is not. The manifestation was the position, and the position reaches what a
practice administrator ordinarily does. A $1.8 million ten-year commitment
across the whole practice is not that, so Vantage's belief was not reasonable.
Sec. 2.03.

The generalization, which the student should state: apparent authority is
bounded by the manifestation. Position-based authority reaches ordinary acts for
that position and stops. A third party facing an extraordinary transaction is on
notice to ask.

Then the contrast that shows the ceiling is about the position, not the money.
Scenario 3: the same $40,000 contract that worked in scenario 2, except that the
cap was printed on Ridgeline's order forms.

```
python scripts/agency.py --scenario 3 --key
```

Not bound — and note for the student that nothing about the position or the act
changed. Only what the third party knew.

## 6. Lingering apparent authority

Return to the seed planted in module 1. Run 6 and 7 back to back; this pair is
the cleanest single-variable comparison in the whole set.

```
python scripts/agency.py --scenario 6      # discharged, nobody told Ridgeline
python scripts/agency.py --scenario 7      # discharged, written notice sent
```

In 6 Calder is bound. Shah was fired three weeks earlier, so actual authority is
gone, but Ridgeline had no notice and still had every reason to believe what
Calder's earlier manifestation conveyed. Apparent authority ends when it is no
longer reasonable for the third party to believe — not when the principal stops
wanting it. Sec. 3.11.

In 7 Calder is not bound. One letter, entirely different outcome.

The question to ask between them:

> Bowman fires an agent on Monday. What does Bowman do on Tuesday morning, and
> why is it cheap?

Tell everyone the agent used to deal with, and collect the cards, keys, and
letterhead. This is the moment the doctrine turns into advice, which is what a
business student came for.

## 7. Check understanding

Offer one:

(a) Exercise 2.3 in the bank.

(b) Conceptual: does apparent authority require that the third party know the
principal's identity?
Answer: the third party must believe the actor acts for a principal. If they
believe no principal exists, there is nothing to have a belief about, and the
doctrine is unavailable — which is module 4's problem, not a gap in this one.

(c) Conceptual: Bowman is bound to Dunn for $40,000. Is Perez in the clear?
Answer: no, and the reason is worth stating now because it repairs the sense of
unfairness students carry out of this module. Perez violated an instruction and
owes Bowman the resulting loss. Sec. 8.09. The doctrine did not decide that
Perez was right; it decided that Dunn should not have to litigate Bowman's
internal rules. Full treatment in module 4.

## Where students get stuck

Believing a secret limit should work because it is a real limit. It is a real
limit — on the agent. Ask them what Dunn was supposed to have done differently.

Treating "reasonable belief" as the whole test and skipping traceability. The
most dangerous error, because it produces the right answer on easy problems.
Diagnostic: ask them to point at the specific act of the principal. If they
cannot, they have been reasoning from the agent's conduct.

Thinking apparent authority is an exception or a fairness override. It is a
freestanding source of power, not a patch. Bowman is bound as fully as if it had
signed the contract itself.

Confusing this with respondeat superior. That doctrine puts torts on employers.
This is contract, and it turns on manifestations, not on employment.

Assuming apparent authority is broader than actual. Sometimes it is narrower.
An agent with sweeping written authority who was never held out to anybody has
wide actual authority and no apparent authority at all.

Next: `references/03-ratification-estoppel.md`.
