# First use: check the setup

Run each check, tell the user in one line what it is for, and fix what you
can. Ask the user only for what you cannot do (installing a program needs
their go-ahead; keys are theirs).

The tutors run on macOS, Linux, and Windows. On Windows, Claude Code's shell
is Git Bash, and the scripts run there. Find the system first: `uname -s`
gives `Darwin` (macOS), `Linux`, or `MINGW...`/`MSYS...` (Windows).

| Check | Command | What it means | Fix |
|---|---|---|---|
| The repository | `test -d ~/repos/tutors` | Where every tutor lives | `git clone https://github.com/kerryback/tutor-starter ~/repos/tutors` (ask first) |
| Python 3.11 or later | `scripts/setup.sh` finds it, or says it is missing | Runs the tutors | The user installs it from python.org (on Windows, with "Add python.exe to PATH" ticked) |
| The Python environment | `test -x ~/repos/tutors/.venv/bin/python -o -x ~/repos/tutors/.venv/Scripts/python.exe` | The programs the tutors run on | `scripts/setup.sh` (also installs each tutor's own packages) |
| The page tests | `command -v node` | Needed to test the web pages | Install Node (table below) |
| The API key | `[ -n "${ANTHROPIC_API_KEY:-}${ANTHROPIC_KEY:-}" ]` | The tutor's model, for local runs and evals | The user sets it in their shell |
| Deploying (only before a deploy) | `railway whoami` | Railway runs the tutors; this says who is signed in | Install the CLI (table below) if `command -v railway` finds nothing, or if `railway --version` is below 5. Then the user runs `railway login` (it opens their browser) |

The voice needs no install: espeak-ng comes with the Python packages.

Install Node with the system's package manager:

| macOS | Windows | Linux (Debian, Ubuntu) |
|---|---|---|
| `brew install node` | `winget install -e --id OpenJS.NodeJS.LTS` | `sudo apt install nodejs npm` |

On another Linux, use its package manager (`dnf`, `pacman`). `sudo` asks for
the user's password, so the user runs that command. If the package manager is
missing (a Mac without Homebrew, a Windows without winget), say so and give
nodejs.org instead of installing a package manager. After a Windows install,
the user opens a new terminal so that `command -v node` finds it.

Install the Railway CLI the same way, with the user's go-ahead:

| macOS | Linux | Windows |
|---|---|---|
| `brew install railway` (`brew upgrade railway` for an old one) | `bash <(curl -fsSL railway.com/install.sh)` | `npm i -g @railway/cli` (needs Node 16 or later), or `scoop install railway` |

`npm i -g @railway/cli` also works on macOS and Linux, and is the way on a Mac
without Homebrew. A new Railway account starts on a 30-day trial with 1 GB of
RAM and a 0.5 GB volume. That is too small for a tutor, which needs about 0.9
GB of RAM and 0.5 GB for its speech models. Deploying needs the Hobby plan ($5
a month, with $5 of usage included), which the user chooses at railway.com.

## The voice

`voice` in `~/repos/tutors/site.toml` chooses who speaks: `"kokoro"` (the
default: free, runs with the tutor) or `"elevenlabs"` (paid; needs
`ELEVENLABS_API_KEY`). An ElevenLabs key in the shell is not used unless the
file says `"elevenlabs"`. Tell the user which voice is set, and change it only
when they ask.

Then run `scripts/test.sh` and report the result in one line ("All tests pass:
the setup works."). If a test fails, find out why before building anything.
