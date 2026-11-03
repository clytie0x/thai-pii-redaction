"""Minimized signed audit heads. The application holds only a public verify key."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from pii_redactor.governance.errors import GovernanceError


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def head(sequence, event_hash):
    if (
        type(sequence) is not int
        or not 0 <= sequence <= 2**63 - 1
        or not isinstance(event_hash, str)
        or not re.fullmatch("[0-9a-f]{64}", event_hash)
        or (sequence == 0 and event_hash != "0" * 64)
    ):
        raise ValueError
    return sequence, event_hash


class _WitnessHistory:
    __slots__ = ("anchors", "authority", "client", "receipt")

    def __init__(self, client, receipt, anchors):
        self.client, self.authority = client, client.authority_binding()
        self.receipt, self.anchors = dict(receipt), tuple(anchors)


class Witness:
    """Reference witness, to be operated under a different custodian and host.

    SQLite is the independent witness journal, never the application database.
    Its file/host/retention protection remains the witness operator's acceptance.
    """

    def __init__(self, path, private_key, *, organization_id=None):
        self.path, self.private_key = path, private_key
        self.organization_id = str(organization_id) if organization_id is not None else None
        with sqlite3.connect(path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS checkpoints (
                organization TEXT NOT NULL, sequence INTEGER NOT NULL, event_hash TEXT NOT NULL,
                checkpointed_at REAL NOT NULL, PRIMARY KEY(organization,sequence))""")

    def exchange(self, request):
        if set(request) not in (
            {"organization", "nonce"},
            {"organization", "nonce", "after"},
            {"organization", "nonce", "sequence", "event_hash", "previous"},
        ):
            raise ValueError
        organization = str(UUID(request["organization"]))
        if self.organization_id is not None and organization != self.organization_id:
            raise ValueError
        if not re.fullmatch("[0-9a-f]{64}", request["nonce"]):
            raise ValueError
        after = request.get("after", 0)
        if type(after) is not int or not 0 <= after <= 2**63 - 1:
            raise ValueError
        with sqlite3.connect(self.path, timeout=3) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT sequence,event_hash,checkpointed_at FROM checkpoints "
                "WHERE organization=? ORDER BY sequence DESC LIMIT 1",
                (organization,),
            ).fetchone()
            if "sequence" in request:
                seq, digest = head(request["sequence"], request["event_hash"])
                previous = request["previous"]
                expected = list(row[:2]) if row else [0, "0" * 64]
                if row and (seq, digest) == tuple(row[:2]):
                    pass  # Retrying an acknowledgement must not refresh checkpoint age.
                elif previous != expected or seq <= (row[0] if row else 0):
                    raise ValueError
                else:
                    db.execute(
                        "INSERT INTO checkpoints VALUES (?,?,?,?)",
                        (organization, seq, digest, time.time()),
                    )
                    row = (seq, digest, time.time())
            if row is None:
                raise ValueError
            anchors = db.execute(
                "SELECT sequence,event_hash FROM checkpoints WHERE organization=? "
                "AND sequence>? ORDER BY sequence LIMIT 33",
                (organization, after),
            ).fetchall()
        payload = {
            "organization": organization,
            "nonce": request["nonce"],
            "sequence": row[0],
            "event_hash": row[1],
            "checkpointed_at": row[2],
            "issued_at": time.time(),
            "anchors": anchors[:32],
            "more": len(anchors) > 32,
        }
        return {
            "payload": payload,
            "signature": base64.b64encode(self.private_key.sign(canonical(payload))).decode(),
        }


