"""Compatibility-preserving queue admission for the vendored `/roundtrip`."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Iterator

from .authority import AuthorityContext
from .provider_queue import ProviderQueue


LEGACY_ROUNDTRIP_PATH = "/api/roundtrip"
_CURRENT_AUTHORITY: ContextVar[AuthorityContext | None] = ContextVar(
    "aiguard_legacy_roundtrip_authority",
    default=None,
)


@contextmanager
def legacy_roundtrip_authority(
    authority: AuthorityContext | None,
) -> Iterator[None]:
    """Bind request authority across FastAPI's copied thread context."""

    token = _CURRENT_AUTHORITY.set(authority)
    try:
        yield
    finally:
        _CURRENT_AUTHORITY.reset(token)


def _validate_legacy_roundtrip_semantics(request) -> None:
    """Keep vendored endpoint validation ahead of scheduler admission.

    FastAPI performs DTO/schema validation before it calls the endpoint, but
    the pinned handler deliberately keeps its value checks in the function
    body. The adapter must repeat those exact checks before it creates an
    internal queue record; otherwise an invalid legacy request could wait for a
    provider slot and turn into a compatibility-breaking ``rate_limited``.
    """

    from app.http_v2 import ContractError
    from app.server import _PROVIDER_FACTORIES, _validate_text_input

    _validate_text_input(request.text)
    if request.mode not in ("token", "surrogate"):
        raise ContractError("invalid_request")
    if _PROVIDER_FACTORIES.get(request.provider) is None:
        raise ContractError("invalid_request")


def install_legacy_roundtrip_admission(app, queue: ProviderQueue) -> None:
    """Wrap the existing sync endpoint without changing its DTO or middleware.

    FastAPI has already validated and bounded the legacy request when this
    wrapper runs.  Raising the vendored ``ContractError`` keeps the exact
    existing 429 response body, contract header, and CORS middleware behavior.
    The original endpoint stays synchronous and therefore continues in the
    framework threadpool while the shared scheduler slot is held.
    """

    if not isinstance(queue, ProviderQueue):
        raise RuntimeError("legacy roundtrip queue is invalid")
    if getattr(app.state, "aiguard_legacy_roundtrip_queue_installed", False):
        raise RuntimeError("legacy roundtrip queue was installed twice")
    matches = [
        route
        for route in app.routes
        if getattr(route, "path", None) == LEGACY_ROUNDTRIP_PATH
        and "POST" in (getattr(route, "methods", set()) or set())
        and getattr(route, "dependant", None) is not None
    ]
    if len(matches) != 1:
        raise RuntimeError("exact legacy roundtrip route was not found")
    route = matches[0]
    original = route.dependant.call
    if not callable(original):
        raise RuntimeError("legacy roundtrip endpoint is invalid")

    @wraps(original)
    def queued_roundtrip(request):
        # Runtime-only import keeps the port-owned queue unit-test surface
        # independent from FastAPI/Pydantic while still raising the vendored
        # exception type inside the built Core image.
        from app.http_v2 import ContractError

        authority = _CURRENT_AUTHORITY.get()
        if not isinstance(authority, AuthorityContext):
            raise ContractError("authentication_required")
        if (
            authority.scope != "priority_invite"
            or authority.service_class != "priority"
        ):
            raise ContractError("control_forbidden")
        _validate_legacy_roundtrip_semantics(request)
        execution = queue.admit_legacy_roundtrip(authority=authority)
        if execution is None:
            raise ContractError("rate_limited")
        succeeded = False
        try:
            result = original(request)
            succeeded = True
            return result
        finally:
            queue.finish_legacy_roundtrip(execution, succeeded=succeeded)

    route.dependant.call = queued_roundtrip
    app.state.aiguard_legacy_roundtrip_queue_installed = True
