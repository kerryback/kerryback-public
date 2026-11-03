"""publish.py commits only what it wrote, and never stops to ask."""

import subprocess

import pytest

from publish import list_resource, publish

CONFIG = """project:
  type: website
  output-dir: docs
  render:
    - index.qmd
  resources:
    - bi2ai.html
    - jbss/**

website:
  title: ""
"""


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, check=True).stdout


@pytest.fixture
def site(tmp_path):
    repo = tmp_path / "homepage"
    repo.mkdir()
    (repo / "_quarto.yml").write_text(CONFIG)
    (repo / "index.qmd").write_text("hello\n")
    git(repo, "init", "-q")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "add", ".")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    git(repo, "config", "user.name", "t")
    git(repo, "config", "user.email", "t@t")
    page = tmp_path / "build" / "aapl.html"
    page.parent.mkdir()
    page.write_text("<html>page</html>")
    return repo, page


def test_the_page_is_listed_once_under_resources(tmp_path):
    cfg = tmp_path / "_quarto.yml"
    cfg.write_text(CONFIG)
    assert list_resource(str(cfg), "aapl.html")
    assert not list_resource(str(cfg), "aapl.html")
    text = cfg.read_text()
    assert text.count("aapl.html") == 1
    assert text.index("- jbss/**") < text.index("- aapl.html") < text.index("website:")


def test_publish_commits_only_its_own_paths(site):
    repo, page = site
    (repo / "index.qmd").write_text("someone else's edit\n")
    report = publish(str(page), homepage=str(repo), push=False)
    assert any(r.startswith("committed") for r in report)
    changed = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert sorted(changed) == ["_quarto.yml", "aapl.html", "docs/aapl.html"]
    assert "index.qmd" in git(repo, "status", "--porcelain")


def test_a_dirty_config_is_edited_but_not_committed(site):
    repo, page = site
    (repo / "_quarto.yml").write_text(CONFIG + "# local note\n")
    report = publish(str(page), homepage=str(repo), push=False)
    assert any("NOT committing _quarto.yml" in r for r in report)
    changed = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert "_quarto.yml" not in changed


def test_republishing_an_unchanged_page_makes_no_commit(site):
    repo, page = site
    publish(str(page), homepage=str(repo), push=False)
    report = publish(str(page), homepage=str(repo), push=False)
    assert any("no commit" in r for r in report)
