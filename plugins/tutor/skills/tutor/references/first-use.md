# First use: check the setup

Run each check, tell the user in one line what it is for, and fix what you
can. Ask the user only for what you cannot do (installing with brew needs
their go-ahead; keys are theirs).

| Check | Command | What it means | Fix |
|---|---|---|---|
| The repository | `test -d ~/repos/tutors` | Where every tutor lives | `git clone https://github.com/kerryback/tutor-starter ~/repos/tutors` (ask first) |
| The Python environment | `test -x ~/repos/tutors/.venv/bin/python` | The programs the tutors run on | `scripts/setup.sh` (also installs each tutor's own packages) |
| The voice | `command -v espeak-ng` | Needed to turn text into speech | `brew install espeak-ng` |
| The page tests | `command -v node` | Needed to test the web pages | `brew install node` |
| The API key | `[ -n "${ANTHROPIC_API_KEY:-}${ANTHROPIC_KEY:-}" ]` | The tutor's model, for local runs and evals | The user sets it in their shell |
| Deploying (only before a deploy) | `koyeb profile 2>/dev/null` | Koyeb runs the tutors | `koyeb login` |

Then run `scripts/test.sh` and report the result in one line ("All tests pass:
the setup works."). If a test fails, find out why before building anything.
