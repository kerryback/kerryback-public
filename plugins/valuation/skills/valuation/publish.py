"""Publish a built valuation page to a Quarto site repo, without stopping to ask.

    python publish.py <page.html> [--slug aapl] [--homepage ~/repos/homepage]

Copies the page to ``<homepage>/<slug>.html`` and ``<homepage>/docs/<slug>.html``
(the copy GitHub Pages serves), lists ``<slug>.html`` under
``project.resources`` in ``_quarto.yml`` so a later ``quarto render`` keeps it,
then commits and pushes only those paths.

It never runs ``quarto render`` and never stages anything it did not write, so
uncommitted work already in the repo is left alone rather than swept into the
commit. If ``_quarto.yml`` itself had uncommitted changes, it is edited but not
committed, and the result says so. Every outcome is reported, none raises: a
failed push is a line in the report, not a stopped run.

If the homepage repo does not exist, nothing is done and the report says the
page was not published. This step is for a site that already has such a repo
(the default is Kerry Back's ~/repos/homepage, served at kerryback.com); for
anyone else the run ends with the page local.

Build the page without ``--live`` first: the reload poller has no server to
reach on the web.
"""

import os
import re
import shutil
import subprocess

HOMEPAGE = os.path.expanduser("~/repos/homepage")
SITE = "https://www.kerryback.com"


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def _dirty(repo, path):
    return bool(_git(repo, "status", "--porcelain", "--", path).stdout.strip())


def list_resource(config_path, entry):
    """Add ``entry`` to ``project.resources`` unless present. True if added."""
    with open(config_path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    if any(re.fullmatch(rf"\s*-\s*['\"]?{re.escape(entry)}['\"]?\s*", ln) for ln in lines):
        return False
    start = next((i for i, ln in enumerate(lines) if re.fullmatch(r"  resources:\s*", ln)), None)
    if start is None:
        raise ValueError(f"no project.resources list in {config_path}")
    last = start
    for i in range(start + 1, len(lines)):
        if re.match(r"    - ", lines[i]):
            last = i
        elif lines[i].strip() and not lines[i].startswith("    "):
            break
    lines.insert(last + 1, f"    - {entry}")
    with open(config_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return True


def publish(page, slug=None, homepage=HOMEPAGE, push=True):
    """Copy, list, commit and push. Returns a list of report lines."""
    homepage = os.path.expanduser(homepage)
    slug = slug or os.path.splitext(os.path.basename(page))[0]
    name = f"{slug}.html"
    report = []

    config = os.path.join(homepage, "_quarto.yml")
    if not (os.path.isdir(os.path.join(homepage, ".git")) and os.path.isfile(config)):
        report.append(f"not published: no Quarto site repo at {homepage}; the page stays local")
        return report
    config_was_dirty = _dirty(homepage, "_quarto.yml")

    shutil.copyfile(page, os.path.join(homepage, name))
    os.makedirs(os.path.join(homepage, "docs"), exist_ok=True)
    shutil.copyfile(page, os.path.join(homepage, "docs", name))
    report.append(f"copied to {name} and docs/{name}")

    paths = [name, f"docs/{name}"]
    if list_resource(config, name):
        report.append(f"listed {name} under project.resources")
        if config_was_dirty:
            report.append("NOT committing _quarto.yml: it already had uncommitted "
                          "changes. Commit it yourself so a render keeps the page.")
        else:
            paths.append("_quarto.yml")

    _git(homepage, "add", "--", *paths)
    if not _git(homepage, "diff", "--cached", "--quiet", "--", *paths).returncode:
        report.append("nothing changed since the last publish; no commit")
        return report
    msg = f"Publish the {slug.upper()} two-stage DCF page"
    done = _git(homepage, "commit", "-m", msg, "--", *paths)
    if done.returncode:
        report.append("commit FAILED: " + (done.stderr or done.stdout).strip())
        return report
    report.append(f"committed: {msg}")

    if push:
        pushed = _git(homepage, "push")
        if pushed.returncode:
            report.append("push FAILED: " + pushed.stderr.strip())
            return report
        report.append(f"pushed; live at {SITE}/{name} within a minute or two")
    return report


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("page")
    ap.add_argument("--slug", help="file-name stem on the site; defaults to the page's")
    ap.add_argument("--homepage", default=HOMEPAGE)
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()
    for line in publish(args.page, args.slug, args.homepage, push=not args.no_push):
        print(line)
