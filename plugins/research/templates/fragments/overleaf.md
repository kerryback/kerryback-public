## Overleaf — the mirror of `draft/`

Some coauthors write in Overleaf and some do not. The ones who do not change
nothing: this repo stays the source of truth. The ones who do get an Overleaf
project that mirrors `draft/` and nothing else — `tools/`, `workspaces/` and
`project/` never go there.

Project `@@OVERLEAF_PROJECT@@`, wired as the `overleaf` remote. One person runs
the bridge; nobody else has to think about two remotes.

Pull Overleaf edits down, then push ours up:

```
git subtree pull --prefix=draft overleaf main
git subtree push --prefix=draft overleaf main
```

Always pull before you push. Overleaf rejects non-fast-forward pushes and forbids
`--force` outright, so a push that is behind simply fails. If nothing changed on
the Overleaf side the pull still writes an empty merge commit (`git subtree pull`
is `--no-ff`); `git fetch overleaf && git diff HEAD:draft overleaf/main` first if
you would rather not carry those.

Three things that will bite:

- Tracked changes and comments. Overleaf documents that mixing them with git
  pushes loses data. Whoever edits there accepts or rejects everything before a
  sync, or leaves track changes off. Invite coauthors with Edit access, never
  Review access — Review makes every edit a suggestion, which is the same hazard
  switched on by default.
- Renames. The bridge turns them into delete-plus-create, so a renamed file loses
  its Overleaf comment anchors. Rename before comments accumulate, not after.
- Direction. Figures and tables are built by code in this repo and flow to
  Overleaf only. Never accept an Overleaf-side change to `figures/` — rebuild it
  from the script instead, or provenance breaks.

`draft/` does not track `.aux`, `.log`, `.out` or `.blg`; they are ignored so
they do not clutter the Overleaf file tree. The ignore rules are scoped to
`draft/` on purpose — a bare `*.log` would swallow run logs elsewhere in the
repo. Anything heavy that is not paper source (referee reports, page renders)
belongs beside `draft/`, not inside it, or it syncs on every push.

The histories were joined by a hand-built `git subtree` commit. Do not rewrite
history through it or the mapping breaks and pushes stop fast-forwarding.

---
