# Controller workflow and records design

This is a proposed organization architecture and a working local planning
prototype. It does not implement a consent ledger, verify identity, delete
records, respond to a person or authorize an external AI call. The prototype
emits proposed tasks; authoritative systems and a controller must verify them.

## Processing path

1. Register a specific purpose, controller, recipients, data sources and
   necessity. Decide applicable scope/exemptions and transfer safeguards.
2. Assess text with the versioned category catalog. Keep category, personal
   attribution and uncertainty separate. Route unsupported media and open-world
   cases to qualified review. A zero finding is not a legal clearance.
3. Minimize direct identifiers through the existing shared masking core.
   Sensitive findings remain warn/review; do not automatically remove all
   health/belief statements or infer race from nationality/photos.
4. Verify a Section24 route and, separately, a Section26 condition when needed.
   Consent is scoped to purpose/notice/version; contract does not replace a
   missing sensitive-data condition. Caller booleans are not evidence.
5. Validate capacity/representative authority, notice, recipients, retention,
   processor instructions and destination safeguards. Approve only the exact
   necessary protected payload through a separately authenticated controller.
6. Record minimized evidence, not original documents or reversible mappings in
   an ordinary audit export. Existing per-run receipt can attest its stated
   artifact; it is not proof of consent or complete RoPA compliance.

## Proposed authoritative records

| Record | Minimal protected fields | Responsibility |
|---|---|---|
| purpose registry | purpose/version, controller, necessity, legal-route and safeguards evidence references | controller/legal reviewer |
| consent event ledger | opaque subject reference, purpose/category scope, notice version, affirmative act/time/channel, representative review, withdrawal event | consent service |
| data inventory | opaque asset/processor/storage references, purpose, source, categories, retention rule, disposal/restriction/correction state | data custodian |
| retention policy | start event, justified duration/rule, legal source, policy owner, review date, hold grounds and review/expiry | controller/custodian |
| rights case | received/completed/check dates, right, identity/authority evidence reference, exceptions, decisions, secure-delivery evidence | rights case manager |
| processor instruction | approved scope/action, idempotency key, acknowledgments/failures and reconciliation state | processor coordinator |
| execution evidence | authorized action reference, verified outcomes, copies/backups and restore suppression, restricted failure records | verified connectors/auditor |

Opaque/HMAC references can remain personal data. Protect linkage keys and
evidence stores, separate duties, restrict access and define retention for the
records themselves. Never store raw identity documents in general logs.
The local planner deliberately accepts closed enums/booleans/dates, not a
free-text purpose or identity payload. Its output never certifies these records.

## Consent state machine

`unrecorded -> presented -> granted/refused -> withdrawn/expired/replaced`.
Every transition needs purpose/version, evidence and authority; retries must be
idempotent and an old grant cannot resurrect a withdrawal. Withdrawal stops
consent-dependent processing and propagates by purpose/recipient. A distinct
lawful purpose can require continued restricted retention, but no silent basis
switch is allowed. Section26 explicit-consent withdrawal is evaluated even
when the general route is contract. Capacity must be reviewed under section20;
do not infer a universal guardian rule from age/disability alone.

## Retention state machine

`active -> due_for_review -> approved_disposal -> execution_pending -> verified`.
A justified hold branches into `restricted_hold -> overdue_hold_review` until
reviewed; it never silently authorizes unrestricted indefinite use or deletion.
Unknown duration remains unknown, not a default30/90-day policy. Retention
expiry is different from a request's response clock.

Include originals, extracts, outputs, mappings, caches, logs, processor copies
and backups. Delayed backup disposal needs suppression of use/access and later
completion; restore must reapply deletion, correction, restriction and withdrawal
records. A successful task dispatch, removed Python reference or missing local
file is not verified erasure. Unlawful-processing section33(4) qualifying
requests cannot be satisfied by substituting anonymization.

## Rights case state machine

`received -> identity/authority_check -> complete/deficient -> scope_and_exception_review
-> approved_partial/full/refused -> execution/delivery_pending -> evidence_verified -> closed`.

- Access2026: initial check within15 days of receipt; correction opportunity
  at least10 days; respond within30 days with a justified/notified extension
  at most30 more. Keep original and corrected-complete receipt separately;
  do not reset clocks for every check. Preserve required case evidence>=2years.
- Qualifying erasure2024:90 days from receipt, subject to applicable exceptions;
  do not borrow the access completeness reset. Keep the conditional receipt
  clock visible while qualification is reviewed. No90-day retention grace.
- Portability: verify applicable automated-processing/data scope and authority
  before a machine-readable export proposal. No universal30-day timer.
- Objection/restriction: segregate or restrict as appropriate during review;
  do not wait in a generic30-day queue. Verify grounds/authority/exceptions.
- Rectification: verify the proposed correction and propagate approved changes
  to processors and future restores; do not expose unrelated persons' data.
- Withdrawal: record and propagate the purpose-specific event; distinguish
  stopping processing from deletion, other purposes and legal retention.

Calendar anchors from the prototype are indicative arithmetic. Applicability,
actual receipt, holidays and service-specific rules require controller review.
No executor may treat `basis_reviewed` or `identity_verified` from an arbitrary
JSON file as authenticated approval. Add signed authority checks and tested
connectors before any organizational rollout.

## Existing capability reuse and boundaries

Evaluation-informed routing: controller-confirmed category inventory is an
independent input, never an inference from zero detector findings. The measured
ACTIVITY/QUASI_IDENTIFIERS gaps require manual classification and purpose review.
Use deep hybrid assessment on relevant records even when a fast screen is
empty. No future executor may grant approval without authoritative inventory,
scope/basis/condition checks and human verification of unresolved capabilities.

`receipt` supplies per-run evidence; `dsar locate` helps discovery; `breach
assess` helps incident triage. None completes consent, rights fulfilment or
regulatory notification. Evaluate DPO, processor agreements, security measures,
incident notification and transfers as separate applicable obligations. The
current HTTPv2/native/Hosted runtimes are not migrated by this local CLI work.

Legal sources and limits: [source report](reports/PDPA%20coverage%20and%20lifecycle.md).
Additional committee-prescribed sensitive categories remain unverified; the
catalog explicitly leaves an open review slot rather than inventing them.
