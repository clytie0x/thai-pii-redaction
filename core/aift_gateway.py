"""AIFT deployment entrypoint around the shared FastAPI application."""

import os

from aift_hosted3.runtime import require_single_worker

require_single_worker()

from app.access_logging import install_uvicorn_access_log_filter  # noqa: E402

install_uvicorn_access_log_filter()

from aift_auth import AuthGateway  # noqa: E402
from aift_hosted3.legacy_roundtrip import install_legacy_roundtrip_admission  # noqa: E402
from aift_hosted3.overlay import Hosted3Overlay  # noqa: E402
from aift_report_policy import install_hosted_report_policy  # noqa: E402

install_hosted_report_policy()

from app import server as _server  # noqa: E402

# Vendored call sites ask for the audit directory before passing it to the
# audit writer. In hosted stdout mode the writer never touches that path, so
# do not try to create `/app/logs` on the intentionally read-only rootfs.
if os.environ.get("AIGUARD_AUDIT_STDOUT") == "1":
    _server._get_audit_log_dir = lambda: "/tmp"  # type: ignore[attr-defined]

core_app = _server.app

hosted3_overlay = Hosted3Overlay(core_app)
install_legacy_roundtrip_admission(core_app, hosted3_overlay.provider_queue)
app = AuthGateway(hosted3_overlay)
