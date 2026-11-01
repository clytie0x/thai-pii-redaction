# Enterprise staff application: setup and acceptance

This is the single-organization Stage 1 application. It uses the shared
governance domain, PostgreSQL authority and a configured OIDC staff issuer.
It is separate from local Desktop/Extension redaction and the Hosted service.
Persistent governance records are protected organization data; the local
reversible PII vault is not persisted here.

Stage 1 supports inventory, notices, independent processing review, staff
membership proposals and minimized scoped audit views. Subject consent,
retention/rights execution, wider governance, checkpoint/recovery and production
pilot acceptance remain M4-M12 work. Do not advertise those as shipped.

## Install the selected optional profile

Use Python 3.13 for the recorded environment, or a supported Python 3.11+
environment qualified separately. Install the hash-locked enterprise profile:

```powershell
$env:PYTHONUTF8='1'
python -m pip install --require-hashes -r requirements-enterprise.lock
```

For an installed artifact, build/qualify the wheel and install that wheel with
the same dependency lock. Running from source alone is not installed-runtime
evidence. No ML/OCR engine or external LLM provider is enabled by this adapter.

## Separate administrative and runtime database credentials

Use an organization-owned PostgreSQL 18 database/schema. Migration and initial
enrollment use an offline administrative credential. The serving process uses
a separate non-superuser role with schema USAGE, not schema CREATE or role/
database creation. Keep the schema owner distinct from the runtime role.

The runtime needs:

- SELECT on the governance schema/version, organization, membership, command,
  activity, notice, grant, audit, outbox, login-state and session tables;
- INSERT on audit/commands/outbox, membership/grant, activity/notice, login-state
  and session tables;
- UPDATE on membership/grant, activity/notice and session tables;
- DELETE on expiring login-state rows only; no audit UPDATE/DELETE or schema DDL.

Grant only those operations in the intended schema. Test readiness and the
actual staff workflows under that runtime role; do not infer least privilege
from tests that connect with a schema-creating administrative account. SQL
migrations are fingerprinted and LF-pinned. Do not edit applied SQL files to
fix an upgrade; add a new migration and verify populated-schema recovery.

## Private configuration files

Create protected files outside the installed package and served static directory.
Use an approved private editor/secret manager rather than placing real values in
shell history, command arguments or tracked files. These are formats only:

```json
{"dsn": "<organization database connection string>"}
```

```json
{"client_secret": "<configured OIDC confidential-client secret>"}
```

Each production configuration file has exactly its named field. Restrict access
to the service account/operators. Use approved PostgreSQL transport/storage/key
and backup policy; the synthetic loopback acceptance does not prove those controls.

Set server-owned references and identifiers:

```powershell
$env:AIGUARD_ENTERPRISE_ORGANIZATION_ID='<organization UUID>'
$env:AIGUARD_ENTERPRISE_DB_FILE='<absolute private database file>'
$env:AIGUARD_ENTERPRISE_OIDC_SECRET_FILE='<absolute private OIDC file>'
$env:AIGUARD_ENTERPRISE_ISSUER='https://<staff issuer>/<realm>'
$env:AIGUARD_ENTERPRISE_CLIENT_ID='<approved confidential client ID>'
$env:AIGUARD_ENTERPRISE_PUBLIC_ORIGIN='https://<staff application host>'
```

PUBLIC_ORIGIN is the exact browser origin, with no path/query/trailing slash.
Register its exact `/auth/callback` URI in the IdP. The current adapter accepts
same-origin discovery authorization/token/JWKS endpoints, signed RS256 identity,
authorization code with S256 PKCE and the `openid` scope. A different issuer
topology/algorithm requires explicit compatibility/security qualification; never
silently follow arbitrary discovered hosts or fall back to another issuer.

The IdP supplies identity, not application roles. Bind staff by reviewed immutable
issuer/subject, not email. Organizational reauthentication/MFA and IdP lifecycle
integration are separately configured decisions. `max_token_age` checks token
`iat`; it does not itself prove `auth_time` freshness or MFA.

## Offline setup, then serving

With the administrative database file selected:

```powershell
python -m app.enterprise migrate
python -m app.enterprise enroll --file '<private reviewed enrollment JSON file>'
```

The enrollment file is an array of at least two distinct, owner-approved staff
identities, with explicit roles and department scopes. Example structure only:

