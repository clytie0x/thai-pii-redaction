"""AIFT deployment entrypoint around the shared FastAPI application."""

from app.access_logging import install_uvicorn_access_log_filter

install_uvicorn_access_log_filter()

from aift_auth import AuthGateway  # noqa: E402
from aift_report_policy import install_hosted_report_policy  # noqa: E402

install_hosted_report_policy()

from app.server import app as core_app  # noqa: E402

app = AuthGateway(core_app)
