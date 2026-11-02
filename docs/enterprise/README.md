# Enterprise application: setup and acceptance

This single-organization application uses the shared governance domain,
PostgreSQL authority and a configured OIDC staff issuer.
It is separate from local Desktop/Extension redaction and the Hosted service.
Persistent governance records are protected organization data; the local
reversible PII vault is not persisted here.

Stage 1 supports inventory, notices, independent processing review, staff
membership proposals and minimized scoped audit views. The current source also
implements configured subject consent, encrypted managed collections/execution
and reviewed retention/holds. These M4-M6 paths are implemented locally;
qualification is pending. The corrected mandatory enterprise gate passes 298
tests without failures or skips after a retained failed retry. Global SDK and
actual subject IdP/browser, new installed-artifact/restart and production gates
have not passed. See the [local-wave record](../acceptance/enterprise/M04-M06-local-wave.md).
Rights/secure delivery, organization records and complete operational recovery
remain unfinished. Do not advertise production readiness.

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

The Stage 1 runtime needs:

- SELECT on the governance schema/version, organization, membership, command,
  activity, notice, grant, audit, outbox, login-state and session tables;
- INSERT on audit/commands/outbox, membership/grant, activity/notice, login-state
  and session tables;
- UPDATE on membership/grant, activity/notice and session tables;
- DELETE on expiring login-state rows only; no audit UPDATE/DELETE or schema DDL.

That Stage 1 list is not a complete grant recipe for M4-M6. The current schema
also includes subject sessions/consent, encrypted collection/evidence and
execution/retention/hold tables in migrations 004-006. Qualify the selected
runtime role against all enabled workflows; do not grant blanket DML or DDL to
make a candidate pass. Append-only audit, consent history and document versions
must keep their intended immutability.

Grant only required operations in the intended schema. Test readiness and the
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

### Optional subject and managed capabilities

Enable subject access with a separate confidential client/audience and secret
file; its client ID must differ from the staff client. It shares the configured
public origin and registers the exact `/subject/auth/callback` URI:

```powershell
$env:AIGUARD_ENTERPRISE_SUBJECT_ISSUER='https://<subject issuer>/<realm>'
$env:AIGUARD_ENTERPRISE_SUBJECT_CLIENT_ID='<approved subject client ID>'
$env:AIGUARD_ENTERPRISE_SUBJECT_OIDC_SECRET_FILE='<absolute private subject OIDC file>'
$env:AIGUARD_ENTERPRISE_MANAGED_KEYS_FILE='<absolute private managed-key file>'
```

The subject secret file has the same single `client_secret` field as the staff
secret file. Partial subject configuration fails closed. Staff credentials
cannot stand in for a subject act; reviewed linkage and the exact current
notice/purpose remain required.

The managed-key file has `organization_id`, `active_version` and `keys`; each key
entry has `version` and `key_hex` (64 hexadecimal characters for a 32-byte key).
The active version must name an entry and the organization must match. Provision
real key material only through the organization's approved private key process.
Serving loads these keys into process memory outside the ciphertext database. This file-backed
authority is not production KMS, key rotation or recovery acceptance.

With no subject configuration, subject routes are disabled. With no managed-key
reference, managed/retention routes are disabled. Selected malformed or missing
key material fails closed; there is no plaintext storage fallback. Managed
collection/evidence reads and actions apply current scope, consent and hold
checks; execution rechecks exact approved targets and retention bindings.

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
When enabled, service readiness additionally checks subject IdP metadata and
managed protection/key availability. CLI `check` remains a schema/enrollment
check; it does not prove those optional capabilities. Neither readiness path
completes M10-M12 storage/checkpoint/restore/pilot gates.

The explicit managed worker consumes one already approved outbox action:

```powershell
python -m app.enterprise work-once --worker-id '<operator-assigned worker ID>'
```

It needs organization/database/key references, not the staff OIDC secret. It
cannot create approval authority or turn queued work into a verified outcome.
Use it only for authorized synthetic qualification until the exact real-data
operation and environment are accepted.

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

The configured subject path is `/subject`, with reviewed staff linkage at
`/subject/staff`. Managed staff work uses `/managed`; reviewed due actions and
holds use `/retention`. Their Thai interfaces have local API/DOM evidence only,
not fresh real-browser accessibility or human usability acceptance. Retention
dispatch supports `restrict`/`suppress`; processor/backup copy obligations remain
separate evidence. Physical ciphertext/history/snapshot, WAL/replica and backup
erasure are not implemented. Collection quarantine/reconciliation does not
establish whole-database recovery.

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
and binds its port to loopback. Public CI now executes after the owner's
visibility decision; the [earlier billing block](../acceptance/enterprise/M00-ci-blocker.md)
is historical. Every job must pass on the exact combined candidate. The current
failed mandatory retry records 286 passed/11 failed/0 skipped; the corrected
complete enterprise gate passes 298/0 failed/0 skipped (2 warnings). The first
full SDK run still records 2,088 passed/52 failed/10 skipped. Final global gates,
source freeze and installed artifacts remain pending.

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
