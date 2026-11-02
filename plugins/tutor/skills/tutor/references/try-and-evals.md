# Stop 2 and evals

## Stop 2: try it locally

- Start it in the background: `scripts/run.sh <tutor>` (port 8010, or pass
  another). It opens the browser.
- Tell the user: sign in with any email; the sign-in code is printed in the
  terminal, not emailed. The browser asks for the microphone.
- Suggest three things to try: a wrong answer with a known mistake, "just
  tell me the answer", and jumping to a later module from the menu.
- For each problem the user reports: reproduce it if you can, fix the tutor
  (or the shared part, see references/later-visits.md), rerun
  `scripts/test.sh <tutor>`, and restart the tutor.

## Evals

Evals play scripted students against the real model and check what the tutor
says and shows.

- Say the cost first (about $0.50 a run) and wait for a yes.
- Run `scripts/eval.sh <tutor>` (or one scenario: `scripts/eval.sh <tutor> <scenario>`).
  The results go to `evals/results/<stamp>-<tutor>.json`; the review page shows
  the latest count.
- Read the transcripts of every failed check. For each, decide whether the
  tutor is at fault (fix the content or tools) or the check is (fix the
  check, and say why). Report in plain words: what the student did, what the
  tutor did, which you fixed.
- A failure the shared rules cause in every tutor (the binomial tutor fails
  it too) is a shared-instructions issue: say so rather than patching one
  tutor.
