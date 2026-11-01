## The two-build protocol — the thing that must not be compromised

Estimator agreement cannot vet a sample: two estimators reading one dataset agree
on whatever that dataset says, right or wrong. So the data build gets its own
independent-verification stage ahead of any analysis.

1. **Two independent builds.** The Analyst and the Replicator each construct the
   sample in their OWN code, from the raw sources — their own pulls, their own
   construction of every column. Never from a shared pre-built file.
2. **Reconcile.** Compare head to head: observation counts, summary statistics of
   every variable, and each screen's effect.
3. **Confirm — a hard gate.** Analysis does not begin until the two agree within
   tolerance. A gap in a count or a moment is a bug, not noise.
4. **Collapse to one.** Only after confirmation, delete one copy and run all
   downstream analysis on the single retained dataset.

Then each still implements the frozen spec in its own code, so the headline
numbers should converge.

**Never average two disagreeing builds.** A gap between two same-spec builds is a
coding bug or a spec hole: fix the code or tighten the spec. Disagreement that
survives a correct, identical spec IS the finding — surface it, never reconcile
it silently.

Check the boundary the protocol depends on:

```bash
python3 -m tools.provenance --independence
```

It lists every edge where a replicator script reads an analyst artifact or the
reverse. Reads of the canonical data are excluded — sharing that is the design.
Anything else is either a deliberate cross-test or an accidental coupling, and
the tool cannot tell which: say which, in the script's docstring.

---

## Spec-first empirics

When a round turns on a number, freeze the method BEFORE spawning any
implementer. Write it to `project/global/method_spec.md` and pin every choice
that could move the headline: sample and screens; variable definitions with
timing and lags; the estimator and every baseline's exact construction; the
learner and its hyperparameters; the cross-validation scheme, named explicitly;
winsorization; the evaluation frame and metric; the inference method.

The numeric parameters live in `workspaces/global/params.py` — import them rather
than retyping them, so a number can never differ because someone typed the wrong
year. Changing that file is a spec change and goes through the same gate.

The spec is frozen for the round. If an implementer flags a choice the spec did
not settle, do not let it stand on a private guess: resolve it, update the spec,
and re-spawn both implementers against the update.

---
