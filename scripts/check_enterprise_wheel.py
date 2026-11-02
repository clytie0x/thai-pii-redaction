"""Check actual wheel contents before installed-runtime acceptance."""

import argparse
import re
import zipfile
from email.parser import BytesParser
from pathlib import Path

DISTRIBUTION = "thai-pii-redaction-core"
REQUIRED = {
    "app/enterprise/__main__.py",
    "app/enterprise/server.py",
    "app/enterprise/auth.py",
    "app/enterprise/static/index.html",
    "app/enterprise/static/app.js",
    "app/enterprise/static/style.css",
    "app/enterprise/static/tokens.css",
    "app/enterprise/static/fonts/IBMPlexSansThaiLooped-Regular.woff2",
    "pii_redactor/governance/migrations/001_foundation.sql",
    "pii_redactor/governance/migrations/002_registry.sql",
    "pii_redactor/governance/migrations/003_staff_sessions.sql",
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument(
        "--expect-version",
        default=(Path(__file__).resolve().parents[1] / "VERSION")
        .read_text(encoding="utf-8")
        .strip(),
    )
    args = parser.parse_args(argv)
    with zipfile.ZipFile(args.wheel) as archive:
        members = archive.namelist()
        names = set(members)
        if len(names) != len(members):
            print("Duplicate archive member paths are not accepted")
            return 1
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        expected_metadata = (
            f"{DISTRIBUTION.replace('-', '_')}-{args.expect_version}.dist-info/METADATA"
        )
        if metadata_names != [expected_metadata]:
            print("Core distribution identity is missing or ambiguous")
            return 1
        metadata = BytesParser().parsebytes(archive.read(expected_metadata))
        if metadata.get_all("Name") != [DISTRIBUTION] or metadata.get_all("Version") != [
            args.expect_version
        ]:
            print("Core distribution metadata does not match the selected identity/version")
            return 1
        missing = sorted(REQUIRED - names)
        if missing:
            print("Missing enterprise package resources: " + ", ".join(missing))
            return 1
        tokens = archive.read("app/enterprise/static/tokens.css").decode("utf-8")
        for name in re.findall(r'url\(["\']?([^"\')]+)', tokens):
            if "app/enterprise/static/" + name not in names:
                print("A referenced enterprise font is missing")
                return 1
        if not any(n.endswith("/licenses/OFL-1.1.txt") for n in names):
            print("Font license text is missing")
            return 1
        if any(Path(n).suffix in {".key", ".env"} or ".superpowers/" in n for n in names):
            print("Unexpected private runtime resource in wheel")
            return 1
    print("Core wheel identity, enterprise caller path, web assets, fonts and migrations passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
