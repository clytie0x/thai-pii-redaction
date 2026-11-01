"""Offline migration/enrollment and a guarded enterprise server entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from app.enterprise.settings import Settings, _secret_file
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import Enrollment
from pii_redactor.governance.store import Store


def _store():
    return Store(
        _secret_file(os.environ["AIGUARD_ENTERPRISE_DB_FILE"], "dsn"),
        UUID(os.environ["AIGUARD_ENTERPRISE_ORGANIZATION_ID"]),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="Apply migrations with the offline migration credential")
    commands.add_parser("check", help="Check schema and enrollment without DDL")
    enroll = commands.add_parser("enroll", help="Enroll initial distinct staff authorities offline")
    enroll.add_argument("--file", type=Path, required=True)
    serve = commands.add_parser("serve", help="Run the authenticated staff application")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    code = "configuration_invalid"
    try:
        if args.command == "serve":
            settings = Settings.from_env()
            if not 1 <= args.port <= 65535 or (
                settings.development and args.host not in {"127.0.0.1", "localhost", "::1"}
            ):
                raise GovernanceError("configuration_invalid")
            import uvicorn

            from app.access_logging import uvicorn_log_config
            from app.enterprise.server import create_app

            uvicorn.run(
                create_app(settings),
                host=args.host,
                port=args.port,
                log_config=uvicorn_log_config(),
                log_level="warning",
                access_log=False,
            )
        elif args.command == "migrate":
            _store().migrate()
            print(
                "Enterprise migrations applied; staff enrollment and runtime checks remain separate."
            )
        elif args.command == "check":
            _store().check_ready()
            print(
                "Enterprise schema and enrollment ready; this is not an IdP/browser/deployment check."
            )
        else:
            if args.file.stat().st_size > 262144:
                raise ValueError
            values = json.loads(args.file.read_text(encoding="utf-8"))
            if not isinstance(values, list):
                raise ValueError
            _store().bootstrap([Enrollment.model_validate(v) for v in values])
            print("Initial distinct staff authorities enrolled; no web setup endpoint was opened.")
        return 0
    except GovernanceError as error:
        code = error.code
    except ImportError:
        code = "enterprise_dependency_unavailable"
    except (KeyError, ValueError, TypeError, OSError, ValidationError):
        pass
    print(code, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
