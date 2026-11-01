# Writing guide

This is the standard for every word that goes into `draft/` — the paper, the
abstract, the slides, the referee response, the cover letter, the grant
proposal. It is binding, not advisory, and it applies when drafting fresh as
much as when revising. It does not apply to the state files, `session.md`, commit
messages, or notes between coauthors.

Read it before you write, not after. Prose composed flat and sanded down later
never fully recovers.

This is the only writing standard the project has. Nothing else competes with
it, and no second file of conventions should ever be started — if a rule about
prose is worth keeping, it belongs in here, in the section it bears on.

## This copy grows

The file arrives vendored from the `research` plugin, and then it becomes the
project's own. When a coauthor corrects a draft, `/style-learn` proposes the
rule behind the correction and, once they accept it, writes it into the section
where it belongs. A rule that contradicts something already here is not appended
alongside it — the existing line gets rewritten, because two rules that disagree
mean the guide has stopped being definitive.

Rules the project added carry a marker, so they can be told apart from the
published craft they sit among and so the tooling can find them:

```
- Say "median-fit," never "pinball."  <!-- learned: no-pinball | hits: 3 | added: 2026-08-17 | last: 2026-08-17 -->
```

One line each. A rule needing a paragraph has not been decided yet.

That marker is also how those rules reach a session. This guide is far too long
to put in context every time — it is a manual you consult for the task in front
of you, not a page you re-read before each paragraph. So a hook extracts the
marked lines and puts just those in context at the start of a session. They are
the ones that need it: published craft is half-known already, while a convention
particular to this project is arbitrary and is exactly what a skim loses. What
gets injected is an excerpt of this file, regenerated every time and never
edited by hand. There is still one standard, and it is this one.

Two things govern everything below.

**Variation is a byproduct, never a target.** You do not sprinkle in a short
sentence every fourth line or quota a fragment per paragraph. That trades one
formula for another, and a reader feels the metronome either way. Real variation
falls out of letting each sentence be exactly as long as its thought —
subordinate a clause because the idea is genuinely subordinate, cut to three
words because the point lands hard. Shape follows meaning.

**You preserve what the text asserts.** Every factual claim, citation,
quotation, and number survives a revision pass untouched, along with the
author's voice and level of formality. You are changing how it reads, never what
it says.

---

# Part I — The principles behind every sentence

## 1. Reader first
"Keep track of what your reader knows and doesn't know." (Cochrane) Most readers
are busy, impatient, and skimming. Make the basic result easy to find. Write for
PhD economists who are not experts in your specific field.

## 2. Triangular style
Most important information first, then the details. Never the joke structure
where the punchline comes at the end. Do not bury the lead.

## 3. One central contribution
Every paper has ONE central, novel contribution, and you can state it in a
paragraph. If you cannot, you have not figured it out yet. Everything in the
paper serves it.

## 4. Concrete, not abstract
Say what you FOUND, not what you looked for. "A 10% increase in X leads to a 3%
decline in Y (SE = 0.8)," not "I analyze data on X and find many interesting
results." For theory: the insight and the mechanism, not "I develop a model."

Concreteness is also the single strongest antidote to machine prose, because
models default to the abstract. Not "the strategy performed robustly" but "the
strategy returned 8% a year after costs, and stayed positive in every decade
since 1970."

## 5. Every word counts
"Most paragraphs have too many sentences and most sentences have too many
words." (Goldin & Katz) Cut ruthlessly. A sentence that adds nothing gets
deleted. Finished papers run 35–45 pages, less in applied micro, more in macro
and theory.

## 6. Active voice, present tense
"I find that…", not "It was found that…". Present tense for your results and for
citing others: "Fama and French (1993) find that…". Keep tense consistent.

Passive is acceptable in two places: methods descriptions where the agent is
irrelevant ("Wages were measured using administrative tax records") and
table/figure notes ("Standard errors are clustered at the state level").
Everywhere else, active.

## 7. Simple beats complex
Short, common words. "Use" not "utilize," "several" not "diverse," "people" not
"agents." No more math than the insight requires, and the simpler estimator when
two will do. The exception is theory and structural work, where the formalism is
the contribution — do not under-formalize to look accessible. Papers dressed up
to look impressive read as insecure.

---

# Part II — Prose that reads as human

The goal is prose a good journal editor passes, not prose that dodges a
detector. Those coincide. What makes text read as machine-written — every
sentence the same length, a transition word bolted to the front of each one, a
paragraph that states its topic and then restates it — is also just weak
scholarly writing. Fix the writing and the machine signature goes with it.

## Why machine prose reads uniform

It regresses to the mean of everything it has seen. The symptoms are specific,
and you catch them by name:

- Sentences cluster around one length — usually 15–25 words — and march in the
  same subject-verb-object order.
- Every paragraph is a self-contained unit: topic sentence, two of support, a
  closing line restating the topic. Read the first and last sentence of each and
  you have read the piece.
- Connective tissue is overbuilt. *However, Therefore, Moreover, Additionally,
  Furthermore, Importantly* do work that a semicolon, a juxtaposition, or
  nothing at all would do better.
- The balanced-contrast tic: "It's not X, it's Y." "Rather than X, Y." "Not only
  X but also Y." The model reaches for it as a default rhythm, not because the
  contrast is real.
- The rule of three, compulsively — every list exactly three items, every
  description three adjectives.
- Hedging and throat-clearing that commits to nothing.

## The tells

Delete or replace on sight, unless the author genuinely talks this way.

**Inflated verbs and nouns**: delve, underscore, leverage (as a verb), foster,
navigate (the landscape), unlock, harness, tapestry, realm, testament to,
treasure trove, shed light on, pave the way.

**Empty intensifiers and modifiers**: robust (outside its statistical meaning),
seamless, powerful, vibrant, crucial, pivotal, notable, comprehensive,
multifaceted, groundbreaking, rich (history), very, extremely, incredibly,
truly.

**Filler openers**: "It's worth noting that," "It is important to note that," "At
its core," "In today's world," "In recent years," "When it comes to," "A comment
is in order," "It is easy to show that" (if it is easy, show it), "An important
question in the literature is."

**Skeleton phrases**: "plays a crucial role in," "a testament to," "stands as,"
"serves as a reminder," "serves to highlight," "From X to Y," "Whether you're …
or …."

**Closers that add nothing**: "In conclusion," "Ultimately," and the summary
paragraph restating what the reader just read.

**Economics-specific throat-clearing**: "This paper contributes to the
literature by" (say what you find), "We investigate the relationship between"
(say what you find), "We perform a regression" (say "I estimate" or "I regress Y
on X"), "The remainder of this paper is organized as follows" (just give the
roadmap), "Results are reported in Table 3" ("Table 3 shows…" — tables can be
subjects).

The em dash is not a tell. It is a fine mark. A fixed cadence of one ornamental
em dash per paragraph is. Vary the punctuation carrying your asides: commas,
parentheses, a colon, a full stop.

## What to do instead

Vary rhythm because the ideas vary. A dense claim earns a long sentence with
room for its qualifications. The consequence that matters earns a short one. Put
them next to each other and the short one hits.

Let paragraphs be the size of their idea. Some run one sentence, some run twelve.
Never trim or pad one to match its neighbors.

