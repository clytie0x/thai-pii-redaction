"""Verify signed synthetic OIDC claims without trusting browser identity fields."""

from __future__ import annotations

import time

import pytest

pytest.importorskip("authlib", reason="optional enterprise identity dependency")
pytest.importorskip("joserfc", reason="optional enterprise identity dependency")

from joserfc import jwt
from joserfc.jwk import RSAKey

from app.enterprise.identity import verify_identity
from pii_redactor.governance.errors import GovernanceError

ISSUER = "https://staff.example.test/realms/staff"
CLIENT = "aiguard-staff"
NONCE = "synthetic-transaction-nonce"


@pytest.fixture(scope="module")
def signing_key():
    return RSAKey.generate_key(2048, parameters={"kid": "synthetic-signing-key"})


def claims(**changes):
    now = int(time.time())
    return {
        "iss": ISSUER,
        "sub": "staff-a",
        "aud": CLIENT,
        "azp": CLIENT,
        "iat": now,
        "exp": now + 120,
        "nonce": NONCE,
        **changes,
    }


def signed(key, payload):
    return jwt.encode({"alg": "RS256", "kid": key.kid}, payload, key)


def verify(key, payload, **options):
    return verify_identity(
        signed(key, payload),
        jwks={"keys": [key.as_dict(private=False)]},
        issuer=ISSUER,
        client_id=CLIENT,
        nonce=NONCE,
        **options,
    )


def test_valid_signature_returns_only_configured_identity(signing_key):
    principal = verify(signing_key, claims(roles=["system_administrator"], email="ignored"))
    assert principal.model_dump() == {"issuer": ISSUER, "subject": "staff-a"}


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://foreign.example.test/realms/staff"},
        {"aud": "foreign-client", "azp": CLIENT},
        {"aud": ["foreign-client"], "azp": CLIENT},
        {"aud": CLIENT, "azp": "foreign-client"},
        {"aud": [CLIENT, "other-client"], "azp": None},
        {"nonce": "foreign-transaction"},
        {"nonce": None},
        {"exp": 1},
        {"iat": 1},
        {"iat": 4_000_000_000},
        {"nbf": 4_000_000_000},
        {"sub": ""},
        {"sub": "bad\nsubject"},
        {"exp": True},
    ],
    ids=[
        "issuer",
        "audience-azp-bypass",
        "audience-list",
        "azp",
        "multi-aud-no-azp",
        "nonce",
        "missing-nonce",
        "expired",
        "too-old",
        "future-issued",
        "future-valid",
        "empty-subject",
        "control-subject",
        "boolean-expiry",
    ],
)
def test_invalid_claims_fail_with_value_free_error(signing_key, changes):
    with pytest.raises(GovernanceError) as caught:
        verify(signing_key, claims(**changes))
    assert str(caught.value) == "authentication_failed"
    assert caught.value.__cause__ is None


@pytest.mark.parametrize("field", ["iss", "sub", "aud", "exp", "iat"], ids=str)
def test_required_identity_claims_cannot_be_omitted(signing_key, field):
    payload = claims()
    payload.pop(field)
    with pytest.raises(GovernanceError, match="^authentication_failed$"):
        verify(signing_key, payload)


def test_signature_must_match_configured_keys(signing_key):
    other = RSAKey.generate_key(2048, parameters={"kid": signing_key.kid})
    with pytest.raises(GovernanceError, match="^authentication_failed$"):
        verify_identity(
            signed(other, claims()),
            jwks={"keys": [signing_key.as_dict(private=False)]},
            issuer=ISSUER,
            client_id=CLIENT,
            nonce=NONCE,
        )


def test_empty_expected_nonce_does_not_disable_nonce_validation(signing_key):
    with pytest.raises(GovernanceError, match="^authentication_failed$"):
        verify_identity(
            signed(signing_key, claims()),
            jwks={"keys": [signing_key.as_dict(private=False)]},
            issuer=ISSUER,
            client_id=CLIENT,
            nonce="",
        )


def test_multiple_audiences_need_matching_authorized_party(signing_key):
    principal = verify(signing_key, claims(aud=[CLIENT, "other-client"], azp=CLIENT))
    assert principal.subject == "staff-a"


@pytest.mark.parametrize(
    "token", ["", "not-a-jwt", "x" * 32769], ids=["empty", "malformed", "oversize"]
)
def test_invalid_token_shape_is_bounded(signing_key, token):
    with pytest.raises(GovernanceError, match="^authentication_failed$"):
        verify_identity(
            token,
            jwks={"keys": [signing_key.as_dict(private=False)]},
            issuer=ISSUER,
            client_id=CLIENT,
            nonce=NONCE,
        )


def test_access_hash_cannot_be_silently_unchecked(signing_key):
    with pytest.raises(GovernanceError, match="^authentication_failed$"):
        verify(signing_key, claims(at_hash="synthetic-access-hash"))


def test_access_hash_must_match_the_returned_access_token(signing_key):
    import base64
    import hashlib

    access_token = "synthetic-access-token"
    at_hash = base64.urlsafe_b64encode(hashlib.sha256(access_token.encode()).digest()[:16])
    payload = claims(at_hash=at_hash.decode().rstrip("="))
    assert verify(signing_key, payload, access_token=access_token).subject == "staff-a"
    with pytest.raises(GovernanceError, match="^authentication_failed$"):
        verify(signing_key, payload, access_token="different-access-token")


def test_unsigned_algorithm_is_never_admitted(signing_key):
    import base64
    import json

    def encode(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")

    token = encode({"alg": "none"}) + "." + encode(claims()) + "."
    with pytest.raises(GovernanceError, match="^authentication_failed$"):
        verify_identity(
            token,
            jwks={"keys": [signing_key.as_dict(private=False)]},
            issuer=ISSUER,
            client_id=CLIENT,
            nonce=NONCE,
        )


@pytest.mark.parametrize("field", ["exp", "iat", "nbf"], ids=str)
def test_huge_numeric_dates_fail_with_constant_error(signing_key, field):
    with pytest.raises(GovernanceError, match="^authentication_failed$") as caught:
        verify(signing_key, claims(**{field: 10**1000}))
    assert caught.value.__context__ is None
