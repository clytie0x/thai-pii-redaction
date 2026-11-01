# PDPA Enterprise Stage 1 Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan inline, task by task, with TDD and one independent final review. Do not ask the owner to repeat the confirmed single-organization choice.

**Goal:** Deliver real staff authentication, durable scoped authority, processing inventory and notices, atomic audit evidence, and a usable staff web path. This is Stage 1 of the full enterprise objective; consent, retention, rights, wider governance and pilot/recovery remain required later stages.

**Architecture:** A dedicated enterprise FastAPI adapter calls one governance domain under `pii_redactor/`. PostgreSQL is the authority for membership, records, sessions and audit. Existing HTTP v2/native and in-memory redaction mappings are unchanged.

**Tech stack:** Python 3.11+, FastAPI, PostgreSQL 18, psycopg 3, Authlib OIDC client, same-origin HTML/CSS/JavaScript using the existing MD3 visual language. New enterprise dependencies are optional and separately locked.

**Spec:** `docs/decisions/2026-10-31-pdpa-enterprise-control-plane.md`.

**Program sequence:** [M0-M12 plan](aiguard-production-milestones.md).
Stage 1 corresponds to M3 after M0 reconciliation. Tasks 1-2 are implemented in
the preserved checkpoint; their unchecked lists below are task requirements,
not the current progress ledger. The owner resumed execution on 2026-11-02 and
requires independent adversarial review at every stage. Continue from Task 3.

## Global constraints

- Single self-hosted organization; no SaaS isolation claim. Every command/read binds to configured organization and current authoritative member scope.
- No real external message, production deployment, real-data disposal or credentials in reports/tests.
- Maintain source law-version references, manual inventory and separate general/sensitive conditions. A zero detector result is never activation authority.
- No custom password/JWT implementation, production auth bypass, client-declared reviewer role, raw request logging or arbitrary connector target.
- Keep existing detector and closed evaluation corpora frozen. No old held-out tuning.
- Use only project-local development dependencies/services. PostgreSQL/IdP unavailability is an explicit acceptance gap, never a SQLite/mock substitute.

## Review focus

- A forged issuer/subject, expired nonce, wrong audience or replayed callback must not create an authenticated staff session.
- A revoked membership/role or session must lose access immediately; stale browser identity must not authorize mutations.
- Membership grant proposer/beneficiary must not approve that privileged grant; setup must not remain an open web endpoint.
- Concurrent updates and changed-payload retries must conflict; a failed audit write must roll back the business state.
- Other departments' records, raw form values and database errors must not leak through lists, errors, audit exports or logs.

## Task 1: Durable authority and transaction boundary

**Files:** `pii_redactor/governance/{__init__,errors,models,store}.py`, `pii_redactor/governance/migrations/001_foundation.sql`, `tests/test_governance_store.py`, optional enterprise requirements/lock.

**Interfaces:** `GovernanceError(code: str)` exposes fixed public codes. `Store(dsn: str, organization_id: UUID)` opens PostgreSQL transactions. `Store.migrate()` uses an advisory migration lock and verifies immutable migration SHA/version. `Store.transaction()` yields a transaction connection with commit/rollback semantics. `Principal(issuer: str, subject: str)` is server-verified identity, not a role claim. Record request models are closed and bounded.

- [ ] Write failing real-PostgreSQL tests for restart persistence, organization mismatch, two-principal bootstrap, repeated/bootstrap conflict and rollback when the required audit insert fails.
- [ ] Run those tests; observe missing implementation failures. An unavailable PostgreSQL service is a setup failure, not a passing skip.
- [ ] Implement explicit versioned SQL migrations, configured organization guard, transactional enrollment and minimized append-only audit chain. Use plain SQL rather than adding an ORM solely for these tables.
- [ ] Re-run tests against PostgreSQL. Verify table/constraint behaviour and transaction rollback from a separate connection.
- [ ] Commit the independently testable boundary and observed evidence.

## Task 2: Scoped domain commands and records

**Files:** `pii_redactor/governance/{authority,registry}.py`, `tests/test_governance_authority.py`, `tests/test_governance_registry.py`.

**Interfaces:** `Authority.require(tx, principal, permission, department_id=None)` reads enabled membership and current grants. `Registry.create_activity(principal, command_key, request)`, `update_activity(..., expected_revision, request)`, `submit_activity(...)`, `review_activity(...)`, `list_activities(principal)` return authorized DTOs. Notice creation creates immutable versions. Mutations bind idempotency keys to canonical request digests and use a transaction with business/audit/outbox writes.

- [ ] Write RED tests for other-department access, revoked roles, self-approval, same-key replay/conflict, stale revisions and an incomplete sensitive activity attempting activation.
- [ ] Implement explicit role permissions, department scope, activity draft/submitted/active/rejected transitions and versioned notices. Reviewer activation requires confirmed inventory, necessity, general basis, separate Section 26 condition where needed, notice, retention and destination evidence.
- [ ] Add privileged role-grant proposal/approval with an approver distinct from proposer and beneficiary. Bootstrap is an offline one-time command, not a web route.
- [ ] Verify concurrent writers, two-person review, audit failure atomicity and minimized evidence. No browser JSON flag substitutes for a recorded independent reviewer decision.
- [ ] Commit tested domain commands.