Prefer juxtaposition to signposting. Two sentences side by side usually imply
"and so" or "but" without the word. Reach for the connective only when a reader
would otherwise take a wrong turn — then use it without guilt.

Cut anything that only restates. If a sentence's job is to summarize the last
one, delete it and trust the reader.

Use field vocabulary naturally where it belongs: "extensive margin" in labor,
"pass-through" in IO, "treatment on the treated" in program evaluation. Generic
phrasing where a term of art exists is itself a tell.

Name the actual dataset, agency, policy, or country. Placeholder generality is a
machine default.

Hedge where the evidence is genuinely uncertain — "This likely reflects…", "One
interpretation is…" — and not elsewhere. Reflexive hedging ("may potentially
suggest") reads as machine caution and weakens claims you could make cleanly.

## Idiomatic phrasing

Read every sentence as if aloud before keeping it. Would a careful economist say
it this way in a seminar or a top-journal paper? If it sounds stilted or
translated, rewrite it. When two wordings mean the same thing, choose the one a
reader will not stumble over.

Specific constructions to avoid:

- Noun stacks: "treatment effect heterogeneity estimation procedure" → "how we
  estimate heterogeneous treatment effects."
- Garden-path sentences that force a re-read.
- Piled-up metaphors. Do not call one thing a calling card, an elevator pitch,
  and a payoff in the same passage. Pick one.
- Redundant pairs: "each and every," "first and foremost," "various different."
- One clear modifier beats three. Cut any word the sentence still means the same
  thing without.

This bans awkwardness, not informality. Deliberate roughness, em dashes, and
parenthetical asides are idiomatic and welcome.

## Structure above the paragraph

Uniformity hides at the document level too.

- Sections need not all be the same length, and not every thought needs a
  heading. Headings on everything chop an argument into interchangeable tiles.
- Reach for a bulleted list only when the items are genuinely parallel and
  discrete. When ideas connect and build, prose carries them better — bullets
  throw away the logic between points. (This section is a list because these
  really are separate checks; the argument above it is not.)
- Drop the closing section that summarizes. End on the strongest point, or on
  what follows from it.
- Transitions between sections do not all need to be smooth. A period and a new
  topic sentence is fine. Real papers have some friction.

## Academic register is the default

Scholarly prose carries its own machine signature on top of the general one.

- Kill the throat-clearing opener. "This paper investigates the relationship
  between…" and "In recent years, growing attention has been paid to…" say
  nothing. Open on the actual question or the actual finding.
- State results as findings, not as the existence of implications. Not "our
  results have important implications for asset pricing" but the implication
  itself.
- Signpost sparingly. "Having established X, we now turn to Y" earns its place
  at a genuine hinge in a long argument, not at every subsection break.

Formality stays high and contractions stay rare. Human does not mean casual.

## Before and after

> Before: In recent years, there has been growing interest in momentum
> strategies. This paper investigates the profitability of momentum. We find
> that momentum is profitable. Our results have important implications for
> investors.
>
> After: Momentum — buying recent winners, shorting recent losers — has drawn
> hard scrutiny since Jegadeesh and Titman (1993). We ask a narrower question:
> does the profit survive realistic trading costs? Mostly it does, though the
> margin is thinner than the gross returns let on.

The contrast tic:

> Before: It's not just about speed. It's about accuracy. However, accuracy
> alone isn't enough. Therefore, cost must also be considered.
>
> After: Speed matters, but accuracy matters more — and neither is worth much if
> the price is wrong.

Each rewrite combines choppy sentences, varies their length, strips the
bolted-on transitions, names the specific instead of the general, and deletes the
sentence that only announced something was important.

---

# Part III — Style rules

## Sentences
Normal structure: subject, verb, object. Keep sentences short and hold down the
number of clauses. Read each one and ask whether it means what it says.

Search for "that" and delete everything before it where you can.

## Word choice
- Simple: "use" not "utilize," "but" not "however," "so" not "consequently."
- Concrete: "people" not "agents," "workers" not "labor market participants."
- No adjectives describing your own work: not "striking results," not "very
  significant."
- No double adjectives: not "very novel."
- Clothe the naked "this": "This regression shows…", never "This shows…".

## Voice and perspective
- "I" for single-authored papers, never the royal "we."
- "We" means the authors in multi-authored papers. Be consistent throughout.
- "We" meaning you-and-the-reader belongs only in single-authored papers, and
  only when the context is plainly inclusive ("we can see from the figure").
- Tables and figures can be subjects: "Table 5 presents…".
- Never "one can see that…".

## Coauthorship
- Agree on voice before writing: "we" throughout, or a consistent lead-author
  style.
- Designate one voice editor responsible for consistent tone, tense, and style
  across sections. A paper that sounds like two people wrote it signals careless
  editing.
- For contribution statements: "Author A conducted the empirical analysis;
  Author B developed the theoretical model."
- On a job market paper the candidate's name goes first, and the introduction
  makes their contribution unmistakable.

## Pronouns and references
- "Where" refers to a place; "in which" refers to a model. Write "models in
  which consumers have shocks."
- Hyphenate compound modifiers before nouns: "risk-free rate," "after-tax
  income." Not when the first word is an -ly adverb: "randomly assigned
  treatment."

## Footnotes
Not for parenthetical comments. If it matters, it goes in the text; if it does
not, delete it. Footnotes are for what typical readers skip and some want: data
documentation, simple algebra, extended references.

## Numbers and notation
- Two or three significant digits, not whatever the software printed.
- Sensible units. Percentages, not 0.0000023.
- Latin letters for variables, Greek for parameters. Define Greek letters by
  name, not just symbol, and remind the reader: "the elasticity of substitution,
  σ, equals 3."
- Subscripts on all variables (i, j, k), smallest unit to largest.

## Paragraphs
One idea each, topic sentence first, flowing logically into the next.

Minimize narrative forward references ("As we will see in Table 6") and backward
ones ("Recall from Section 2 that…"). They usually signal material in the wrong
order — if a reader needs it now, present it now. This does not cover standard
cross-references to numbered tables, figures, and appendix items, which should
always be referenced from the main text. Brief backward references to earlier
results are fine when you are building on them.

---

# Part IV — The sections of a paper

## Title

Formulas:
- Best: "The Impact of [D] on [Y]: Evidence from [Context]"
- Shorter and acceptable: "[D] and [Y]"
- Theory: name the mechanism or insight, not the technique
- Structural: "[Counterfactual Question]: Evidence from [Context]"

Under 12 words is ideal, under 15 acceptable. Do not emphasize methodology
unless you invented the method.

Score a title on clarity (can a non-specialist get the topic in one reading?),
specificity (are cause and effect both named?), length, memorability (would
someone recall it at a conference?), and whether it leads with the finding
rather than the method.

- Good: "The Oregon Health Insurance Experiment: Evidence from the First Year"
- Good: "The China Syndrome: Local Labor Market Effects of Import Competition"
- Good: "Pollution and Mortality: Evidence from the 1952 London Fog"
- Bad: "A Difference-in-Differences Analysis of Education Policy" (method, not
  finding)
- Bad: "On the Relationship Between Various Factors and Economic Outcomes" (says
  nothing)

## Abstract

