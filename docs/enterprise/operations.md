# M10 operator and recovery candidate

This is local synthetic engineering, not M10 acceptance or permission to deploy.
Use the accepted single-organization design. All declared storefronts remain in
scope. TLS/IdP/host, real witness custody, key/backup custodians, RPO/RTO, capacity,
exact images, independent review and the owner's acceptance remain open.

## Readiness and authority

`/health/live` reports only process liveness. Production construction no longer
needs a reachable DB or IdP. One background qualifier checks the complete
historical key decryptability, audit chain and retained signed witness history.
A successful full proof expires within the profile's `checkpoint_max_age`.
Historical verification uses one private SQL `REPEATABLE READ READ ONLY`
snapshot. It takes no organization advisory lock and cannot be mounted as an
application store, mutate records or publish a witness head. Keys, audit and all
retained witness anchors refer to that same snapshot; the audit is scanned once.
The signed witness journal is fetched before opening the snapshot. After the
scan, a fresh signed extension and a short normal production transaction recheck
the actual organization, schema, database role/identity, operational/key epoch
and configuration before publishing a proof. Normal session/API/worker paths
continue to check current business authority and data under their live guards;
they never serve the verifier's older rows.
HTTP requests never execute those scans. Cold requests cannot start them;
invalidation signals the single existing background qualifier. A cold or expired
gate returns 503 while liveness remains available.

Each admitted request checks the exact current configuration, artifact/schema,
organization, key authority, effective runtime privileges and operational epoch.
A fresh signed witness response must extend the previously qualified prefix;
its bounded audit extension rejects changed/truncated/divergent history and
exceeded checkpoint lag. More than 32 new witness heads or 10,000 new audit
events requires background full qualification. Before fetching full event rows,
each bounded check enforces a 1 MiB budget on their serialized, decompressed size.
HTTP admission repeats the bounded check after potentially blocking IdP I/O;
it cannot reuse a proof that expired or was quarantined during that wait.
New audit metadata is bounded to 4,096-byte details and 128-byte event codes.
Oversized legacy rows remain intact and block qualification before their payloads
are transferred; migration 011 adds these checks without validating/replacing old
rows. Full historical witness checking
remains unchanged; the bounded request check does not replace it. Fresh staff
and subject IdP probes run after local checks, sharing only an in-flight probe
between overlapping requests. An old request cannot erase a newer full proof.
An unconfigured profile is blocked. No ready response is an owner sign-off.
All runtime transactions take the organization fence. Migration 011 adds a
fixed-schema, fixed-search-path security-definer guard for reads and writes;
runtime roles cannot disable it with a session setting. Its operational row lock
serializes quarantine/key changes against already admitted database operations.
The offline migration/recovery authority is deliberately separate from runtime.
DB owners can bypass these controls; it is not protection against a malicious owner.

The example profile is deliberately invalid. Its lag numbers are example local
bounds, not agreed production RPO/RTO. Replace them before the real workload.
Evidence fields reference separately controlled owner records, never passwords,
PII, plaintext evidence or keys. The software cannot verify human acceptance
from a reference string; infrastructure acceptance is still a separate gate.

Use a qualified immutable image `registry/name@sha256:<observed digest>`, locked
dependencies from `requirements-enterprise.lock`, software inventory and an
independently retained manifest. Do not invent a digest or use a floating tag.
Use `python -m app.enterprise.operations identity` to bind source/locks/assets
and migration digests. Installed wheels and source archives need the same declared
inventory. The identity helper supports source and installed-wheel layouts,
including canonical runtime files, fonts, migrations, version/build inputs,
distribution ownership and derived bytecode. Each layout has its own digest.
The final integrated wheels and images still require exact-artifact qualification;
source tests and earlier development wheels do not satisfy that gate.
An older binary fails if schema digests differ. There is no down migration.
Rollback requires the exact privacy-qualified artifact, matching schema and
quarantined compatible backup, or reviewed forward repair.

## Private inputs and least privilege

