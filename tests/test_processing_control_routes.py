"""Processing routes use caller-owned identity, scope, origin and CSRF hooks."""

from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")
pytest.importorskip("fastapi", reason="optional enterprise HTTP dependency")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.enterprise.processing_control_routes import build_processing_router
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.processing_controls import ProcessingControls
from tests import test_governance_processing_controls as fixtures

database = fixtures.database
context = fixtures.context
subject_context = fixtures.subject_context
consent_context = fixtures.consent_context
integrated = fixtures.integrated


def app(c):
    actor = {"value": c.a}

    def identity(request, *, mutation=False):
        if actor["value"] is None:
            raise GovernanceError("authentication_required")
        if mutation and (
            request.headers.get("origin") != "https://guard.example.test"
            or request.headers.get("x-csrf-token") != "synthetic-csrf"
        ):
            raise GovernanceError("forbidden")
        return actor["value"]

    application = FastAPI()
    application.include_router(build_processing_router(ProcessingControls(c.store), identity))
    return TestClient(application, base_url="https://guard.example.test"), actor


def test_processing_routes_require_identity_and_csrf_without_body_echo(integrated):
    c = integrated
    client, actor = app(c)
    actor["value"] = None
    assert client.get("/processing-controls").status_code == 401
    actor["value"] = c.a
    assert client.get("/processing-controls").status_code == 200
    result = client.post(
        "/api/enterprise/v1/processing",
        json={"command_key": str(uuid4()), "data": {"synthetic-private-canary": "not-a-schema"}},
        headers={"origin": "https://guard.example.test", "x-csrf-token": "synthetic-csrf"},
    )
    assert result.status_code == 422 and "synthetic-private-canary" not in result.text
    assert "no-store" in result.headers["cache-control"]


def test_processing_route_executes_reviewed_versioned_workflow(integrated):
    c = integrated
    fixtures.production.consent_fixtures.command(c, "grant")
    rows, _law = fixtures.controls(c)
    client, actor = app(c)
    base = "/api/enterprise/v1/processing"
    headers = {"origin": "https://guard.example.test", "x-csrf-token": "synthetic-csrf"}

    def post(path, data):
        result = client.post(path, json={"command_key": str(uuid4()), **data}, headers=headers)
        assert result.status_code == 200, result.text
        return result.json()

    payload = {"data": fixtures.request(c, rows).model_dump(mode="json")}
    assert client.post(base, json={"command_key": str(uuid4()), **payload}).status_code == 403
    row = post(base, payload)
    path = base + "/" + row["id"]
    row = post(path + "/submit", {"expected_revision": row["revision"]})
    actor["value"] = c.b
    preview = client.post(
        path + "/preview", json={"expected_revision": row["revision"]}, headers=headers
    )
    assert preview.status_code == 200 and len(preview.json()["controls"]) == 8
    row = post(
        path + "/review",
        {"expected_revision": row["revision"], "decision": "approve", "evidence_ref": str(uuid4())},
    )
    row = post(path + "/activate", {"expected_revision": row["revision"]})
    assert row["usable"] and not row["legal_clearance"]
    assert client.get(base + "?department_id=operations").json()["items"][0]["id"] == row["id"]
    assert len(client.get(base + "/controls?department_id=operations").json()["legal"]) == 8
    assert client.get(base + "/activities?department_id=operations").json()["items"]
    assert client.get(base + "?department_id=other").status_code == 403
    first = client.get(path + "/history?limit=2").json()
    assert len(first["items"]) == 2 and first["next_cursor"] == 2
    second = client.get(path + "/history?limit=2&after=2").json()
    assert len(second["items"]) == 2 and second["next_cursor"] is None
