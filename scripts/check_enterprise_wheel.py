"""Check actual wheel contents before installed-runtime acceptance."""

import argparse
import re
import zipfile
from pathlib import Path

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
    args = parser.parse_args(argv)
    with zipfile.ZipFile(args.wheel) as archive:
        names = set(archive.namelist())
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
    print("Enterprise wheel contains its caller path, web assets, fonts and migrations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
