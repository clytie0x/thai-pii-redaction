"""Audit logging for process and security events.

SECURITY-CRITICAL: entries NEVER contain original PII, pseudonyms, or vault content, only
step names, timestamps, counts, safe flags, error types, and non-authorizing correlation IDs.
"""

import json
import os
import re
import time
from pathlib import Path

# Filename allowlist for the correlation ID. `session_id` is a legacy name; callers pass a fresh
# operation ID, never a live session authority.
_SESSION_ID_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")

# Hosted mode: AMPHRANG_AUDIT_STDOUT=1 emits one JSON line per entry on stdout (container
# platforms rotate stdout; a bind-mounted file would grow unbounded). Read dynamically.
_STDOUT_ENV = "AMPHRANG_AUDIT_STDOUT"


def _stdout_mode() -> bool:
    return os.environ.get(_STDOUT_ENV) == "1"


def _emit(entry: dict, path: Path) -> Path:
    """Write one entry to stdout (hosted) or append to `path`; in stdout mode no file is touched."""
    if _stdout_mode():
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        return path
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def _log_path(session_id: str, log_type: str, output_dir: str) -> Path:
    """Path for an audit log file (log_type is "process" or "security")."""
    safe_id = _SESSION_ID_UNSAFE.sub("_", session_id)
    return Path(output_dir) / f"audit_{safe_id}_{log_type}.jsonl"


def write_process_log(
    session_id: str,
    step: str,
    entity_count: int,
    validation_result: str,
    flags: list[str],
    latency_ms: float,
    output_dir: str = ".",
) -> Path:
    """Write a process audit entry; returns the log path.

    SECURITY: never log PII, pseudonyms, or vault content. flags may carry entity_ids only.
    """
    entry = {
        "type": "process",
        "session_id": session_id,
        "step": step,
        "timestamp": time.time(),
        "entity_count": entity_count,
        "validation_result": validation_result,
        "flags": flags,
        "latency_ms": latency_ms,
    }
    return _emit(entry, _log_path(session_id, "process", output_dir))


def write_security_log(
    session_id: str,
    layer: str,
    pii_scan_result: str,
    mapping_table_access_count: int,
    retry_count: int,
    error_type: str | None,
    rollback_occurred: bool,
    output_dir: str = ".",
) -> Path:
    """Write a security audit entry; returns the log path.

    SECURITY: never log PII, pseudonyms, or vault content.
    pii_scan_result: "clean" | "unexpected_pii" | "expected_pii".
    """
    entry = {
        "type": "security",
        "session_id": session_id,
        "layer": layer,
        "timestamp": time.time(),
        "pii_scan_result": pii_scan_result,
        "mapping_table_access_count": mapping_table_access_count,
        "retry_count": retry_count,
        "error_type": error_type,
        "rollback_occurred": rollback_occurred,
    }
    return _emit(entry, _log_path(session_id, "security", output_dir))