Write it last, after the introduction is finished. Pull sentences from the hook,
research question, and value-added parts of the introduction, then polish.
(Bellemare)

100–150 words, in four moves: what the paper does (the question or the insight);
how (data and identification, or model and mechanism); what it finds (the
central concrete result); and why it matters, if space permits.

- Be concrete. Say what you find.
- No literature, with one exception: a single prior finding to set up a puzzle,
  kept brief.
- No passive voice, no unnecessary jargon. A smart college-educated
  non-economist should follow it.
- Empirical papers name the identification strategy (DiD, IV, RDD, RCT).
  Theory papers name the mechanism. Structural papers state the key
  counterfactual.
- Finance journals often cap at 100 words. Check.

> Good: "Two easily measured variables, size and book-to-market equity, combine
> to capture the cross-sectional variation in average stock returns associated
> with market beta, size, leverage, book-to-market equity, and earnings-price
> ratios." (Fama and French 1992)
>
> Bad: "I analyze data on executive compensation and find many interesting
> results."

## Introduction

This is where accept/reject decisions are effectively made, and it is the
highest-leverage part of the paper. Write it first, rewrite it every time you
touch the paper, and expect to revise it many times over.

**Paragraphs 1–2, the hook.** Connect to something that matters. Four strategies:
Y matters (people are hurt or helped when it moves); Y is puzzling (it defies
easy explanation); Y is controversial (economists disagree); Y is big or common.
Start with a striking fact, a puzzle, or a bold claim grounded in data.

Do not start with philosophy ("Financial economists have long wondered…"), with
the literature ("The literature has long been interested in…"), with policy
motivation ("Given the importance of X for society…"), with a cute quotation, or
— for theory — with "the literature lacks a model of…". All of it is clearing
your throat. Start with your contribution.

**Paragraph 3, the question.** State plainly what the paper does: "This paper
examines whether [X causes Y] using [method] and [data]." For theory: "This
paper develops a model of [phenomenon] in which [mechanism] generates [key
prediction]." Give the main result here — the actual coefficient, the actual
insight — not a vague preview.

**Paragraphs 4–6, the results.** Top journals give 25–30% of the introduction to
results. The central finding with its magnitude and significance (or the main
proposition and its intuition), key robustness or extensions, and economic
significance rather than just statistical significance.

**Paragraphs 7–9, literature and value added.** The literature review belongs
here, not in a separate section, and takes 20–30% of the introduction.

It is a story, not an annotated bibliography. The narrative hinges on a
"however" or an "although": here is what others did, here is what remains
incomplete, here is how this paper addresses it. Discuss the 5–10 closest papers
— closer to 5 is better — and for each, say what they did *and* what limitation
remains. Then name roughly three contributions: to internal validity (better
identification), to external validity (new context or population), and
methodological or theoretical.

Be generous with citations. You do not have to say anyone was wrong, and you
never insult prior authors. Spell out full names; never "FF" for Fama and
French. Working papers are citable, but note when key results are forthcoming or
have changed, and prefer the journal version when one exists.

**Final paragraph, the roadmap.** Customize it. Not "Section 2 presents the
model, Section 3 discusses data" but the specific landmarks: problems,
solutions, key results. Keep it short.

**Length.** Three to five pages. Three is the upper limit for applied papers;
theory and structural may need four or five.

**The six ways it goes wrong**: burying the lead (main result on page 20);
bait-and-switch (promising interesting, delivering boring); travelogue
(narrating your research journey instead of presenting the product);
throat-clearing; bland enumeration ("Smith found X. Jones found Y."); and no
results at all until the results section.

## Model section (theory and structural)

Start with an example, and the simplest one that generates the key insight
(Varian). Glaeser likewise urges starting from an interesting real-world puzzle,
not a literature gap. If a two-period model works, do not use infinite horizon —
the model is a lens for isolating one mechanism, and structure that does not
change the result only obscures which assumptions drive it. Every assumption
earns its place.

