# Problem bank

Every answer here was produced by `scripts/agency.py` at the command shown.
Still run the command before you grade — it costs nothing, and it protects the
student from a confident wrong correction.

Give one problem at a time and stop. Do not paste a list.

## Making new problems

The bank runs out; the generator does not.

```
python scripts/agency.py --random --seed 42        # a coherent problem you have not seen
python scripts/agency.py --random --seed 42 --key  # the key for it
```

Guidelines that make a problem teach something:

- Change one variable and reuse everything else. A pair that differs in exactly
  one fact is worth three unrelated problems, because the student can see what
  the fact did. Nearly every entry below has a designated partner for this.
- Rotate `--context`. A student who sees Bowman and Dunn six times starts
  answering from the names rather than from the facts.
- Do not let every problem bind the principal. Students infer the pattern fast
  and stop analyzing.
- Put the interesting fact in the middle of the narrative. A dispositive fact in
  the last sentence gets found by position rather than by reasoning.
- For ratification problems, vary what the principal knew and when. That is
  where the doctrine lives, and it is the element students skip.

## Module 1 — actual authority

1.1 `--context 3 --grant broad --act 1 --position general_manager --belief position`
Harbor's practice administrator orders $3,000 of routine imaging supplies.
Answer: express actual authority — the principal named the act. Bound. The
warm-up; do not spend time here.

1.2 `--context 1 --grant broad --act 2 --position sales_rep --belief position`
A Calder salesperson, told to move inventory and use their judgment, sells three
excavators at a 15% discount with a service plan thrown in.
Answer: implied actual authority. Discounting is incidental to the objective of
moving inventory. Bound. Ask the follow-up that matters: would the answer change
if the discount were 60%? Push them to say why size alone can take an act
outside "incidental."

1.3 `--context 0 --grant narrow --act 2 --position general_manager --belief position`
Perez's written instructions confine Perez to routine day-to-day matters; anything
larger goes to the owners. Perez signs the $40,000 supply contract.
Answer: no actual authority — the act is outside the objective and not
incidental to it. But Bowman is still bound, on apparent authority. Use this as
the bridge into module 2 rather than as a module 1 problem, and stop the student
at rung 1 the first time through.

1.4 `--context 2 --grant broad --act 3 --position general_manager --belief position`
The gallery director, with a broad grant, consigns the gallery's entire Rothko
holding to a buyer for resale on commission.
Answer: not bound, on any theory. Neither the grant nor the directorship reaches
an act that disposes of the inventory itself. The partner problem for 1.2 — same
broad grant, different magnitude.

1.5 Conceptual. Bowman's instruction to Perez is arbitrary and commercially
foolish: never buy from any supplier whose name begins with D. Perez buys from
Dunn. Actual authority?
Answer: none. The principal's instruction does not have to be sensible. Ask what
Perez's remedy is if the instruction is intolerable — quit, not disobey.

## Module 2 — apparent authority

2.1 `--context 3 --grant capped --act 2 --position general_manager --belief position`
Harbor's practice administrator is capped at $25,000 for equipment leases and
signs a $60,000 ultrasound lease. Vantage was never told about the cap.
Answer: no actual authority; apparent authority; Harbor bound. Iverson owes
Harbor the loss under sec. 8.09. The core configuration in the subject.

2.2 `--context 3 --grant capped --act 2 --position general_manager --belief position --limit-told-tp`
Identical, except the $25,000 cap is printed on the order forms Vantage signs.
Answer: not bound, and now Iverson is liable to Vantage for breach of the
implied warranty of authority, sec. 6.10. Partner to 2.1 — run them back to
back and make the student name the one fact that moved.

2.3 `--context 2 --grant none --act 2 --position sales_rep --belief agent_said`
A gallery floor associate with no instructions of any kind tells a first-time
buyer "I have full authority to sign this" and sells a $22,000 print with a
written authenticity guarantee.
Answer: not bound. The only source of the belief was the agent. The gallery
made no manifestation to Reyes at all. Novak is liable to Reyes under sec. 6.10.

2.4 `--context 0 --grant broad --act 2 --position general_manager --belief position --terminated no_notice`
Bowman discharged Perez three weeks ago. Nobody told Dunn, and Perez still has
the cards and letterhead. Perez signs the $40,000 contract.
Answer: bound. Actual authority died with the relationship; apparent authority
did not, because Dunn had no notice. Sec. 3.11.

2.5 `--context 0 --grant broad --act 2 --position bookkeeper --belief position`
Perez has a broad grant from Bowman but the job is bookkeeper in the back
office. Dunn knows Perez in that role and deals on the $40,000 contract.
Answer: bound — but on actual authority, not apparent. The grant reaches the
act; the position does not. Worth its place in the bank because it breaks the
assumption that apparent authority is always the wider of the two.

2.6 `--context 1 --grant broad --act 2 --position sales_rep --belief principal_said --terminated notice_given`
Calder had told Ridgeline directly to deal with Shah, then discharged Shah and
sent written notice. Shah sells the three discounted excavators anyway.
Answer: not bound. Notice ended the apparent authority the manifestation had
created. Partner to 2.4.

2.7 Conceptual. Bowman is bound to Dunn on apparent authority for a contract it
expressly forbade. Bowman's owner asks you why the law lets an employee do that.
Answer in two sentences.
Answer: because between two innocent parties, the loss goes to the one who chose
the agent and could have said something; and because Bowman is not actually out
the money — it has a claim against Perez. A student who gives only the first
sentence has module 2 but not module 4.

## Module 3 — ratification and estoppel

