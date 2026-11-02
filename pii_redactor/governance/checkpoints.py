"""Minimized signed audit heads. The application holds only a public verify key."""

from __future__ import annotations

import base64
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

    def check(self, store, *, publish=False):
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
