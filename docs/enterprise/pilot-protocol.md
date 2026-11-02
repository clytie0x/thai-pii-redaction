# M11 organizational pilot protocol

Status: **DRAFT / UNEXECUTED**, 2026-11-03. This preregistration template serves
[M11 of the existing plan](../implementation/aiguard-production-milestones.md).
It authorizes no deployment, publication, participant enrollment, external call
or real-data operation. Record execution in [M11-pilot.md](../acceptance/enterprise/M11-pilot.md).

## Entry gate and frozen scope

The full organizational pilot cannot start yet. M7 rights/secure delivery and M8
organization control records are absent; M10 whole-database recovery, independent
checkpoints, rotation, operator workflows and drills remain incomplete. The
current source is still changing. Complete global source/CI/performance checks,
exact artifacts, actual staff/subject IdP/browser, restricted database role and
restart acceptance must be rebound to the frozen candidate. Historical and
[local-wave results](../acceptance/enterprise/M04-M06-local-wave.md) do not clear
these gates. A synthetic rehearsal of existing paths cannot accept missing ones.

Before observation, owner, service operator and qualified organization reviewer
must freeze a private registration containing:

- candidate source/tree, artifact/image, dependency/model, schema and non-secret
  configuration digests; applicable storefront/browser/OS and evidence references;
- organization/departments, intended uses, permitted data categories/modalities,
  lawful access and reviewer decisions, notices, retention and processor/transfer
  controls; actual staff/subject IdP and TLS identity evidence;
- opaque participant/role references, distinct approvers, observer, support and
  incident contacts, key/backup/checkpoint custodians and alternates;
- first named source system, allowed discovery/export/manual tasks, exact targets,
  provider/egress permissions, prohibited actions and independent outcome checks;
- fixed workload, task/quality thresholds, sample selection, observation window,
  fault/recovery plan, support targets and explicit stop/resume authority.

Public documents contain only opaque references and value-free results. Keep
identities, issuer/client/host details, keys, documents, labels, screenshots and
participant observations in approved private stores with access/retention rules.
Do not publish hashes derived from personal values. An evidence reference identifies
a privately retained record; it is not that record's sensitive contents.

The following are **PROPOSED, awaiting owner/reviewer/operator agreement**:

| Item | Proposed registration |
| --- | --- |
| Ordinary users | At least 8 participants across 2 scoped departments, including staff and separately authenticated subjects; sufficient distinct people for every review boundary |
| Observation | 5 working days; short common orientation, then an observed task session and ordinary work without observer takeover |
| Usability | At least 90% of assigned tasks completed without assistance; participant clarity rating at least 4/5. Freeze task-specific time limits before observation |
| Quality sample | At least 100 permitted representative documents, independently labelled by at least 2 qualified reviewers; stratify by intended type/modality and report sparse groups explicitly |
| Recovery | RPO at most 15 minutes and RTO at most 4 hours, measured for the agreed pilot scope |
| Support | Acknowledgement within 30 minutes during the staffed pilot window; name an alternate and an out-of-window stop procedure |

These numbers are not accepted requirements or results. Unagreed thresholds
block the relevant observation. The existing performance rule remains accepted:
20% time / 15% resident-memory budget against the unchanged baseline, with the
existing controlled-performance hold unresolved. This protocol grants no waiver.

## People and authority

| Responsibility | Actual authority and required separation |
| --- | --- |
| Owner/service owner | Approves exact pilot scope, participants, data/environment actions, thresholds and final accept/extend/reject decision; no implied M12 launch |
| Qualified organization reviewer | Reviews applicability, permitted use, notices, obligations, quality risks and any refusal/limitation; supplies human decisions, not agent sign-off |
| Ordinary staff | Use only privately assigned current roles: `data_steward` creates inventory/collections/policies; `custodian` handles scoped content, propagation and instructions; `case_manager` handles linkage proposals/holds |
| Independent reviewers | `identity_steward` reviews subject linkage; `privacy_reviewer` reviews processing/notices, linkage privacy, instructions/retention and hold release; `authority_reviewer` approves membership proposals. Preserve each workflow's distinct-person rule |
| Administrator/auditor | `system_administrator` manages membership suspension and scoped recovery, without implicit privacy approval. `auditor` inspects minimized authorized audit; cross-department access needs explicit scope |
| Subject | Uses separate subject OIDC/session and reviewed linkage; staff identity cannot supply a consent act. Representative use stays blocked unless its implemented authority path qualifies |
| Operator/custodians | Own environment, restricted runtime/migration/key separation, worker, checkpoints, backups and measured recovery. Operating access confers no application approval role |
| Observer/quality reviewers | Observe without completing tasks for users; independently label/adjudicate permitted documents. Record assistance and disagreement rather than hiding them |
| Incident lead/support | Receives private reports, pauses unsafe work, preserves minimized evidence and coordinates review. Any outward notification needs its own authority |

