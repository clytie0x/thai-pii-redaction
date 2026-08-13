"""AIFT deployment entrypoint around the shared FastAPI application."""

import os

from app.access_logging import install_uvicorn_access_log_filter

install_uvicorn_access_log_filter()

from aift_auth import AuthGateway  # noqa: E402
from aift_report_policy import install_hosted_report_policy  # noqa: E402

install_hosted_report_policy()

from app import server as _server  # noqa: E402

# Vendored call sites ask for the audit directory before passing it to the
# audit writer. In hosted stdout mode the writer never touches that path, so
# do not try to create `/app/logs` on the intentionally read-only rootfs.
if os.environ.get("AIGUARD_AUDIT_STDOUT") == "1":
    _server._get_audit_log_dir = lambda: "/tmp"  # type: ignore[attr-defined]

core_app = _server.app

app = AuthGateway(core_app)
