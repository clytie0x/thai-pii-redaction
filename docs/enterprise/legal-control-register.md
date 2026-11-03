# Organization controls and legal-source register

M8 worker candidate, based on clean-history commit
`b4a8897edc277fcf6eb7f4e988b4bad83c5d6c55`. This document describes the
organization-register implementation and its integration contract. It does not
accept M8, clear an organization for real-person processing, or authorize a pilot.

## Registers and authority

`Processors`, `Transfers`, `Incidents`, `Assessments`, `Responsibilities`,
`Policies` and `LegalControls` share `control_register.Register`. The helper is
shared because all seven require the same exact-revision transaction, current
membership checks, department isolation, immutable history, audit, outbox and
idempotent receipt. Domain payloads stay in their own modules. No detector,
provider, vault or scoring path is copied or changed.

Each record has a concrete department, accountable opaque owner reference,
evidence reference, expiration, revision-bound dependencies and workflow links.
The lifecycle is `draft -> submitted -> reviewed -> active`, with independent
rejection and explicit exact-revision supersession. `reviewed` is not active.
The current privacy reviewer must be different from the proposer. Both membership
revisions and permissions are checked again at activation and every authoritative
use. Replacing a payload increments its revision, clears approval and returns it
to draft. Changed policies, primary sources, processors, destinations, workflow
revisions, expired safeguards or revoked authority invalidate dependent use.
Historical snapshots preserve the original approval and source version.

The existing permission matrix is reused without editing shared permissions:

| Action | Existing permission | Existing role |
| --- | --- | --- |
| Create / replace / submit | `activity.create` / `activity.update` / `activity.submit` | `data_steward` |
| Review / reject / activate | `activity.review` | `privacy_reviewer`, distinct from proposer |
| Read / history / release findings | `retention.read` | `data_steward`, `privacy_reviewer`, `custodian`, `auditor` |

Administrator status alone grants none of these actions. Evidence references
are organization reviewer attestations to separately protected records, not
verification of external documents by this service. Do not put names, incident
bodies, contracts, subject identifiers or notification content into these forms.

Processor records require agreement, instructions, purpose, recipient, actual
destination/access and explicit subprocessor inventory. Transfers additionally
bind the exact processor and primary-source revisions, reviewed classification,
safeguard/exception evidence and expiry. A cloud label cannot substitute for
these fields. Review of a transfer fails if its destination or recipient differs
from the reviewed processor.

Incidents record actual awareness time when known, awareness evidence,
uncertainty, risk review, escalation and conditional notification tasks. The
72-hour target is conditional triage advice from awareness, not a legal deadline
verdict or an exemption. Unknown awareness/risk/applicability remains unresolved.
Notification drafts are not outcome evidence. External evidence can be recorded
and independently reviewed; the service never declares notification closure and
has no sending endpoint. `pii_redactor.breach.assess_breach` remains the existing
optional operator triage tool: link its reviewed value-free report using
`triage_evidence_ref`. The register never reads arbitrary incident files or runs
the detector automatically.

Responsibilities cover controller/processor/representative, incident, training,
complaints and DPO work. They require designation, independence, conflicting-duty
review, escalation, backup and applicability rationale references. Unknown DPO
applicability cannot activate. There is no size/SME exemption switch.
Assessments cover risk, complaints, training and periodic review with findings,
mitigation and follow-up references. Policies carry explicit version references;
source policies additionally carry fetched-byte metadata, effective version and
qualified amendment-review evidence. Pending source review cannot activate.

## Release-control coverage

`LegalControls.release_findings(principal, {"department_id": "..."})` checks all
eight accepted-design review areas, including absent records. It reports
`unresolved`, `required` or `reviewed_not_applicable`, with the bound original
source/version, reviewer and membership revision, review time, rationale,
implementation and operational evidence. `blocked` means evidence is unresolved;
it is never a compliance score, DPO verdict or legal clearance. Inapplicable rows
remain visible with reviewed evidence. Required rows need both implementation
and operational references. Unresolved incident reviews/tasks in the department,
including notification drafts, block findings even when omitted from a legal
record's dependency list. Pending linked assessments also remain unresolved.

| Control key | Act anchor | Organization evidence still required |
| --- | --- | --- |
| `scope_roles` | 4-6 | Organization scope, role, identifiability and open categories |
| `consent_notice` | 19-23 | Capacity, notice, actual subject act, withdrawal, purpose changes |
| `processing_conditions` | 24-27 | Distinct general/sensitive conditions and processing authority |
| `international_transfers` | 28-29 | Recipient/access classification and exact safeguard or exception |
| `rights` | 30-36 | Identity, case clocks, exceptions, execution and delivery evidence |
| `security_retention_incidents` | 37 | Security controls, holds/copies, awareness/risk and actual obligations |
| `responsibility_records_processors` | 38-40 | Representative, controller/processor records, agreements/instructions |
| `dpo` | 41-42 | All applicable DPO routes, duties, independence and conflicts |

