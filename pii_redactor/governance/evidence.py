"""Protected evidence and envelopes. Keys are supplied by an independent authority."""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import Literal, Protocol
from uuid import UUID, uuid4

from pydantic import Field, ValidationError, model_validator

from pii_redactor.governance.commands import identifier, run_command
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import ClosedModel
from pii_redactor.governance.permissions import in_scope, require_member
from pii_redactor.governance.registry import RecordID

MAX_CONTENT_BYTES = 32768
ContentType = Literal["text/plain", "application/json"]


class KeyProvider(Protocol):
    def key_for(self, organization_id: UUID, collection_id: UUID, version: str) -> bytes: ...


class SyntheticKeyProvider:
    """In-memory keys for synthetic local exercises, never production key management."""

    def __init__(self, keys):
        if not isinstance(keys, dict) or not keys:
            raise GovernanceError("key_configuration_invalid")
        for scope, key in keys.items():
            if (
                not isinstance(scope, tuple)
                or len(scope) != 3
                or not isinstance(scope[0], UUID)
                or (scope[1] is not None and not isinstance(scope[1], UUID))
                or not isinstance(scope[2], str)
                or not scope[2]
                or type(key) is not bytes
                or len(key) != 32
            ):
                raise GovernanceError("key_configuration_invalid")
        self._keys = dict(keys)

    def key_for(self, organization_id, collection_id, version):
        key = self._keys.get((organization_id, collection_id, version))
        if key is None:
            key = self._keys.get((organization_id, None, version))
        if key is None:
            raise GovernanceError("key_version_unavailable")
        return key


