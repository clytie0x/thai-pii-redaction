"""Authenticated bounded whole-DB archives, restored only into new quarantine DBs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import subprocess
import threading
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.operations import Operations, artifact_identity, schema_identity
from pii_redactor.governance.operator_files import create_private, require_private
from pii_redactor.governance.store import Store

MAGIC = b"AIGDB1\x00"
CHUNK = 65536
MAX_BYTES = 4 * 1024**3
TIMEOUT = 300


def _read(stream, length):
    data = bytearray()
    while len(data) < length:
        chunk = stream.read(length - len(data))
        if not chunk:
            raise ValueError
        data.extend(chunk)
    return bytes(data)


def seal_stream(source, target, key, manifest):
    try:
        cipher = AESGCM(key)
        raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        if len(key) != 32 or len(raw) > CHUNK:
            raise ValueError
        prefix = os.urandom(8)
        target.write(MAGIC + prefix)
        total, index = 0, 0
        h = hashlib.sha256()
        while True:
            plain = raw if index == 0 else source.read(CHUNK)
            if index and not plain:
                plain = json.dumps({"bytes": total, "digest": h.hexdigest()}).encode()
                kind = b"F"
            else:
                kind = b"M" if index == 0 else b"D"
            nonce = prefix + struct.pack("!I", index)
            header = kind + struct.pack("!I", len(plain) + 16)
            encrypted = cipher.encrypt(nonce, plain, MAGIC + header)
            target.write(header + encrypted)
            if kind == b"F":
                return {"bytes": total, "digest": h.hexdigest()}
            if index:
                total += len(plain)
                h.update(plain)
                if total > MAX_BYTES:
                    raise ValueError
            index += 1
    except OSError:
        raise GovernanceError("backup_io_failure") from None
    except Exception:
        raise GovernanceError("backup_integrity_failure") from None


def open_stream(source, target, key):
    """Only write to a discard sink or an isolated quarantine pg_restore pipe."""
    try:
        if len(key) != 32 or _read(source, len(MAGIC)) != MAGIC:
            raise ValueError
        cipher, prefix = AESGCM(key), _read(source, 8)
        total, index, manifest = 0, 0, None
        h = hashlib.sha256()
        while True:
            header = _read(source, 5)
            kind, length = header[:1], struct.unpack("!I", header[1:])[0]
            if not 16 <= length <= CHUNK + 16:
                raise ValueError
            plain = cipher.decrypt(
                prefix + struct.pack("!I", index), _read(source, length), MAGIC + header
            )
            if index == 0:
                if kind != b"M":
                    raise ValueError
                manifest = json.loads(plain)
                if not isinstance(manifest, dict):
                    raise ValueError
            elif kind == b"D":
                total += len(plain)
                if total > MAX_BYTES:
                    raise ValueError
                h.update(plain)
                target.write(plain)
            elif kind == b"F":
                if json.loads(plain) != {"bytes": total, "digest": h.hexdigest()} or source.read(1):
                    raise ValueError
                return manifest
            else:
                raise ValueError
            index += 1
    except Exception:
        raise GovernanceError("backup_integrity_failure") from None


class Discard:
    def write(self, value):
        return len(value)


class DumpReader:
    """Do not seal the final archive marker if pg_dump failed."""

    def __init__(self, process):
        self.process = process

    def read(self, size):
        chunk = self.process.stdout.read(size)
        if not chunk and self.process.wait(timeout=TIMEOUT) != 0:
            raise GovernanceError("backup_process_failed")
        return chunk


def validate_archive(path, key):
    require_private(path)
    with Path(path).open("rb") as stream:
        manifest = open_stream(stream, Discard(), key)
    if (
        manifest.get("format") != 1
        or manifest.get("artifact") != artifact_identity()
        or manifest.get("schema") != {str(k): v for k, v in schema_identity().items()}
        or manifest.get("rollback") != "exact_artifact_and_schema_only"
    ):
        raise GovernanceError("backup_compatibility_failure")
    return manifest


def _environment(dsn):
    info = conninfo_to_dict(dsn)
    # Never allow arbitrary libpq env, service/passfile/options to change the target.
    if (
        set(info) - {"host", "port", "dbname", "user", "password", "sslmode", "sslrootcert"}
        or not info.get("dbname")
        or not info.get("host")
    ):
        raise GovernanceError("backup_configuration_invalid")
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PG")}
    for name, value in info.items():
        env["PGDATABASE" if name == "dbname" else "PG" + name.upper()] = value
    env["PGCONNECT_TIMEOUT"] = "5"
    return env


def _process(binary_dir, name, args, dsn, *, stdin=None, stdout=None):
    binary = Path(binary_dir).resolve() / (name + (".exe" if os.name == "nt" else ""))
    if not binary.is_file():
        raise GovernanceError("postgres_tool_unavailable")
    process = subprocess.Popen(
        [str(binary), *args],
        stdin=stdin,
        stdout=stdout,
        stderr=subprocess.DEVNULL,
        env=_environment(dsn),
    )
    timer = threading.Timer(TIMEOUT, process.kill)
    timer.daemon = True
    timer.start()
    return process, timer


def backup_database(store, binary_dir, path, key, *, checkpoint):
    store.check_ready()
    receipt = checkpoint.check(store)
    archive_id = str(uuid4())
    manifest = {
        "format": 1,
        "archive_id": archive_id,
        "organization": str(store.organization_id),
        "artifact": artifact_identity(),
        "schema": schema_identity(),
        "rollback": "exact_artifact_and_schema_only",
        "checkpoint": receipt,
    }
    # pg_dump's exported snapshot is held by this read-only transaction. The audit
    # lock prevents a commit between head capture and snapshot export.
    process = timer = None
    try:
        with store._transaction(check_organization=False) as tx:
            tx.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            org = tx.execute("SELECT organization_id FROM governance_organization").fetchone()
            if not org or org["organization_id"] != store.organization_id:
                raise GovernanceError("organization_mismatch")
            store.lock(tx)
            state = tx.execute("SELECT active_key_version FROM governance_operations").fetchone()
            manifest["active_key_version"] = state["active_key_version"] if state else None
            manifest["snapshot_head"] = tx.execute(
                "SELECT sequence,event_hash FROM governance_audit ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            snapshot = tx.execute("SELECT pg_export_snapshot() AS id").fetchone()["id"]
            with create_private(path) as output:
                process, timer = _process(
                    binary_dir,
                    "pg_dump",
                    [
                        "--format=custom",
                        "--no-owner",
                        "--no-privileges",
                        "--snapshot=" + snapshot,
                        "--exclude-table-data=*.governance_operations",
                    ],
                    store._dsn,
                    stdout=subprocess.PIPE,
                )
                result = seal_stream(DumpReader(process), output, key, manifest)
                process.stdout.close()
                if process.wait(timeout=TIMEOUT) != 0:
                    raise GovernanceError("backup_process_failed")
                output.flush()
                os.fsync(output.fileno())
        validate_archive(path, key)
        return {"archive_id": archive_id, "state": "validated", **result}
    except GovernanceError:
        raise
    except Exception:
        raise GovernanceError("backup_process_failed") from None
    finally:
        if timer:
            timer.cancel()
        if process:
            if process.poll() is None:
                process.kill()
            process.wait()


def validate_target(name, *, confirmation):
    if (
        not isinstance(name, str)
        or not re.fullmatch(r"aig_restore_[0-9a-f]{32}", name)
        or confirmation != name
    ):
        raise GovernanceError("restore_target_invalid")


def restore_database(admin_dsn, binary_dir, path, key, *, name, confirmation):
    validate_target(name, confirmation=confirmation)
    manifest = validate_archive(path, key)  # Entire archive, before even CREATE DATABASE.
    if not isinstance(manifest.get("snapshot_head"), dict):
        raise GovernanceError("backup_lineage_missing")
    info = conninfo_to_dict(admin_dsn)
    _environment(admin_dsn)
    if info["dbname"] == name:
        raise GovernanceError("restore_target_invalid")
    target_dsn = make_conninfo(admin_dsn, dbname=name)
    process = timer = None
    try:
        with psycopg.connect(admin_dsn, autocommit=True, connect_timeout=5) as admin:
            exists = admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone()
            if exists:
                raise GovernanceError("restore_target_exists")
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0 ALLOW_CONNECTIONS false").format(
                    sql.Identifier(name)
                )
            )
            admin.execute(
                sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(name))
            )
            admin.execute(
                sql.SQL("ALTER DATABASE {} ALLOW_CONNECTIONS true").format(sql.Identifier(name))
            )
        # No runtime principal is enrolled or granted CONNECT on the new DB.
        process, timer = _process(
            binary_dir,
            "pg_restore",
            [
                "--no-owner",
                "--no-privileges",
                "--exit-on-error",
                "--single-transaction",
                "--dbname=" + name,
            ],
            target_dsn,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
        )
        with Path(path).open("rb") as stream:
            open_stream(stream, process.stdin, key)
        process.stdin.close()
        if process.wait(timeout=TIMEOUT) != 0:
            raise GovernanceError("restore_process_failed")
        store = Store(target_dsn, UUID(manifest["organization"]))
        store.check_ready()
        with store.transaction() as tx:
            tx.execute(
                "INSERT INTO governance_operations(singleton,active_key_version) VALUES (true,%s)",
                (manifest.get("active_key_version"),),
            )
        from pii_redactor.governance.recovery_controls import restore_function_acls

        with store.transaction() as tx:
            restore_function_acls(tx)
        Operations(store).quarantine(UUID(manifest["archive_id"]), manifest=manifest)
        return {"state": "quarantined", "archive_id": manifest["archive_id"], "target": name}
    except GovernanceError:
        raise
    except Exception:
        raise GovernanceError("restore_process_failed") from None
    finally:
        if timer:
            timer.cancel()
        if process:
            if process.poll() is None:
                process.kill()
            process.wait()
