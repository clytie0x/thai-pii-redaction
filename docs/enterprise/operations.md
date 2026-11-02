# M10 operator and recovery candidate

This is local synthetic engineering, not M10 acceptance or permission to deploy.
Use the accepted single-organization design. All declared storefronts remain in
scope. TLS/IdP/host, real witness custody, key/backup custodians, RPO/RTO, capacity,
exact images, independent review and the owner's acceptance remain open.

## Readiness and authority

`/health/live` reports only process liveness. Production construction no longer
needs a reachable DB or IdP. `/health/ready` and **every production request** check
the declared profile, source/lock/assets/schema identity, DB enrollment, historical
key decryptability, audit chain, independently signed checkpoint and restore
state. Staff and subject IdP probes run only after local prerequisites pass.
An unconfigured profile is blocked. No ready response is an owner sign-off.
All runtime transactions take the organization fence; migration 007 also checks
quarantine inside mutations, so quarantine and a concurrent mutation serialize.
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
inventory. This candidate's identity helper currently targets the source layout;
installed-image qualification remains blocked until that layout is supplied and tested.
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
python -m app.enterprise.operations restore-reconcile --source-db-file <current-authoritative-source-file>
```

Quarantine revokes staff/subject sessions and turns restored pending/running
execution approvals/leases into unknown, requiring reviewed reconciliation.
Immutable audit, outcome, version and snapshot manifests are not rewritten.
Collection-level M5 snapshot/quarantine/reconcile remains available and is not
replaced by these whole-DB tools.

**Release is intentionally blocked in this branch:** a mandatory M7 case/export
revocation handler is absent. `control_handlers()` supplies conservative equality
proofs for managed history, consent/withdrawal, holds/copy obligations and immutable
execution outcomes. If current source authority changed, refresh the backup;
this candidate does not invent a merge of stale consent/audit histories. All five
handlers (including future M7) must replay/prove their complete scope in the
locked source/target transactions. A missing handler/source/checkpoint or a
changed control leaves quarantine. The parent must integrate and independently
test current-authority replay, new approvals and case/export revocation before
any release. Do not label this partial barrier an accepted full recovery drill.

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
