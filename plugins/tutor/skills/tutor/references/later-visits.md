# Later visits: changing a tutor

Start with `scripts/test.sh <tutor>`, so you know the state before you change
anything.

| The user wants | Do |
|---|---|
| To change an intro, board line or objective | Open `scripts/review.sh <tutor>` (a tutor built before the review page has no `review.json`: write one with `stop` 2 from its files first), or edit `content/module-intros.md`; rerun the tests and update the prompt hash |
| To add or reorganize modules | Build the change as in references/build.md, update `review.json`, and show the review page |
| To add or fix a tool | Test it against the user's code first; update `topic.md`, the scripts and `review.json`'s code blocks |
| To check behavior | Evals (cost first), references/try-and-evals.md |
| To redeploy | references/deploy.md |

## Changing the shared parts

`engine/`, `instructions/` and `evals/` are shared by every tutor.

- Make the change only if it is right for every tutor. A need only one tutor
  has stays in that tutor's folder.
- Run `scripts/test.sh` (every tutor). A change to `instructions/` changes every
  tutor's prompt, so every pinned prompt test fails until updated: run each
  tutor's evals first (cost first), then update each hash.
- Tell the user which tutors the change reaches, then, with their go-ahead,
  `scripts/deploy-all.sh`. It tests every tutor and stops before deploying if
  one fails.
