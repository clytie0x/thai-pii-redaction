"""Headless worker prerequisites without staff or subject login credentials."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from psycopg.conninfo import conninfo_to_dict

from app.enterprise.auth import OIDCClient
from app.enterprise.operations import load_profile_checkpoint
from app.enterprise.settings import _url
from pii_redactor.governance import operations as governance
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.key_operations import verify_keys
from pii_redactor.governance.operations import ProductionProfile, digest, readiness, schema_identity
from pii_redactor.governance.operator_files import file_authority_binding, require_private
from pii_redactor.governance.runtime_roles import check_runtime_role
from pii_redactor.governance.store import Store, verifier_identity

_WORKER_FILES = ("PROFILE", "CHECKPOINT", "DB", "MANAGED_KEYS")


def require_loopback(store):
    try:
        info = conninfo_to_dict(store._dsn)
        if info.get("host") in {"127.0.0.1", "localhost", "::1"} and info.get("hostaddr") in {
            None,
            "127.0.0.1",
            "::1",
        }:
            return
    except Exception:
        pass
    raise GovernanceError("configuration_invalid") from None


def _issuers(env):
    try:
        staff = env["AIGUARD_ENTERPRISE_ISSUER"]
        issuers = {staff, env.get("AIGUARD_ENTERPRISE_SUBJECT_ISSUER", staff)}
        if any(
            not isinstance(value, str)
            or not 1 <= len(value) <= 2048
            or _url(value).scheme != "https"
            for value in issuers
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise GovernanceError("configuration_invalid") from None
    return tuple(sorted(issuers))


def _worker_binding(store, provider, profile, checkpoint, environment):
    """Bind only headless DB/key/profile/witness references, never login secrets."""
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    from app.enterprise.capabilities import ConfiguredKeyProvider

    try:
        values = [str(store.organization_id), provider.active_version, _issuers(environment)]
        for name in _WORKER_FILES:
            path = Path(os.environ["AIGUARD_ENTERPRISE_" + name + "_FILE"])
            if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                raise GovernanceError("operator_file_unprotected")
            with path.open("rb") as source:
                raw = source.read(65537)
            if len(raw) > 65536:
                raise GovernanceError("operator_file_invalid")
            current = json.loads(raw)
            if name == "DB":
                if (
                    not isinstance(current, dict)
                    or set(current) - {"dsn", "purpose"}
                    or not isinstance(current.get("dsn"), str)
                    or conninfo_to_dict(current["dsn"]) != conninfo_to_dict(store._dsn)
                ):
                    raise GovernanceError("configuration_invalid")
            elif name == "PROFILE":
                if ProductionProfile.parse(current) != profile:
                    raise GovernanceError("production_profile_invalid")
            elif name == "CHECKPOINT":
                if (
                    not isinstance(current, dict)
                    or set(current) != {"url", "token", "public_key_hex"}
                    or not isinstance(current["url"], str)
                    or current["url"].rstrip("/") != checkpoint.url
                    or not isinstance(current["token"], str)
                    or not hmac.compare_digest(
                        current["token"].encode(), checkpoint._token.encode()
                    )
                    or bytes.fromhex(current["public_key_hex"])
                    != checkpoint.public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
                ):
                    raise GovernanceError("checkpoint_configuration_invalid")
            else:
                active = ConfiguredKeyProvider(path, store.organization_id)
                if (
                    active.active_version != provider.active_version
                    or set(active._keys) != set(provider._keys)
                    or any(
                        not hmac.compare_digest(key, provider._keys[version])
                        for version, key in active._keys.items()
                    )
                ):
                    raise GovernanceError("key_configuration_invalid")
            values.extend(
                (str(path.resolve()), hashlib.sha256(raw).hexdigest(), file_authority_binding(path))
            )
        values.append(checkpoint.authority_binding())
        return digest(values)
    except GovernanceError:
        raise
    except Exception:
        raise GovernanceError("configuration_invalid") from None


class _WorkerProof:
    def __init__(self, store, provider, environment, profile, checkpoint, binding, capture):
        self.store, self.provider, self.environment = store, provider, environment
        self.profile, self.checkpoint, self.binding = profile, checkpoint, binding
        self.capture, self.receipt = capture, None
        self.authority = checkpoint.authority_binding()
        self.until = time.monotonic() + profile.checkpoint_max_age

    def _fresh_inputs(self):
        if (
            time.monotonic() >= self.until
            or self.store.runtime_key_version != self.provider.active_version
            or self.profile.artifact != governance.artifact_identity()
            or self.profile.schema != digest(schema_identity())
            or self.authority != self.checkpoint.authority_binding()
            or self.binding
            != _worker_binding(
                self.store, self.provider, self.profile, self.checkpoint, self.environment
            )
            or time.monotonic() >= self.until
        ):
            raise GovernanceError("production_prerequisites_unverified")

    def prepare_current(self):
        self._fresh_inputs()
        self.receipt = self.checkpoint.fetch(after=self.capture["witness"]["sequence"])
        self._fresh_inputs()

    def validate_locked(self, tx):
        self._fresh_inputs()
        if self.receipt is None:
            raise GovernanceError("production_prerequisites_unverified")
        tx.execute("SELECT governance_runtime_guard()")
        operation = tx.execute("SELECT * FROM governance_operations WHERE singleton").fetchone()
        organization = tx.execute("SELECT * FROM governance_organization").fetchone()
        applied = {
            row["version"]: row["digest"]
            for row in tx.execute("SELECT version,digest FROM governance_schema")
        }
        if (
            operation != self.capture["operations"]
            or organization != self.capture["organization"]
            or applied != self.capture["schema"]
            or verifier_identity(tx) != self.capture["identity"]
        ):
            raise GovernanceError("production_prerequisites_unverified")
        check_runtime_role(self.store, tx=tx)
        self.checkpoint.check_extension(
            self.store, self.capture["head"], self.capture["witness"], tx=tx, receipt=self.receipt
        )
        self._fresh_inputs()


def _qualify_snapshot(store, provider, environment):
    for name in _WORKER_FILES:
        require_private(os.environ["AIGUARD_ENTERPRISE_" + name + "_FILE"])
    profile, checkpoint = load_profile_checkpoint(store.organization_id)
    binding = _worker_binding(store, provider, profile, checkpoint, environment)
    history = checkpoint.prepare_history()
    capture = {}
    with store.private_snapshot() as snapshot:
        report = readiness(
            snapshot,
            profile,
            checkpoint,
            lambda: verify_keys(snapshot, provider),
            capture=capture,
            checkpoint_history=history,
        )
        with snapshot.transaction() as tx:
            live = {
                "operations": tx.execute(
                    "SELECT * FROM governance_operations WHERE singleton"
                ).fetchone(),
                "organization": tx.execute("SELECT * FROM governance_organization").fetchone(),
                "schema": {
                    r["version"]: r["digest"]
                    for r in tx.execute("SELECT version,digest FROM governance_schema")
                },
                "identity": snapshot.identity,
                "head": (capture["audit"]["events"], capture["audit"]["tail_hash"])
                if "audit" in capture
                else None,
                "witness": capture.get("checkpoint"),
            }
    if report["status"] != "ready":
        return report, None
    if binding != _worker_binding(store, provider, profile, checkpoint, environment):
        raise GovernanceError("production_prerequisites_unverified")
    return report, _WorkerProof(store, provider, environment, profile, checkpoint, binding, live)


def worker_readiness(
    store, key_provider, *, environment=None, identity_transport=None, qualification=None
):
    version = getattr(key_provider, "active_version", None)
    if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", version):
        raise GovernanceError("key_configuration_invalid")
    store.runtime_key_version, store.production_operations_required = version, True
    env = os.environ if environment is None else environment
    issuers = _issuers(env)
    report, proof = _qualify_snapshot(store, key_provider, env)
    if report["status"] != "ready":
        return report

    async def public_identity_health():
        # check_ready only reads bounded public metadata; no OAuth login is used.
        await asyncio.gather(
            *(
                OIDCClient(
                    SimpleNamespace(issuer=issuer), transport=identity_transport
                ).check_ready(refresh=True)
                for issuer in issuers
            )
        )

    try:
        asyncio.run(public_identity_health())
        report["checks"]["idp"] = "ready"
        proof.prepare_current()
        with store.transaction() as tx:
            proof.validate_locked(tx)
        report["checks"]["action_proof"] = "ready"
        if qualification is not None:
            qualification["proof"] = proof
    except GovernanceError:
        if report["checks"].get("idp") != "ready":
            report["checks"]["idp"] = "blocked"
        report["checks"]["action_proof"] = "blocked"
        report["status"] = "blocked"
    return report


class _QualifiedWorkerStore(Store):
    """Keep the action proof at actual live transaction entry and commit boundaries."""

    def __init__(self, source, provider):
        super().__init__(source._dsn, source.organization_id)
        self.production_operations_required, self.runtime_key_version = (
            True,
            provider.active_version,
        )
        self._action_proof = None

    @contextmanager
    def _transaction(self, *, check_organization=True):
        with super()._transaction(check_organization=check_organization) as tx:
            proof = self._action_proof
            if proof is not None:
                proof.validate_locked(tx)
            yield tx
            if proof is not None:
                proof.validate_locked(tx)


def run_qualified_once(
    store, key_provider, worker_id, *, environment=None, identity_transport=None
):
    from app.enterprise.capabilities import managed_services

    private = _QualifiedWorkerStore(store, key_provider)
    capture = {}
    report = worker_readiness(
        private,
        key_provider,
        environment=environment,
        identity_transport=identity_transport,
        qualification=capture,
    )
    if report["status"] != "ready" or capture.get("proof") is None:
        raise GovernanceError("production_prerequisites_unverified")
    _collection, _evidence, _execution, worker = managed_services(private, key_provider)
    private._action_proof = capture["proof"]
    try:
        return worker.run_once(worker_id)
    finally:
        private._action_proof = None
