"""Reversible managed-primary operations; no remote, filesystem or delete adapter."""

from pii_redactor.governance.collections import document_context
from pii_redactor.governance.errors import GovernanceError


class ManagedDocuments:
    def __init__(self, collection, evidence):
        self.collection, self.evidence = collection, evidence

    def apply(self, tx, collection, document, instruction, member):
        if (
            instruction["collection_id"] != collection["collection_id"]
            or instruction["document_id"] != document["document_id"]
            or document["collection_id"] != collection["collection_id"]
            or instruction["target_version"] != document["current_version"]
            or instruction["target_revision"] != document["revision"]
        ):
            raise GovernanceError("target_substitution_denied")
        action = instruction["action"]
        if action not in {"restrict", "suppress", "correct"}:
            raise GovernanceError("destructive_execution_disabled")
        version, state = document["current_version"], document["state"]
        if state == "quarantined":
            raise GovernanceError("restore_quarantined")
        if action == "correct":
            evidence = self.evidence.resolve(
                tx,
                member,
                instruction["evidence_id"],
                collection_id=collection["collection_id"],
                document_id=document["document_id"],
                version=version,
            )
            content = self.evidence.content(tx, evidence)
            version += 1
            sealed = self.collection.protection.seal(
                self.collection.store.organization_id,
                collection["collection_id"],
                collection["key_version"],
                content,
                document_context(
                    self.collection.store.organization_id,
                    collection["collection_id"],
                    document["document_id"],
                    version,
                    evidence["content_type"],
                ),
            )
            self.collection.insert_version(
                tx, document["document_id"], version, evidence["content_type"], sealed
            )
        elif action == "restrict" and state != "suppressed":
            state = "restricted"
        elif action == "suppress":
            state = "suppressed"
        row = tx.execute(
            """UPDATE governance_managed_documents SET current_version=%s,state=%s,revision=revision+1,last_instruction_id=%s
            WHERE document_id=%s AND revision=%s AND current_version=%s RETURNING *""",
            (
                version,
                state,
                instruction["instruction_id"],
                document["document_id"],
                instruction["target_revision"],
                instruction["target_version"],
            ),
        ).fetchone()
        if not row:
            raise GovernanceError("revision_conflict")
        proof = tx.execute(
            "SELECT * FROM governance_document_versions WHERE document_id=%s AND version=%s",
            (document["document_id"], version),
        ).fetchone()
        if not proof:
            raise GovernanceError("primary_verification_failed")
        self.collection.protection.open(
            self.collection.store.organization_id,
            collection["collection_id"],
            proof,
            document_context(
                self.collection.store.organization_id,
                collection["collection_id"],
                document["document_id"],
                version,
                proof["content_type"],
            ),
        )
        return {
            "result_version": version,
            "result_revision": row["revision"],
            "result_state": state,
            "ciphertext_digest": proof["ciphertext_digest"],
        }
