"""Encrypted, recipient-bound deliveries with separate download and receipt evidence."""

import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from psycopg.types.json import Jsonb

from pii_redactor.governance.commands import check_revision, identifier, run_command
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.evidence import validate_content
from pii_redactor.governance.rights import RIGHTS_ACTION_MAP, require_rights_role
from pii_redactor.governance.subjects import require_subject_actor


class Delivery:
    def __init__(self, rights):
        self.rights, self.store = rights, rights.store

    def _emit(self, tx, code, row, revision):
        event = self.store.append_event(
            tx, event_code=code, target_id=row["delivery_id"], revision=revision
        )
        tx.execute(
            "INSERT INTO governance_outbox(event_id,event_code,payload) VALUES (%s,%s,%s)",
            (event, code, Jsonb({"record_id": str(row["delivery_id"]), "revision": revision})),
        )

    @staticmethod
    def _context(row):
        return {
            **{
                k: str(row[k])
                for k in ("delivery_id", "case_id", "plan_version", "subject_id", "link_revision")
            },
            "expires_at": row["expires_at"].astimezone(UTC).isoformat(),
        }

    @staticmethod
    def _view(row):
        return {
            "id": str(row["delivery_id"]),
            "revision": row["revision"],
            "state": row["state"],
            "case_id": str(row["case_id"]),
            "export_version": row["plan_version"],
            "expires_at": row["expires_at"].isoformat(),
            "fulfilled": row["state"] == "received",
        }

    def issue(self, principal, key, case_id, revision, approved_export_version, expires_at):
        if type(approved_export_version) is not int or approved_export_version < 1:
            raise GovernanceError("invalid_request")
        if (
            not isinstance(expires_at, datetime)
            or expires_at.tzinfo is None
            or not datetime.now(UTC) < expires_at <= datetime.now(UTC) + timedelta(hours=24)
        ):
            raise GovernanceError("invalid_request")
        expires_at = expires_at.astimezone(UTC)

        def scope(tx, member):
            require_rights_role(member, "delivery.issue")
            row = self.rights._case(tx, member, case_id)
            self.rights._authority(tx, row)
            return row

        def effect(tx, member, row):
            check_revision(row, revision)
            if (
                row["plan_version"] != approved_export_version
                or expires_at > row["approval_expires_at"]
            ):
                raise GovernanceError("export_version_conflict")
            targets = [t for t in row["plan"]["targets"] if t["right"] in {"access", "portability"}]
            if not targets:
                raise GovernanceError("export_unavailable")
            if tx.execute(
                "SELECT 1 FROM governance_rights_deliveries WHERE case_id=%s AND plan_version=%s",
                (row["case_id"], row["plan_version"]),
            ).fetchone():
                raise GovernanceError("export_already_issued")
            v = row["verification"]
            delivery = {
                "delivery_id": uuid4(),
                "case_id": row["case_id"],
                "plan_version": row["plan_version"],
                "subject_id": identifier(v.get("recipient_subject_id") or row["subject_id"]),
                "link_revision": v.get("recipient_link_revision") or row["link_revision"],
                "expires_at": expires_at,
                "collection_id": identifier(targets[0]["collection_id"]),
            }
            content = validate_content(self.rights._export(tx, row, member))
            bucket = self.rights.collection._scope(tx, member, delivery["collection_id"])
            sealed = self.rights.collection.protection.seal(
                self.store.organization_id,
                delivery["collection_id"],
                bucket["key_version"],
                content,
                self._context(delivery),
            )
            stored = tx.execute(
                """INSERT INTO governance_rights_deliveries(delivery_id,case_id,plan_version,
                subject_id,link_revision,collection_id,expires_at,key_version,nonce,ciphertext,ciphertext_digest)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                tuple(
                    delivery[k]
                    for k in (
                        "delivery_id",
                        "case_id",
                        "plan_version",
                        "subject_id",
                        "link_revision",
                        "collection_id",
                        "expires_at",
                    )
                )
                + tuple(
                    sealed[k] for k in ("key_version", "nonce", "ciphertext", "ciphertext_digest")
                ),
            ).fetchone()
            return self._view(stored)

        return run_command(
            self.store,
            principal,
            key,
            RIGHTS_ACTION_MAP["delivery.issue"],
            "rights.delivery_issued",
            {
                "case_id": str(identifier(case_id)),
                "revision": revision,
                "version": approved_export_version,
                "expires_at": expires_at.isoformat(),
            },
            effect,
            scope=scope,
        )

    def _authorize(self, tx, actor, delivery_id):
        require_subject_actor(tx, self.store.organization_id, actor)
        row = tx.execute(
            "SELECT * FROM governance_rights_deliveries WHERE delivery_id=%s FOR UPDATE",
            (identifier(delivery_id),),
        ).fetchone()
        if (
            not row
            or row["subject_id"] != actor.subject_id
            or row["link_revision"] != actor.link_revision
        ):
            raise GovernanceError("record_unavailable")
        case = tx.execute(
            "SELECT * FROM governance_rights_cases WHERE case_id=%s AND organization_id=%s FOR UPDATE",
            (row["case_id"], self.store.organization_id),
        ).fetchone()
        if not case or case["plan_version"] != row["plan_version"] or row["state"] == "revoked":
            raise GovernanceError("delivery_revoked")
        self.rights._authority(tx, case)
        if row["expires_at"] <= tx.execute("SELECT clock_timestamp() AS now").fetchone()["now"]:
            raise GovernanceError("delivery_expired")
        return row, case

    def consume(self, subject_actor, delivery_id):
        with self.store.transaction() as tx:
            self.store.lock(tx)
            row, case = self._authorize(tx, subject_actor, delivery_id)
            if row["state"] != "issued":
                raise GovernanceError("delivery_replay")
            content = self.rights.collection.protection.open(
                self.store.organization_id, row["collection_id"], row, self._context(row)
            ).decode("utf-8")
            require_subject_actor(tx, self.store.organization_id, subject_actor)
            if (
                min(row["expires_at"], case["approval_expires_at"])
                <= tx.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            ):
                raise GovernanceError("delivery_expired")
            receipt = uuid4()
            tx.execute(
                "UPDATE governance_rights_deliveries SET state='downloaded',revision=revision+1,downloaded_session=%s,receipt_ref=%s WHERE delivery_id=%s",
                (subject_actor.session_id, receipt, row["delivery_id"]),
            )
            self._emit(tx, "rights.delivery_downloaded", row, row["revision"] + 1)
            return {
                "id": str(row["delivery_id"]),
                "revision": row["revision"] + 1,
                "export_version": row["plan_version"],
                "content": content,
                "receipt_token": str(receipt),
                "fulfilled": False,
            }

    def acknowledge(self, actor, delivery_id, revision, receipt_token):
        token = identifier(receipt_token)
        with self.store.transaction() as tx:
            self.store.lock(tx)
            row, case = self._authorize(tx, actor, delivery_id)
            check_revision(row, revision)
            if (
                row["state"] != "downloaded"
                or row["downloaded_session"] != actor.session_id
                or not secrets.compare_digest(str(token), str(row["receipt_ref"]))
            ):
                raise GovernanceError("receipt_required")
            row = tx.execute(
                "UPDATE governance_rights_deliveries SET state='received',revision=revision+1 WHERE delivery_id=%s RETURNING *",
                (row["delivery_id"],),
            ).fetchone()
            self._emit(tx, "rights.delivery_received", row, row["revision"])
            return self._view(row)

    def revoke(self, principal, key, case_id, revision, evidence_ref):
        evidence_ref = identifier(evidence_ref)

        def effect(tx, member, row):
            tx.execute(
                "UPDATE governance_rights_deliveries SET state='revoked',revision=revision+1 WHERE case_id=%s AND state<>'revoked'",
                (row["case_id"],),
            )
            return self.rights._save(
                tx, row, member, "delivery_revoked", state=row["state"], review_ref=evidence_ref
            )

        return self.rights._run(
            principal, key, case_id, revision, "delivery.revoke", str(evidence_ref), effect
        )