## Current primary-source retrieval, not legal sign-off

Actual HTTPS response bytes were retrieved on 2026-11-03 Bangkok time
(2026-11-02 around 20:03 UTC), saved in ignored local research evidence at
`benchmark/reports/m8/sources/`, and SHA-256 hashed from those bytes. The
manifest records fetch timestamps, final URLs, sizes, digests and failures.
This is a draft source register. No qualified organization reviewer has attested
amendment completeness, applicability or sector duties. All legal-source and
organization acceptance gates remain pending. These rows are not automatically
seeded as approved runtime records.

| Retrieved primary instrument / publication version | Actual bytes | SHA-256 |
| --- | ---: | --- |
| [PDPA B.E. 2562, Gazette 27 May 2019](https://ratchakitcha.soc.go.th/documents/17082307.pdf) | 343490 | `9fd1027c2e5ad93029a01d68d52d524750c1e8946b97f12fb230c11959da2f70` |
| [Processor records B.E. 2565, Gazette 20 June 2022](https://ratchakitcha.soc.go.th/documents/17211325.pdf) | 82634 | `e59f3b3843d9394173b5afbd0451dd635e0f96e1596c079d894e5482f7d82a12` |
| [Controller security measures B.E. 2565, Gazette 20 June 2022](https://ratchakitcha.soc.go.th/documents/17211326.pdf) | 104606 | `cfe3bfbfd6caa6f5648d997740afdd5620fa7595f831cf4e84787d845186f08d` |
| [DPO Section 41(2), B.E. 2566, Gazette 14 September 2023](https://ratchakitcha.soc.go.th/documents/140D226S0000000001200.pdf) | 87134 | `d8f067a9724ae13e80eca8387f0074d58d904090504121e05b48666faa1af3b8` |
| [Public-body DPO amendment (No. 2), B.E. 2568, Gazette 9 October 2025](https://ratchakitcha.soc.go.th/documents/88831.pdf) | 50859 | `90a520447f6d1ddcaa3242cea45a5e16e10ecd325a248b56003ba9d31b6102bd` |
| [Transfer Section 28, B.E. 2566, Gazette 25 December 2023](https://ratchakitcha.soc.go.th/documents/14915.pdf) | 74627 | `d3acae6ae04f005906cc733bf27dff826957b8b198dbf1d8adbe0eda1f71f862` |
| [Transfer Section 29, B.E. 2566, Gazette 25 December 2023](https://ratchakitcha.soc.go.th/documents/14913.pdf) | 118392 | `810b1490655d72f50c570024753a6ac316993a6934ddf18671ed5b70a09480e0` |

Act, processor and security text was extracted from actual downloaded bytes.
Transfer and public-body DPO PDF text has damaged character mappings; byte and
publication identity evidence does not close full visual/legal review. Effective
and amended versions must be established by the qualified reviewer before a
runtime source policy can activate. Do not copy an inferred effective date into
an approved record.

The [official public-sector catalogue](https://www.police9.go.th/รวมกฎหมายว่าด้วยการคุ้/)
also identifies later review candidates. Its links are discovery evidence only:

| Unresolved source area | Direct source attempted / identified | Status |
| --- | --- | --- |
| Breach criteria B.E. 2565 | [Gazette legacy primary URL](https://ratchakitcha.soc.go.th/DATA/PDF/2565/E/292/T_0010.PDF), [PDPC 2405](https://www.pdpc.or.th/2405/) | Fetch unavailable; no invented digest or closed source gate |
| Section 29 regulator page | [PDPC 2507](https://www.pdpc.or.th/2507/) | Unavailable; Gazette bytes above retrieved, qualified review pending |
| Small-controller records exemption B.E. 2567 | [PDPC 10095](https://www.pdpc.or.th/10095/) | Unavailable; do not rely solely on the older 2565 exemption |
| Small-processor records exemption B.E. 2567 | [PDPC 10102](https://www.pdpc.or.th/10102/) | Unavailable; applicability pending |
| Breach electronic channel revised B.E. 2568 | [PDPC 9953](https://www.pdpc.or.th/9953/) | Unavailable; no sending configured |
| Complaint channel revised B.E. 2568 | [PDPC 9948](https://www.pdpc.or.th/9948/) | Unavailable; no submission configured |
| Binding corporate policy certification B.E. 2568 | [PDPC 17272](https://www.pdpc.or.th/17272/) | Unavailable; do not treat a policy upload as certification |
| Erasure/anonymization B.E. 2567 | [PDPC 7020](https://www.pdpc.or.th/7020/) | Unavailable; M6 logical suppression is not physical erasure |
| Public-body DPO original, amendments, sector duties and newer instruments | Qualified current-source inventory | Pending, not established by search snippets |

A fetched 12,262,689-byte Department of Lands document was found to be a broad
guideline compilation, not the requested primary breach instrument. Its digest
`818521de141c59ff5e2906e4dd3490465546496c3d751aba846f8da52f72df4e`
is retained locally as negative source evidence and does not close breach review.

## Parent integration hooks

The worker does not edit shared server/settings/permissions. Parent integration:

1. Apply this worker's `007_organization_controls.sql` as **008** after M7's
   migration. Renumber before applying to the combined candidate, never rename
   an already applied production migration. `test_enterprise_migrations.py`
   derives the expected version from the authoritative migration inventory.
2. Include `build_governance_router(store, identity, case_checker=...)` from
   `app.enterprise.governance_routes` in the existing staff app. Reuse the exact
   parent `identity(request, mutation=True)` origin/session/CSRF boundary. Serve
   the existing static directory and link `/governance` from the parent console.
   No new keys, storage roots or production dependency are needed.
3. Staff actions live under `/api/enterprise/v1/governance/{kind}` for
   `processor`, `transfer`, `incident`, `assessment`, `responsibility`, `policy`,
   `legal`: GET list/detail/history; POST create/replace/submit/review/activate.
   GET `/schemas` supplies closed form schemas. GET `/release-findings` requires
   a concrete department. Every mutation carries `command_key`; transitions and
   replacement also carry `expected_revision`; review carries decision/evidence.
4. M3 activity/notice, M4 consent-purpose and M6 retention-policy links are exact
   revision and same-department checks against existing tables. Consent links
   refer to an immutable purpose/notice revision, not proof of a subject grant.
   Normal consent evaluation remains separately required. M7 case links remain
   opaque and fail closed without the parent checker. The checker signature is
   `(tx, organization_id, department_id, case_id, expected_revision) -> True`.
   It must verify the current case and scope in that transaction; existence is
   not proof of rights fulfilment. A checker result other than literal `True`
   leaves activation/use pending.
5. To bind authoritative processing, call the relevant register's
   `assert_active(tx, control_id, expected_revision, department_id)` **inside**
   the parent's existing `Store.lock(tx)` action transaction, after checking the
   action's own current permission/consent. Bind exact controls to the M5 action
   and recheck before issuance/execution, including worker retry. A separate
   `require_active` preflight is not an atomic processing authorization. Parent
   owns the shared action wiring and must qualify it on the combined tree.
6. Qualify real staff sessions/CSRF, restricted roles, browser/IdP/restart,
   combined migration upgrade and stale-control execution on that candidate.
   Do not mark these accepted from the standalone router's controlled identity
   tests or synthetic DOM checks. Existing M3 performance holds remain.
7. Add `tests/test_governance_organization_controls.py`,
   `tests/test_governance_organization_domains.py`,
   `tests/test_governance_controls_routes.py` and
   `tests/test_governance_controls_ui.py` to the parent-owned mandatory
   `scripts/run_enterprise_tests.py` inventory. The worker's frozen runner
   explicitly includes all four in addition to that existing complete inventory
   and rejects any failure, error or skip.

## Worker evidence boundary

Focused RED runs observed missing domain/router modules and the initial UI
failure before the caller paths were completed. Later real PostgreSQL failures
exposed fixture construction and stale-dependency expectations and were repaired.
Final frozen evidence: the complete existing mandatory enterprise inventory
plus all four new test files passed **347 tests, zero failures/errors/skips**,
including **25 M8 tests**. The locked Node 22 root JavaScript suite passed
**178 tests**; the new UI also passed its synthetic DOM workflow. Root Ruff
check/format passed (395 Python files), version synchronization passed at
unchanged `0.1.0`, and the staged diff passed whitespace checking. Project
imports were verified inside this isolated checkout. Full root/SDK/Office,
images, installed artifacts, CI and real browser/IdP/restart qualification of
the combined candidate remain parent gates. No
production deployment, real-data use, notification, external submission, push,
PR, main merge, qualified legal review or organizational pilot is performed here.

The five-iteration performance attempt on the final source measured detect
9.85 ms, sanitize 27.44 ms, restore 0.51 ms and PDF 103.81 ms (medians). All exceed
the unchanged time budgets; RSS is unmeasured because the read-only enterprise
cache lacks `psutil`. This is a **failed performance gate**, with no baseline
update or waiver. These measurements do not isolate the cause of the existing
performance hold. An earlier measurement overlapped orphaned tests from the
interrupted gate and is retained as weaker evidence, not the final measurement.
Only those exact owned test processes were then stopped before remeasurement.
The sign-off commit is held for parent review and qualification, not permission
to land or release this candidate.
