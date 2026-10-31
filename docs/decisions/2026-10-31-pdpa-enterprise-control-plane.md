# PDPA enterprise control plane

Status: **Proposed; architecture approval pending.** No enterprise implementation,
deployment, identity-provider configuration or real-data action is authorized by
this document alone. The owner requested work toward a full organization system
on 31 October 2026. The existing local assessment prototype remains usable.

## Outcome and proposed first deployment

Build an operational system in which an organization can register processing,
record scoped consent, manage retention and rights cases, approve specific
actions, and inspect evidence of their actual outcome. A successful task dispatch
or a detector finding is not legal approval or verified fulfilment.

**Builder proposal:** one self-hosted organization, multiple departments and
separate staff roles. The owner has been asked whether this should instead be a
multi-organization SaaS. Do not treat the proposal as an answered preference.
No SaaS isolation, availability or production claim follows from a local build.

Keep this work in the existing repository and shared Python core. Use a dedicated
enterprise FastAPI application and web interface so persistent governance records
do not silently change the local in-memory mapping boundary or existing HTTP v2,
native broker, Desktop, Extension, Office and AI for Thai contracts.

The first complete execution scope is an application-managed document collection
with synthetic integration fixtures. External business systems start as explicit
manual fulfilment tasks with reviewed evidence, not pretend automatic connectors.
A real deployment needs a named organization, IdP, storage owner and exact first
external system; these have not been supplied.

## Existing alternatives and remaining gap

Sources checked on 31 October 2026:

| Alternative | Observed capability | Decision for this project |
|---|---|---|
| PDPC GPPC PLUS | Official site lists RoPA, consent, breach and rights management | Prefer adoption/interoperation if it meets the organization's needs; self-hosting/API/export eligibility is unverified. Do not claim those functions are novel. |
| Ethyca commercial platform | Current documentation covers consent, privacy requests, identity verification and access packages | A possible procurement alternative; pricing, Thai-specific configuration and deployment rights require evaluation. |
| Fides public repository | Public repository is archived, read-only since 28 August 2026 | Reference its patterns, but do not introduce an archived fork as the maintained enterprise foundation. |
| Existing AI Guard | Local Thai text assessment, masking, receipts, DSAR discovery and breach triage | Reuse these capabilities. They are not a durable governance registry or execution system. |

The justified new work is a Thai-law-versioned, evidence-gated workflow integrated
with the existing local detection core and organization-owned execution evidence.
It is not a claim that writing another generic consent dashboard is necessary.

