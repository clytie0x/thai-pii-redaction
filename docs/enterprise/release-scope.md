# Enterprise release scope and outstanding owner inputs

Updated: 2026-11-02. This is an execution-scope register, not deployment acceptance.

The owner authorized work through M0-M12 and YRSS completion, leaving actions
that require the owner or real participants explicit. "Anti-jobs" was clarified
as a fresh independent adversarial subagent review at every stage. This replaces
the earlier implementation pause; it does not authorize an unspecified real-data
deletion, external notification, public submission or production promotion.

## Engineering scope

- Continue existing single-organization self-hosted governance, preserving the
  authority/registry commits and local in-memory redaction-vault boundary.
- Complete staff/subject authentication, inventory, consent, managed collection,
  execution/holds/retention, rights, governance and recovery in dependency order.
- Review every stage independently. Reproduce each material finding before a
  fix and record the exact source, commands, evidence level and unresolved gates.
- Prepare YRSS evidence-linked poster, slides, speaker material and Q&A using
  frozen research results. Do not tune on or reopen closed evaluation data.
- Use synthetic local services and data. Prepare concrete pilot/release artifacts
  before requesting the final action-specific approval.

## Capability boundaries

| Area | Source/evidence | Current allowed claim |
|---|---|---|
| Root protection | `pii_redactor/`, HTTP contract 2, native protocol 1 | Source implementation with candidate-specific tests; no automatic package/live acceptance |
| Enterprise | Preserved domain commits, reconciled M0 `9711d79`, [M3 evidence](../acceptance/enterprise/M03-authority-progress.md) | Staff OIDC/console works with synthetic real IdP/database/browser and installed-wheel/restart evidence; performance/CI acceptance and later stages remain open |
| Hosted | `apps/hosted/STATE.md`, source `core/VERSION` 0.1.0 | Historical record describes 3.0.2 deployment; production was not rechecked for M0 |
| SDK | `packages/amphrang/`, separate lock/tests/engine copy | Local source SDK; publication and shared-core compatibility remain open |
| Desktop/Extension | Source 0.1.0, broker boundary | Earlier 3.0.0 package records are archived evidence, not a new 0.x installer or Store publication |
| Office | Existing task pane and fixed-port contract 2 | Real-host gates remain open; Word-only release manifest until other hosts qualify |
| Release platforms | Current release workflow matrix | Windows/macOS only; retained Linux helpers need fresh qualification if re-enabled |
| YRSS | `research/yrss2026/RESULTS.md`, separate `ai-guard-docs/stt52-2026` | Synthetic research and prepared presentation evidence; owner prints/presents/submits |

These are not interchangeable acceptance levels. Main's newer reproducible
benchmark and the frozen YRSS experiment are separate studies and must retain
their own corpus/source identities.

## Inputs that only the organization/owner can settle

| Required input or action | Responsible role | Blocks |
|---|---|---|
| Named organization/controller, departments and applicable sector duties | Owner + qualified privacy reviewer | Real-data/pilot scope and legal acceptance |
| Two distinct approved staff identities and role owners | Owner + organization authority reviewer | Production enrollment and separation of duties |
| Actual staff and customer IdP issuer/client configuration | Organization IdP administrator | Real-environment authentication acceptance |
| Storage, key and backup custodians; checkpoint sink and recovery targets | Service owner/operator | Production storage/integrity/recovery readiness |
| Exact first external system and its authorization/fencing capability | Source-system owner | Connector acceptance; irreversible execution stays disabled without proof |
| Representative permitted documents and independent human annotation | Data owner + qualified reviewers | Real-document quality claim |
| Ordinary pilot participants, support coverage and approved observation window | Service owner | Human pilot acceptance |
| Final source-bound release/deployment and any outward messages | Owner | Production promotion, stores/PyPI, regulatory or conference submission |
| YRSS authorship/content approval, timing rehearsal, print and presentation | Presenter/owner | Physical delivery and presentation acceptance |

Unknown inputs do not block synthetic engineering work. They remain explicit
release blockers; an agent or test fixture cannot sign them on the owner's behalf.

## Starting integration decision

The original checkpoint reconciliation was completed and its identities were
later mapped by the owner-authorized screenshot-only privacy rewrite. Preserve
that provenance; do not repeat the old merge or push preserved old-history clones.
Current engineering uses `.worktrees/pdpa-enterprise-clean/`, branch
`feat/pdpa-enterprise`, with the S0/S1 prerequisite checkpoint based on `6f1e63f`.
Its local artifact evidence does not clear the held main-integration gates.
`origin/main` is the clean main reference; the clone currently has no local main.

The owner approved warn/report, direct first-party core consumption, distribution
name `thai-pii-redaction-core` and fixed proxy errors with qualified rollback.
The [Astra/Sol execution addendum](../implementation/2026-11-02-astra-sol-execution-review.md)
defines the next integration/checkpoint steps. Those choices do not accept an
unimplemented adapter, an untested public projection or a release/deployment.
