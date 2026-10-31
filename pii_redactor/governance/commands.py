"""One transaction for an authorized mutation, receipt, audit and outbox event."""

import hashlib
import json
from uuid import UUID

from psycopg.types.json import Jsonb

from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.permissions import require_member


def identifier(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise GovernanceError("invalid_request") from None


def digest(value):
    raw = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def check_revision(record, expected_revision):
    if type(expected_revision) is not int or expected_revision < 1:
        raise GovernanceError("invalid_request")
    if record["revision"] != expected_revision:
        raise GovernanceError("revision_conflict")


def run_command(
    store,
    principal,
    command_key,
    permission,
    event_code,
    request,
    effect,
    *,
    department_id=None,
    scope=None,
):
    key = identifier(command_key)
    fingerprint = digest({"operation": event_code, "request": request})
    with store.transaction() as tx:
        store.lock(tx)
        member = require_member(tx, store.organization_id, principal, permission, department_id)
        target = scope(tx, member) if scope else None
        previous = tx.execute(
            "SELECT request_digest, response FROM governance_commands WHERE actor_id=%s AND command_key=%s",
            (member["member_id"], key),
        ).fetchone()
        if previous:
            if previous["request_digest"] != fingerprint:
                raise GovernanceError("idempotency_conflict")
            return previous["response"]
        response = effect(tx, member, target)
        event_id = store.append_event(
            tx,
            event_code=event_code,
            actor_id=member["member_id"],
            target_id=identifier(response["id"]),
            revision=response["revision"],
        )
        tx.execute(
            "INSERT INTO governance_outbox(event_id, event_code, payload) VALUES (%s,%s,%s)",
            (
                event_id,
                event_code,
                Jsonb({"record_id": response["id"], "revision": response["revision"]}),
            ),
        )
        tx.execute(
            "INSERT INTO governance_commands(actor_id,command_key,request_digest,response) VALUES (%s,%s,%s,%s)",
            (member["member_id"], key, fingerprint, Jsonb(response)),
        )
        return response
