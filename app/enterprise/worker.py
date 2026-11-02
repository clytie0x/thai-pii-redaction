"""Explicit managed-action worker. This is separate from AI-for-Thai emulation."""

from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.outbox import validate_worker


class Worker:
    def __init__(self, execution, outbox):
        self.execution, self.outbox = execution, outbox

    def run_once(self, worker_id):
        worker_id = validate_worker(worker_id)
        task = self.outbox.claim(worker_id)
        if task is None:
            return {"state": "idle", "primary_verified": False}
        try:
            return self.execution.execute(worker_id, task)
        except GovernanceError as error:
            # A lost commit acknowledgement cannot prove rollback.
            code = "outcome_unknown" if error.code == "storage_failure" else error.code
        except Exception:
            code = "outcome_unknown"
        try:
            return self.outbox.record_failure(worker_id, task, code)
        except GovernanceError:
            return {"state": "unknown", "primary_verified": False, "error_code": "outcome_unknown"}
