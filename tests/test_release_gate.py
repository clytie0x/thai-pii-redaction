"""scripts/check_release.py is the gate release.yml runs before building a
wheel: VERSION, the CHANGELOG section, and the git tag must agree, or nothing
is published. Pure stdlib so it runs before any pip install."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_release", ROOT / "scripts" / "check_release.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "VERSION").write_text("1.2.3\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n## [1.2.3] - 2026-09-01\n\n### Fixed\n\n- a thing\n\n"
        "## [1.2.2] - 2026-08-01\n\n- older\n",
        encoding="utf-8",
    )
    return tmp_path


def test_happy_path_returns_no_problems_and_the_notes(repo):
    cr = _load()
    assert cr.check(repo, expect_tag="v1.2.3", require_dated=True) == []
    notes = cr.release_notes(repo, "1.2.3")
    assert notes.startswith("## amprang 1.2.3 (2026-09-01)")
    assert "- a thing" in notes
    assert "older" not in notes


def test_tag_must_equal_v_plus_version(repo):
    cr = _load()
    problems = cr.check(repo, expect_tag="v1.2.4", require_dated=True)
    assert any("v1.2.4" in p and "1.2.3" in p for p in problems)


def test_version_must_be_semver(repo):
    cr = _load()
    (repo / "VERSION").write_text("1.2\n", encoding="utf-8")
    assert any("semver" in p.lower() for p in cr.check(repo))


def test_changelog_section_must_exist(repo):
    cr = _load()
    (repo / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    assert any("CHANGELOG" in p for p in cr.check(repo))


def test_unreleased_section_is_fine_for_ci_but_not_for_a_tag(repo):
    cr = _load()
    (repo / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.2.3] - unreleased\n\n- pending\n", encoding="utf-8"
    )
    assert cr.check(repo) == []
    assert any("dated" in p for p in cr.check(repo, require_dated=True))


def test_real_repo_passes_the_ci_form_of_the_gate():
    cr = _load()
    assert cr.check(ROOT) == []


def test_main_exit_codes(repo, capsys):
    cr = _load()
    assert cr.main(["--root", str(repo), "--expect-tag", "v1.2.3", "--notes"]) == 0
    assert "## amprang 1.2.3" in capsys.readouterr().out
    assert cr.main(["--root", str(repo), "--expect-tag", "v0.0.1"]) == 1


@pytest.mark.skipif(sys.platform == "win32", reason="exec bit irrelevant on Windows")
def test_script_has_no_third_party_imports():
    text = (ROOT / "scripts" / "check_release.py").read_text(encoding="utf-8")
    assert "import amprang" not in text and "import requests" not in text