Sources: [GPPC PLUS](https://register-gppc-plus.pdpc.or.th/),
[Ethyca documentation](https://www.ethyca.com/docs),
[Fides repository](https://github.com/ethyca/fides).

## Architecture and boundaries

Proposed components:

1. A same-origin staff web application, with guided setup, work queues, forms,
   review screens and accessible loading/empty/error states. Retain the existing
   lightweight browser stack; no unrelated frontend rewrite.
2. `app/enterprise/`: a dedicated FastAPI adapter and browser session boundary.
   Browser DTOs contain only fields authorized for the current role and scope.
3. `pii_redactor/governance/`: authoritative domain commands, transitions,
   permissions, idempotency and execution policy. Reuse `pdpa_assessment`,
   `pdpa_lifecycle`, detection and protection; never fork the detector.
4. PostgreSQL 18 with schema migrations, transactional command/audit/outbox
   commits and revision-based concurrency control. No SQLite-only test can prove
   PostgreSQL locking, isolation, migration or recovery behaviour.
5. An organization identity provider via OpenID Connect, authorization code with
   PKCE and a backend-for-frontend session. No custom password/OTP platform.
6. A worker using a transactional outbox with leases, retry classification,
   bounded concurrency and reconciliation. Do not add Redis merely for a queue.
7. Protected document/evidence storage, an independent audit checkpoint sink,
   and narrowly configured execution adapters. No arbitrary URL, SQL or path
   from a browser can select an execution target.

The proposed new production dependencies are an OIDC client and PostgreSQL
driver/migration tooling in a separate enterprise optional dependency set. Before
installation, verify current maintenance, supported versions, licenses, advisories
and lock compatibility. Pin tested artifacts; never use an unbounded image tag.
No dependency or identity provider has been installed for this proposal.

PostgreSQL 18 is a currently supported line, not an invented future prerequisite:
[version policy](https://www.postgresql.org/support/versioning/).
OAuth web clients also need PKCE protections:
[RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html).

### Identity and authority

Bind a staff principal to the configured issuer and immutable subject, not an
email or browser-supplied role. Validate issuer, audience, signature/algorithm,
nonce, state, token age and PKCE through a maintained client. Server-side sessions
use hashed random identifiers, HttpOnly/Secure/SameSite cookies, expiration,
logout/revocation and CSRF protection. Do not put provider tokens in browser
storage. Deny untrusted origins and ignore client-supplied identity headers.

Role assignments and scope are authoritative records checked on every command
and read. Revocation must take effect without waiting for a stale browser token.
An IdP admin claim does not automatically make someone a legal approver.

| Role | Allowed responsibility | Separation requirement |
|---|---|---|
| system administrator | IdP, configuration, membership proposals and operational health | Cannot approve a legal basis, activate a privileged role grant or approve their own destructive action merely by being admin |
| authority reviewer | Approve privileged role/scope changes under the owner-approved enrollment policy | Cannot approve their own grant or a proposal they authored; no implicit legal/action approval |
| data steward | Inventory, processing drafts, collection and correction proposals | Cannot activate their own processing approval |
| privacy reviewer | Basis, sensitive condition, capacity and exception decisions | Approval requires evidence and a distinct proposer where required |
| case manager | Receive requests, verify identity/authority, coordinate fulfilment | Cannot close a case solely from a successful job dispatch |
| identity steward | Review authoritative subject/source links within approved scope | Cannot merge subjects from detector similarity, names or a shared phone alone |
| custodian | Review and run approved connector actions for assigned assets | Cannot broaden target, purpose, version or action |
| auditor | Read minimized event/evidence views and verify checkpoints | No workflow mutations or raw-document access by default |

The first organization needs at least two distinct authorized staff principals
for separation-of-duty operations. No development bypass may enable a production
mutation. Unconfigured authentication means startup/readiness failure, not an
open dashboard. Synthetic development identity is isolated from production.

Builder resolution after independent review: initial offline enrollment records
two distinct pre-approved issuer/subject identities and role/scope assignments
under the organization's owner-controlled setup procedure. It runs once on a
new organization before web writes are enabled. Subsequent privileged membership
or scope changes require a proposal and approval by an already authorized,
distinct reviewer who is neither proposer nor beneficiary. No web admin can
self-promote, replace that approval, or create another IdP identity with assumed
legal authority. IdP administration and application approval are different duties.
Recovery is an offline owner/quorum procedure that disables ordinary writes,
records independently checkpointed evidence, revokes old sessions and re-enrolls
staff; it cannot forge legal approvals or authorize a pending disposal. This does
not claim protection from collusion or a fully compromised owner/DB/IdP.

### Persistence and evidence

Use UUID references and explicit schema/revision versions. All records bind to
one configured organization and department/asset scope. Subject references and
evidence links remain protected personal information, even when opaque.

| Record | Required content and invariant |
|---|---|
| Organization and membership | Immutable IdP binding, role/scope, enabled/revoked state and assignment audit |
| Processing activity / RoPA | Controller/processor role, purpose/version, necessity, subject/category inventory, recipients, destination, retention, security and legal evidence references; reviewer activation |
| Notice version | Immutable published text, language, purpose/category scope, effective dates and digest; changes create a new version |
| Subject linkage | Restricted organization identifiers and resolution provenance; no PII hashes in general audit exports |
| Consent event | Affirmative act/refusal/withdrawal, notice/purpose versions, scope, channel/time and capacity/representative evidence; append-only history |
| Asset and retention policy | Exact owner/connector scope, policy trigger and due date, copies, disposal method, hold grounds/expiry/review and revision |
| Rights case | Original receipt, completeness, identity/authority decision, exceptions, deadlines, approved scope, tasks and secure delivery evidence |
| Processor and transfer | Agreement/version, instructions, recipients/subprocessors, destination/safeguards and reviewed validity |
| Incident | Awareness time, facts/uncertainty, risk review, actions, conditional notification clocks and actual submission/delivery evidence |
| Risk assessment | Necessity/proportionality, sensitive/high-risk scenarios, mitigations, owner review and follow-up; not an automatic legal certification |
| Execution instruction | Approver, exact target/version/action, idempotency key, authorization expiry, worker lease, attempts and independently checked outcome |
| Audit event | Actor reference, fixed event code, affected opaque record/revision, time, previous-event hash and checkpoint; no request bodies, raw values, identity documents or credentials |

Each write, corresponding minimized audit event and outbox task must commit
atomically. An audit failure prevents the authoritative transition. Unique
command keys bind to a canonical request digest: same command returns the prior
outcome; reusing a key with a different payload returns a conflict. Stale record
revisions return a conflict and never overwrite a later withdrawal or hold.

Hash chains alone do not protect against an administrator rewriting the whole
database. Checkpoints go to independently controlled append-only storage with
separate retention/access. Until that sink and restore drill pass, report audit
integrity as local tamper evidence, not immutable audit.

Documents and evidence use encryption at rest, restricted access, key rotation
and backup policy. The key store and ciphertext must not share identical access
authority. General logs/metrics are value-free; no raw-content exception dumps.
Rights exports are purpose-scoped, encrypted, short-lived and audited, with third
party redaction and a verified delivery outcome. They are not public file URLs.

## Operational workflows

### Processing and consent

An activity moves from draft to submitted, reviewed and active, or rejected.
Activation requires confirmed inventory, necessity, general legal basis, separate
sensitive-data condition where applicable, notice, retention and destination
review. Unknown/unsupported detector coverage is a review blocker, not clearance.
Existing sensitive findings remain warn/review and never trigger blanket deletion.

Consent is scoped to subject, purpose, categories and notice versions. Re-grant
requires a new evidenced affirmative event; a retry of an old grant cannot undo
a withdrawal. Verification of capacity/representative authority is explicit.
Withdrawal immediately changes effective processing authority and schedules
recipient instructions. Failed propagation stays visible; no silent switch to
another basis. Ongoing necessary retention remains separately justified and
restricted. The staff console cannot manufacture a subject's affirmative act.

Builder resolution after independent review: Stage 2 includes a separate subject
consent portal. The first authenticated-person flow uses an approved customer
OIDC issuer/client, distinct from staff audiences and role claims; the local
integration environment supplies real synthetic customer identities. Bind the
authenticated subject to reviewed source-system identity before a purpose-scoped
grant/refusal/withdrawal. Show the exact immutable notice and separate affirmative
choices; withdrawal is available with equivalent effort. Record the authenticated
actor, notice digest, selected scope, server receipt time and event version.
Alternative verified offline withdrawal remains a case-manager workflow with
source evidence and independent review, not a fabricated portal click. Website
cookie consent, anonymous marketing banners and importing arbitrary third-party
consent receipts are separate adapters, not implied by this first flow.

Subject resolution uses an authoritative organization customer/employee key plus
source-system provenance, reviewed by an identity steward and a distinct privacy
reviewer for cross-department links. Name/email/phone/NER similarity only proposes
a review candidate. Conflicting links remain unresolved and block disclosure or
destruction. Departments cannot enumerate the central linkage store; reviewers
receive only the specifically authorized case scope. Corrections create new link
versions, invalidate affected execution approvals and retain restricted history.

### Retention, holds and execution

The scheduler identifies due assets and proposes exact actions. A distinct
authorized reviewer approves a bounded plan. The worker rechecks current hold,
policy, consent/rights restrictions, target revision and approval immediately
before execution. A concurrent hold wins over a stale disposal instruction.

Use bounded allowlisted connectors, never caller-defined filesystem paths or
SQL. The first real reference adapter controls only the application-managed
document collection, whose encrypted content/version and control records reside
in the same PostgreSQL transaction boundary. Verify deletion/restriction/correction from the target and
record failures per target. Retry is idempotent; a crash after a remote action
requires reconciliation, not blind repeat or an exactly-once claim.

Builder resolution after independent review: for the managed collection, lock the
asset guard, current policy/hold and exact instruction, revalidate approval, then
perform the primary-store mutation, audit/outbox write and outcome state in one
transaction. A committed hold before this serialization point prevents disposal.
A hold request received during the transaction must not be acknowledged as an
effective pre-disposal hold; after serialization it returns the actual action
state and opens an urgent post-action review where necessary. It cannot undo a
committed irreversible action. Capture request/commit times and distinguish
pending, effective and post-action hold states in the UI.

For remote stores, automatic irreversible execution is disabled unless the
connector supports an equivalent tested conditional/fencing boundary. A last
second HTTP check is insufficient. Without such support, use a named manual task
and evidence review, with this race limitation visible. Primary logical removal
does not prove physical removal from PostgreSQL pages, WAL, replicas or backups;
those remain explicit obligations before overall erasure is called verified.

Backups, derived copies and processors have separate fulfilment states. A
primary deletion does not close them. Restore quarantine reapplies suppression,
correction, withdrawal and restrictions before the data is served. A broken
checkpoint/backup or unknown restore scope prevents readiness.

### Rights and delivery

Accept requests through documented channels, retain the original receipt and
review identity/representative authority without gathering excessive identity
documents. Public intake, if enabled later, is rate-limited and cannot reveal
whether a person exists. Staff and subject sessions are separate authorities.

Use the existing law-versioned planner only as an advisor. Derive authoritative
context from reviewed records, not a user JSON flag. Preserve distinct access
and erasure clocks, explicit extension/refusal reasons, partial outcomes and
applicability review. Do not invent one deadline for every right. Existing
calendar arithmetic is not holiday/jurisdiction acceptance evidence.

Closure requires every in-scope target, processor/backup obligation, delivery
or justified refusal to have evidence. Unsupported systems become named manual
tasks with accountable owners and reviewed evidence, never green automated
successes. A withdrawn request does not erase the audit/retention obligations.

### Wider organization controls

The release must also support processor agreements and transfers, versioned
policies/notices, DPO/responsibility records, incident handling, risk/security
assessments, review/training attestations and complaints/escalation. These are
reviewable organization records and tasks, not automated determinations that a
DPO is required or that an incident must be reported. Regulatory submissions,
external messages and real deployments require the owner's explicit authority.

Legal grounding remains the [PDPA coverage source report](../../research/pdpa-coverage/reports/PDPA%20coverage%20and%20lifecycle.md)
and [controller lifecycle design](../../research/pdpa-coverage/LIFECYCLE-DESIGN.md).
Validate the full release control matrix against current primary Thai sources
and a qualified organization reviewer before handling real people.

### Release control matrix

These references identify engineering review areas, not a legal opinion that all
statutory duties apply to every organization. Each release control must carry an
owner, applicable legal instrument/version, reviewed applicability, implementation
evidence and operational acceptance. Unknown applicability remains unresolved.

| Review area | Primary Act anchor | Product evidence required |
|---|---|---|
| Scope, controller/processor role and identifiability | Sections 4-6 | Approved organization/processing scope and an open category inventory |
| Consent, notice, capacity and changes of purpose | Sections 19-23 | Immutable notice versions, actual subject act/withdrawal, authority and purpose review |
| General and sensitive processing conditions | Sections 24-27 | Distinct reviewed basis/condition records and restricted activation |
| International destinations and safeguards | Sections 28-29 | Destination, recipient and applicable safeguard review, not a country-name checkbox |
| Rights, exceptions and fulfilment | Sections 30-36 and applicable notices | Case-specific clocks, identity/scope decisions, target/delivery evidence and refusal reasons |
| Security, retention and incidents | Section 37 and applicable notices | Enforced controls, disposal/hold records, conditional incident review and actual notification evidence |
| Responsibility, records and processors | Sections 38-40 | Controller/processor records, required representative review, agreements and instructions |
| DPO applicability and responsibilities | Sections 41-42 and applicable notices | Reviewed applicability, designated responsibility, independence and escalation records |

Primary text: [Personal Data Protection Act](https://ratchakitcha.soc.go.th/documents/17082307.pdf).
Do not call a control complete merely because its schema or menu exists. The
current text detector and prior synthetic F2 results do not satisfy this matrix.

### Verified subordinate-source boundaries

Additional primary notification review on 31 October 2026 changes the required
applicability/evidence fields below. These are release requirements; no rule
engine, organization decision or legal sign-off has been implemented.

| Source reviewed | Required organization evidence | Required failure/decision example |
|---|---|---|
| [2023 DPO notification under Section 41(2)](https://ratchakitcha.soc.go.th/documents/140D226S0000000001200.pdf), clauses 4-8 | Core-activity purpose, regular/systematic monitoring, scale factors, relevant listed activities, reviewer rationale and conflicting-duty review | Fewer than 100,000 subjects is not an automatic DPO exemption. The 100,000 condition is one deemed-large-scale case; other criteria and Section 41 routes still require review. |
| [2022 small-organization record exemption](https://www.dga.or.th/document/106104/), clauses 3-4 and linked notification PDF | Qualifying organization type, relevant computer-traffic provider status, frequency, rights/freedoms risk and Section 26 processing; explicit scope of exemption | An SME checkbox cannot disable every record or audit trail. The notification specifies Section 39(1) items (1)-(6) and (8); item (7) is not included. Non-occasional, risky or sensitive processing requires separate assessment. |
| [2023 international-transfer notification under Section 28](https://ratchakitcha.soc.go.th/documents/14915.pdf), clauses 3-7 | Actual destination/recipient, technical and legal access capability, reviewed transfer classification, adequacy evidence or exact applicable exception and authority | A foreign-cloud label does not by itself settle transfer classification. Neither storage location nor a generic consent flag proves adequate protection or a valid exception. Section 29 safeguards require their own reviewed source. |

The Section 28 PDF's extracted text was corrupted; all three rendered pages were
visually inspected against the original. Preserve that distinction from text-only
metadata discovery. Original bytes were downloaded into ignored local research
evidence at `benchmark/reports/pdpa-enterprise-law/`; SHA-256 fingerprints:

- DPO Section 41(2): `d8f067a9724ae13e80eca8387f0074d58d904090504121e05b48666faa1af3b8`.
- Small-organization exemption, DGA-hosted official notification copy:
  `ff48c7f8b9668a30518a4bd227ca8b17c070c8c6b40894771f5d1627b6b894fd`.
- Transfer Section 28: `d3acae6ae04f005906cc733bf27dff826957b8b198dbf1d8adbe0eda1f71f862`.

Do not label this an exhaustive or consolidated legal register. The security
notification legacy Gazette URL was inaccessible through the web reader, and
primary-text review of security, breach notification, processor records, Section
29 safeguards, amendments and sector-specific duties remains open. Catalogue
search results alone do not close those gates. Each applies-to/does-not-apply
decision needs the organization reviewer and current source/version evidence.

## Staged delivery and proof

Do not describe every stage as production-ready. Every stage must have a working
staff-facing path, failure states, migrations, tests and current operational docs.

| Stage | Complete working result | Required acceptance evidence |
|---|---|---|
| 1. Authority and inventory | OIDC staff login, scoped roles, processing registry, notices, persistent transactions and audit | Real local IdP/PostgreSQL restart; forged/expired/revoked identity, CSRF, role escalation, two-person approval and lost-update tests; no raw values in logs |
| 2. Consent | Real subject grant/refusal/withdrawal history, notice proof and effective processing check | Old grant replay cannot restore authority; consent/withdrawal race; representative review; propagation failure remains unresolved |
| 3. Retention and holds | Policies, due queue, holds, two-person approval, worker and managed-document adapter | Concurrent hold/approval race, worker crash, target substitution, retry/conflict, verified primary disposal and incomplete backup state |
| 4. Rights | Intake, verified case workflow, legal clocks, asset discovery, correction/restriction/export and controlled delivery | Identity mismatch, third-party disclosure prevention, access/erasure clock distinction, partial failure, secure download expiry, closure blocked without evidence |
| 5. Organization governance | Processor/transfer, incidents, assessments, DPO/policies and review/complaint queues | Permission-specific workflows; evidence/notification gates; no automatic external submission; traceability to source/version |
| 6. Pilot and recovery | Hardened deployment, exact artifact, first external connector and operational runbooks | Real TLS/IdP/storage acceptance, adversarial review, backup/restore/key-rotation drills, audit checkpoints, representative human-labelled trial and owner sign-off |

These stages are one integrated program, not six empty modules. No fixed release
date or organization-wide scale target is fabricated before the environment and
first integration are known. Proposed initial acceptance workload: 20 concurrent
staff and 10,000 synthetic registry/case/consent records; publish the measured
hardware, p50/p95, failure rate, storage growth and worker throughput. The owner
can replace that provisional workload before capacity claims are made.

## Non-negotiable failure cases

- An unsupported/zero-result detector never authorizes a processing activity.
- A disabled staff account, stale role or browser-provided reviewer flag cannot
  approve, export, execute or view another department's protected records.
- An administrator cannot bypass independent legal/action approval.
- No transaction can publish a record without its required audit/outbox event.
- A stale grant/approval cannot undo withdrawal, an effective committed hold or
  target revision. Holds after the irreversible serialization point are never
  misreported as having prevented disposal.
- A worker success message without target evidence cannot close fulfilment.
- Audit integrity and restore failures stop readiness; they do not disappear
  behind a healthy HTTP process or a green unit suite.
- No production authentication bypass, global cleartext evidence bucket,
  arbitrary connector target, real customer fixture or silent model fallback.

## Owner decisions and next action

One material question is pending: self-hosted single organization or multi-tenant
SaaS. The proposal recommends the former. The proposed core boundary and persistent
authority model require architecture approval under this repository's AGENTS.md.
After approval, write the concrete Stage 1 implementation plan, independently
review the change, and build/verify each complete stage in order. Do not mark the
enterprise objective complete from this design or from the prior 2,840-test suite.

Independent builder check completed read-only. Its four material questions about
privileged enrollment, real subject consent, cross-department identity and the
hold/execution serialization boundary are resolved above as builder proposals.
No product tests, database, identity provider or execution adapter were created
or run in this design phase. Local document links and whitespace checks passed.
