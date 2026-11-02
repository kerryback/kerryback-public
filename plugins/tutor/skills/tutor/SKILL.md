---
name: tutor
description: Use when the user wants a voice whiteboard tutor for a topic they teach ("make a tutor for <topic>", "build a voice tutor", "turn my slides or notebooks into a tutor"), or wants to change, test, evaluate, review or redeploy an existing tutor in ~/repos/tutors (such as the binomial tutor).
---

# Building voice whiteboard tutors

A tutor is a voice whiteboard app that teaches one topic in modules: it talks,
writes on a board, and checks the student's answers with tools. Every tutor
lives in ~/repos/tutors and runs the same engine. The user is a teacher who
has never built an app. They decide the content; you do the building.

## The stops

You build the whole tutor first, then work moves through fixed stops. Each
one is a gate: nothing after it happens until the user approves it.

| Stop | You show | The user | Reference |
|---|---|---|---|
| First use | the setup checks and a green `scripts/test.sh` | fixes what you cannot | references/first-use.md |
| Build | nothing: you read the sources, design the modules and build the tutor | agrees the name and sources, answers any question that blocks the build | references/build.md |
| 1 Review | the built tutor on the review page (intros, plots, examples, mistakes, scripts on request) | edits, listens, asks for changes (structural ones too), approves | references/build.md, references/review-json.md |
| 2 Try it | the tutor running locally | tries it, reports problems | references/try-and-evals.md |
| Evals | the eval results in plain words | approves the cost first | references/try-and-evals.md |
| Deploy | the live site | gives the go-ahead first | references/deploy.md |

For a tutor that already exists, read references/later-visits.md.

Read the reference for a stop when you reach it, not before.

## Rules

- Agree the folder name and check every source path before you build.
- No local run before the user has seen and approved the intros on the review page.
- No eval run without saying the cost (about $0.50) and getting a yes.
- No deploy, push, domain or DNS change without the user's go-ahead.
- Every number the tutor says comes from a tool. The tutor never computes in its head.
- Lessons never depend on a network. Worked examples and exercises use data
  frozen in `<tutor>/snapshot/`. Live data, if the topic wants it, is only in a
  last module, and that module says plainly when the source fails.
- If a data source fails when you download the snapshot, stop and ask. Never
  swap in another source or made-up numbers.
- If a source the user names is missing or at another path, say so and ask
  before you clone, download or substitute anything.
- Build on the user's own code where it exists (name the file and function),
  and test the tutor's tools against it.
- The engine and `instructions/` are shared by every tutor. Do not restate
  their rules in a tutor's files. A change there is a change to every tutor:
  run every tutor's tests and say so (references/later-visits.md).

## Talking to the user

- Say what each step does, why, and what the user does next. Short, direct
  sentences in active voice. No bold.
- Name files by what they are ("the module intros", `module-intros.md`) the
  first time.
- When you stop at a stop, end with the one thing you need from the user.

## Where things live

| Path | What it is |
|---|---|
| `~/repos/tutors/README.md` | The layout, the scripts and the Koyeb settings |
| `engine/`, `instructions/`, `evals/` | Shared by every tutor |
| `binomial/` | The finished example tutor: copy its patterns |
| `<tutor>/review.json` | The plan and the code explanations the review page shows |
| `scripts/` | `setup.sh`, `test.sh`, `review.sh`, `run.sh`, `eval.sh`, `deploy.sh`, `deploy-all.sh` |