```json
[
  {"principal":{"issuer":"https://staff.example.test/realms/staff","subject":"reviewed-admin-subject"},
   "roles":["system_administrator","data_steward"],"departments":["operations"]},
  {"principal":{"issuer":"https://staff.example.test/realms/staff","subject":"reviewed-reviewer-subject"},
   "roles":["authority_reviewer","privacy_reviewer","auditor"],"departments":["operations"]}
]
```

Enrollment is one-time and offline; no web setup/self-promotion endpoint exists.
Subsequent enrollment, role/scope change and reactivation use proposals plus a
distinct authorized reviewer. Immediate suspension reduces access; protected
last-authority constraints still apply. A system administrator is not implicitly
a privacy approver or auditor.

Switch DB_FILE to the restricted runtime credential before serving:

```powershell
python -m app.enterprise check
python -m app.enterprise serve --host 127.0.0.1 --port 8765
```

`check` verifies schema/enrollment and local audit integrity, not live IdP/browser
or deployment acceptance. Serving does not run migrations or privileged DDL.
Unconfigured or unenrolled service fails closed. The server validates IdP
metadata during startup; `/health/ready` rechecks schema, enrollment, local audit
integrity and IdP metadata. `/health/live` proves only that the process responds.
Readiness is Stage 1 authority readiness, not completion of M10-M12 production
storage/checkpoint/restore/pilot gates.

Use the configured TLS reverse proxy/origin for production. Preserve the exact
Host authority, deny untrusted proxy headers and keep authentication queries,
cookies, Authorization and request/provider bodies out of proxy/access logs.
The supplied entry point disables access logging and configures the shared
redaction filter. It cannot certify an external proxy's logging configuration.
Keep protocol DEBUG logging disabled and exercise the complete logging path.

## Staff web path

- Sign in through the organization IdP. Only an enabled, independently enrolled
  member receives an application session. A new IdP identity alone grants nothing.
- Create/edit a scoped activity draft; categories are manually confirmed
  inventory, not detector clearance. Record purpose, necessity, basis, retention,
  recipients, destinations and references before independent review.
- Create notices against an exact activity revision. Published notices are
  immutable. A changed activity cannot silently bind an older drafted notice.
- Submit and have another authorized person publish/review. The activation is
  reviewer attestation to referenced evidence, not automatic inspection or a
  compliance certificate. Sensitive conditions remain distinct from general basis.
- Membership reviewers see explicit target, roles, departments and enable/
  suspend/unchanged effect. Target metadata/revision is rechecked before approval.
- Department auditors see activity/notice events within scope. Organization-wide
  authority/session events require the explicit `*` scope; no raw values or audit
  details are projected. A local hash chain is not an independent checkpoint sink.

Cookies are opaque; the server keeps their hashes and binds session authority to
current membership revision. CSRF/origin checks protect mutations. Suspension,
logout and revision changes deny old cookies and already resolved principals.
Session deadlines are checked again after acquiring authorization locks. The UI
clears private references on expiry, revocation or principal/scope replacement;
it does not use localStorage/sessionStorage for records or credentials.

## Mandatory automated and real-path gates

```powershell
python scripts/run_enterprise_tests.py --report '<ignored report path>'
npm run test:js
python -m ruff check .
python -m ruff format --check .
python scripts/check_version.py
git diff --check
```

The dedicated test gate requires all enterprise dependencies, PostgreSQL 18 and
AIGUARD_TEST_DB_FILE referencing a private **synthetic** loopback test database:
its JSON contains `dsn` plus `purpose: synthetic_enterprise_tests`. This is a
test configuration, separate from production/migration/runtime files. Missing
dependencies/configuration, failed DB connection, missing suite, skipped test or
empty test report fails the gate. It cannot turn core-only optional skips into
enterprise acceptance. The dedicated CI job pins the official PostgreSQL image
and binds its port to loopback. CI execution is still blocked by the account
billing condition recorded in [M0 CI evidence](../acceptance/enterprise/M00-ci-blocker.md).

Package qualification must build with the pinned backend constraints, verify
actual wheel resources with `scripts/check_enterprise_wheel.py`, install outside
source and exercise the app/SQL/web assets under the restricted runtime role.
Fresh real IdP and browser tests must use synthetic identities/data and record
source/artifact/config identities without credentials, token bodies or mappings.

Before any real-data pilot, name the organization and reviewers; approve current
legal applicability, IdP/storage/key/backup owners, intended uses and source-system
scope. Verify backup/restore quarantine, independent checkpoints, suppression,
rotation and operational recovery under M10-M12. No real-data deletion, external
notification, public deployment or release follows from Stage 1 local checks.
