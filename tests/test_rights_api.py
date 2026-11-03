"""Real domain/router path with explicit BFF hooks, synthetic staff and M4 sessions."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")
pytest.importorskip("fastapi", reason="optional enterprise API dependency")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.enterprise.rights_routes import build_rights_router
from tests import test_governance_rights as fixtures
from tests.test_governance_rights import approved, intake

database = fixtures.database
context = fixtures.context
rights_context = fixtures.rights_context


def test_router_subject_receipt_and_private_headers(rights_context):
    c = rights_context
    row = approved(c)
    current = {"staff": c.a}
    mutations = []

    def staff(request, *, mutation=False):
        mutations.append(("staff", mutation))
        return current["staff"]

    def subject(request, *, mutation=False):
        mutations.append(("subject", mutation))
        return c.sessions.resolve(c.grant.cookie)

    app = FastAPI()
    app.include_router(
        build_rights_router(c.rights, staff_identity=staff, subject_identity=subject)
    )
    with TestClient(app) as client:
        path = "/api/enterprise/v1/rights/" + row["id"]
        response = client.post(
            path + "/delivery",
            json={
                "command_key": str(uuid4()),
                "expected_revision": row["revision"],
                "approved_export_version": row["plan_version"],
                "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
            },
        )
        assert response.status_code == 200, response.text
        d = response.json()
        url = "/api/subject/v1/rights/deliveries/" + d["id"]
        download = client.post(url + "/consume", json={"command_key": str(uuid4())})
        assert download.status_code == 200, download.text
        assert (
            "no-store" in download.headers["cache-control"]
            and "no-referrer" in download.headers["referrer-policy"]
        )
        data = download.json()
        receipt = client.post(
            url + "/receipt",
            json={
                "command_key": str(uuid4()),
                "expected_revision": data["revision"],
                "receipt_token": data["receipt_token"],
            },
        )
        assert receipt.status_code == 200 and receipt.json()["fulfilled"]
        current["staff"] = c.b
        result = client.post(
            path + "/close",
            json={
                "command_key": str(uuid4()),
                "expected_revision": row["revision"],
                "evidence_ref": str(uuid4()),
            },
        )
        assert result.json()["state"] == "closed"
        assert ("subject", True) in mutations and ("staff", True) in mutations


def test_validation_and_scope_errors_do_not_echo_values(rights_context):
    c = rights_context
    app = FastAPI()
    app.include_router(
        build_rights_router(
            c.rights, staff_identity=lambda *a, **k: c.c, subject_identity=lambda *a, **k: c.actor
        )
    )
    with TestClient(app) as client:
        bad = client.post(
            "/api/enterprise/v1/rights",
            json={"data": {"synthetic_private_marker": "never-echo"}, "command_key": "invalid"},
        )
        assert bad.status_code == 422 and "never-echo" not in bad.text
        assert "no-store" in bad.headers["cache-control"]
        row = c.rights.receive(c.a, uuid4(), intake(c))
        denied = client.get("/api/enterprise/v1/rights/" + row["id"])
        assert denied.status_code == 403 and row["id"] not in denied.text


def test_subject_page_queries_forward_bound_cursor_and_limit(rights_context):
    c = rights_context
    for _ in range(3):
        c.rights.receive(c.a, uuid4(), intake(c))
    app = FastAPI()
    app.include_router(
        build_rights_router(
            c.rights,
            staff_identity=lambda *a, **k: c.a,
            subject_identity=lambda *a, **k: c.sessions.resolve(c.grant.cookie),
        )
    )
    with TestClient(app) as client:
        first = client.get("/api/subject/v1/rights?limit=2")
        assert first.status_code == 200 and len(first.json()["items"]) == 2
        cursor = first.json()["next_cursor"]
        second = client.get("/api/subject/v1/rights", params={"limit": 2, "cursor": cursor})
        assert second.status_code == 200 and len(second.json()["items"]) == 1
        assert second.json()["next_cursor"] is None
        assert {r["id"] for r in first.json()["items"]}.isdisjoint(
            {r["id"] for r in second.json()["items"]}
        )
        denied = client.get("/api/subject/v1/rights?cursor=synthetic-invalid-cursor")
        assert denied.status_code == 409 and "synthetic-invalid-cursor" not in denied.text