The private assignment matrix must make each required independent review possible.
Do not merge identities or broaden permissions to get through a script.
Role and route references are the current
[permission table](../../pii_redactor/governance/permissions.py),
[staff server](../../app/enterprise/server.py),
[subject router](../../app/enterprise/subject_routes.py),
[managed router](../../app/enterprise/managed_routes.py) and
[retention router](../../app/enterprise/retention_routes.py). Recheck these against
the frozen candidate before assigning real tasks.

## Scripted synthetic exercise

Run synthetic records first on the exact accepted pilot environment. Each row
requires observed browser behavior plus independent minimized state/outcome
evidence, not a successful request alone. Use unique opaque record/command/task
references. Preserve failed attempts, retries, assistance and unresolved state.

Current staff APIs are under `/api/enterprise/v1`; the staff UI is `/`.
Subject UI/API are `/subject` and `/api/subject/v1`. Managed staff work uses
`/managed` and `/api/enterprise/v1/managed`; retention uses `/retention` and
`/api/enterprise/v1/retention`. These optional routes require explicit configured
capabilities. They do not establish that M7/M8 routes exist.
Keep separate synthetic granted and withdrawn purpose/subject vectors: P04's
positive path uses a current genuine grant, while P03's withdrawal remains a
negative control. Never edit database history to reset consent for a demo.

| ID | Participant script | Expected proof and denial/failure check |
| --- | --- | --- |
| P01 | Staff signs in, creates an activity and notice; a different authorized reviewer activates/publishes their exact revisions | Immutable published notice/purpose references and independent review; self-review, stale revision and foreign department denied |
| P02 | Case manager proposes linkage at `/subject/staff`; distinct identity/privacy reviews bind the subject | Exact reviewed link and separate subject session; conflicting/unreviewed link and staff-cookie substitution deny disclosure/subject acts |
| P03 | Subject views exact notice, grants one purpose, refuses another and withdraws the grant | Presentation and append-only event/receipt references; no preselection or silent basis switch. Stale/replayed presentation and pending/failed propagation cannot authorize processing |
| P04 | Steward creates a consent-bound collection and synthetic document in `/managed`; custodian reads only the allowed version | Encrypted storage/protection result and exact activity/purpose/category binding verified privately. Wrong scope, withdrawn consent and unavailable selected key deny access without plaintext fallback |
| P05 | Custodian proposes an exact `restrict` instruction; distinct privacy reviewer checks and approves it; operator runs one approved action | Instruction target/version/revision/action, actors, attempt and independent target outcome agree. Self-approval, changed target/actor, expiry and duplicate delivery cannot execute stale authority; queued is not completed |
| P06 | Case manager places a hold before an approved action; operator attempts work; distinct persons propose/review release | Effective hold ordering and non-applied target outcome; stale approval cannot bypass the hold. Release review does not silently execute an old instruction |
| P07 | Steward proposes a retention policy/trigger; reviewer verifies exact due detail and approves; custodian issues the due instruction | Reviewed policy/trigger/due/instruction binding, worker outcome and separate copy obligations. Stale due records, changed purpose, unknown copy evidence and a late hold remain blocked/unresolved honestly |
| P08 | Administrator suspends a synthetic staff identity while it has an open draft; user retries and later changes principal | Old session/resolved authority denied; private drafts/old responses cleared; reactivation follows independent authority review. Test logout, expiry, interrupted request and missing/cross-origin CSRF failures |
| P09 | Operator performs the preregistered worker interruption and collection quarantine exercise on isolated synthetic targets | Lease/retry/reconciliation proves at-most-one effective outcome; unresolved work stays unresolved. Scoped independent restore review reapplies controls before reads; restriction/suppression is not lost |
| P10 | After M7 exists and qualifies, ordinary users complete access, correction, restriction, erasure and justified refusal cases, including expired/revoked delivery and partial manual failure | Scope/identity/representative review, clocks, third-party review, recipient-bound delivery and all-target outcome/refusal evidence. **BLOCKED: no current M7 case/delivery path; managed correction alone does not qualify it** |
| P11 | After M8 exists and qualifies, reviewer links processor/transfer/responsibility records and a synthetic incident to actual workflow obligations | Reviewed applicability and evidence; stale/unknown agreement cannot be called approved. **BLOCKED: current M8 records absent. Private support escalation alone does not accept M8** |
| P12 | Operator performs the M10 approved isolated whole-database recovery/checkpoint/key drill, then verifies staff/subject and worker behavior | Timed recovery point, checkpoint integrity, suppression/withdrawal/holds, key authority and current actors all reconcile before readiness. **BLOCKED: collection snapshots alone do not qualify M10** |

