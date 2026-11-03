"""File-backed production gates and offline operator commands. No web mutations."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import sys
import threading
import time
from pathlib import Path
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.enterprise.capabilities import ConfiguredKeyProvider
from pii_redactor.governance.checkpoints import CheckpointClient
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.key_operations import verify_keys
from pii_redactor.governance.operations import (
    Operations,
    ProductionProfile,
    control_handlers,
    readiness,
)
from pii_redactor.governance.operator_files import (
    file_authority_binding,
    read_private,
    require_private,
    windows_security_query,
)
from pii_redactor.governance.store import Store


def load_profile_checkpoint(organization_id):
    """Offline operators need only their profile and witness credentials."""
    profile = ProductionProfile.parse(read_private(os.environ["AIGUARD_ENTERPRISE_PROFILE_FILE"]))
    config = read_private(os.environ["AIGUARD_ENTERPRISE_CHECKPOINT_FILE"])
    if set(config) != {"url", "token", "public_key_hex"}:
        raise GovernanceError("checkpoint_configuration_invalid")
    witness = CheckpointClient(
        config["url"],
        config["token"],
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(config["public_key_hex"])),
        organization_id,
        max_age=profile.checkpoint_max_age,
        max_events=profile.checkpoint_max_events,
    )
    return profile, witness


def configuration(settings):
    profile, witness = load_profile_checkpoint(settings.organization_id)
    if profile.public_origin != settings.public_origin or settings.development:
        raise GovernanceError("production_profile_invalid")
    for env in (
        "AIGUARD_ENTERPRISE_DB_FILE",
        "AIGUARD_ENTERPRISE_OIDC_SECRET_FILE",
        "AIGUARD_ENTERPRISE_MANAGED_KEYS_FILE",
        "AIGUARD_ENTERPRISE_SUBJECT_OIDC_SECRET_FILE",
    ):
        require_private(os.environ[env])
    return profile, witness


def runtime_report(
    settings,
    store,
    key_provider,
    *,
    capture=None,
    checkpoint_history=None,
    prepared_configuration=None,
):
    store.runtime_key_version = getattr(key_provider, "active_version", "")
    try:
        profile, checkpoint = prepared_configuration or configuration(settings)
    except Exception:
        profile = checkpoint = None
    if capture is not None:
        capture.update(configuration_profile=profile, checkpoint_client=checkpoint)
    result = readiness(
        store,
        profile,
        checkpoint,
        lambda: verify_keys(store, key_provider) if key_provider else False,
        capture=capture,
        checkpoint_history=checkpoint_history,
    )
    return result


def _windows_security_query():
    return windows_security_query()


def _file_authority_binding(path):
    return file_authority_binding(path)


def _runtime_binding(settings, provider, store=None, subject_settings=None):
    """Hash fixed-size configuration and in-memory keys, without exposing either."""
    keys = getattr(provider, "_keys", None)
    if not isinstance(keys, dict) or not 1 <= len(keys) <= 32:
        raise GovernanceError("key_configuration_invalid")
    values = [
        str(settings.organization_id),
        settings.public_origin,
        settings.issuer,
        settings.client_id,
        settings.client_secret,
    ]
    for name in (
        "AIGUARD_ENTERPRISE_PROFILE_FILE",
        "AIGUARD_ENTERPRISE_CHECKPOINT_FILE",
        "AIGUARD_ENTERPRISE_DB_FILE",
        "AIGUARD_ENTERPRISE_OIDC_SECRET_FILE",
        "AIGUARD_ENTERPRISE_MANAGED_KEYS_FILE",
        "AIGUARD_ENTERPRISE_SUBJECT_OIDC_SECRET_FILE",
    ):
        path = Path(os.environ[name])
        if path.is_symlink():
            raise GovernanceError("production_prerequisites_unverified")
        with path.open("rb") as source:
            raw = source.read(65537)
        if len(raw) > 65536:
            raise GovernanceError("production_prerequisites_unverified")
        if name == "AIGUARD_ENTERPRISE_DB_FILE":
            from psycopg.conninfo import conninfo_to_dict

            current = json.loads(raw)
            if (
                not isinstance(current, dict)
                or set(current) - {"dsn", "purpose"}
                or not isinstance(current.get("dsn"), str)
                or conninfo_to_dict(current["dsn"]) != conninfo_to_dict(settings.database_dsn)
                or (
                    store is not None
                    and conninfo_to_dict(current["dsn"]) != conninfo_to_dict(store._dsn)
                )
            ):
                raise GovernanceError("configuration_invalid")
        elif name in {
            "AIGUARD_ENTERPRISE_OIDC_SECRET_FILE",
            "AIGUARD_ENTERPRISE_SUBJECT_OIDC_SECRET_FILE",
        }:
            current = json.loads(raw)
            client = settings if name == "AIGUARD_ENTERPRISE_OIDC_SECRET_FILE" else subject_settings
            if (
                not isinstance(current, dict)
                or set(current) != {"client_secret"}
                or not isinstance(current["client_secret"], str)
                or not current["client_secret"]
                or client is None
                or not hmac.compare_digest(
                    current["client_secret"].encode(), client.client_secret.encode()
                )
            ):
                raise GovernanceError("configuration_invalid")
        if name == "AIGUARD_ENTERPRISE_MANAGED_KEYS_FILE":
            current = ConfiguredKeyProvider(path, settings.organization_id)
            if (
                current.active_version != provider.active_version
                or set(current._keys) != set(keys)
                or any(
                    not hmac.compare_digest(value, keys[version])
                    for version, value in current._keys.items()
                )
            ):
                raise GovernanceError("key_configuration_invalid")
        values.extend(
            (str(path.resolve()), hashlib.sha256(raw).hexdigest(), _file_authority_binding(path))
        )
    values.append(provider.active_version)
    for version, value in sorted(keys.items(), key=lambda item: str(item[0])):
        if type(value) is not bytes or len(value) != 32:
            raise GovernanceError("key_configuration_invalid")
        values.extend((str(version), hashlib.sha256(value).hexdigest()))
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()


def _witness_binding(checkpoint):
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    values = (
        checkpoint.url,
        str(checkpoint.organization_id),
        checkpoint.max_age,
        checkpoint.max_events,
        hashlib.sha256(checkpoint._token.encode()).hexdigest(),
        checkpoint.public_key.public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
    )
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()


class RuntimeGate:
    """Full qualification runs off-request; requests verify its bounded extension."""

    def __init__(self, settings, store, key_provider):
        self.settings, self.store, self.key_provider = settings, store, key_provider
        self.subject_settings = None
        self._proof = None
        self._refresh_lock = threading.Lock()
        self._proof_lock = threading.Lock()
        self._closed, self._refresh_needed = threading.Event(), threading.Event()
        self._requests = threading.BoundedSemaphore(4)

    @staticmethod
    def blocked():
        return {"status": "blocked", "checks": {"full_qualification": "blocked"}}

    def invalidate(self, *, expected=None):
        with self._proof_lock:
            if expected is not None and self._proof is not expected:
                return
            self._proof = None
        self._refresh_needed.set()

    def refresh(self):
        """Called only by startup/background work, never by an HTTP request."""
        from pii_redactor.governance.operations import artifact_identity, digest, schema_identity
        from pii_redactor.governance.runtime_roles import check_runtime_role
        from pii_redactor.governance.store import verifier_identity

        if self._closed.is_set() or not self._refresh_lock.acquire(blocking=False):
            return self.blocked()
        try:
            # Reject absent/unprotected configuration before any historical scan.
            profile, checkpoint = configuration(self.settings)
            binding = _runtime_binding(
                self.settings, self.key_provider, self.store, self.subject_settings
            )
            witness_authority = _witness_binding(checkpoint)
            history = checkpoint.prepare_history()
            capture = {}
            with self.store.private_snapshot() as snapshot:
                report = runtime_report(
                    self.settings,
                    snapshot,
                    self.key_provider,
                    capture=capture,
                    checkpoint_history=history,
                    prepared_configuration=(profile, checkpoint),
                )
                with snapshot.transaction() as tx:
                    operation = tx.execute(
                        "SELECT * FROM governance_operations WHERE singleton"
                    ).fetchone()
                    organization = tx.execute("SELECT * FROM governance_organization").fetchone()
                    snapshot_schema = {
                        row["version"]: row["digest"]
                        for row in tx.execute("SELECT version,digest FROM governance_schema")
                    }
                database_identity = snapshot.identity
            if report["status"] != "ready" or self._closed.is_set():
                raise GovernanceError("production_prerequisites_unverified")
            if (
                binding
                != _runtime_binding(
                    self.settings, self.key_provider, self.store, self.subject_settings
                )
                or profile.artifact != artifact_identity()
                or profile.schema != digest(schema_identity())
                or witness_authority != _witness_binding(checkpoint)
            ):
                raise GovernanceError("production_prerequisites_unverified")
            # Network/history work is finished before taking the short live fence.
            fresh = checkpoint.fetch(after=capture["checkpoint"]["sequence"])
            with self.store.transaction() as tx:
                self.store.lock(tx)
                tx.execute(
                    "SELECT set_config('aiguard.production_operations','on',true),set_config('aiguard.key_version',%s,true)",
                    (self.key_provider.active_version,),
                )
                tx.execute("SELECT governance_runtime_guard()")
                current_operation = tx.execute(
                    "SELECT * FROM governance_operations WHERE singleton"
                ).fetchone()
                current_organization = tx.execute(
                    "SELECT * FROM governance_organization"
                ).fetchone()
                current_schema = {
                    row["version"]: row["digest"]
                    for row in tx.execute("SELECT version,digest FROM governance_schema")
                }
                if (
                    current_operation != operation
                    or current_organization != organization
                    or current_schema != snapshot_schema
                    or verifier_identity(tx) != database_identity
                ):
                    raise GovernanceError("production_prerequisites_unverified")
                check_runtime_role(self.store, tx=tx)
                checkpoint.check_extension(
                    self.store,
                    (capture["audit"]["events"], capture["audit"]["tail_hash"]),
                    capture["checkpoint"],
                    tx=tx,
                    receipt=fresh,
                )
                if (
                    not operation
                    or operation["state"] != "reconciled"
                    or operation["active_key_version"] != self.key_provider.active_version
                    or binding
                    != _runtime_binding(
                        self.settings, self.key_provider, self.store, self.subject_settings
                    )
                    or profile.artifact != artifact_identity()
                    or profile.schema != digest(schema_identity())
                    or witness_authority != _witness_binding(checkpoint)
                ):
                    raise GovernanceError("production_prerequisites_unverified")
                proof = {
                    "profile": profile,
                    "checkpoint": checkpoint,
                    "binding": binding,
                    "witness_authority": witness_authority,
                    "schema": snapshot_schema,
                    "operations": dict(operation),
                    "database_identity": database_identity,
                    "head": (capture["audit"]["events"], capture["audit"]["tail_hash"]),
                    "witness": capture["checkpoint"],
                    "until": time.monotonic() + profile.checkpoint_max_age,
                }
                with self._proof_lock:
                    if not self._closed.is_set():
                        self._proof = proof
            return report
        except Exception:
            self.invalidate()
            return self.blocked()
        finally:
            self._refresh_lock.release()

    def request_report(self):
        import psycopg
        from psycopg.rows import dict_row

        from pii_redactor.governance.operations import artifact_identity, digest, schema_identity
        from pii_redactor.governance.runtime_roles import check_runtime_role
        from pii_redactor.governance.store import verifier_identity

        with self._proof_lock:
            proof = self._proof
        if proof is None or self._closed.is_set():
            return self.blocked()
        if not self._requests.acquire(blocking=False):
            return {"status": "blocked", "checks": {"request_capacity": "blocked"}}
        try:
            profile = proof["profile"]
            if (
                time.monotonic() >= proof["until"]
                or proof["binding"]
                != _runtime_binding(
                    self.settings, self.key_provider, self.store, self.subject_settings
                )
                or profile.artifact != artifact_identity()
                or proof["schema"] != schema_identity()
                or profile.schema != digest(proof["schema"])
            ):
                raise GovernanceError("production_prerequisites_unverified")
            checkpoint = proof["checkpoint"]
            if proof["witness_authority"] != _witness_binding(checkpoint):
                raise GovernanceError("production_prerequisites_unverified")
            # Fetch before holding database row locks. The signed reply is size-bounded.
            receipt = checkpoint.fetch(after=proof["witness"]["sequence"])
            with psycopg.connect(
                self.store._dsn, autocommit=True, row_factory=dict_row, connect_timeout=5
            ) as connection:
                with connection.transaction():
                    connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                    connection.execute("SET LOCAL statement_timeout='10s'")
                    connection.execute("SET LOCAL lock_timeout='5s'")
                    connection.execute(
                        "SELECT set_config('aiguard.production_operations','on',true),set_config('aiguard.key_version',%s,true)",
                        (self.key_provider.active_version,),
                    )
                    connection.execute("SELECT governance_runtime_guard()")
                    organization = connection.execute(
                        "SELECT organization_id,enrolled_at FROM governance_organization"
                    ).fetchone()
                    if (
                        not organization
                        or organization["organization_id"] != self.store.organization_id
                        or organization["enrolled_at"] is None
                    ):
                        raise GovernanceError("organization_mismatch")
                    operation = connection.execute(
                        "SELECT * FROM governance_operations WHERE singleton"
                    ).fetchone()
                    applied = {
                        row["version"]: row["digest"]
                        for row in connection.execute(
                            "SELECT version,digest FROM governance_schema"
                        )
                    }
                    if (
                        dict(operation or {}) != proof["operations"]
                        or applied != proof["schema"]
                        or verifier_identity(connection) != proof["database_identity"]
                    ):
                        raise GovernanceError("production_prerequisites_unverified")
                    check_runtime_role(self.store, tx=connection)
                    checkpoint.check_extension(
                        self.store, proof["head"], proof["witness"], tx=connection, receipt=receipt
                    )
            if (
                time.monotonic() >= proof["until"]
                or proof["binding"]
                != _runtime_binding(
                    self.settings, self.key_provider, self.store, self.subject_settings
                )
                or profile.artifact != artifact_identity()
                or proof["schema"] != schema_identity()
                or proof["witness_authority"] != _witness_binding(checkpoint)
            ):
                raise GovernanceError("production_prerequisites_unverified")
            with self._proof_lock:
                if self._proof is not proof:
                    raise GovernanceError("production_prerequisites_unverified")
            return {
                "status": "ready",
                "checks": dict.fromkeys(
                    (
                        "full_qualification",
                        "profile",
                        "database",
                        "schema",
                        "enrollment",
                        "runtime_role",
                        "keys",
                        "restore",
                        "audit_extension",
                        "checkpoint",
                    ),
                    "ready",
                ),
            }
        except Exception:
            self.invalidate(expected=proof)
            return self.blocked()
        finally:
            self._requests.release()

    async def run(self):
        while not self._closed.is_set():
            await asyncio.to_thread(self.refresh)
            with self._proof_lock:
                proof = self._proof
            delay = max(1, min(30, proof["profile"].checkpoint_max_age / 2)) if proof else 5
            self._refresh_needed.clear()
            await asyncio.to_thread(self._refresh_needed.wait, delay)

    def close(self):
        self._closed.set()
        self.invalidate()


def runtime_request_report(_settings, _store, _key_provider):
    # Without a process-local qualified gate, serving is blocked.
    return RuntimeGate.blocked()


def _store(file=None):
    config = read_private(file or os.environ["AIGUARD_ENTERPRISE_DB_FILE"])
    if set(config) not in ({"dsn"}, {"dsn", "purpose"}) or config.get("purpose") not in (
        None,
        "synthetic_enterprise_tests",
    ):
        raise GovernanceError("configuration_invalid")
    return Store(config["dsn"], UUID(os.environ["AIGUARD_ENTERPRISE_ORGANIZATION_ID"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("identity", help="Print minimized runtime source/schema digests")
    commands.add_parser("readiness")
    commands.add_parser("checkpoint-publish")
    commands.add_parser("checkpoint-verify")
    commands.add_parser("keys-verify")
    rotate = commands.add_parser("keys-prepare")
    rotate.add_argument("--output", required=True)
    rotate.add_argument("--version", required=True)
    activate = commands.add_parser("keys-activate")
    activate.add_argument("--candidate", required=True)
    for name in ("backup", "backup-validate", "restore-quarantine"):
        command = commands.add_parser(name)
        command.add_argument("--archive", required=True)
        if name == "restore-quarantine":
            command.add_argument("--target", required=True)
            command.add_argument("--confirm-target", required=True)
    reconcile = commands.add_parser("restore-reconcile")
    reconcile.add_argument("--source-db-file", required=True)
    reconcile.add_argument("--runtime-db-file", required=True)
    initial_context = commands.add_parser("initial-review-context")
    initial_context.add_argument("--runtime-db-file", required=True)
    initial = commands.add_parser("activate-initial")
    initial.add_argument("--runtime-db-file", required=True)
    initial.add_argument("--review-file", required=True)
    args = parser.parse_args(argv)
    try:
        from pii_redactor.governance.operations import artifact_identity, digest, schema_identity

        if args.command == "identity":
            result = {
                "artifact": artifact_identity(),
                "schema": digest(schema_identity()),
                "rollback": "exact_artifact_and_schema_only",
            }
        else:
            store = _store()
            if args.command.startswith("checkpoint") or args.command in {
                "backup",
                "restore-reconcile",
                "initial-review-context",
                "activate-initial",
            }:
                profile, checkpoint = load_profile_checkpoint(store.organization_id)
            if args.command.startswith("checkpoint"):
                checkpoint.check(store, publish=args.command == "checkpoint-publish")
                result = {"state": "verified"}
            elif args.command == "readiness":
                from app.enterprise.settings import Settings

                settings = Settings.from_env()
                provider = ConfiguredKeyProvider(
                    os.environ["AIGUARD_ENTERPRISE_MANAGED_KEYS_FILE"], store.organization_id
                )
                result = runtime_report(settings, store, provider)
                # Offline readout cannot certify current IdP connectivity.
                result["checks"]["idp"] = "unverified_offline"
                result["status"] = "blocked"
            elif args.command.startswith("keys-"):
                from pii_redactor.governance.key_operations import (
                    activate_rotation,
                    prepare_rotation,
                )

                filename = os.environ["AIGUARD_ENTERPRISE_MANAGED_KEYS_FILE"]
                require_private(filename)
                provider = ConfiguredKeyProvider(filename, store.organization_id)
                if args.command == "keys-prepare":
                    result = prepare_rotation(filename, args.output, version=args.version)
                elif args.command == "keys-activate":
                    require_private(args.candidate)
                    new = ConfiguredKeyProvider(args.candidate, store.organization_id)
                    result = activate_rotation(store, provider, new)
                else:
                    verify_keys(store, provider)
                    result = {"state": "verified"}
            elif args.command in {"initial-review-context", "activate-initial"}:
                from pii_redactor.governance.initial_activation import (
                    InitialFileAuthority,
                    activate_initial,
                    review_context,
                )

                filename = os.environ["AIGUARD_ENTERPRISE_MANAGED_KEYS_FILE"]
                require_private(filename)
                provider = ConfiguredKeyProvider(filename, store.organization_id)
                runtime = _store(args.runtime_db_file)
                authority = InitialFileAuthority(
                    operator_db=os.environ["AIGUARD_ENTERPRISE_DB_FILE"],
                    runtime_db=args.runtime_db_file,
                    profile_file=os.environ["AIGUARD_ENTERPRISE_PROFILE_FILE"],
                    checkpoint_file=os.environ["AIGUARD_ENTERPRISE_CHECKPOINT_FILE"],
                    managed_keys=filename,
                    review_file=args.review_file if args.command == "activate-initial" else None,
                )
                if args.command == "initial-review-context":
                    result = review_context(
                        store,
                        runtime_store=runtime,
                        profile=profile,
                        key_provider=provider,
                        checkpoint=checkpoint,
                        authority=authority,
                    )
                else:
                    result = activate_initial(
                        store,
                        read_private(args.review_file),
                        runtime_store=runtime,
                        profile=profile,
                        key_provider=provider,
                        checkpoint=checkpoint,
                        authority=authority,
                    )
            elif args.command == "restore-reconcile":
                filename = os.environ["AIGUARD_ENTERPRISE_MANAGED_KEYS_FILE"]
                require_private(filename)
                provider = ConfiguredKeyProvider(filename, store.organization_id)
                result = Operations(store).reconcile(
                    _store(args.source_db_file),
                    handlers=control_handlers(),
                    checkpoint=checkpoint,
                    runtime_store=_store(args.runtime_db_file),
                    profile=profile,
                    key_provider=provider,
                )
            else:
                from pii_redactor.governance.backup import (
                    backup_database,
                    restore_database,
                    validate_archive,
                )

                config = read_private(os.environ["AIGUARD_ENTERPRISE_BACKUP_KEY_FILE"])
                if set(config) != {"key_hex"}:
                    raise GovernanceError("key_configuration_invalid")
                key = bytes.fromhex(config["key_hex"])
                if args.command == "backup-validate":
                    manifest = validate_archive(args.archive, key)
                    result = {"state": "validated", "archive_id": manifest["archive_id"]}
                elif args.command == "backup":
                    result = backup_database(
                        store,
                        os.environ["AIGUARD_ENTERPRISE_PG_BIN"],
                        args.archive,
                        key,
                        checkpoint=checkpoint,
                    )
                else:
                    result = restore_database(
                        store._dsn,
                        os.environ["AIGUARD_ENTERPRISE_PG_BIN"],
                        args.archive,
                        key,
                        name=args.target,
                        confirmation=args.confirm_target,
                    )
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("status") != "blocked" else 1
    except GovernanceError as error:
        code = error.code
    except Exception:
        code = "operator_operation_failed"
    print(code, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