3.1 `--context 3 --grant none --act 2 --position bookkeeper --belief agent_said --after kept_benefits_knowing`
Harbor's billing clerk signs the $60,000 ultrasound lease on their own say-so.
Harbor learns the full terms a week later, says nothing, and accepts and uses
two deliveries.
Answer: bound by ratification, relating back to the date of signing. Both rungs
of authority failed.

3.2 `--context 3 --grant none --act 2 --position bookkeeper --belief agent_said --after kept_benefits_unknowing`
Identical, except nobody at Harbor had seen the contract or knew its terms when
the deliveries were accepted.
Answer: not bound. No knowledge of the material facts, so no ratification.
Sec. 4.06. Partner to 3.1, and the single most useful pair in the module.

3.3 `--context 1 --grant none --act 2 --position sales_rep --belief agent_said --after affirmed --tp-withdrew`
Ridgeline writes to Calder withdrawing from the unauthorized excavator deal.
Calder then writes back affirming it.
Answer: not bound. Ratification is ineffective once the third party has
withdrawn. Sec. 4.05. Ask what Calder would have been holding if the rule were
otherwise.

3.4 `--context 3 --grant none --act 2 --position bookkeeper --belief agent_said --careless`
A Harbor billing clerk has been holding themselves out to vendors as able to
sign equipment leases. Harbor knows and does nothing. Vantage, relying on it,
turns down other business and stocks the unit.
Answer: bound by estoppel, sec. 2.05 — no manifestation by Harbor, so no
apparent authority, but notice plus silence plus detrimental reliance. Follow
up: can Harbor enforce the lease against Vantage? No. Estoppel runs one way.

3.5 `--context 2 --grant narrow --act 2 --position sales_rep --belief position --after repudiated`
A gallery floor associate, confined by instructions to routine sales, sells the
$22,000 print to a repeat customer who knows the associate in that role. The
gallery repudiates the next day.
Answer: bound, on apparent authority. Repudiation does nothing here, and that is
the point of the problem: rejecting a deal matters only when the deal was
unauthorized in the first place. Students who have just learned ratification
start seeing it everywhere.

3.6 Conceptual. Harbor ratifies the ultrasound lease. Does Harbor still have a
claim against the clerk who signed it?
Answer: in principle yes, for breach of the duty to stay within actual
authority, but ratification usually leaves no loss to recover. Useful for
students who read ratification as absolution.

## Module 4 — who is liable

4.1 `--context 2 --grant broad --act 2 --position sales_rep --belief agent_said --status unidentified`
Reyes knows Novak is buying for some company but is never told which.
Answer: the gallery is bound on implied actual authority, and Novak is also a
party to the contract, sec. 6.02. Two defendants. The practical follow-up: what
should Novak have written on the signature line?

4.2 `--context 3 --grant capped --act 2 --position general_manager --belief agent_said --status undisclosed --after kept_benefits_knowing`
Iverson runs the practice day to day and never mentions Harbor; Vantage has
never heard of Harbor. Iverson exceeds the cap. Harbor learns what is happening
and takes the benefit anyway.
Answer: no apparent authority — unavailable by definition where the third party
does not know a principal exists. No ratification either, sec. 4.03. But Harbor
is reached under sec. 2.06, and Iverson is personally a party under sec. 6.03,
and owes Harbor under sec. 8.09. Three separate liabilities from one signature;
make the student list them.

4.3 `--context 1 --grant none --act 2 --position sales_rep --belief agent_said --status undisclosed`
The same undisclosed setup, but Calder knew nothing of the dealing until it was
done.
Answer: Calder is not bound at all. Shah alone is liable, as a party to the
contract. Partner to 4.2 — the variable is what the principal knew and when.

4.4 `--context 0 --grant none --act 2 --position bookkeeper --belief none`
A Bowman bookkeeper signs the $40,000 contract. Dunn made no inquiry and had
never dealt with Bowman before.
Answer: nobody is bound but the agent, who is liable to Dunn for breach of the
implied warranty of authority, sec. 6.10. The measure of damages is worth
asking about: what Dunn would have had if the representation had been true.

4.5 Conceptual. Distinguish, in one sentence each, sec. 6.10 liability from
sec. 8.09 liability.
Answer: 6.10 runs from the agent to the third party and applies when the
principal is not bound; 8.09 runs from the agent to the principal and applies
when the principal is bound. Opposite directions, mutually exclusive triggers.

## Mixed and diagnostic

M.1 Give the student a fact pattern and ask only for the ladder — which rung
each fact bears on, in order, without an answer. Tests structure rather than
rules, and exposes students who are keyword-matching. Any scenario works;
scenario 12 works best because facts bear on rungs the student expects to skip.

M.2 Give them scenario 2 and then change one fact at a time, asking for the
answer after each: the cap is on the order form; Dunn is a first-time customer
who has never met Perez; Perez was fired last month with notice; Perez was fired
last month without notice; Bowman takes two deliveries knowing everything. Five
answers, one fact apart. This is the highest-yield exercise in the bank and
takes about ten minutes.

M.3 Reverse the direction. Tell the student the outcome — "the principal is
bound on estoppel and the agent is liable to nobody" — and ask them to write a
fact pattern that produces it. Then check it with `--build`. Students who can
construct a problem have understood the doctrine in a way that answering cannot
demonstrate.

M.4 Ask the student to find the seam. Run any scenario, then ask: what fact
would a real lawyer want to know that this problem does not tell you, and which
way would it cut? The right answers are things the model cannot hold — what was
actually said, what is customary in the trade, what the course of dealing was.
Good closing exercise, and it inoculates them against treating the script as an
oracle.
