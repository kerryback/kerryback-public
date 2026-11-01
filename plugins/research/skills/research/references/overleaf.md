# Wiring an Overleaf project to `draft/`

Read this when a project has coauthors who write in Overleaf and coauthors who
do not. The goal is that neither group has to care about the other: Overleaf
people see a normal Overleaf project, git people see a normal git repo, and
exactly one person holds both.

## The shape

The Overleaf project mirrors `draft/` only — never the repo root. `tools/`,
`workspaces/` and `project/` have no business in a LaTeX project, and Overleaf's
flat single-branch model would make a mess of them.

Non-Overleaf coauthors change nothing. They keep using the git remote exactly as
before. One designated person runs the bridge. That is the whole trick for a
mixed team.

## What the bridge can and cannot do

Overleaf's git integration gives each project its own repo at
`https://git.overleaf.com/<project-id>`, push and pull both directions. It is a
premium feature, and the rule is generous: if the project owner has premium,
every collaborator on that project can use git.

Constraints that shape everything below:

- One branch only (`main` on new projects, `master` on old ones).
- Force push is prohibited outright. Not "discouraged" — the server rejects it.
- No tags, no submodules, no LFS, no symlinks, no exec bits.
- Renames arrive as delete-plus-create, so comment anchors die on rename.
- Mixing git pushes with tracked changes and comments is documented as causing
  data loss.

## Before you touch git

Get these decided first — they are cheap now and expensive after coauthors have
started commenting.

1. Name the main file `main.tex`. Overleaf picks its main document by name and
   cannot guess between `paper.tex` and `paper-appendix.tex`. Rename the `.bbl`
   and `.pdf` with it: LaTeX and BibTeX derive those from the job name, so the
   old ones become orphans the moment the renamed source compiles.
2. Stop tracking LaTeX build noise. Untrack `.aux`, `.log`, `.out`, `.blg`;
   they regenerate on every compile and would churn in every sync. Scope the
   ignore rules to the draft directory — a bare `*.log` will silently swallow run
   logs elsewhere in the repo, which is a trap that surfaces months later.
3. Move anything heavy that is not paper source out of the mirrored prefix.
   Referee reports, PDF page renders, review evidence. Subtree pushes the whole
   prefix; there is no per-file exclusion.
4. Check whether the `.tex` cross-reference each other (`\input`, `\include`,
   `xr`/`externaldocument`) before renaming anything.

## Authentication

Do not handle the user's token. Have them run one authenticating command in
their own terminal:

```
git ls-remote https://git@git.overleaf.com/<project-id>
```

Username is `git` (already in the URL); the password is a token from Overleaf
Account Settings. Tokens expire after a year, ten per account. On macOS the
system gitconfig sets `credential.helper=osxkeychain`, so it is cached once and
every later push and pull — including yours — runs without prompting.

To test whether credentials are cached without hanging on a prompt:

```
GIT_TERMINAL_PROMPT=0 git ls-remote <url>
```

## Bootstrapping the join

This is the part that is not obvious. The Overleaf project starts as an
unrelated root commit (a stub `main.tex`), and force push is prohibited, so the
stub must become an ancestor of anything you push.

`git subtree add --prefix=draft overleaf main` is the normal way to establish
that ancestry, but it refuses to run when the prefix already exists — and in a
project that has been going for a while, `draft/` always exists.

So build the join commit `subtree add` would have written, by hand:

```bash
MAINLINE=$(git rev-parse HEAD)
SPLIT=$(git rev-parse overleaf/main)          # after: git fetch overleaf

git merge -s ours --no-commit --allow-unrelated-histories $SPLIT
git commit -F - <<EOF
Add 'draft/' from commit '$SPLIT'

git-subtree-dir: draft
git-subtree-mainline: $MAINLINE
git-subtree-split: $SPLIT
EOF
```

`-s ours` keeps your tree byte-identical — Overleaf's stub `main.tex` never
enters the repo — while recording the stub as a second parent. The three
trailers are what `git subtree split` greps for (`find_existing_splits`) to map
your history onto the Overleaf side; without them the split drops the stub and
the push is rejected as non-fast-forward.

Verify before pushing:

```bash
git diff $MAINLINE HEAD                       # must be empty: tree unchanged
git subtree split --prefix=draft -b overleaf-sync
git merge-base --is-ancestor $SPLIT overleaf-sync && echo "will fast-forward"
```

Then `git subtree push --prefix=draft overleaf main`. The stub `main.tex`
disappears in that push, which is what you want.

## Verify the round trip

Push, then fetch and list the remote tree to confirm what actually landed.
Then test the pull direction — with nothing new upstream it is a no-op that
still writes an empty merge commit, so reset it away and note the behavior.

If the draft compiles locally, compile it after any rename and check the page
count against whatever the project's state file records. A rename that breaks a
`\graphicspath` or a bibliography is silent until someone compiles.

## What to tell the coauthors

Put this in `protocols.html` (or whatever the human-facing doc is), not only in
`CLAUDE.md`, and lead with the hazard rather than the mechanics:

- Turn track changes off. This is the one that costs real work — edits vanish
  silently rather than raising a conflict anyone can see.
- Invite with Edit access, not Review access. Review makes every edit a
  suggestion, which is tracked changes switched on by default.
- Prefer email invitations over link sharing: a named account is what lets a
  coauthor use git directly under the owner's premium plan, and it can be
  revoked per person.
- More than one collaborator per project is itself a premium feature. Confirm
  the plan covers the number of coauthors before assuming the invitations land.
- Claude does the syncing, per `CLAUDE.md`. Nobody needs to learn `git subtree`
  to write a paper.
