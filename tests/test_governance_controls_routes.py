"""Real database BFF contracts using synthetic controlled identities."""

from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")
pytest.importorskip("fastapi", reason="optional enterprise HTTP dependency")

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.enterprise.governance_routes import build_governance_router
from pii_redactor.governance.errors import GovernanceError
from tests import governance_helpers as fixtures
from tests.test_governance_organization_controls import policy

context = fixtures.context
database = fixtures.database


def client_for(c):
    app = FastAPI()

    def identity(request, *, mutation=False):
        if request.headers.get("x-test-role") == "reviewer":
            actor = c.b
        elif request.headers.get("x-test-role") == "finance":
            actor = c.c
        else:
            actor = c.a
        if mutation and (
            request.headers.get("origin") != "https://guard.example.test"
            or request.headers.get("x-csrf-token") != "synthetic"
        ):
            raise GovernanceError("forbidden")
        return actor

    @app.exception_handler(GovernanceError)
    async def failure(request, exc):
        return JSONResponse({"error": {"code": str(exc)}}, status_code=403)

    app.include_router(build_governance_router(c.store, identity))
    return TestClient(app)


def test_routes_exact_revision_and_csrf_hook(context):
    client = client_for(context)
    base = "/api/enterprise/v1/governance/policy"
    body = {"command_key": str(uuid4()), "data": policy()}
    assert client.post(base, json=body).status_code == 403
    headers = {"origin": "https://guard.example.test", "x-csrf-token": "synthetic"}
    response = client.post(base, json=body, headers=headers)
    assert response.status_code == 200
    row = response.json()
    assert client.get(base + "/" + row["id"], headers={"x-test-role": "finance"}).status_code == 403
    submitted = client.post(
        base + "/" + row["id"] + "/submit",
        json={"command_key": str(uuid4()), "expected_revision": 1},
        headers=headers,
    ).json()
    assert submitted["state"] == "submitted"
    schema = client.get("/api/enterprise/v1/governance/schemas").json()
    assert set(schema) == {
        "processor",
        "transfer",
        "incident",
        "assessment",
        "responsibility",
        "policy",
        "legal",
    }
    assert (
        client.post(
            base + "/" + row["id"] + "/review",
            json={
                "command_key": str(uuid4()),
                "expected_revision": 1,
                "decision": "approve",
                "evidence_ref": str(uuid4()),
            },
            headers={**headers, "x-test-role": "reviewer"},
        ).status_code
        == 403
    )
    assert client.get(
        "/api/enterprise/v1/governance/release-findings?department_id=operations"
    ).json()["blocked"]
    assert (
        client.post(base, json={**body, "reviewed_by": str(uuid4())}, headers=headers).status_code
        == 422
    )
    reviewed = client.post(
        base + "/" + row["id"] + "/review",
        json={
            "command_key": str(uuid4()),
            "expected_revision": 2,
            "decision": "approve",
            "evidence_ref": str(uuid4()),
        },
        headers={**headers, "x-test-role": "reviewer"},
    )
    assert reviewed.status_code == 200 and reviewed.json()["state"] == "reviewed"
    active = client.post(
        base + "/" + row["id"] + "/activate",
        json={"command_key": str(uuid4()), "expected_revision": 3},
        headers={**headers, "x-test-role": "reviewer"},
    )
    assert active.status_code == 200 and active.json()["usable"]
    assert len(client.get(base + "/" + row["id"] + "/history").json()["items"]) == 4