Keep JSON inputs in an operator-owned directory with mode 0700 and files 0600
(Windows DACL: current operator, SYSTEM and Administrators only). Symlinks and
other readable principals fail closed. No DSN/key value is a CLI argument.
Separate DB migration, runtime, backup/restore, managed-key and witness custody.
The runtime role must not own schema/tables, create roles/databases, disable
triggers or modify schema/checkpoint records. Grant only required table/sequence
operations; validate on the exact combined schema with the operator. Do not
copy a superuser test-cluster DSN into production.

### Runtime grant matrix

Create a new dedicated LOGIN role under the database custodian, with separately
protected credentials. Apply the reviewed
[runtime role grants](../../deployment/enterprise/runtime-role.sql) only after
the exact combined migrations. The script does not create a password, reset an
existing role's unrelated privileges, or grant migration/operator authority.
Use PostgreSQL's authenticated connection settings; do not replace SCRAM with
trust authentication to make the qualification pass.

| Record class | Runtime privileges |
| --- | --- |
| Organization/schema/operations, initial activation and restore session/journal metadata | SELECT only |
| Immutable audit/history/ciphertext/outcomes, command receipts and instruction bindings | SELECT, INSERT |
| Reviewed mutable application records | SELECT, INSERT, UPDATE |
| Ephemeral staff/subject login attempts | SELECT, INSERT, DELETE |
| Required sequences | USAGE, SELECT; no UPDATE/reset authority |
| Fixed `governance_runtime_guard()` | Explicit EXECUTE; PUBLIC execution is revoked |

The application verifies the effective table **and column** grants, required
minimum operations, schema/database DDL, object ownership, role memberships,
session role switching and the guard's definer/search-path settings. Unknown or
missing application tables fail qualification. Runtime roles cannot update
operational/schema rows, rewrite immutable history/bindings, truncate tables or
attach triggers. The matrix includes M7/M8, processing-control and operator-only
restore/initial activation bookkeeping records. A SELECT-only role cannot claim readiness: the
local role test performs a real staff login/session and registry mutation.

Rotation takes the organization fence, compares the expected active version,
and verifies current managed, evidence and rights-delivery ciphertext with both
keysets in that same transaction. Stale concurrent candidates cannot replace a
newly active keyset. Old keys needed by immutable history and off-DB backups are
retained; this does not authorize key disposal or historical re-encryption.

Existing runtime files and environment are described in [README](README.md).
Additional protected files:

| Environment | File contents |
| --- | --- |
| `AIGUARD_ENTERPRISE_PROFILE_FILE` | Versioned production profile, see deployment template |
| `AIGUARD_ENTERPRISE_CHECKPOINT_FILE` | `url`, `token`, `public_key_hex`; **no witness private key** |
| `AIGUARD_ENTERPRISE_BACKUP_KEY_FILE` | `key_hex`, 32-byte AES key encoded as 64 hex characters |
| `AIGUARD_ENTERPRISE_DB_FILE` | `dsn` for this command's exact DB/authority |
| `AIGUARD_ENTERPRISE_PG_BIN` | Trusted qualified PostgreSQL tool directory, not a secret |

`python -m app.enterprise.operations` exposes `identity`, `readiness`,
`checkpoint-publish`, `checkpoint-verify`, `backup`, `backup-validate`,
`restore-quarantine`, `restore-reconcile`, `keys-verify`, `keys-prepare`, and
`keys-activate`. Offline readiness cannot prove IdP connectivity and exits blocked.
Runtime `work-once` also refuses an unverifiable production profile/recovery state.
It uses a private worker store and public IdP metadata without staff or subject
OAuth login secrets. One historical snapshot proof is followed by current
checks after IdP I/O and at actual claim/execute transaction entry and commit.
The deadline is checked again after input I/O, so expiry during lock waits or
final validation cannot commit a new claim. Runtime deployment-byte checks
remain explicit work under the fence; production capacity is not yet measured.

## Independently controlled checkpoints

