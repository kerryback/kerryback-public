# critique

Review work Claude produced, then say what to do about it.

Claude spawns reviewer subagents that read the work from different angles,
challenges what they find before showing you any of it, and publishes an HTML
guide laying out the alternative routes forward.

## Install

```
/plugin marketplace add kerryback/kerryback-public
/plugin install critique@kerryback-public
```

Then `/critique`, optionally with a file path or a description of what to look
at. With no argument it critiques the most recent substantial thing Claude
produced in the conversation.

## The reviewers

| reviewer | asks |
| --- | --- |
| Correctness & completeness | Are the facts, logic, and maths right? Does every number trace back to the file that produced it? |
| Clarity & persuasiveness | Is the structure sound? What's buried, redundant, or confusing? |
| Devil's advocate | What would a hostile referee say? Does the code do what the document claims it does? |
| Referee | Does the evidence support the central claim, at the precision claimed? |

The first three always run, in parallel, read-only. The referee lane runs on
academic papers — a manuscript, thesis chapter, or job market paper — and Claude
asks before adding it, because when the `econ-review` skill is installed that
lane hands the paper to it, and econ-review is a heavy package that can take
longer than the other three combined.

Two of the lanes are pointed at the artifacts rather than the prose. Reviewing a
document against itself finds typos; reviewing it against the code and data that
produced it finds the number that no longer matches its script.

## What holds the panel to a standard

Every reviewer works to the same evidence bar, adapted from Lu Han's
`econ-review`:

- A finding needs typed evidence with a locator — a quote, a table cell, a
  figure feature, a file and line, a computation actually run, or a *checked*
  absence naming what was searched.
- It needs a consequence specific to this work, a proportionate repair, and a
  statement of what would prove it wrong. Miss any of those and it is a note,
  not a finding.
- Severity tracks the verified consequence, never how alarming the words sound
  or how many times something recurs.
- A disclosed limitation with claims that stay inside it is not a defect. A
  missing fashionable check is not a flaw.

Then Claude argues with the reviewers. Every critical and major finding gets the
strongest reply its author would give, and Claude goes looking through the
appendix, the exhibits, and the code for the thing that defeats it. Findings that
do not survive never reach you.

## The guide

The deliverable is an HTML page, published as an artifact so you can keep the
link and send it to coauthors. It leads with the verdict and with what is worth
preserving, then lays out the paths.

The paths are the point. Different repairs are usually alternatives, not a
to-do list — narrow the claim, run one decisive check, reframe the contribution,
redesign, or ship as is — and a review that stacks them into a cumulative
checklist does real harm. The guide puts them side by side with what each costs,
what it buys, and what it closes, and marks a recommendation. You still choose.

Below that: the ranked findings with their evidence, and an explicit account of
what was checked and what was not, so "we looked and it was fine" is
distinguishable from "we did not look."

## Cost

Heavyweight by design. Each subagent reads the work in full, and the challenge
pass re-reads the source looking for refutations, so a critique costs several
times a single-pass review. That is the point — independent readings catch what
one pass rationalizes away — but it is not the thing to run on a paragraph.

After you take a path, it offers a second pass, which also checks that the
revision did not drop a caveat while answering a criticism. That is the most
common way a critique makes work worse.