class ProtectedStorage:
    def __init__(self, key_provider):
        self.key_provider = key_provider

    def require_key(self, organization_id, collection_id, version):
        if self.key_provider is None:
            raise GovernanceError("key_service_unavailable")
        try:
            key = self.key_provider.key_for(organization_id, collection_id, version)
        except GovernanceError:
            raise
        except Exception:
            raise GovernanceError("key_service_unavailable") from None
        if type(key) is not bytes or len(key) != 32:
            raise GovernanceError("key_configuration_invalid")
        return key

    @staticmethod
    def _aad(context, key_version):
        return json.dumps(
            {"context": context, "key_version": key_version}, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

    def seal(self, organization_id, collection_id, key_version, content, context):
        content = validate_content(content)
        key = self.require_key(organization_id, collection_id, key_version)
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError:
            raise GovernanceError("key_service_unavailable") from None
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(key).encrypt(nonce, content, self._aad(context, key_version))
        return {
            "key_version": key_version,
            "nonce": nonce,
            "ciphertext": ciphertext,
            "ciphertext_digest": hashlib.sha256(ciphertext).hexdigest(),
        }

    def open(self, organization_id, collection_id, envelope, context):
        key = self.require_key(organization_id, collection_id, envelope["key_version"])
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            ciphertext = bytes(envelope["ciphertext"])
            if hashlib.sha256(ciphertext).hexdigest() != envelope["ciphertext_digest"]:
                raise ValueError
            return AESGCM(key).decrypt(
                bytes(envelope["nonce"]), ciphertext, self._aad(context, envelope["key_version"])
            )
        except Exception:
            raise GovernanceError("protected_content_invalid") from None


def validate_content(content, content_type="text/plain"):
    if isinstance(content, str):
        content = content.encode("utf-8")
    if type(content) is not bytes or not 1 <= len(content) <= MAX_CONTENT_BYTES:
        raise GovernanceError("content_invalid")
    if content_type not in {"text/plain", "application/json"}:
        raise GovernanceError("content_invalid")
    try:
        text = content.decode("utf-8")
        if content_type == "application/json":
            json.loads(text)
    except (UnicodeError, ValueError, RecursionError):
        raise GovernanceError("content_invalid") from None
    return content


class EvidenceInput(ClosedModel):
    collection_id: RecordID
    document_id: RecordID | None = None
    expected_version: int | None = Field(default=None, ge=1)
    content_type: ContentType = "text/plain"
    content: str = Field(min_length=1, max_length=MAX_CONTENT_BYTES)

    @model_validator(mode="after")
    def target_is_complete(self):
        if (self.document_id is None) != (self.expected_version is None):
            raise ValueError("incomplete evidence target")
        validate_content(self.content, self.content_type)
        return self


def evidence_context(organization_id, row):
    return {
        "kind": "evidence",
        "organization": str(organization_id),
        "collection": str(row["collection_id"]),
        "evidence": str(row["evidence_id"]),
        "document": str(row["document_id"]) if row["document_id"] else None,
        "version": row["target_version"],
        "content_type": row["content_type"],
    }


class Evidence:
    def __init__(self, store, key_provider, *, collection=None):
        self.store = store
        self.protection = ProtectedStorage(key_provider)
        self.collection = collection

    def _scope(self, tx, member, collection_id):
        row = tx.execute(
            "SELECT * FROM governance_collections WHERE collection_id=%s AND organization_id=%s FOR UPDATE",
            (identifier(collection_id), self.store.organization_id),
        ).fetchone()
        if not row or not in_scope(member, row["department_id"]):
            raise GovernanceError("record_unavailable")
        if row["state"] != "ready":
            raise GovernanceError("restore_quarantined")
        if self.collection is None:
            from pii_redactor.governance.collections import Collection

            collection = Collection(self.store, self.protection.key_provider)
        else:
            collection = self.collection
        collection._active(tx, row)
        collection.check_consent(tx, row, None, "evidence")
        return row

    def put(self, principal, command_key, request):
        try:
            data = EvidenceInput.model_validate(request.model_dump())
        except (ValidationError, AttributeError):
            raise GovernanceError("invalid_request") from None
        content = validate_content(data.content, data.content_type)

        def scope(tx, member):
            collection = self._scope(tx, member, data.collection_id)
            if data.document_id:
                target = tx.execute(
                    "SELECT * FROM governance_managed_documents WHERE document_id=%s AND collection_id=%s FOR UPDATE",
                    (data.document_id, data.collection_id),
                ).fetchone()
                if not target or target["current_version"] != data.expected_version:
                    raise GovernanceError("record_unavailable")
            return collection

        def effect(tx, member, collection):
            row = {
                "evidence_id": uuid4(),
                "collection_id": data.collection_id,
                "document_id": data.document_id,
                "target_version": data.expected_version,
                "content_type": data.content_type,
            }
            sealed = self.protection.seal(
                self.store.organization_id,
                data.collection_id,
                collection["key_version"],
                content,
                evidence_context(self.store.organization_id, row),
            )
            tx.execute(
                """INSERT INTO governance_protected_evidence(evidence_id,organization_id,collection_id,
                document_id,target_version,key_version,nonce,ciphertext,ciphertext_digest,content_type,created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    row["evidence_id"],
                    self.store.organization_id,
                    data.collection_id,
                    data.document_id,
                    data.expected_version,
                    sealed["key_version"],
                    sealed["nonce"],
                    sealed["ciphertext"],
                    sealed["ciphertext_digest"],
                    data.content_type,
                    member["member_id"],
                ),
            )
            return {"id": str(row["evidence_id"]), "revision": 1, "state": "protected"}

        return run_command(
            self.store,
            principal,
            command_key,
            "evidence.create",
            "evidence.created",
            data.model_dump(mode="json"),
            effect,
            scope=scope,
        )

    def resolve(self, tx, member, evidence_id, *, collection_id, document_id=None, version=None):
        row = tx.execute(
            "SELECT * FROM governance_protected_evidence WHERE evidence_id=%s AND organization_id=%s",
            (identifier(evidence_id), self.store.organization_id),
        ).fetchone()
        if (
            not row
            or row["collection_id"] != identifier(collection_id)
            or row["document_id"] != (identifier(document_id) if document_id else None)
            or row["target_version"] != version
        ):
            raise GovernanceError("evidence_unavailable")
        self._scope(tx, member, row["collection_id"])
        return row

    def content(self, tx, row):
        return self.protection.open(
            self.store.organization_id,
            row["collection_id"],
            row,
            evidence_context(self.store.organization_id, row),
        )

    def read(self, principal, evidence_id):
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "evidence.read")
            row = tx.execute(
                "SELECT * FROM governance_protected_evidence WHERE evidence_id=%s AND organization_id=%s",
                (identifier(evidence_id), self.store.organization_id),
            ).fetchone()
            if not row:
                raise GovernanceError("evidence_unavailable")
            self._scope(tx, member, row["collection_id"])
            if row["document_id"]:
                doc = tx.execute(
                    "SELECT state,current_version FROM governance_managed_documents WHERE document_id=%s FOR UPDATE",
                    (row["document_id"],),
                ).fetchone()
                if (
                    not doc
                    or doc["state"] != "active"
                    or doc["current_version"] != row["target_version"]
                ):
                    raise GovernanceError("record_restricted")
            self.store.append_event(
                tx,
                event_code="evidence.read",
                actor_id=member["member_id"],
                target_id=row["evidence_id"],
            )
            return {
                "id": str(row["evidence_id"]),
                "content_type": row["content_type"],
                "content": self.content(tx, row).decode("utf-8"),
            }
