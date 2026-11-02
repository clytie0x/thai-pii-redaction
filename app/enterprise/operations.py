"""File-backed production gates and offline operator commands. No web mutations."""

from __future__ import annotations

import argparse
import json
import os
import sys
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
from pii_redactor.governance.operator_files import read_private, require_private
from pii_redactor.governance.store import Store


def configuration(settings):
    profile = ProductionProfile.parse(read_private(os.environ["AIGUARD_ENTERPRISE_PROFILE_FILE"]))
    if profile.public_origin != settings.public_origin or settings.development:
        raise GovernanceError("production_profile_invalid")
    config = read_private(os.environ["AIGUARD_ENTERPRISE_CHECKPOINT_FILE"])
    if set(config) != {"url", "token", "public_key_hex"}:
        raise GovernanceError("checkpoint_configuration_invalid")
    witness = CheckpointClient(
        config["url"],
        config["token"],
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(config["public_key_hex"])),
        settings.organization_id,
        max_age=profile.checkpoint_max_age,
        max_events=profile.checkpoint_max_events,
    )
    for env in (
        "AIGUARD_ENTERPRISE_DB_FILE",
        "AIGUARD_ENTERPRISE_OIDC_SECRET_FILE",
        "AIGUARD_ENTERPRISE_MANAGED_KEYS_FILE",
        "AIGUARD_ENTERPRISE_SUBJECT_OIDC_SECRET_FILE",
    ):
        require_private(os.environ[env])
    return profile, witness


def runtime_report(settings, store, key_provider):
    try:
        profile, checkpoint = configuration(settings)
    except Exception:
        profile = checkpoint = None
    result = readiness(
        store,
        profile,
        checkpoint,
        lambda: verify_keys(store, key_provider) if key_provider else False,
    )
    return result


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
            }:
                from app.enterprise.settings import Settings

                _, checkpoint = configuration(Settings.from_env())
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
            elif args.command == "restore-reconcile":
                result = Operations(store).reconcile(
                    _store(args.source_db_file), handlers=control_handlers(), checkpoint=checkpoint
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
