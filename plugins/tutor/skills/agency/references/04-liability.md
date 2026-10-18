# Module 4 — Who is liable: disclosed, unidentified, undisclosed

Goal: the student should stop asking only "is the principal bound?" and start
asking "who is on this contract, and who can sue whom?" — which is the question
a client actually has.

By now the student has run three modules in which the answer was a yes or a no
about the principal. Say out loud that the frame is about to widen.

## 1. Three ways to be a principal

Ask before defining:

> When Perez signs the Dunn contract, whose name goes on it, and does Dunn know
> who is really behind the deal? Give me three different ways that could go.

Let them build the taxonomy themselves; most get to two of the three. Sec.
1.04(2):

- Disclosed — the third party knows a principal exists and who it is.
- Unidentified — the third party knows there is a principal but not which one.
  The Second Restatement called this partially disclosed. If the student learned
  that term, tell them they are the same thing.
- Undisclosed — the third party does not know a principal exists at all, and
  believes they are dealing with the agent as owner.

The categories are about what the third party knew at the time of the deal.
Nothing else.

## 2. The agent's exposure on the contract

Take them in order, one question each.

Disclosed. Ask: Bowman is bound to Dunn on apparent authority. Is Perez a party
to the contract?

No. Everyone knew the deal was Bowman's, so the agent drops out. Sec. 6.01.

Unidentified. Run scenario 13:

```
python scripts/agency.py --scenario 13
```

Ask whether the agent is on the hook when the third party knew there was a
company but never learned which one.

Yes — the agent is a party too, unless the agent and the third party agreed
otherwise. Sec. 6.02. Ask why that is the sensible default:

> Vantage agreed to extend credit to somebody. Who did it get to evaluate?

Only the agent. A third party who cannot identify the principal cannot check the
principal's credit, so the agent stays on until someone says otherwise. This is
also the practical lesson: sign with the principal's name on the signature block
or you are a party to your employer's contracts.

Undisclosed. Run scenario 12:

```
python scripts/agency.py --scenario 12
```

Shah runs the Katy lot day to day and never mentions Calder. Ridgeline has never
heard of Calder. Shah exceeds what Calder authorized. Then Calder, knowing what is
happening, takes the benefit.

Two questions, in this order, and do not merge them.

> First: can Ridgeline reach Calder on apparent authority?

No, and the reason is definitional rather than a matter of degree. Apparent
authority requires the third party to believe the actor is acting for a
principal. Ridgeline believed no principal existed, so there was no belief for a
manifestation to have created. Sec. 2.03 cmt. c.

> Second: does that end it?

No, and students who stop here have made the error the scenario exists to catch.
An undisclosed principal cannot rely on the agent's lack of authority where the
principal had notice the agent was dealing with the third party, and that the
third party might be induced to change position, and took no reasonable steps.
Sec. 2.06. Calder knew and let it run.

And Shah is personally a party to the contract, Sec. 6.03 — which is the
one part of the undisclosed-principal case students never guess and never
forget, because Ridgeline thought it was dealing with Shah and it was.

While you are here, ask about ratification for the undisclosed principal:

> Could Calder have ratified instead?

No. Only acts taken by someone purporting to act as an agent on the principal's
behalf can be ratified, and Shah purported to be acting for no one else. Sec. 4.03. The
route is sec. 2.06 or nothing.

## 3. The agent who guessed wrong

Now the case where nobody is bound. Run scenario 4 again, or 14:

```
python scripts/agency.py --scenario 14 --key
```

Ask: the principal is not bound and the third party has been left holding
nothing. Is that the end of the story?

No. A person who purports to contract on another's behalf impliedly warrants
that they have the power to bind that person. An agent without it is liable to
the third party for breach of that warranty — measured by what the third party
would have had if the representation had been true. Sec. 6.10.

The clean way to put the structure, and worth having the student say it back:

> Apparent authority present: the principal is bound and the agent's warranty is
> satisfied, because the agent did in fact have the power to bind. No authority
> of any kind: the principal walks and the agent pays.

## 4. The agent's exposure to the principal

Return to scenario 2, where Bowman is bound for $40,000 it never authorized.
Students finish module 2 feeling this is unjust; this closes it.

> Bowman is out $40,000. Does Bowman have a claim against Perez?

Yes. An agent has a duty to act only within the scope of actual authority and to
comply with the principal's lawful instructions, and is liable for the loss from
breaching it. Sec. 8.09. That Bowman is bound to Dunn is precisely why Bowman
has a claim against Perez.

The framing sentence: apparent authority does not decide who was right. It
decides who bears the risk of the agent's misconduct as against an innocent
third party, and leaves the principal to collect from the agent. Two separate
allocations, and students who see only the first think the doctrine is unfair.

## 5. One tort question, to draw a boundary

Business-law students will have met respondeat superior, and it bleeds into this
material. Ask:

> Perez rear-ends someone while driving to meet Dunn. Is Bowman liable?

Different doctrine, different question. An employer is liable for torts of
employees acting within the scope of employment. Secs. 2.04, 7.07. Nothing about
manifestations, nothing about what anyone believed.

The test to hand them: if the question is whether a contract binds, you are in
authority. If the question is whether someone pays for harm, you are in
respondeat superior. Do not let them run the ladder on a tort.

## 6. Check understanding

Offer one:

(a) Exercise 4.2 in the bank.

(b) Conceptual: an undisclosed principal is bound on a contract. Can the
principal sue the third party to enforce it?
Answer: generally yes, subject to real exceptions — where the contract was for
personal services chosen for the agent's own qualities, or where the third party
would be materially prejudiced. Worth flagging that this is thinner ice than the
rest of the module.

(c) Practical: the student is signing a contract as an employee. What exactly
should the signature block say, and why?
Answer: the principal's name, then "By:" and the signer's name and title. It
converts an unidentified-principal problem into a disclosed one and takes the
signer off the contract. Sec. 6.01, sec. 6.02.

## Where students get stuck

Reading "undisclosed" as "secret" in a pejorative sense. It is ordinary and
lawful — buying land through a nominee so the seller does not raise the price is
the standard example. The doctrine is about allocation, not misconduct.

Thinking the disclosure categories describe the principal. They describe the
third party's knowledge at the time of contracting.

Missing sec. 6.03 for the undisclosed principal, and letting the agent out. Ask
whose name the third party thought was on the deal.

Answering "is the principal bound?" and stopping. The habit built by modules
1 through 3. Ask "and who else?" every time until they stop needing it.

Next: `references/exercises.md` for problems, or back to any module.