Run the witness under a different host/operator/retention policy, never with the
application's DB/key authority. The reference `Witness` and `witness_handler`
classes are used by the actual localhost cryptographic tests. Their SQLite
journal is a separate witness store, not the application DB or a production
service claim. The application has a pinned Ed25519 public key and a submit/read
token. Only the witness has its private signing key. Transport is HTTPS in
production; HTTP is accepted only by explicit loopback test construction.
The separate custodian can run the reference process with
`python -m pii_redactor.governance.witness_operator --config-file <protected-file>`.
Its private file has `organization`, `signing_key_hex` (32-byte Ed25519 seed),
`token`, absolute `store` path and `port`; never mount it in the application.
`--identity` prints only the pinned organization/public key. The server binds only
loopback and pins one organization. Its standard-library HTTP process still needs
separate TLS, service supervision, storage/retention and deployment qualification.

Only organization, sequence/hash, times and a random nonce cross the adapter.
The sink append checks its previous head under a transaction; conflicting writes
cannot replace it. The client checks the signature, challenge, age and exact DB
anchor. Truncation/divergence, excess event/time lag, bad signatures and an
unreachable sink fail readiness. A fresh signed read of an unchanged head is
valid even when the application was idle. Publish before the configured lag
bound, alert on failure, and reconcile a divergent DB against independent evidence.
Do not reset the witness to make a restored chain pass.
Every retained witness head is checked, so a compromised submit token cannot
hide a rewrite by publishing a newer head. Reads are bounded to 64 pages of 32
heads per verification; exceeding that candidate limit blocks readiness. A
larger independently reviewed history/retention design and measured cost are
required before production adoption; no old checkpoint is silently discarded.

## Whole database backup and quarantine

Set the DB file to the **read-only backup role** for the exact enrolled DB.
Run `python -m app.enterprise.operations backup --archive <new-protected-file>`.
An exported repeatable-read PostgreSQL snapshot binds `pg_dump` to one DB state.
The tool encrypts each bounded chunk with AES-256-GCM and authenticates metadata,
chunk ordering and an end marker containing total bytes and plaintext digest.
No unencrypted dump is written to disk. Keys are not placed in the archive.
The format has a 4 GiB/300 second bound; larger deployments need an explicit
capacity decision. A failed output stays invalid and must not be promoted.
The archive excludes the transient operations readiness row and preserves its key
version policy in encrypted metadata. Restoring cannot resurrect a ready state,
including a crash between the DB restore commit and the quarantine command.

`backup-validate --archive <file>` decrypts to a discard sink, checks all tags,
the final digest, exact runtime/schema/rollback identity and reads no DB data.
This verifies archive integrity and compatibility, not recovery readiness.

For restore, select a separate isolated cluster or a reviewed quarantine
administrative connection. It must be unreachable by the runtime role.
The tool accepts only a **new** `aig_restore_<32 lowercase hex>` database and
requires `--target` and `--confirm-target` to match exactly. It validates the
entire archive before CREATE DATABASE, refuses existing DBs, revokes PUBLIC
CONNECT, uses one atomic `pg_restore` transaction, then marks whole-DB quarantine.
It never drops or overwrites a DB. A failed restore remains an offline target;
the operator owns protected cleanup after exact-target review.

Example (all values here are paths or a generated disposable DB name):

```powershell
python -m app.enterprise.operations backup-validate --archive <protected-archive>
python -m app.enterprise.operations restore-quarantine --archive <protected-archive> --target <new-quarantine-name> --confirm-target <same-new-quarantine-name>
python -m app.enterprise.operations restore-reconcile --source-db-file <current-authoritative-source-file> --runtime-db-file <dedicated-target-runtime-file>
```

A new archive binds its authenticated manifest to the actual exported snapshot's
audit sequence/hash, schema, artifact and active key version. Read-only validation
of an older archive does not establish this lineage; an archive without that
snapshot head cannot enter this cutover path. Restore records operator-only local
`governance_restore_sessions`/`governance_restore_journal` evidence and revokes
staff/subject sessions. It leaves canonical audit as the exact source prefix,
rather than appending an unwitnessed quarantine fork. Existing forked targets
are rejected and retained; the tool never deletes or rewrites their audit.