Structure: describe the environment, agents, timing, and information in plain
English before any math; then the formal primitives, preferences, technology,
constraints; then the equilibrium definition and solution concept; then the main
results; then comparative statics discussed verbally ("When X increases, Y falls
because…"); then extensions relaxing key assumptions one at a time.

**Propositions and proofs.** State each proposition in plain English, then
formally. Give the economic intuition immediately after the statement and before
the proof — which incentives, constraints, and trade-offs drive the result — so
the reader grasps the mechanism instead of reconstructing it from the algebra. A
clean derivation or proof sketch can itself carry the mechanism. Proofs go in the
appendix unless they illuminate the economics; for complex ones, sketch in the
text and prove in the appendix. Number only what you reference elsewhere.

**Assumptions.** List and number them. For each: the formal statement, its
economic content in plain English, and whether it is essential or simplifying.
Say what happens when the key ones are relaxed.

**Equations in text.** Number only what you reference later. Introduce every
equation verbally before displaying it ("Firm i's profit is…"). Define every
variable immediately after, even if defined earlier. Do not display what can be
said in words — "wages equal the marginal product of labor" needs no display.

**Testable predictions.** State them explicitly, even if you do not test them,
and say what data would be needed. In mixed theory-empirical papers, map each
regression to a specific proposition.

## Data section

Name the dataset, time period, geographic coverage, and unit of observation in
the first sentence. Then sample construction (inclusion and exclusion criteria,
merges, final size), then key variables defined precisely with their
measurement, then a summary statistics table, then institutional background if
the setting is unfamiliar.

- Answer every question a reader might have about the data before they ask it.
- Define every variable the first time it appears. Do not make readers hunt
  through footnotes.
- Describe any cleaning decision that materially affects results — winsorizing,
  dropping outliers.
- Address sample selection: who is in, who is out, and why.
- For restricted-access data, describe how others can get it.
- With multiple datasets, describe the merge and the match rates.
- Never bury an important data limitation in a footnote.

Report balance tests in a separate table for RCTs and quasi-experiments.

## Conclusion

Keep it to about one page for a twenty-page paper.

**Summary (1–2 paragraphs).** Restate the main findings in a *different* way
from the abstract and introduction. Tell a story; do not copy-paste.

**Implications (1 paragraph).** Applied: policy implications with a rough
cost-benefit assessment; back-of-the-envelope is fine. Name winners and losers.
Theory: broader applicability of the mechanism and what the model says about
unresolved debates. Structural: what the counterfactuals imply for policy and
welfare.

**Future research (1 paragraph).** One or two concrete directions — better
identification, richer data, broader external validity, extensions of the model.

Rules: do not restate every finding verbatim ("One statement in the abstract,
one in the introduction, once more in the body should be enough" — Cochrane). Do
not speculate past the data or model. Do not write your grant application here.
Do not say "I leave X for future research" — describe what the extension would
actually look like.

Project confidence. Avoid a generic caveats dump that undermines the findings. A
brief, specific limitations paragraph tied to your analysis is fine, and is often
expected in experimental and policy-facing work; broader caveats belong in the
body next to the relevant analysis.

## Appendix and online supplement

The main paper stands alone — a reader should never need the appendix to follow
the argument. Put robustness checks, additional specifications, variable
definitions, data cleaning details, proofs, and extended tables there. Number
appendix exhibits separately (Table A1, Figure A1), reference every one from the
main text, and organize the appendix in the same order as the paper. The most
important robustness checks stay in the main paper.

---

# Part V — Empirical substance

## Identification

The three most important things are identification, identification, and
identification. (Cochrane) You owe the reader:

1. What economic mechanism caused dispersion in your right-hand variables.
2. What constitutes the error term — what else causes variation in Y.
3. Why the error term is uncorrelated with X, in economic terms.
4. The economics of why your instruments are valid.
5. The source of variation driving your estimates, for every number you present.

## Results presentation

Start with the main result. No warmup exercises. Follow with the graphs and
tables that give intuition, then show the result is a robust feature of
compelling stylized facts, then limited robustness checks with most of them in
the appendix. Give stylized facts in the data, not only estimates and p-values.

Explain economic significance, not just statistical significance. With a large
enough sample even a trivial effect becomes statistically significant, so a small
p-value alone says little — the reader needs the magnitude against a benchmark.
Translate coefficients into dollars, percentage points, standard deviations, or
policy benchmarks, and compare the effect to the mean of the dependent variable,
to a well-known intervention, or to a policy-relevant threshold: "The effect
equals 40% of the Black-white test score gap." For elasticities, say whether they
are at the mean, at the median, or arc. Back-of-envelope calculations are
welcome.

Present specifications from most to least parsimonious so the reader watches the
estimate move as controls are added. Coefficient stability is suggestive, not
conclusive, evidence against omitted-variable bias, and only when the added
controls move the R-squared meaningfully — a coefficient can be stable and still
biased if the controls explain little. Report the R-squared changes, ideally with
an Oster (2019) bound, rather than leaning on stability alone.

## Null results

A null result is a result. Frame it as informative, not as failure.

Distinguish a precisely estimated zero from an imprecise estimate whose interval
covers both zero and meaningful effects. Failing to reject zero is not
establishing zero; only a tight interval excluding economically meaningful
effects says anything about absence. Report confidence intervals alongside or
instead of p-values — "we can rule out effects larger than X." Discuss power:
was the study able to detect an economically meaningful effect? If
pre-registered, say so, because it rules out specification search. Relate the
null to prior work: does it contradict or refine?

## Common mistakes

- **R-squared.** Its interpretation is contextual. In cross-sectional micro
  regressions 0.1–0.3 is typical, and an R-squared near 1 in a cross-section
  usually signals a mechanical relationship — you included "right shoes" to
  predict "left shoes." In time series or macro, high may be appropriate. Never
  judge a paper by R-squared; the coefficient on X and its standard error are
  what matter.
- **Bad controls.** Do not include every determinant of Y. A bad control is
  itself an outcome of the treatment, so conditioning on it does not cleanly
  remove a mechanism — it compares non-comparable groups and induces selection
  bias. Education works partly through industry, so controlling for industry
  does not isolate a "non-industry" return; it biases the estimate (Angrist and
  Pischke, §3.2.3).
- Do not confuse instruments with controls.
- Do not claim causality without explaining the identification strategy.
- Always address reverse causality, unobserved heterogeneity, and measurement
  error.

## Standard errors and inference

Cluster at the level of treatment assignment, not the most granular unit, and
state the level explicitly. When treatment is assigned and shocks are correlated
within a cluster, observations are not independent, so treating them as
independent understates standard errors and overstates significance.

With few clusters — under roughly 40, worse when sizes are unbalanced —
cluster-robust standard errors over-reject. The estimator is consistent only as
the number of clusters grows, so with few clusters it is biased down and standard
critical values reject true nulls too often. Use the wild cluster bootstrap
(Cameron, Gelbach, and Miller 2008) or randomization inference.

In randomized or design-based settings, randomization inference is often more
credible than asymptotic standard errors.

## Heterogeneity

Present it after the main result, never before. Pre-specify subgroups from
theory, not from the data. Report how many subgroups you tested. Interpret
magnitudes — "the effect is 3x larger for women" beats "the interaction term is
significant." Use forest plots or coefficient plots when there are many.

## Mechanisms

Test specific channels; do not speculate. Structure as: theory predicts
mechanism M; if M operates we should observe X; we test for X. Distinguish
mediation analysis from suggestive evidence. Be honest about what the data can
and cannot identify. Do not list every possible mechanism without testing any.

## Modern practices

These are credibility-revolution conventions referees and data editors expect.
Treat them as defaults.

**Pre-registration.** State it in the introduction if the study is registered —
it is a credibility asset. Distinguish pre-specified from exploratory analyses.
Report every deviation from the plan with its reason. Reference the registry
number.

**Multiple testing.** Acknowledge the problem when testing multiple outcomes or
subgroups. Pre-specify outcome families and consider summary indices to cut the
number of tests. Report family-wise corrections (Bonferroni, Holm) or false
discovery rate (Benjamini-Hochberg); for pre-specified families, Anderson (2008)
sharpened FDR q-values. At minimum, flag which results survive correction.

**Specification robustness.** Do not present only the specification that works.
Consider a specification curve or multiverse analysis for key results, and report
the distribution of estimates across reasonable specifications.

**Transparency.** State data availability clearly — public, restricted, or
proprietary. Provide or reference replication code. Describe cleaning decisions
that materially affect results. For restricted data, describe the application
process.

**Citation integrity.** Verify every citation: author names, year, journal, and
key finding. Check you are citing the right specification — the preferred
estimate, not a robustness check. Distinguish working-paper from published
versions, since findings sometimes change. Do not cite papers you have not read;
if you know one only through a secondary citation, cite the secondary source. For
well-known results, cite the original, not a textbook or survey.

**Replication packages (AEA Data Editor standards).** Every empirical paper at
AEA journals, and increasingly elsewhere, needs one. Include a README on the
Social Science Data Editors template: Data Availability and Provenance
Statements, Dataset List, Computational Requirements (software versions,
hardware, expected runtime), Description of Programs, Instructions for
Replicators. Cite every dataset in the References, including ones you built.
Directory structure `data/raw/`, `data/analysis/`, `code/`, `results/`, never
commingling code and data. Code must reproduce all results without manual
intervention, the sole exception being one config file for directory paths. For
restricted data, give a Data Availability Statement with application procedures,
wait times, and costs. Include a `LICENSE.txt` — CC-BY 4.0 for data and
documents, modified BSD for code. Map every exhibit to a program file: "Table 3
is produced by `code/table3_main_results.do`." These apply to AEA, Econometrica,
the Economic Journal, and increasingly field journals.

**AI disclosure.** AEA policy: AI may not be an author, and use in drafting or
editing is disclosed at submission. The Econometric Society requires a statement
that all coauthors accept responsibility for all content. Disclose drafting
assistance, code generation, literature search, and analysis suggestions;
spell-check, grammar tools, and LaTeX formatting typically need no disclosure.
Whatever the policy, you are responsible for verifying every AI-generated
citation, number, and statistical interpretation. Practical rule: read an
AI-drafted paragraph as if a careless RA wrote it.

---

# Part VI — Writing by identification strategy

Different strategies need different narrative structures.

## Randomized controlled trials
Randomization makes treatment independent of potential outcomes, so the groups
are comparable in expectation and a simple difference in means is unbiased for
the ATE. Lead with the intervention and its policy relevance. Describe the
randomization mechanism and balance tests early. Intent-to-treat is the main
specification; compliance and LATE come separately. Attrition and spillovers are
the primary threats. Report take-up rates — they are central to interpreting the
effects. State the registry number in the introduction if registered. Order the
results ITT, then LATE/IV if compliance is imperfect, then heterogeneity.
External validity is usually the main concern: say what populations this
generalizes to.

## Difference-in-differences
Under parallel trends and no anticipation, the control group's before-after
change is the counterfactual for the treated group, so the second difference nets
out fixed group differences and common shocks, leaving the effect on the treated
(ATT, not ATE).

Lead with the policy change or natural experiment. Give parallel trends a full
paragraph — it is the identification. Show pre-trends visually; an event study
plot is mandatory in modern DiD papers. A flat, insignificant pre-trend does not
prove parallel counterfactual trends and pre-tests are often underpowered, so
report sensitivity with HonestDiD (Rambachan and Roth 2023).

For staggered adoption, address the recent econometrics: report the
Goodman-Bacon (2021) decomposition to show which comparisons drive the result,
and use an appropriate estimator — Callaway and Sant'Anna (2021) for
heterogeneous effects over event time, Sun and Abraham (2021) for event studies,
de Chaisemartin and D'Haultfœuille (2020) against the sign reversal TWFE can
produce under heterogeneity. Present both the traditional TWFE and the robust
estimate; if they differ, explain why. Show the event-study plot from the robust
estimator.

Also: results with and without covariates, anticipation effects if the policy was
announced early, and compositional changes in the groups over time.

## Instrumental variables
A valid instrument moves the endogenous regressor only through a channel
unrelated to the outcome's error, so 2SLS uses just that variation; under
monotonicity it recovers a LATE for the compliers, which generally differs from
both OLS and the population ATE.

Name the instrument in the first paragraph of the introduction. Give relevance a
full paragraph, reporting the effective (Montiel Olea and Pflueger 2013) or
Kleibergen-Paap F-statistic and treating "F > 10" as a minimal screen, not a
guarantee. Give the exclusion restriction a full paragraph, argued economically.
Report both OLS and IV, and explain why they differ. Describe the compliers —
whose behavior does the instrument actually shift? For weak or moderate
instruments report Anderson-Rubin confidence intervals; for single-instrument
t-tests apply the tF adjustment of Lee, McCrary, Moreira, and Porter (2022).
Address monotonicity. Handle Bartik/shift-share, judge-leniency, and
historical/geographic instruments with particular care.

## Regression discontinuity
If potential outcomes vary smoothly through the cutoff, units just above and
below are comparable in everything but treatment, so a jump at the threshold is
the causal effect — locally, at the cutoff.

Lead with the running variable and the cutoff. The RD plot is your Figure 1 and
is mandatory. Test for manipulation of the running variable (McCrary/density).
Show bandwidth sensitivity; results should hold across reasonable bandwidths.
Report local polynomial estimates with an optimal bandwidth (Calonico, Cattaneo,
and Titiunik). Emphasize that estimates are local and discuss external validity
explicitly. For fuzzy RDD, report the reduced form and first stage separately.
Address any other discontinuity at the cutoff.

## Synthetic control
A weighted average of untreated donors — non-negative weights summing to one —
chosen to track the treated unit's pre-treatment path and predictors, proxies its
no-treatment counterfactual. Given close pre-period fit, the post-intervention
gap is the estimated effect.

Lead with the treated unit and the event. Describe donor pool selection. Show
pre-treatment fit visually; that is your identification, and poor fit means the
method failed. Placebo/permutation tests are the primary inference tool. Report
the donor weights. Address interpolation bias if donors differ sharply from the
treated unit. With multiple treated units, consider augmented/penalized synthetic
control or synthetic DiD.

## Synthetic difference-in-differences
Lead with the policy change and why neither DiD nor synthetic control alone
suffices. Explain the doubly robust property: valid if either parallel trends or
the synthetic weights are right. Present standard DiD, synthetic control, and
synthetic DiD side by side. Show unit and time weights so readers see which
comparison units and pre-periods drive the estimate. Use the placebo-based
inference procedure, not asymptotic standard errors. Say when it is preferred:
few treated units where DiD is noisy, or many pre-periods where synthetic control
may overfit.

## Bunching
A kink changes the marginal incentive and a notch changes the level; either way,
agents who would have optimized just past the threshold relocate to it, and the
excess mass relative to a smooth counterfactual density reveals how strongly
behavior responds — mapping to a structural elasticity under an optimization
model.

Lead with the kink or notch. The bunching plot is your central figure. Describe
the counterfactual distribution and how you estimated it. Report the implied
elasticity. Discuss optimization frictions: bunching estimates are lower bounds
when adjustment costs exist. Separate manipulation from real responses. Show
robustness to bandwidth and polynomial order. For notches, discuss the dominated
region and what it implies about rationality.

## Shift-share / Bartik
The instrument isolates variation driven by pre-period industry shares
interacting with common sectoral shocks. It is valid only if that predicted
variation is uncorrelated with the local error — either because initial shares
are as-good-as-randomly assigned, or because the many shocks are themselves
quasi-random.

Name it in the introduction and describe both components: the shares (exposure
weights) and the shifts (national/sectoral shocks). State which source of
variation you rely on, and argue for it: share exogeneity (Goldsmith-Pinkham,
Sorkin, and Swift 2020) or shock exogeneity (Borusyak, Hull, and Jaravel 2022).
Report the effective F-statistic, discuss the granularity of shares and how many
shocks drive the variation, present leave-one-out estimates, and address
pre-trends using the shift-share structure.

## Event studies
Identification is the dynamic form of parallel trends plus no anticipation.
Pre-event coefficients near zero are consistent with — but do not prove — treated
and control units evolving together absent the event; post-event coefficients
trace the dynamic effect relative to the omitted base period.

Lead with the event and its economic significance. The event study plot is the
central figure. Include at least three or four pre-periods. Normalize one
pre-period to zero, typically t = −1. Interpret the post-event dynamics: is the
effect immediate, gradual, or temporary? Under staggered timing with
heterogeneous effects, raw TWFE leads and lags can be contaminated (Sun and
Abraham 2021) — use a robust estimator. Report point estimates and confidence
intervals for the key post-event periods, and address anticipation if the event
was foreseeable.

## Machine learning for causal inference
State plainly whether ML is doing prediction, heterogeneity, or causal
estimation. For heterogeneous treatment effects (causal forests, Wager and Athey
2018, building on the honest sample-splitting trees of Athey and Imbens 2016),
describe the splitting procedure and how overfitting is avoided. For
double/debiased ML (Chernozhukov et al. 2018), explain cross-fitting and why it
is necessary. Report traditional standard errors and confidence intervals — ML
does not change inference requirements. Discuss the interpretability trade-off,
and compare to simpler parametric estimates for credibility. For LASSO-based
selection, justify data-driven selection and report sensitivity to the penalty.

## Structural estimation
State the model and its key assumptions in plain English before the math.
Distinguish identifying assumptions from functional form assumptions. Explain
identification intuitively: what variation in the data pins down each parameter?
Report model fit against key moments and validate out of sample where possible.
Counterfactual simulations are the payoff — present them prominently. Discuss
sensitivity to key assumptions, compare to reduced-form estimates for
credibility, and report the sensitivity of estimates to the identifying moments
(Andrews, Gentzkow, and Shapiro 2017).

## Descriptive and measurement papers
Lead with why the measurement matters for economics. Be explicit: "This paper
does not estimate a causal effect. It documents [the pattern]." The data
construction process is the contribution, so describe it in detail. Show the
patterns are robust to alternative definitions and samples. Say what causal
questions the new facts enable. Relate the findings to existing theory.

## Papers using several strategies
Designate one primary and present it first; the others are robustness or
complementary evidence. When estimates converge, say so: "The IV estimate is
statistically indistinguishable from the DiD estimate, reinforcing the causal
interpretation." When they diverge, explain why — different local populations
(LATE vs. ATT), different assumptions, different margins. Do not weight them
equally unless you genuinely have no reason to prefer one; readers want to know
which result you stand behind. Name the primary strategy in the introduction and
mention the secondary briefly.

## Adapting the introduction by paper type

| Paper type | Hook strategy | Paragraphs 4–6 | Key threat to discuss |
|---|---|---|---|
| RCT | Policy relevance of the intervention | ITT and LATE estimates | Attrition, spillovers, external validity |
| DiD | Policy change or natural experiment | Main estimate + event study | Parallel trends, anticipation |
| IV | The instrument and why it is clever | OLS vs. IV comparison | Exclusion restriction, weak instruments |
| RDD | The cutoff and its stakes | RD estimate + bandwidth sensitivity | Manipulation, other discontinuities |
| Synthetic control | The treated unit and the event | Synthetic vs. actual trajectory | Pre-treatment fit, donor pool |
| Synthetic DiD | Policy change, few treated units | SDiD vs. DiD vs. SC | Parallel trends, synthetic fit |
| Structural | The question that requires a model | Key counterfactual results | Model assumptions, external validity |
| Theory | The puzzle the model resolves | Main proposition and intuition | Robustness of mechanism to assumptions |
| Descriptive | Why the fact matters | Key patterns with magnitudes | Measurement validity, sample selection |
| Bunching | The kink/notch and who is affected | Elasticity + bunching plot | Optimization frictions, manipulation |
| Shift-share | The shock and local exposure | Main estimate + leave-one-out | Share exogeneity, shock exogeneity |
| Event study | The event and its stakes | Event study plot + key coefficients | Pre-trends, anticipation |
| ML/causal | The prediction or heterogeneity question | ML vs. parametric comparison | Overfitting, interpretability |

---

# Part VII — Tables and figures

## Regression tables
- A self-contained caption explaining the regression, the variables, and what is
  shown.
- No number appears in a table that is not discussed in the text.
- Plain English variable names ("Years of education", "Female"), never code
  names.
- Consistent decimal places, two or three, across all tables.
- Standard errors for every important number, with the clustering level stated.
- At the bottom: N, R-squared, which fixed effects are included, and the
  controls.
- Significance stars * 10%, ** 5%, *** 1% — though some journals discourage
  them; check.
- A reader should be able to write down the exact regression from the table
  alone.

## Descriptive statistics tables
N, mean, SD, min, max for all key variables. Separate panels for treatment and
control where applicable. Balance tests as a difference in means with p-values,
in their own column or table. Every variable defined in the notes. Two or three
meaningful decimals.

## Figures
A good figure conveys a pattern more clearly than a table of many rows. Give
self-contained captions with verbal definitions of symbols. Label axes with
sensible units. Avoid dotted lines that vanish when reproduced, and dashes for
volatile series.

## Figures vs. tables
Figures for trends over time, distributions, non-linear relationships, RD and
event-study plots, and any result where the visual pattern is the point. Tables
for regression coefficients with standard errors, precise numerical comparisons
across specifications, and summary statistics.

A coefficient plot beats a twenty-row table. If you find yourself writing "as
Table 3 shows, there is an inverted-U relationship," replace the table with a
figure. Every key result appears in either a figure or a table, not both. Put the
most important exhibit near the beginning of the results.

## Data visualization
Show the data, not the analyst's cleverness. Reduce non-data ink. Direct labels
beat legends. Highlight the comparison that matters. Keep color schemes
consistent across related figures.

---

# Part VIII — Structures and conventions

## Standard applied economics paper
Title · Abstract (100–150 words, concrete) · Introduction (3–5 pages, includes
the literature review) · Theoretical framework (optional, only if it helps the
empirics) · Data and descriptive statistics · Empirical framework (estimation
and identification) · Results and discussion (main, robustness, mechanisms,
limitations) · Conclusion · References · Appendix.

## Theory paper
Title · Abstract (state the main result) · Introduction (puzzle, main insight,
mechanism, literature) · Model setup (primitives, assumptions, timing — as simple
as possible) · Analysis and main results (propositions with intuition before
proofs) · Extensions · Discussion and empirical implications · Conclusion ·
References · Appendix (proofs).

## Mixed theory-empirical
Title · Abstract (both the theoretical insight and the empirical finding) ·
Introduction (both contributions) · Model (derive testable predictions) · Data
and institutional background · Empirical strategy (how you test the predictions)
· Results (mapped explicitly back to the predictions) · Conclusion · References ·
Appendix.

## Structural paper
Title · Abstract (the key counterfactual finding) · Introduction (question,
approach, key counterfactual results) · Model · Data and institutional background
· Estimation (identification, method, computation) · Model fit and validation ·
Counterfactual analysis — the payoff · Conclusion · Appendix.

## Field conventions

The defaults above are applied-micro defaults. Where a field convention conflicts
with one — page length, abstract length, primary exhibit — the field convention
wins.

**Applied micro** (labor, public, health, education, development). The default.
Development RCTs: pre-registration is nearly mandatory, include a CONSORT-style
flow diagram, report cost-effectiveness alongside treatment effects. Balance
tables are central to experimental work and belong up front, not in an appendix.

**Macro.** Papers run 40–60 pages; the under-40 advice does not apply.
Calibration tables are standard, with columns for parameter, value, and
source/target moment. Impulse response functions are the primary results
visualization, not regression tables. A model fit section comparing model moments
to data moments is expected. DSGE papers describe the steady state, the
solution or log-linearization method, and the shock specification. Results are
often framed as "the model generates X" rather than "I find X."

**Trade.** Gravity estimation has its own conventions: PPML (Santos Silva and
Tenreyro 2006), multilateral resistance controls, a specific fixed effects
structure. General equilibrium counterfactuals are expected in structural work.
Use 3- or 5-year panel intervals rather than annual, with justification.

**Finance.** Abstracts often capped at 100 words. Fama-MacBeth regressions and
portfolio sorts are standard presentation. Winsorization at 1%/99% is expected
and must be reported. Some journals use Chicago rather than AEA citation style.

## Job market papers
The JMP is your calling card: it has to show you can identify an important
question, execute credibly, and write clearly, by yourself. Make the title
memorable and field-signaling — committees scan hundreds. Lead the abstract with
the finding and make it intelligible outside your subfield. Polish the
introduction hardest; many committee members read only that, so the most
impressive result goes up front. Aim short, 30–35 pages, because shorter papers
get read more carefully. Signal awareness of the literature beyond your subfield
— departments want colleagues, not narrow specialists. If the paper uses a novel
method, emphasize the economic insight it delivers, not the method; committees
hire economists. Job talk slides follow the same rule: the main result inside ten
minutes.

## Three-essay dissertations
An introduction chapter (10–15 pages) establishing the thematic link and
background — not a literature review, since each essay has its own — then three
free-standing papers, each readable independently with its own abstract,
introduction, and conclusion, then a conclusion chapter (5–10 pages) tying them
together. Roughly 150 pages. At least one essay sole-authored, ideally the JMP.
Order by quality: the strongest first, since committees often read only that one
in detail. Senior and undergraduate theses differ — usually a preface, a table of
contents, and a single extended paper.

---

# Part IX — Writing that is not a paper

All the principles and style rules above still apply. These add task-specific
guidance.

## Presentations
Get to the main result immediately — no literature review, no motivation, no
preview. "Gene Fama usually starts with 'Look at table 1.' That's a good model."
(Cochrane) Slides carry equations, tables, and graphs, not a bullet for every
word. Leave a slide up long enough to digest; one per minute is too fast. Speak
loudly, slowly, clearly, and listen to a question all the way through before
answering.

## Surveys and review papers (JEL, JEP, Handbook)
The contribution is the synthesis and the framing, not new results, so state the
organizing framework in the introduction. Structure by research question or
theme, not by method or chronology. Build a narrative argument about where the
field stands and where it should go. Citation density runs much higher than in
original papers — 50 to 200+ references is normal. JEL: abstracts under 100
words, section headings in Roman numerals. JEP: accessible to all economists,
minimal math, intuition-forward, usually commissioned. Handbook chapters:
definitive, can be technical, 40–80 pages. The common failure is listing papers
without building toward a conclusion about the state of knowledge.

## Working paper to journal version
Find the core 15-page paper and move everything else to the appendix. Cut in this
order: redundant motivation, literature tangents, robustness checks that do not
change the story, theory restating known results (cite instead), verbose
captions. Length norms: AER: Insights caps at 6,000 words and 5 exhibits; REStat
enforces 45 pages double-spaced 12pt and can return overlong manuscripts
unreviewed, with a separate Short Papers track; AER recommends ~40 pages at 11pt
1.5 spacing and averages 35–36 typeset pages. Move extended robustness, data
appendices, and proofs online, referencing every item from the main text.
Organize defensively — separate the core contribution from extensions a referee
might demand you cut. After acceptance, do not update the working paper; append a
citation to the published version.

## Grant proposals
Lead with the question and why it matters now. State the expected contribution in
one sentence: "This project will [produce/estimate/test] [specific output] that
[specific benefit]." Demonstrate feasibility — data you already have access to,
methods you have already used, preliminary results if any. The research design
must be concrete: name the datasets, the identification strategy, the sample
period. "I will use the 2015–2023 ACS linked to IRS tax records" beats "I will
collect data." Tie budget lines to activities: "RA support ($X) for cleaning
[specific dataset]," not "RA support for research assistance." NSF: follow the
required structure and treat the 15-page limit as strict. ERC: emphasize PI track
record and the high-risk, high-gain framing. Keep the timeline realistic. For
broader impacts or societal relevance, connect to real policy questions, not
abstract advancement of knowledge. The common failure is writing a proposal like
a finished paper — a proposal sells a plan, so emphasize what you will learn.

## Policy briefs, op-eds, blog posts
These ship as finished prose. Do not leave `[AUTHOR: …]` placeholders for core
content; if a number is unknown, supply a defensible illustrative value and note
it after the piece. Treat the word limit as binding and self-trim to it — never
append a note telling the reader to cut.

Lead with the policy implication, not the research question. Plain language: no
jargon, no Greek letters, no regression terminology, and not "standard
deviations," "elasticity," or "extensive margin." Use one concrete example to
illustrate the mechanism. Translate magnitudes into everyday terms yourself — a
0.3 SD test-score gain is roughly a 12-percentile-point move, about a third of
the Black-white gap. One figure maximum, self-explanatory without the text. Under
1,500 words for a brief, under 800 for an op-ed, and actually hit it. No standard
errors, p-values, or confidence intervals — convey precision in words, varying
the phrasing rather than reusing a stock sentence. End with a concrete
recommendation, never "more research is needed."

## Referee responses
Open with a brief, respectful summary thanking the editor and referees.
Structure point by point: quote each comment, respond immediately below. For
each, state what you changed, where (page and line), and why. When you disagree,
be respectful and direct, and give evidence or reasoning. Describe new analyses
briefly and reference the new exhibit. Never be defensive or dismissive; even an
unhelpful comment gets a measured response. Close with a brief statement that
the paper is improved.

---

# Part X — LaTeX

## Preamble

```latex
\documentclass[12pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{setspace}\doublespacing  % many journals require double or 1.5 -- check
\usepackage{amsmath,amssymb}
\usepackage{graphicx,float}
\usepackage{booktabs,threeparttable}
\usepackage{natbib}
\usepackage[hidelinks]{hyperref}
\usepackage{cleveref}
\usepackage{appendix}
```

| Package | Purpose |
|---|---|
| `amsmath` | Aligned equations, multi-line math |
| `booktabs` | Professional table rules |
| `threeparttable` | Table notes below tables |
| `natbib` | Author-year citations (the economics standard) |
| `siunitx` / `dcolumn` | Decimal-aligned columns |
| `subcaption` | Subfigures (a), (b) |
| `tikz` | Diagrams, game trees, timelines |
| `cleveref` | Smart cross-references |

## Tables

Use booktabs, never `\hline`: `\toprule`, `\midrule`, `\bottomrule`, and no
vertical lines. Wrap regression tables in `threeparttable` for notes.

```latex
\begin{table}[t]
\begin{threeparttable}
\caption{Effect of X on Y}\label{tab:main}
\begin{tabular}{lcc}
\toprule
 & (1) & (2) \\
\midrule
Treatment & 0.45*** & 0.38** \\
 & (0.12) & (0.15) \\
Controls & No & Yes \\
Observations & 5,000 & 5,000 \\
\bottomrule
\end{tabular}
\begin{tablenotes}\small
\item \textit{Notes:} Standard errors in parentheses. *** p<0.01.
\end{tablenotes}
\end{threeparttable}
\end{table}
```

Decimal alignment: `S[table-format=1.3]` from `siunitx`. For multi-panel tables,
separate panels with `\midrule` and label each with `\multicolumn`.

## Figures

Always PDF vector graphics, not PNG or JPG — the exception is photographs and
maps. Export with `graph export fig.pdf, replace` (Stata), `ggsave("fig.pdf",
width=6, height=4)` (R), `plt.savefig("fig.pdf", bbox_inches="tight")` (Python).
Keep all figures the same width for visual consistency. Subfigures via
`subcaption`.

## Math

`equation` for single-line, `align` for multi-line, never `eqnarray`. Number only
referenced equations — `equation*` or `\nonumber` otherwise — and cite them with
`\eqref`. Latin letters for observables, Greek for parameters, defined on first
use.

## Cross-references and bibliography

Label every table, figure, and equation, and use `\cref` from `cleveref` so
"Table 1" never appears as "table 1" somewhere else.

`natbib` with `\bibliographystyle{aer}` or `chicago`: `\citet{FF1993}` gives
"Fama and French (1993)", `\citep{FF1993}` gives "(Fama and French, 1993)".
`biblatex` with `style=authoryear` works but is less common in economics
submissions. For working papers include `note = {NBER Working Paper No.\ 12345}`,
and update to the published version before submission.

## Submission

| Journal | Key requirements |
|---|---|
| AER | 11–12pt, 1.5 spacing, 1-inch margins; ~40–45 pp incl. everything; single-blind |
| QJE | Similar to AER; online appendix as a separate PDF |
| Econometrica | Own `ecta` class; strict formatting |
| REStud | `restud` class; figures at the end |
| JPE | Chicago bibliography; standard article class |

For anonymous submissions, remove author names and identifying self-citations,
use `\thanks{}` sparingly, and `\date{}` to suppress the date. Count words with
`texcount paper.tex`, but note top-5 journals state length in pages: AER ~40–45,
Econometrica and REStud cap at 45 (12pt, 1.5 spacing), QJE and JPE set no hard
limit. A 40-page double-spaced manuscript is roughly 10,000 words. Online
appendices get their own file and title page, cross-referenced as "see Online
Appendix Table A1."

## Common pitfalls

Floats landing far from the text: use `[t]` or `[!htbp]`, with `float` and `[H]`
as a last resort; placing all exhibits at the end sidesteps it for submissions.
Overfull boxes: check the log. Tables too wide: restructure with fewer columns or
abbreviated headers, or split into panels — do not `\resizebox` down to
illegible. Missing references: run BibTeX then LaTeX twice, or `latexmk -pdf`.

## Beamer

```latex
\documentclass{beamer}
\usetheme{metropolis}
\setbeamertemplate{navigation symbols}{}
```

One idea per slide, `\pause` sparingly. Put backup slides after `\appendix` under
a "Backup Slides" frame and link to them with
`\hyperlink{backup1}{\beamerbutton{Detail}}`.

---

# Part XI — Checks

## Before you call a draft done

Read it back and ask:

- Do three or more sentences in a row land at nearly the same length and shape?
- Is a transition word doing work that juxtaposition already did?
- Does any contrast follow the "not X, but Y" template without a real contrast
  under it?
- Are the paragraphs all the same size? Every section? A bulleted list where the
  ideas actually connect?
- Any tell-word from Part II still sitting there?
- Does a sentence merely restate its neighbor?
- Read one paragraph aloud in your head. Does it sound like a person thinking, or
  a template being filled?

Revise where the answer is yes. Leave the rest alone. Do not rewrite a working
sentence to prove you were here.

Then the substance:

- [ ] Central contribution stated concretely in paragraphs 1–3 of the
      introduction
- [ ] Main results in the introduction, with magnitudes
- [ ] No needless passive voice in prose (search "to be" + past participle — "was
      estimated," "is shown," "are reported" — and "by"-agent phrases; not every
      "is"/"are," which also mark present tense)
- [ ] No throat-clearing before the main point
- [ ] Literature review tells a story, not a list
- [ ] Every table has a self-contained caption with the SE/clustering
      specification
- [ ] Every number in every table is discussed in the text
- [ ] Standard errors reported for every important number
- [ ] Identification explained in economic terms
- [ ] Conclusion under one page, projecting confidence, no generic caveats dump
- [ ] Abstract under 150 words and concrete
- [ ] Paper within the target journal's length
- [ ] All Greek letters and notation defined by name
- [ ] No "illustrative" empirical work
- [ ] No abbreviated author names
- [ ] Pre-trends shown visually for DiD; RD plot shown for RDD
- [ ] Heterogeneity results pre-specified and multiple-testing-aware
- [ ] Mechanisms section tests channels rather than speculating
- [ ] Data availability and replication information stated
- [ ] Every appendix item referenced from the main text
- [ ] Title under 15 words, naming treatment and outcome (or the mechanism, for
      theory)
- [ ] Propositions carry economic intuition before their formal proofs
- [ ] Descriptive statistics table present, variables defined in the notes
- [ ] Every equation introduced verbally before display, every variable defined
      after

## Reviewing a draft

Three passes, each with its own standard.

**The methodologist.** Identification explained in plain language before the
equations. The key identifying assumption stated and defended. Threats to
validity — selection, omitted variables, reverse causality — listed and
addressed. Standard errors accounting for clustering, heteroskedasticity, or
serial correlation. Robustness across alternative specifications, samples, and
definitions. Where applicable: first-stage F (IV), parallel trends (DiD),
bandwidth sensitivity (RDD). Pre-registration status disclosed or its absence
justified. Sample size adequate for the claimed precision.

**The field expert.** Contribution positioned against the 3–5 closest papers. A
fair literature review that cites disagreeing work, not only supporters. Results
economically significant, with effect sizes in context. Institutional details
accurate and sufficient. Policy implications warranted by the evidence, with no
overclaiming. External validity discussed honestly. Data sources described well
enough to judge quality.

**The writing critic.** Active voice throughout. Concrete language with
magnitudes. No throat-clearing at paragraph openings. Tables readable alone.
Figures with informative titles and axis labels. Every word earning its place, no
repetition across sections. Paragraphs opening with a claim, not a citation.
Transitions that feel motivated. And every tell in Part II.

Score out of 100 — title 10, abstract 10, introduction 20, identification 15,
results presentation 15, writing quality 15, tables and figures 10, conclusion 5.
Roughly: 90+ ready for a top-5 submission; 80–89 a strong draft needing minor
revisions; 70–79 a solid working paper needing another round; 60–69 major
structural or methodological gaps; below 60, rethink the framing or the
identification before rewriting.

Prioritize: the three most impactful changes first, then the minor ones. For each
issue, say what is wrong, why it matters, and how to fix it with a concrete
example.

## Journal fit

Ask whether the question is of broad interest or primarily a subfield's; whether
the paper makes a methodological contribution or applies known methods; whether
the setting is one country or speaks to a universal mechanism; and how large the
likely audience is — would seminar attendees outside your field engage?

- *AER*: broad interest, clean identification, well written, important question.
- *QJE*: strong narrative, big question, often historical or institutional depth;
  rewards ambitious scope.
- *Econometrica*: methodological novelty required — a new estimator, theoretical
  result, or structural model.
- *REStud*: technically rigorous; rewards theoretical or structural contributions
  alongside empirical work.
- *JPE*: clean empirical design, interesting question, concise writing.

Decision rule: if the paper's main appeal is "interesting result in domain X"
rather than "new insight about how economies work," target the top field journal.
A well-cited field journal paper beats a desk-rejected top-5 submission.

---

*This guide merges two sources. The economics content synthesizes 50+ guides by
working economists — Cochrane, McCloskey, Shapiro, Head, Bellemare, Goldin and
Katz, Glaeser, Kremer, Nikolov, Schwabish, Evans, Dudenhefer, and others —
collected by Lu Han (github.com/hanlulong/econ-writing-skill). The prose
standards in Part II come from the `human-write` skill.*
