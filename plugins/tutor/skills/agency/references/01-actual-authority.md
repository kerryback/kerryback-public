# Module 1 — Actual authority: express and implied

Goal: the student should be able to say what the agent was entitled to do, and
name the evidence for it, without once mentioning what the third party thought.

Keeping the third party out of module 1 is the whole design. Students who meet
both doctrines at once never separate them again.

Teach it in this order. Stop at each question.

## 1. What agency is, in one exchange

Do not define it. Ask instead:

> You hire a real estate broker to sell your house. The broker signs a contract
> with a buyer. You have never met the buyer and never saw the contract. Are you
> obligated to sell?

Most students say yes immediately. Then ask why, and let them flounder for a
moment — the answer they reach for ("because I hired the broker") is the right
instinct and the wrong precision. Agency is a relationship in which one person
manifests assent that another act on their behalf and subject to their control,
and the other so consents. Sec. 1.01. The payoff sentence: this is the machinery
that lets a company with eleven stores be legally present in all eleven at once.

One more, worth thirty seconds because it comes back in module 4:

> Does it matter that the contract calls the broker an "independent contractor"?

No. The relationship is agency or not based on what it is, not what the parties
called it. Sec. 1.02.

## 2. Express actual authority

Run the script and paste the student the fact pattern:

```
python scripts/agency.py --scenario 1
```

Bowman Foods put Rosa Perez in as general manager of the Westheimer store and
told Perez to take charge of keeping it stocked and use their own judgment.
Perez signed a $40,000 twelve-month supply contract with Dunn.

Start easier than the problem. Ask: if Perez had placed the routine $2,000
weekly produce order instead, would that be authorized?

Yes, obviously — that is precisely what Perez was told to do. That is express
actual authority: the principal named the act. Sec. 2.01. Get the easy one on
the table so the hard one has something to be compared to.

## 3. Implied actual authority

Now the real question. Ask it and wait:

> Nobody told Perez to sign a twelve-month contract, and nobody forbade it.
> Was Perez authorized?

Let them argue it. The answer is yes, and the reasoning is the part that
matters: actual authority extends to acts the agent reasonably believes,
from the principal's manifestations, the principal wishes done — which includes
whatever is incidental to the objective the principal actually named. Sec. 2.02.
Bowman named an objective, keeping the store stocked, and handed over a general
manager's job. A twelve-month supply contract is how that objective gets met.

The test question, which separates students who have it from students who have
memorized it:

> Whose belief does the rule ask about, and what evidence goes into it?

The agent's belief, formed from what the principal manifested to the agent.
Nothing Dunn thought is admissible on this question. Nothing Perez said to Dunn
is either. If the student reaches for either, that is module 2 leaking in — name
it and push it back a module.

## 4. Where implied authority stops

Same tree, bigger act:

```
python scripts/agency.py --build --context 0 --grant narrow --act 3 \
    --position general_manager --belief position --key
```

A five-year exclusive supply agreement covering all eleven stores, $2.4 million.
Ask whether that is incidental to keeping one store stocked.

It is not, and the student should be able to say why in their own words: the act
has outgrown the objective. Incidental means in service of; it does not mean
vaguely related to the same business.

Then the reliable follow-up:

> Where exactly is the line between the $40,000 contract and the $2.4 million
> one? Give me the principle, not the number.

There is no bright line, and saying so is the correct answer, but a student who
answers only "it depends" has not done the work. Push for the factors: how far
the act reaches beyond what the principal named, how unusual it is for the job,
how irreversible, how large relative to the business, and whether it is the kind
of thing a principal would obviously want to decide themselves.

## 5. Limits, and the thing that ends authority

Two moves that both kill actual authority, and students should see them as the
same move:

An express limit. Run scenario 2 and ask about rung 1 only.

```
python scripts/agency.py --scenario 2
```

Perez is authorized to sign supply contracts up to $10,000, and signs for
$40,000. Ask: is there actual authority for the $40,000?

No. Perez cannot reasonably believe the principal wishes what the principal
expressly forbade. Sec. 2.02. Stop there — do not let the conversation run to
whether Bowman is bound. That question is module 2, and holding it back one turn
is what makes module 2 land.

Termination. Ask:

> Bowman fires Perez on the 1st. On the 14th Perez signs another supply contract.
> Actual authority?

None. It ended with the relationship, and it ended whether or not anyone else
was told. Secs. 3.06, 3.10. Then plant the seed and leave it: "Hold onto the
'whether or not anyone else was told.' We come back to it."

## 6. Check understanding

Offer one and ask which they want:

(a) Exercise 1.2 in the bank — the discount case, where the question is whether
a salesperson's authority to sell implies authority to discount.

(b) Conceptual: Perez is told to keep the store stocked, and hires a temporary
worker to unload the trucks. Actual authority?
Answer: yes, implied — you cannot keep a store stocked without someone to
unload. Useful because the act is not a purchase, so students cannot
pattern-match on dollar amounts.

(c) Conceptual: does a principal's instruction have to be in writing, or even in
words?
Answer: no. A manifestation can be conduct — a course of dealing the principal
watched and never objected to is a manifestation. Sec. 1.03. This one pays off
in module 3.

Check any of these with `--key`.

## Where students get stuck

Reading "reasonably believe" as "believed." A sincere but unreasonable belief by
the agent is not actual authority. Ask what a reasonable person in the agent's
position, holding the same instructions, would have concluded.

Thinking a limit has to be reasonable to be effective. It does not. A principal
may give an arbitrary, foolish, or unexplained instruction, and the agent who
disobeys it has no actual authority. The remedy for a bad instruction is to quit.

Confusing implied actual authority with apparent authority. The single most
common error in the subject, and the reason for the module order. Diagnostic
question: "Whose head are we inside?"

Assuming a title settles it. A title is powerful evidence of what the principal
manifested, but it is evidence, not a rule, and its real work happens in module
2.

Next: `references/02-apparent-authority.md`.
