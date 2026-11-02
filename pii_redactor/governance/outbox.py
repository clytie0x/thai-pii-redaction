"""Bounded PostgreSQL leases for managed actions; unknown outcomes are held."""

import re
from uuid import uuid4

from pii_redactor.governance.commands import identifier
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.execution import emit


def validate_worker(worker_id):
    if not isinstance(worker_id, str) or not re.fullmatch(
        r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", worker_id
    ):
        raise GovernanceError("invalid_request")
    return worker_id


def failure_class(code):
    if code in {"outcome_unknown", "lease_lost", "outcome_reconciliation_required"}:
        return "unknown"
    if code in {"storage_failure", "key_service_unavailable", "key_version_unavailable"}:
        return "retryable"
    return "terminal"


class Outbox:
    def __init__(self, store, *, lease_seconds=30, max_attempts=3):
        if (
            type(lease_seconds) is not int
            or not 1 <= lease_seconds <= 300
            or type(max_attempts) is not int
            or not 1 <= max_attempts <= 10
        ):
            raise GovernanceError("configuration_invalid")
        self.store, self.lease_seconds, self.max_attempts = store, lease_seconds, max_attempts

    def _transition(self, tx, instruction_id, state, event_code):
        row = tx.execute(
            "UPDATE governance_execution_instructions SET state=%s,revision=revision+1 WHERE instruction_id=%s AND organization_id=%s RETURNING *",
            (state, instruction_id, self.store.organization_id),
        ).fetchone()
        if not row:
            raise GovernanceError("record_unavailable")
        emit(self.store, tx, event_code, row)
        return row

    def _expire(self, tx):
        expired = tx.execute(
            """SELECT t.instruction_id FROM governance_execution_tasks t
            JOIN governance_execution_instructions i USING(instruction_id)
            WHERE i.organization_id=%s AND t.state='running' AND t.lease_until<=clock_timestamp()
            ORDER BY t.instruction_id LIMIT 100 FOR UPDATE OF t""",
            (self.store.organization_id,),
        ).fetchall()
        for row in expired:
            tx.execute(
                """UPDATE governance_execution_tasks SET state='unknown',worker_id=NULL,lease_token=NULL,
                lease_until=NULL,last_error='lease_expired',updated_at=clock_timestamp() WHERE instruction_id=%s""",
                (row["instruction_id"],),
            )
            self._transition(tx, row["instruction_id"], "unknown", "execution.lease_expired")

    def claim(self, worker_id):
        worker_id = validate_worker(worker_id)
        with self.store.transaction() as tx:
            self.store.lock(tx)
            self._expire(tx)
            task = tx.execute(
                """SELECT t.* FROM governance_execution_tasks t
                JOIN governance_execution_instructions i USING(instruction_id)
                WHERE i.organization_id=%s AND t.state='pending' AND i.state='pending'
                AND t.available_at<=clock_timestamp()
                ORDER BY t.available_at,t.instruction_id LIMIT 1 FOR UPDATE OF t SKIP LOCKED""",
                (self.store.organization_id,),
            ).fetchone()
            if not task:
                return None
            if task["attempts"] >= min(task["max_attempts"], self.max_attempts):
                tx.execute(
                    "UPDATE governance_execution_tasks SET state='failed',last_error='attempt_limit_reached',updated_at=clock_timestamp() WHERE instruction_id=%s",
                    (task["instruction_id"],),
                )
                self._transition(
                    tx, task["instruction_id"], "failed", "execution.attempts_exhausted"
                )
                return None
            token = uuid4()
            row = tx.execute(
                """UPDATE governance_execution_tasks SET state='running',attempts=attempts+1,
                worker_id=%s,lease_token=%s,lease_until=clock_timestamp()+(%s * interval '1 second'),
                max_attempts=LEAST(max_attempts,%s),updated_at=clock_timestamp()
                WHERE instruction_id=%s RETURNING instruction_id,lease_token,lease_until,attempts""",
                (worker_id, token, self.lease_seconds, self.max_attempts, task["instruction_id"]),
            ).fetchone()
            self._transition(tx, task["instruction_id"], "running", "execution.started")
            return row

    def record_failure(self, worker_id, task, code):
        worker_id = validate_worker(worker_id)
        if not isinstance(code, str) or not re.fullmatch(r"[a-z][a-z_]{1,63}", code):
            code = "outcome_unknown"
        with self.store.transaction() as tx:
            self.store.lock(tx)
            row = tx.execute(
                """SELECT t.* FROM governance_execution_tasks t JOIN governance_execution_instructions i USING(instruction_id)
                WHERE t.instruction_id=%s AND i.organization_id=%s AND t.state='running' AND t.worker_id=%s AND t.lease_token=%s FOR UPDATE OF t""",
                (
                    identifier(task["instruction_id"]),
                    self.store.organization_id,
                    worker_id,
                    identifier(task["lease_token"]),
                ),
            ).fetchone()
            if not row:
                raise GovernanceError("lease_lost")
            kind = failure_class(code)
            now = tx.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if row["lease_until"] <= now:
                kind = "unknown"
            state = "unknown" if kind == "unknown" else "failed"
            if kind == "retryable" and row["attempts"] < row["max_attempts"]:
                state = "pending"
            delay = min(60, 2 ** row["attempts"])
            tx.execute(
                """UPDATE governance_execution_tasks SET state=%s,worker_id=NULL,lease_token=NULL,lease_until=NULL,
                last_error=%s,available_at=clock_timestamp()+(%s * interval '1 second'),updated_at=clock_timestamp()
                WHERE instruction_id=%s""",
                (state, code, delay, row["instruction_id"]),
            )
            self._transition(
                tx,
                row["instruction_id"],
                state,
                "execution." + ("retry_pending" if state == "pending" else state),
            )
            return {
                "id": str(row["instruction_id"]),
                "state": state,
                "primary_verified": False,
                "error_code": code,
            }
