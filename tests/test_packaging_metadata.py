"""The setuptools package list is explicit, so a new subpackage is silently
dropped from any wheel until someone adds it by hand. Source-tree tests never
see that: they import from the repo root, where sys.path makes the omission
invisible."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_source_package_is_declared_for_distribution():
    declared = set(
        tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"][
            "packages"
        ]
    )
    found = {
        ".".join(init.parent.relative_to(ROOT).parts)
        for init in (ROOT / "amphrang").rglob("__init__.py")
    }
    assert found <= declared, f"missing from pyproject packages: {sorted(found - declared)}"


def test_bundled_font_ships_with_its_ofl_license():
    """IBM Plex is SIL OFL-1.1, which requires the license text to travel with
    the font file. The license must sit next to the TTF and be covered by the
    same package-data glob, or an installed wheel carries the font alone."""
    fonts_dir = ROOT / "amphrang" / "engine" / "fonts"
    assert (fonts_dir / "IBMPlexSansThaiLooped-Regular.ttf").is_file()
    ofl = fonts_dir / "OFL-1.1.txt"
    assert ofl.is_file(), "amphrang/engine/fonts/OFL-1.1.txt is missing"
    assert "SIL OPEN FONT LICENSE" in ofl.read_text(encoding="utf-8")

    package_data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"][
        "setuptools"
    ]["package-data"]["amphrang.engine"]
    assert any(ofl.relative_to(fonts_dir.parent).match(glob) for glob in package_data), (
        f"no package-data glob in {package_data} covers fonts/OFL-1.1.txt"
    )
