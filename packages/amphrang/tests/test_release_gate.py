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


def _write_surface(root, facade_names, manifest_names=None):
    """Minimal facade + manifest pair for the surface gate."""
    pkg = root / "amphrang"
    pkg.mkdir(exist_ok=True)
    body = ", ".join(repr(n) for n in facade_names)
    (pkg / "__init__.py").write_text(f"__all__ = [{body}]\n", encoding="utf-8")
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    names = facade_names if manifest_names is None else manifest_names
    (docs / "api-surface.txt").write_text(
        "# frozen public surface\n" + "".join(f"{n}\n" for n in names), encoding="utf-8"
    )


def _write_profile(root, token_names, documented_names=None):
    """Minimal TOKEN_LABEL + coverage-profile pair for the profile gate."""
    pkg = root / "amphrang" / "engine" / "anonymizer"
    pkg.mkdir(parents=True, exist_ok=True)
    body = ", ".join(f'"{n}": "label"' for n in token_names)
    (pkg / "token_generator.py").write_text(
        f"TOKEN_LABEL: dict[str, str] = {{{body}}}\n", encoding="utf-8"
    )
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    names = token_names if documented_names is None else documented_names
    rows = "".join(f"| `{n}` | label | basis | 1.000 | 1.000 |\n" for n in names)
    (docs / "pdpa-coverage.md").write_text(
        "# profile\n\n| data_type | label | basis | recall | precision |\n|---|---|---|---|---|\n"
        + rows,
        encoding="utf-8",
    )


def test_happy_path_returns_no_problems_and_the_notes(repo):
    cr = _load()
    assert cr.check(repo, expect_tag="v1.2.3", require_dated=True) == []
    notes = cr.release_notes(repo, "1.2.3")
    assert notes.startswith("## amphrang 1.2.3 (2026-09-01)")
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


# --- public-surface gate ----------------------------------------------------


def test_surface_gate_passes_when_manifest_matches(repo):
    cr = _load()
    _write_surface(repo, ["anonymize", "detect"])
    assert cr.check_surface(repo) == []


def test_surface_gate_fails_on_an_added_export(repo):
    cr = _load()
    _write_surface(
        repo, ["anonymize", "detect", "new_thing"], manifest_names=["anonymize", "detect"]
    )
    problems = cr.check_surface(repo)
    assert len(problems) == 1
    assert "new_thing" in problems[0]
    assert "api-surface.txt" in problems[0]


def test_surface_gate_fails_on_a_removed_export(repo):
    cr = _load()
    _write_surface(repo, ["detect"], manifest_names=["anonymize", "detect"])
    problems = cr.check_surface(repo)
    assert len(problems) == 1
    assert "anonymize" in problems[0]


def test_surface_gate_fails_when_the_manifest_is_missing(repo):
    cr = _load()
    _write_surface(repo, ["detect"])
    (repo / "docs" / "api-surface.txt").unlink()
    assert any("api-surface.txt" in problem for problem in cr.check_surface(repo))


def test_surface_gate_ignores_manifest_comments_and_order(repo):
    cr = _load()
    _write_surface(repo, ["detect", "anonymize"], manifest_names=["anonymize", "detect"])
    assert cr.check_surface(repo) == []


def test_real_repo_surface_matches_the_manifest():
    cr = _load()
    assert cr.check_surface(ROOT) == []


def test_main_fails_on_surface_drift(repo, capsys):
    cr = _load()
    _write_surface(repo, ["detect", "sneaky"], manifest_names=["detect"])
    assert cr.main(["--root", str(repo)]) == 1
    assert "sneaky" in capsys.readouterr().err


def test_main_exit_codes(repo, capsys):
    cr = _load()
    _write_surface(repo, ["detect"])
    _write_profile(repo, ["NAME"])
    assert cr.main(["--root", str(repo), "--expect-tag", "v1.2.3", "--notes"]) == 0
    assert "## amphrang 1.2.3" in capsys.readouterr().out
    assert cr.main(["--root", str(repo), "--expect-tag", "v0.0.1"]) == 1


@pytest.mark.skipif(sys.platform == "win32", reason="exec bit irrelevant on Windows")
def test_script_has_no_third_party_imports():
    text = (ROOT / "scripts" / "check_release.py").read_text(encoding="utf-8")
    assert "import amphrang" not in text and "import requests" not in text


# --- PDPA coverage-profile gate ---------------------------------------------


def test_profile_gate_passes_when_profile_matches(repo):
    cr = _load()
    _write_profile(repo, ["NAME", "PHONE"])
    assert cr.check_profile(repo) == []


def test_profile_gate_fails_on_a_type_missing_from_the_doc(repo):
    cr = _load()
    _write_profile(repo, ["NAME", "PHONE"], documented_names=["NAME"])
    problems = cr.check_profile(repo)
    assert len(problems) == 1
    assert "PHONE" in problems[0]
    assert "pdpa-coverage.md" in problems[0]


def test_profile_gate_fails_on_a_type_only_in_the_doc(repo):
    cr = _load()
    _write_profile(repo, ["NAME"], documented_names=["NAME", "GHOST_TYPE"])
    problems = cr.check_profile(repo)
    assert len(problems) == 1
    assert "GHOST_TYPE" in problems[0]


def test_profile_gate_fails_when_the_profile_is_missing(repo):
    cr = _load()
    _write_profile(repo, ["NAME"])
    (repo / "docs" / "pdpa-coverage.md").unlink()
    assert any("pdpa-coverage.md" in problem for problem in cr.check_profile(repo))


def test_real_repo_profile_matches_token_label():
    cr = _load()
    assert cr.check_profile(ROOT) == []