For P05/P07, `python -m app.enterprise work-once --worker-id '<private worker reference>'`
consumes one already approved managed outbox item. It needs private organization,
database and managed-key references, not the staff OIDC secret. The operator uses
the approved private configuration/runbook. This document executes no command.
`restrict`/`suppress` are logical controls, not physical erasure; no general undo
UI is promised. Corrections create reviewed versions. Do not test real erasure,
destroy snapshots/keys, or bypass retained controls as a pilot smoke test.

## Representative quality and first system

Freeze intended-use inclusion/exclusion, sampling strata, independent labels,
adjudication, scoring code/candidate and minimum per-type/span/character quality
thresholds before disclosure/scoring. Unset thresholds block acceptance. Reviewers
record unsupported modalities, false positives, missed spans, masking/restoration
errors and manual/blocking burden with counts and uncertainty. Keep a disjoint
evaluation set and do not tune on disclosed holdout. A miss requires restricted
use or a new candidate/fresh evaluation, not a revised threshold after results.
Neither synthetic research nor a zero finding establishes legal clearance.

The first real external system still needs a named private scope and authorization;
the current managed-document connector is not a general external connector.
Qualify discovery/export/manual fulfilment, changed targets, revoked access,
partial failure, retry and independent reconciliation on that exact system.
Without proven conditional execution/fencing, accept only explicitly documented
human execution plus independent outcome review. A request sent or task queued
never proves external fulfilment or automatic deletion capability.

## Observe, stop and decide

Observer records task attempt, result, elapsed time, assistance, mistakes,
abandonment and recovery using opaque IDs. Users perform tasks themselves;
agent-only browser automation is engineering evidence. Support tracks queue age,
failures, unresolved propagation/retention/rights, resource pressure, readiness,
checkpoint/backup age and participant reports throughout the agreed window.

Stop the affected activity immediately for unintended disclosure/authority,
wrong-target mutation, lost controls after restore, unverifiable audit/outcome,
missing key/checkpoint/backup integrity, severe participant harm, unstaffed
support, or an unexplained measured regression. The incident lead/operator
contains only within the approved runbook, preserves private minimized evidence
and notifies the designated internal owner. No external message is authorized.
Resume only after accountable review, reproduced correction and affected-gate
requalification; a changed candidate gets a new evidence binding.

At the frozen window's end, summarize every task and quality stratum, failures,
assistance, support/recovery measurements and unresolved obligations. Owner,
qualified organization reviewer and operator explicitly accept, extend or reject
the bounded pilot in the evidence record. Missing M7/M8/M10, unmeasured intended
uses, unresolved severe defects or unmet mandatory gates prevent acceptance.
Any allowed limitation needs an enforced restriction and named private acceptance.
M11 acceptance does not authorize M12 deployment/publication or real erasure.