The offline reconciliation command requires both operator DB connections, the
current protected key provider, an exact production profile, the signed witness
and a separately provisioned target runtime role. The target archive intentionally
omits owner/ACL grants. Reapply the reviewed runtime grant matrix; the command
checks the actual dedicated role and re-revokes PUBLIC function execution defaults.
Only a controlled qualification connection is used before release; do not start
application traffic on the quarantined target. The operator also needs access to
`pg_control_system()` to distinguish real database/cluster identities from DSN
host aliases. This does not grant that privilege to runtime credentials.

Cutover has explicit failure boundaries:

1. Verify source/target organization, schema, artifact, keys and canonical audit
   prefix. Current authoritative source and an independent witness must exist.
2. Commit the source's durable quarantine first, including a witnessed canonical
   freeze event bound to the current control digest. Runtime reads and writes
   then fail the transaction/database fence. Source commit failure cannot release
   the destination. Source remains frozen if a later step fails.
3. Replay current authority/grants, registry/notices/purposes, subject/consent
   histories, managed primary/ciphertext/outcomes, holds/retention, rights cases
   and organization/processing controls in foreign-key order. Existing immutable
   rows must match; missing verified rows may be appended. Extend the exact
   canonical audit before importing outbox rows whose event IDs refer to it.
   This is not a generic upsert or a merge of divergent chains.
4. Revoke restored sessions/login attempts, old delivery authority and open case
   approval/preview authority. Uncommitted work becomes terminally failed and
   requires a fresh instruction and review. Independently verified immutable
   outcomes and genuine receipt/history evidence remain; commit acknowledgements
   can be reconciled without replaying primary mutations. Pending old outbox
   dispatch remains failed rather than falsely marked delivered.
5. Publish and verify the target's prepared canonical head while it is still
   quarantined. Recheck unchanged source freeze/control digest, exact target
   controls, keys, profile and actual runtime grants, then release the target.
   Source remains frozen. Retrying the same recorded phase is supported; it does
   not resume old export URLs, sessions, leases or approvals.

There is no distributed transaction or zero-downtime promise. DB, disk, source,
witness, immutable-row, key, scope or lineage uncertainty leaves quarantine.
Never replace a failed source/cutover identity, bypass a fence, or re-enable both
databases manually. A lost authoritative source needs separately qualified
recovery evidence, not an assumption that an old backup contains every later
withdrawal. Key-version changes need matching current key custody and a compatible
archive; source/target key disagreement is rejected.

Collection-level M5 recovery remains separate. This implementation and synthetic
drills do not qualify an actual host, independent custodian, RPO/RTO, load,
permissioned real data, legal review or organization pilot. Independent combined
review and exact-artifact staging acceptance remain required before production.

## Key rotation and loss drill

`keys-prepare --version <new-version> --output <new-protected-file>` adds a random
key and preserves every old key in a separate candidate. It never overwrites the
original. `keys-verify` decrypt-probes all retained document/evidence versions.
`keys-activate --candidate <candidate-file>` checks old key bytes remain intact,
switches collection write versions, quarantines the DB, revokes sessions and
invalidates pending/running approvals. Stop and restart all app/worker processes
with the candidate configured; already-running processes must never keep writing
with an old key provider. Reconcile before release. Keep old custodial copies.

Loss recovery restores key material from the separately controlled key backup,
then decrypt-probes old content and validates DB backups. The synthetic test
deliberately removes a key, observes failure, restores it and reads history.
Historical ciphertext is not re-encrypted and keys are not retired. Full historical
re-encryption/physical erasure needs a reviewed design covering immutable versions,
snapshots, WAL, replicas, exported ciphertext and key custody. That gate remains
blocked. Logical suppression is not physical erasure.

## Local evidence and remaining gates

`scripts/run_operations_drill.py --pg-bin <existing-18-bin>` creates a fresh owned
loopback cluster, uses only synthetic data, forces imports from this source,
records a minimized report and stops the owned cluster on exit. `--full-enterprise`
includes all existing mandatory enterprise suites. No owner lab, provider,
third-party witness, production key or real dataset is selected.