## Task 3: OIDC staff login and server-side sessions

**Files:** `app/enterprise/{__init__,settings,auth}.py`, `tests/test_enterprise_auth.py`.

**Interfaces:** `Settings.from_env()` validates organization UUID, PostgreSQL URL, exact staff issuer/client, HTTPS public origin and secret-file references. `create_app(settings)` refuses incomplete/unconfigured production setup. `GET /auth/login`, `GET /auth/callback`, `POST /auth/logout` use Authlib, PKCE, state and nonce. Server-side login state and staff sessions are expiring, single-use/revocable PostgreSQL records; cookies carry only random identifiers.

- [ ] Write RED tests using signed synthetic IdP responses and controlled HTTP transport: issuer/audience/signature/nonce/state/PKCE failure, callback replay, stale membership, logout and CSRF.
- [ ] Implement maintained OIDC verification with fixed issuer/discovery endpoints, bounded timeouts, exact redirect URI and current membership lookup. Cache keys only within a bounded verified issuer context. No caller-supplied token endpoint or role header.
- [ ] Add HttpOnly/Secure/SameSite cookies, idle/absolute expiry, origin checks and session-bound CSRF token. Tokens and cookies never reach logs or HTML error pages.
- [ ] Verify the entire code flow against a real local IdP with synthetic accounts. Transport-mocked verification alone leaves real IdP acceptance open.
- [ ] Commit the tested session boundary and honest acceptance state.

## Task 4: Caller-facing registry API and web application

**Files:** `app/enterprise/{server,schemas}.py`, `app/enterprise/static/{index.html,app.js,style.css}`, `tests/test_enterprise_api.py`, `tests/enterprise/enterprise_ui.test.js`, `vitest.config.js`, `pyproject.toml` package entries/data.

**Interfaces:** `GET /api/enterprise/v1/me`, activity/notice lists and detail, explicit create/update/submit/review routes, grant proposal/approval routes and a role-filtered audit view. Exact organization is server configuration, never an arbitrary request tenant selector. Fixed error DTO: `{error: {code, correlation_id}}` with no rejected values or internal exceptions. A readiness route distinguishes database, schema, enrollment and IdP configuration from process liveness.

- [ ] Write RED API tests for unauthenticated requests, forged headers, CSRF, body limits, unknown fields, invalid transitions, pagination/scope and value-free failure paths. Add `tests/enterprise/**/*.test.js` to Vitest discovery and verify the UI tests are collected and fail for a missing behavior before implementation.
- [ ] Implement adapters over the domain commands, bounded pagination, security headers, strict same-origin session handling and no public business CORS.
- [ ] Build functional login, first-use setup guidance, inventory list/form/detail, submission/review queue and audit screens. Include keyboard labels, loading/empty/error states, optimistic-revision conflict recovery, readable Thai UI and responsive layout. No fake dashboard counts or success placeholders.
- [ ] Exercise the real local web-to-API-to-PostgreSQL path and responsive/keyboard failure states using an available permitted browser verification mechanism. Do not substitute static source assertions for browser acceptance.
- [ ] Commit the working caller path and integration evidence.

## Task 5: Operations, packaging and independent review

**Files:** `app/enterprise/__main__.py`, `docs/enterprise/README.md`, `docs/project-status.md`, `README.md`, packaging tests and local acceptance manifest.

- [ ] Provide actual migrate/enroll/serve commands, environment/secret-file guidance, least-privilege database roles, source/lock identity, backup/restore prerequisites and reversible development teardown instructions. Do not print DSNs, secrets or subject identifiers on error.
- [ ] Verify installed package includes domain migrations and web assets; an editable source run alone does not prove package contents.
- [ ] Run focused security/transaction tests, full Python suite, lint/format/version/diff and existing-path performance measurement. Preserve the pre-existing sanitizer anchor failure and explain any new regression.
- [ ] Independently review the whole Stage 1 diff against the spec, fix reproduced material findings RED-to-GREEN, and record remaining operational gates.
- [ ] Update acceptance evidence and progress ledger. Stage 1 completion does not complete the full enterprise goal; proceed to consent, retention, rights, wider governance and pilot/recovery stages from the parent spec.

## Execution record

Use `.superpowers/sdd/pdpa-enterprise-stage1/progress.md` as the ignored execution ledger. Record the plan identity, each test's observed RED/GREEN outcome, commits, deviations and acceptance gaps. Do not replace original evidence with later summaries.

Builder ruling: native T3 worktree status currently targets `C:/Users/teera/dev`, not this Git repository, and its handoff has no target-repository parameter. Use a managed Git worktree under this repository's ignored `.worktrees/` rather than changing the app's project configuration or creating another thread. Reuse the verified root Python environment for initial tests; add enterprise dependencies in a project-local environment without changing the ordinary application's lock.
