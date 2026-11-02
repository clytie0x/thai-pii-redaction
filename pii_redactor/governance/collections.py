"""Application-managed encrypted documents within the governance transaction boundary."""

from __future__ import annotations

import hashlib
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import Field, ValidationError

from pii_redactor.governance.commands import check_revision, digest, identifier, run_command
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.evidence import ContentType, ProtectedStorage, validate_content
from pii_redactor.governance.models import ClosedModel
from pii_redactor.governance.permissions import in_scope, require_member
from pii_redactor.governance.registry import RecordID


class CollectionInput(ClosedModel):
    activity_id: RecordID
    expected_activity_revision: int = Field(ge=1)
    subject_id: RecordID | None = None
    purpose_version: RecordID | None = None


def document_context(organization_id, collection_id, document_id, version, content_type):
    return {
        "kind": "document",
        "organization": str(organization_id),
        "collection": str(collection_id),
        "document": str(document_id),
        "version": version,
        "content_type": content_type,
    }


def collection_view(row):
    return {
        "id": str(row["collection_id"]),
        "revision": row["revision"],
        "activity_id": str(row["activity_id"]),
        "department_id": row["department_id"],
        "state": row["state"],
        "consent_bound": row["consent_bound"],
    }


def document_view(row):
    return {
        "id": str(row["document_id"]),
        "collection_id": str(row["collection_id"]),
        "revision": row["revision"],
        "version": row["current_version"],
        "state": row["state"],
    }