Deployment templates in `deployment/enterprise/` preserve one origin, secure
cookies, no CORS bypass, a loopback-only upstream, dropped capabilities,
read-only root, protected secrets and parameterized request/resource limits.
They do not provision IdP/DB/witness authority or prove images/TLS. Docker is
unavailable locally. Measure the declared workload, lock/RSS/growth/backlog and
recovery targets on accepted hardware; no SLO or M10 acceptance is claimed here.

## First organization activation

A new database stays quarantined after migrations and offline staff enrollment.
Restore reconciliation cannot activate it: that path requires an authenticated
archive and an independent current source. Use `initial-review-context` and
`activate-initial` only for a never-activated organization with no subject,
registry, processing or restore data. Existing staff authority/enrollment records
are checked and bound; they do not become legal approval.

Provision the dedicated runtime database role using the reviewed grant matrix,
and keep its protected DB reference separate from the offline operator reference.
Configure the exact source/schema production profile, managed key provider and
independently controlled witness. These operator commands do not read staff or
subject OAuth login secrets.

```powershell
python -m app.enterprise.operations initial-review-context --runtime-db-file <protected-runtime-db-file>
python -m app.enterprise.operations activate-initial --runtime-db-file <protected-runtime-db-file> --review-file <protected-reviewed-json>
```

The first command returns a `review_template` with `decision=pending_review`
and minimized authority candidates (opaque member IDs, roles and revisions).
It is deliberately invalid as an activation approval. The operator obtains the
actual independent reviews, saves only the completed template in an owner-only
file and supplies two distinct current enrolled authorities: a system
administrator proposer and an authority reviewer. Record each review's evidence
reference, the actual zoned review time, an explicit expiry within 24 hours,
and `decision=approved`. The record binds organization, artifact/schema/profile
digests, exact TLS origin, current key version, actual server/database/schema
identity and qualified runtime role identity. These identities enter the template
and review digest before approval; a first-use review cannot be redirected to a
newly enrolled clone with the same organization/member IDs.
The code checks these declarations against current state; it cannot prove that
two humans acted, accept legal applicability, or authorize deployment for them.

Activation first commits immutable review/journal evidence and a canonical audit
head while serving remains quarantined. Only after the separate witness has
published and verified that exact head does a second locked transaction recheck
authority, key material/version, profile, database/role identity, freshness and
all scope digests, then release the operational fence. The runtime is still
unable to process data until the applicable M8 binding is independently reviewed
and active. Real IdP/browser, TLS, custody, workload, pilot and owner launch
acceptance remain separate.

The template also binds the five selected operator, runtime, profile, checkpoint
and managed-key files. Activation includes the completed review file as a sixth
authority. File content, physical identity and current ownership/DACL or POSIX
mode are checked before preparation, after witness I/O and immediately before
release. Current JSON configuration is compared with the actual loaded DB,
profile, witness, review and key-provider state, so a valid changed key file
cannot qualify a stale in-memory key set. A changed or missing file requires a
fresh context/review rather than silently replacing the prepared authority.

A failed witness or final database transaction leaves the prepared record and
quarantine intact. Retrying the exact still-valid record is idempotent. A new
explicitly reviewed template may supersede an unreleased prepared record; its
old evidence stays immutable. A released record cannot be replaced or reused to
clear later quarantine. `already_activated` is a historical receipt with current
readiness unverified; if current state is quarantined the result is blocked and
the command exits nonzero. Restored targets reject this path even if an old
initial activation record was included in the archive. Never replace these
checks with an ad hoc `UPDATE governance_operations`.

The local activation tests use synthetic review references, real PostgreSQL,
actual dedicated-role login/session/registry operations and a separately signed
loopback witness. They do not establish real organizational review or production
host acceptance.

Core callers must supply a concrete `InitialFileAuthority` for configured files.
There is no user-selected validator callback or production "ignore files" mode.
The separate `SyntheticActivationAuthority` is an explicit loopback/in-memory
test-provider contract, rejects configured file-key providers and does not
establish host or custody acceptance.
