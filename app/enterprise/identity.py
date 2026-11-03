"""Validate configured OIDC identity without accepting claimed staff roles."""

from __future__ import annotations

import math
import time

from authlib.oidc.core import CodeIDToken
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from pydantic import ValidationError

from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import Principal


def verify_identity(
    id_token: str,
    *,
    jwks: dict,
    issuer: str,
    client_id: str,
    nonce: str,
    access_token: str | None = None,
    max_token_age: int = 300,
    clock_skew: int = 30,
) -> Principal:
    """Bound token issue age; login freshness and state are separate checks."""
    try:
        if (
            not isinstance(id_token, str)
            or not 1 <= len(id_token) <= 32768
            or not isinstance(issuer, str)
            or not issuer
            or not isinstance(client_id, str)
            or not client_id
            or not isinstance(nonce, str)
            or not 1 <= len(nonce) <= 256
            or not isinstance(jwks, dict)
            or not isinstance(jwks.get("keys"), list)
            or not 1 <= len(jwks["keys"]) <= 64
            or type(max_token_age) is not int
            or not 1 <= max_token_age <= 3600
            or type(clock_skew) is not int
            or not 0 <= clock_skew <= 60
        ):
            raise ValueError
        decoded = jwt.decode(id_token, KeySet.import_key_set(jwks), algorithms=["RS256"])
        if "at_hash" in decoded.claims and (
            not isinstance(decoded.claims["at_hash"], str)
            or not decoded.claims["at_hash"]
            or not isinstance(access_token, str)
            or not 1 <= len(access_token) <= 16384
        ):
            raise ValueError
        claims = CodeIDToken(
            decoded.claims,
            decoded.header,
            options={
                "iss": {"essential": True, "value": issuer},
                "sub": {"essential": True},
                "aud": {"essential": True, "value": client_id},
                "azp": {"value": client_id},
            },
            params={"client_id": client_id, "nonce": nonce, "access_token": access_token},
        )
        for name in ("exp", "iat", "nbf"):
            if name in claims and (
                type(claims[name]) not in (int, float) or not math.isfinite(claims[name])
            ):
                raise ValueError
        now = time.time()
        claims.validate(now=now, leeway=clock_skew)
        if now - claims["iat"] > max_token_age + clock_skew:
            raise ValueError
        return Principal(issuer=issuer, subject=claims["sub"])
    except (JoseError, ValidationError, TypeError, ValueError, KeyError, OverflowError):
        pass
    # Do not chain provider claims or token errors into the public exception.
    raise GovernanceError("authentication_failed") from None