class Collection:
    def __init__(self, store, key_provider, *, consent_check=None, key_version="v1"):
        if not isinstance(key_version, str) or not 1 <= len(key_version) <= 64:
            raise GovernanceError("key_configuration_invalid")
        self.store, self.consent_check = store, consent_check
        self.protection = ProtectedStorage(key_provider)
        self.key_version = key_version

    def _hold_fence(self, tx, collection, document, action):
        from pii_redactor.governance.holds import Holds

        return Holds(self.store).fence(
            tx,
            collection_id=collection["collection_id"],
            document_id=document["document_id"] if document else None,
            action=action,
        )

    def check_consent(self, tx, collection, document, action):
        self._hold_fence(tx, collection, document, action)
        if not collection["consent_bound"]:
            return
        if self.consent_check is None:
            raise GovernanceError("consent_authority_unavailable")
        try:
            allowed = self.consent_check(
                tx, collection=collection, document=document, action=action
            )
        except GovernanceError:
            raise
        except Exception:
            raise GovernanceError("consent_authority_unavailable") from None
        if allowed is not True:
            raise GovernanceError("consent_required")

    def _active(self, tx, collection):
        activity = tx.execute(
            "SELECT * FROM governance_activities WHERE activity_id=%s AND organization_id=%s FOR UPDATE",
            (collection["activity_id"], self.store.organization_id),
        ).fetchone()
        if (
            not activity
            or activity["state"] != "active"
            or activity["revision"] != collection["activity_revision"]
        ):
            raise GovernanceError("activity_authority_changed")
        return activity

    def _scope(self, tx, member, collection_id, *, allow_quarantine=False):
        row = tx.execute(
            "SELECT * FROM governance_collections WHERE collection_id=%s AND organization_id=%s FOR UPDATE",
            (identifier(collection_id), self.store.organization_id),
        ).fetchone()
        if not row or not in_scope(member, row["department_id"]):
            raise GovernanceError("record_unavailable")
        if row["state"] != "ready" and not allow_quarantine:
            raise GovernanceError("restore_quarantined")
        self._active(tx, row)
        self.protection.require_key(
            self.store.organization_id, row["collection_id"], row["key_version"]
        )
        return row

    def _document(self, tx, collection_id, document_id):
        row = tx.execute(
            "SELECT * FROM governance_managed_documents WHERE document_id=%s AND collection_id=%s AND organization_id=%s FOR UPDATE",
            (identifier(document_id), identifier(collection_id), self.store.organization_id),
        ).fetchone()
        if not row:
            raise GovernanceError("record_unavailable")
        return row

    def create(self, principal, command_key, request):
        try:
            data = CollectionInput.model_validate(request.model_dump())
        except (ValidationError, AttributeError):
            raise GovernanceError("invalid_request") from None

        def scope(tx, member):
            row = tx.execute(
                "SELECT * FROM governance_activities WHERE activity_id=%s AND organization_id=%s FOR UPDATE",
                (data.activity_id, self.store.organization_id),
            ).fetchone()
            if not row or not in_scope(member, row["department_id"]):
                raise GovernanceError("record_unavailable")
            check_revision(row, data.expected_activity_revision)
            if row["state"] != "active":
                raise GovernanceError("activity_inactive")
            return row

        def effect(tx, member, activity):
            record_id = uuid4()
            consent_bound = (
                activity["data"].get("general_basis") == "consent"
                or activity["data"].get("sensitive_condition") == "explicit_consent"
            )
            if consent_bound and (data.subject_id is None or data.purpose_version is None):
                raise GovernanceError("consent_scope_required")
            if not consent_bound and (
                data.subject_id is not None or data.purpose_version is not None
            ):
                raise GovernanceError("invalid_request")
            self.protection.require_key(self.store.organization_id, record_id, self.key_version)
            row = tx.execute(
                """INSERT INTO governance_collections(collection_id,organization_id,activity_id,activity_revision,
                department_id,consent_bound,subject_id,purpose_version,key_version,created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    record_id,
                    self.store.organization_id,
                    data.activity_id,
                    activity["revision"],
                    activity["department_id"],
                    consent_bound,
                    data.subject_id,
                    data.purpose_version,
                    self.key_version,
                    member["member_id"],
                ),
            ).fetchone()
            self.check_consent(tx, row, None, "create")
            return collection_view(row)

        return run_command(
            self.store,
            principal,
            command_key,
            "collection.create",
            "collection.created",
            data.model_dump(mode="json"),
            effect,
            scope=scope,
        )

    def put(
        self,
        principal,
        command_key,
        collection_id,
        content,
        *,
        content_type: ContentType = "text/plain",
    ):
        collection_id = identifier(collection_id)
        content = validate_content(content, content_type)
        record_id = uuid4()

        def scope(tx, member):
            collection = self._scope(tx, member, collection_id)
            self.check_consent(tx, collection, {"document_id": record_id}, "put")
            return collection

        def effect(tx, member, collection):
            sealed = self.protection.seal(
                self.store.organization_id,
                collection_id,
                collection["key_version"],
                content,
                document_context(
                    self.store.organization_id, collection_id, record_id, 1, content_type
                ),
            )
            row = tx.execute(
                """INSERT INTO governance_managed_documents(document_id,collection_id,organization_id,current_version)
                VALUES (%s,%s,%s,1) RETURNING *""",
                (record_id, collection_id, self.store.organization_id),
            ).fetchone()
            self.insert_version(tx, record_id, 1, content_type, sealed)
            return document_view(row)

        return run_command(
            self.store,
            principal,
            command_key,
            "collection.put",
            "document.created",
            {
                "collection_id": str(collection_id),
                "content_type": content_type,
                "content_digest": hashlib.sha256(content).hexdigest(),
            },
            effect,
            scope=scope,
        )

    @staticmethod
    def insert_version(tx, document_id, version, content_type, sealed):
        tx.execute(
            """INSERT INTO governance_document_versions(document_id,version,key_version,nonce,ciphertext,ciphertext_digest,content_type)
            VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (
                document_id,
                version,
                sealed["key_version"],
                sealed["nonce"],
                sealed["ciphertext"],
                sealed["ciphertext_digest"],
                content_type,
            ),
        )

    def list(self, principal):
        with self.store.transaction() as tx:
            member = require_member(tx, self.store.organization_id, principal, "collection.read")
            rows = tx.execute(
                "SELECT * FROM governance_collections WHERE organization_id=%s ORDER BY created_at,collection_id LIMIT 100",
                (self.store.organization_id,),
            ).fetchall()
            return [collection_view(row) for row in rows if in_scope(member, row["department_id"])]

    def recovery_collections(self, principal):
        """Operational metadata only; restore authority does not grant content access."""
        with self.store.transaction() as tx:
            member = require_member(tx, self.store.organization_id, principal, "restore.manage")
            rows = tx.execute(
                "SELECT * FROM governance_collections WHERE organization_id=%s ORDER BY created_at,collection_id LIMIT 100",
                (self.store.organization_id,),
            ).fetchall()
            return [collection_view(row) for row in rows if in_scope(member, row["department_id"])]

    def documents(self, principal, collection_id):
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "collection.read")
            collection = self._scope(tx, member, collection_id)
            self.check_consent(tx, collection, None, "list")
            rows = tx.execute(
                "SELECT * FROM governance_managed_documents WHERE collection_id=%s ORDER BY created_at,document_id LIMIT 100",
                (collection["collection_id"],),
            ).fetchall()
            return [document_view(row) for row in rows]

    def read_version(self, principal, collection_id, document_id, version):
        if type(version) is not int or version < 1:
            raise GovernanceError("invalid_request")
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "collection.read")
            collection = self._scope(tx, member, collection_id)
            document = self._document(tx, collection_id, document_id)
            self.check_consent(tx, collection, document, "read")
            if document["state"] != "active":
                raise GovernanceError("record_restricted")
            if document["current_version"] != version:
                raise GovernanceError("version_unavailable")
            row = tx.execute(
                "SELECT * FROM governance_document_versions WHERE document_id=%s AND version=%s",
                (document["document_id"], version),
            ).fetchone()
            if not row:
                raise GovernanceError("protected_content_invalid")
            content = self.protection.open(
                self.store.organization_id,
                collection["collection_id"],
                row,
                document_context(
                    self.store.organization_id,
                    collection["collection_id"],
                    document["document_id"],
                    version,
                    row["content_type"],
                ),
            )
            self.store.append_event(
                tx,
                event_code="document.read",
                actor_id=member["member_id"],
                target_id=document["document_id"],
                revision=document["revision"],
            )
            return {
                **document_view(document),
                "content_type": row["content_type"],
                "content": content.decode("utf-8"),
            }

    def snapshot(self, principal, command_key, collection_id):
        collection_id = identifier(collection_id)

        def effect(tx, member, collection):
            rows = tx.execute(
                "SELECT * FROM governance_managed_documents WHERE collection_id=%s ORDER BY document_id FOR UPDATE",
                (collection_id,),
            ).fetchall()
            manifest = [document_view(row) for row in rows]
            row = tx.execute(
                """INSERT INTO governance_collection_snapshots(snapshot_id,collection_id,collection_revision,manifest,manifest_digest,captured_by)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    uuid4(),
                    collection_id,
                    collection["revision"],
                    Jsonb(manifest),
                    digest(manifest),
                    member["member_id"],
                ),
            ).fetchone()
            return {
                "id": str(row["snapshot_id"]),
                "revision": row["revision"],
                "state": row["state"],
                "document_count": len(manifest),
            }

        return run_command(
            self.store,
            principal,
            command_key,
            "restore.manage",
            "collection.snapshot",
            {"collection_id": str(collection_id)},
            effect,
            scope=lambda tx, member: self._scope(tx, member, collection_id),
        )

    def _snapshot(self, tx, member, snapshot_id):
        row = tx.execute(
            "SELECT * FROM governance_collection_snapshots WHERE snapshot_id=%s FOR UPDATE",
            (identifier(snapshot_id),),
        ).fetchone()
        if not row:
            raise GovernanceError("record_unavailable")
        self._scope(tx, member, row["collection_id"], allow_quarantine=True)
        if digest(row["manifest"]) != row["manifest_digest"]:
            raise GovernanceError("restore_integrity_failure")
        return row

    def restore_quarantine(self, principal, command_key, snapshot_id, expected_revision):
        snapshot_id = identifier(snapshot_id)

        def effect(tx, member, snapshot):
            check_revision(snapshot, expected_revision)
            if snapshot["state"] != "captured":
                raise GovernanceError("invalid_transition")
            collection = self._scope(tx, member, snapshot["collection_id"])
            self._hold_fence(tx, collection, None, "restore_quarantine")
            unresolved = tx.execute(
                "SELECT 1 FROM governance_execution_instructions WHERE collection_id=%s AND state IN ('pending','running','unknown') LIMIT 1",
                (snapshot["collection_id"],),
            ).fetchone()
            if unresolved:
                raise GovernanceError("restore_reconciliation_required")
            docs = tx.execute(
                "SELECT * FROM governance_managed_documents WHERE collection_id=%s ORDER BY document_id FOR UPDATE",
                (snapshot["collection_id"],),
            ).fetchall()
            if {str(d["document_id"]) for d in docs} != {d["id"] for d in snapshot["manifest"]}:
                raise GovernanceError("restore_scope_unknown")
            controls = [document_view(row) for row in docs]
            tx.execute(
                "UPDATE governance_collections SET state='quarantined',revision=revision+1 WHERE collection_id=%s",
                (snapshot["collection_id"],),
            )
            for document in snapshot["manifest"]:
                tx.execute(
                    "UPDATE governance_managed_documents SET current_version=%s,state='quarantined',revision=revision+1 WHERE document_id=%s",
                    (document["version"], identifier(document["id"])),
                )
            row = tx.execute(
                "UPDATE governance_collection_snapshots SET state='quarantined',restore_controls=%s,restored_by=%s,revision=revision+1 WHERE snapshot_id=%s RETURNING *",
                (Jsonb(controls), member["member_id"], snapshot_id),
            ).fetchone()
            return {"id": str(snapshot_id), "revision": row["revision"], "state": "quarantined"}

        return run_command(
            self.store,
            principal,
            command_key,
            "restore.manage",
            "collection.restore_quarantined",
            {"snapshot_id": str(snapshot_id), "revision": expected_revision},
            effect,
            scope=lambda tx, member: self._snapshot(tx, member, snapshot_id),
        )

    def reconcile_restore(self, principal, command_key, snapshot_id, expected_revision):
        snapshot_id = identifier(snapshot_id)

        def effect(tx, member, snapshot):
            check_revision(snapshot, expected_revision)
            if snapshot["state"] != "quarantined" or not isinstance(
                snapshot["restore_controls"], list
            ):
                raise GovernanceError("invalid_transition")
            if member["member_id"] == snapshot["restored_by"]:
                raise GovernanceError("separation_required")
            collection = self._scope(tx, member, snapshot["collection_id"], allow_quarantine=True)
            self.check_consent(tx, collection, None, "restore_release")
            unresolved = tx.execute(
                "SELECT 1 FROM governance_execution_instructions WHERE collection_id=%s AND state IN ('pending','running','unknown') LIMIT 1",
                (snapshot["collection_id"],),
            ).fetchone()
            if unresolved:
                raise GovernanceError("restore_reconciliation_required")
            for control in snapshot["restore_controls"]:
                if control["state"] not in {"active", "restricted", "suppressed"}:
                    raise GovernanceError("restore_integrity_failure")
                doc = self._document(tx, snapshot["collection_id"], control["id"])
                self.check_consent(tx, collection, doc, "restore_release")
                row = tx.execute(
                    "SELECT * FROM governance_document_versions WHERE document_id=%s AND version=%s",
                    (doc["document_id"], control["version"]),
                ).fetchone()
                if not row:
                    raise GovernanceError("restore_integrity_failure")
                self.protection.open(
                    self.store.organization_id,
                    snapshot["collection_id"],
                    row,
                    document_context(
                        self.store.organization_id,
                        snapshot["collection_id"],
                        doc["document_id"],
                        control["version"],
                        row["content_type"],
                    ),
                )
                # The pre-restore effective controls reapply corrections and restrictions.
                tx.execute(
                    "UPDATE governance_managed_documents SET current_version=%s,state=%s,revision=revision+1 WHERE document_id=%s",
                    (control["version"], control["state"], doc["document_id"]),
                )
            tx.execute(
                "UPDATE governance_collections SET state='ready',revision=revision+1 WHERE collection_id=%s",
                (snapshot["collection_id"],),
            )
            row = tx.execute(
                "UPDATE governance_collection_snapshots SET state='reconciled',reviewed_by=%s,revision=revision+1 WHERE snapshot_id=%s RETURNING *",
                (member["member_id"], snapshot_id),
            ).fetchone()
            return {"id": str(snapshot_id), "revision": row["revision"], "state": "reconciled"}

        return run_command(
            self.store,
            principal,
            command_key,
            "execution.reconcile",
            "collection.restore_reconciled",
            {"snapshot_id": str(snapshot_id), "revision": expected_revision},
            effect,
            scope=lambda tx, member: self._snapshot(tx, member, snapshot_id),
        )

    def check_ready(self):
        self.store.verify_audit()
        with self.store.transaction() as tx:
            self.store.lock(tx)
            rows = tx.execute(
                "SELECT * FROM governance_collections WHERE organization_id=%s FOR UPDATE",
                (self.store.organization_id,),
            ).fetchall()
            if self.protection.key_provider is None:
                raise GovernanceError("key_service_unavailable")
            for row in rows:
                if row["state"] != "ready":
                    raise GovernanceError("restore_quarantined")
                self.protection.require_key(
                    self.store.organization_id, row["collection_id"], row["key_version"]
                )
                if row["consent_bound"] and self.consent_check is None:
                    raise GovernanceError("consent_authority_unavailable")
                documents = tx.execute(
                    """SELECT d.document_id,d.current_version,d.state,v.*
                    FROM governance_managed_documents d JOIN governance_document_versions v
                    ON v.document_id=d.document_id AND v.version=d.current_version WHERE d.collection_id=%s""",
                    (row["collection_id"],),
                ).fetchall()
                for document in documents:
                    if document["state"] == "quarantined":
                        raise GovernanceError("restore_quarantined")
                    self.protection.open(
                        self.store.organization_id,
                        row["collection_id"],
                        document,
                        document_context(
                            self.store.organization_id,
                            row["collection_id"],
                            document["document_id"],
                            document["current_version"],
                            document["content_type"],
                        ),
                    )
            return {
                "collections": len(rows),
                "destructive_execution": False,
                "recovery_acceptance": "not_accepted",
            }