def witness_handler(witness, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            try:
                if (
                    self.path != "/checkpoint"
                    or self.headers.get("Transfer-Encoding")
                    or not hmac.compare_digest(
                        self.headers.get("Authorization", ""), "Bearer " + token
                    )
                ):
                    raise ValueError
                size = int(self.headers.get("Content-Length", "0"))
                if not 1 <= size <= 4096:
                    raise ValueError
                self.connection.settimeout(3)
                data = canonical(witness.exchange(json.loads(self.rfile.read(size))))
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self.send_error(409, "checkpoint_rejected")

    return Handler


class CheckpointClient:
    def __init__(
        self,
        url,
        token,
        public_key,
        organization_id,
        *,
        development=False,
        max_age=300,
        max_events=100,
    ):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            and not (
                development
                and parsed.scheme == "http"
                and parsed.hostname in {"127.0.0.1", "::1", "localhost"}
            )
        ) or (
            parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or not parsed.hostname
            or type(max_age) is not int
            or not 1 <= max_age <= 86400
            or type(max_events) is not int
            or not 0 <= max_events <= 10000
            or not isinstance(organization_id, UUID)
            or not isinstance(token, str)
            or not 1 <= len(token) <= 4096
        ):
            raise GovernanceError("checkpoint_configuration_invalid")
        self.url, self._token, self.public_key = url.rstrip("/"), token, public_key
        self.organization_id = organization_id
        self.max_age, self.max_events = max_age, max_events

    def _exchange(self, fields):
        nonce = secrets.token_hex(32)
        request = {"organization": str(self.organization_id), "nonce": nonce, **fields}
        try:
            with httpx.Client(timeout=3, follow_redirects=False, trust_env=False) as client:
                with client.stream(
                    "POST",
                    self.url + "/checkpoint",
                    json=request,
                    headers={"Authorization": "Bearer " + self._token},
                ) as response:
                    response.raise_for_status()
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 4096:
                            raise ValueError
            value = json.loads(raw)
            payload = value["payload"]
            self.public_key.verify(
                base64.b64decode(value["signature"], validate=True), canonical(payload)
            )
            if (
                set(payload)
                != {
                    "organization",
                    "nonce",
                    "sequence",
                    "event_hash",
                    "checkpointed_at",
                    "issued_at",
                    "anchors",
                    "more",
                }
                or payload["organization"] != str(self.organization_id)
                or payload["nonce"] != nonce
                or abs(time.time() - payload["issued_at"]) > 10
                or not 0 <= payload["issued_at"] - payload["checkpointed_at"]
            ):
                raise ValueError
            head(payload["sequence"], payload["event_hash"])
            if (
                not isinstance(payload["anchors"], list)
                or len(payload["anchors"]) > 32
                or type(payload["more"]) is not bool
            ):
                raise ValueError
            for anchor in payload["anchors"]:
                head(*anchor)
            return payload
        except Exception:
            raise GovernanceError("checkpoint_unavailable") from None

    def fetch(self, *, after=None):
        return self._exchange({} if after is None else {"after": after})

    def authority_binding(self):
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        values = (
            self.url,
            str(self.organization_id),
            self.max_age,
            self.max_events,
            hashlib.sha256(self._token.encode()).hexdigest(),
            self.public_key.public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
        )
        return hashlib.sha256(canonical(values)).hexdigest()

    def prepare_history(self):
        """Fetch the complete bounded signed journal before opening a DB snapshot."""
        authority = self.authority_binding()
        receipt = page = self.fetch()
        after, anchors = 0, []
        for _ in range(64):
            if (page["sequence"], page["event_hash"]) != (
                receipt["sequence"],
                receipt["event_hash"],
            ):
                raise GovernanceError("checkpoint_integrity_failure")
            for sequence, event_hash in page["anchors"]:
                if not after < sequence <= receipt["sequence"]:
                    raise GovernanceError("checkpoint_integrity_failure")
                anchors.append((sequence, event_hash))
                after = sequence
            if not page["more"]:
                if (
                    not anchors
                    or anchors[-1] != (receipt["sequence"], receipt["event_hash"])
                    or authority != self.authority_binding()
                ):
                    raise GovernanceError("checkpoint_integrity_failure")
                return _WitnessHistory(self, receipt, anchors)
            if not page["anchors"]:
                raise GovernanceError("checkpoint_integrity_failure")
            page = self.fetch(after=after)
        raise GovernanceError("checkpoint_history_limit")

    def _check_snapshot(self, store, history):
        if (
            not isinstance(history, _WitnessHistory)
            or history.client is not self
            or history.authority != self.authority_binding()
        ):
            raise GovernanceError("checkpoint_integrity_failure")
        audit = store.verify_audit()
        expected = dict(history.anchors)
        expected[history.receipt["sequence"]] = history.receipt["event_hash"]
        if history.receipt["sequence"] > audit["events"]:
            raise GovernanceError("checkpoint_integrity_failure")
        with store.transaction() as tx:
            observed = {
                row["sequence"]: row["event_hash"]
                for row in tx.execute(
                    "SELECT sequence,event_hash FROM governance_audit WHERE sequence=ANY(%s)",
                    (list(expected),),
                )
            }
        if observed != expected:
            raise GovernanceError("checkpoint_integrity_failure")
        # Current lag/age are checked against the real current DB after verification.
        return dict(history.receipt)

    def publish(self, sequence, event_hash, *, previous=(0, "0" * 64)):
        try:
            head(sequence, event_hash)
            head(*previous)
        except (ValueError, TypeError):
            raise GovernanceError("checkpoint_integrity_failure") from None
        return self._exchange(
            {"sequence": sequence, "event_hash": event_hash, "previous": list(previous)}
        )

    def verify_chain(self, chain, receipt):
        seq = receipt["sequence"]
        if (
            chain.get(seq) != receipt["event_hash"]
            or max(chain, default=0) - seq > self.max_events
            or (
                max(chain, default=0) > seq
                and not 0 <= time.time() - receipt["checkpointed_at"] <= self.max_age
            )
        ):
            raise GovernanceError("checkpoint_integrity_failure")
        return True

    def check(self, store, *, publish=False, history=None):
        if getattr(store, "_verifier_snapshot", False):
            if publish:
                raise GovernanceError("verifier_snapshot_only")
            return self._check_snapshot(store, history or self.prepare_history())
        if history is not None:
            raise GovernanceError("verifier_snapshot_only")
        if not publish and getattr(store, "production_operations_required", False):
            prepared = self.prepare_history()
            with store.private_snapshot() as snapshot:
                receipt = self.check(snapshot, history=prepared)
                audit = snapshot.verify_audit()
            fresh = self.fetch(after=receipt["sequence"])
            with store.transaction() as tx:
                return self.check_extension(
                    store, (audit["events"], audit["tail_hash"]), receipt, tx=tx, receipt=fresh
                )
        store.verify_audit()
        with store.transaction() as tx:
            # Bounded server cursor avoids loading a long chain into memory.
            tail = tx.execute(
                "SELECT sequence,event_hash FROM governance_audit ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            if not tail:
                raise GovernanceError("checkpoint_integrity_failure")
            if publish:
                try:
                    previous = self.fetch()
                except GovernanceError:
                    # Only the sink may accept initial publication. Never overwrite its head.
                    previous = {"sequence": 0, "event_hash": "0" * 64}
                anchor = tx.execute(
                    "SELECT event_hash FROM governance_audit WHERE sequence=%s",
                    (previous["sequence"],),
                ).fetchone()
                if previous["sequence"] and (
                    not anchor or anchor["event_hash"] != previous["event_hash"]
                ):
                    raise GovernanceError("checkpoint_integrity_failure")
                receipt = self.publish(
                    tail["sequence"],
                    tail["event_hash"],
                    previous=(previous["sequence"], previous["event_hash"]),
                )
            else:
                receipt = self.fetch()
            anchor = tx.execute(
                "SELECT event_hash FROM governance_audit WHERE sequence=%s", (receipt["sequence"],)
            ).fetchone()
            chain = {tail["sequence"]: tail["event_hash"]}
            if anchor:
                chain[receipt["sequence"]] = anchor["event_hash"]
            self.verify_chain(chain, receipt)
            # Every independently retained head must still exist in the DB. Checking
            # only the latest would let a compromised submit token bless a rewrite.
            page = self.fetch()
            after = 0
            for _ in range(64):
                if (page["sequence"], page["event_hash"]) != (
                    receipt["sequence"],
                    receipt["event_hash"],
                ):
                    raise GovernanceError("checkpoint_integrity_failure")
                for sequence, event_hash in page["anchors"]:
                    if sequence <= after:
                        raise GovernanceError("checkpoint_integrity_failure")
                    row = tx.execute(
                        "SELECT event_hash FROM governance_audit WHERE sequence=%s", (sequence,)
                    ).fetchone()
                    if not row or row["event_hash"] != event_hash:
                        raise GovernanceError("checkpoint_integrity_failure")
                    after = sequence
                if not page["more"]:
                    return receipt
                if not page["anchors"]:
                    raise GovernanceError("checkpoint_integrity_failure")
                page = self.fetch(after=after)
            raise GovernanceError("checkpoint_history_limit")

    def check_extension(self, store, verified_head, verified_witness, *, tx=None, receipt=None):
        """Check a bounded extension of a separately verified full history proof."""
        from contextlib import nullcontext

        from pii_redactor.governance.store import _event_digest

        try:
            sequence, previous_hash = head(*verified_head)
            witness_sequence, witness_hash = head(
                verified_witness["sequence"], verified_witness["event_hash"]
            )
        except (ValueError, KeyError, TypeError):
            raise GovernanceError("checkpoint_integrity_failure") from None
        # This method never publishes or replaces the full historical verification.
        receipt = self.fetch(after=witness_sequence) if receipt is None else receipt
        if (
            receipt["sequence"] < witness_sequence
            or (receipt["sequence"] == witness_sequence and receipt["event_hash"] != witness_hash)
            or receipt["more"]
        ):
            raise GovernanceError("checkpoint_extension_limit")
        anchors = receipt["anchors"]
        if receipt["sequence"] > witness_sequence and (
            not anchors or tuple(anchors[-1]) != (receipt["sequence"], receipt["event_hash"])
        ):
            raise GovernanceError("checkpoint_integrity_failure")
        last = witness_sequence
        for current, _event_hash in anchors:
            if current <= last:
                raise GovernanceError("checkpoint_integrity_failure")
            last = current
        with store.transaction() if tx is None else nullcontext(tx) as tx:
            saved = tx.execute(
                "SELECT event_hash FROM governance_audit WHERE sequence=%s", (sequence,)
            ).fetchone()
            if not saved or saved["event_hash"] != previous_hash:
                raise GovernanceError("checkpoint_integrity_failure")
            required = {witness_sequence: witness_hash, receipt["sequence"]: receipt["event_hash"]}
            required.update(anchors)
            existing = {
                row["sequence"]: row["event_hash"]
                for row in tx.execute(
                    "SELECT sequence,event_hash FROM governance_audit WHERE sequence=ANY(%s)",
                    (list(required),),
                )
            }
            if existing != required:
                raise GovernanceError("checkpoint_integrity_failure")
            metadata = tx.execute(
                "SELECT sequence,octet_length(details::text) AS detail_bytes,octet_length(event_code) AS code_bytes,"
                "CASE WHEN octet_length(details::text)<=4096 AND octet_length(event_code)<=128 "
                "THEN octet_length(row_to_json(event)::text) ELSE 1048577 END AS event_bytes "
                "FROM governance_audit event WHERE sequence>%s ORDER BY sequence LIMIT %s",
                (sequence, 10001),
            ).fetchall()
            if (
                len(metadata) > 10000
                or sum(row["event_bytes"] for row in metadata) > 1048576
                or any(row["detail_bytes"] > 4096 or row["code_bytes"] > 128 for row in metadata)
            ):
                raise GovernanceError("checkpoint_extension_limit")
            rows = (
                tx.execute(
                    "SELECT * FROM governance_audit WHERE sequence>%s AND sequence<=%s "
                    "AND octet_length(details::text)<=4096 AND octet_length(event_code)<=128 ORDER BY sequence LIMIT 10000",
                    (sequence, metadata[-1]["sequence"]),
                ).fetchall()
                if metadata
                else []
            )
            if len(rows) != len(metadata):
                raise GovernanceError("checkpoint_integrity_failure")
            for event in rows:
                if (
                    event["sequence"] != sequence + 1
                    or event["organization_id"] != store.organization_id
                    or event["previous_hash"] != previous_hash
                    or event["event_hash"] != _event_digest(event)
                ):
                    raise GovernanceError("checkpoint_integrity_failure")
                sequence, previous_hash = event["sequence"], event["event_hash"]
            tail = tx.execute(
                "SELECT sequence,event_hash FROM governance_audit ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            if not tail or (tail["sequence"], tail["event_hash"]) != (sequence, previous_hash):
                raise GovernanceError("checkpoint_integrity_failure")
            self.verify_chain({**existing, sequence: previous_hash}, receipt)
        return receipt
