# Reviewed processing controls

This is the M8 activity-to-processing authorization path. It records explicit
organization decisions, not a compliance score or an automated legal verdict.
Qualified legal review, real-host acceptance, M10 recovery and the pilot remain
separate gates.

## Staff workflow

1. Open `/processing-controls`, verify the current staff identity and choose a
   concrete department. Select an active, reviewed M3 activity and its exact
   revision.
2. Choose all eight current legal-control decisions explicitly. A reviewed
   not-applicable decision still needs its source, reason, reviewer and evidence.
   Choose any additional processor, transfer, policy or other controls relevant
   to this activity. Their transitive dependencies are bound automatically.
3. Record an opaque evidence reference and a zoned expiry. Save and submit the
   proposal. Do not enter personal content, credentials or document contents.
4. A different privacy reviewer opens the exact evidence preview. The preview
   includes selected controls, dependency/source versions, source digests and
   the proposed scope. Approval requires that reviewer's matching preview and
   current membership revision. Activation checks the approved scope again.
5. Propose a new M5 instruction and obtain its separate independent approval.
   The instruction displays the immutable processing snapshot that it uses.
   Activation cannot revive a cancelled instruction or a previous approval.

Drafts, submissions, reviewed decisions, activation, replacement and supersession
retain immutable histories. Lists and history have bounded pagination. Client
responses received after lifecycle or authority changes cannot restore an old
selection or evidence preview. An uncertain mutation retry keeps its exact
command key; changing identity/scope or explicitly starting a new proposal
clears that pending command context.

## Runtime boundary

The full organization profile sets `Store.production_operations_required`.
Missing, unknown, expired or stale processing controls then deny processing.
The factory installs a separate `processing_check` before the collection's
non-consent early return, so this gate covers consent and independently reviewed
non-consent activities. A production `Collection` constructed without that
callback uses the fail-closed canonical guard instead. This does not supply a
new legal basis or bypass the existing consent/category checks and hold fences.

The legacy independent M3/M5 profiles remain useful for their named tests and
tools; their unbound instructions are not full organization authorization.
Once an instruction has a processing snapshot, its exact binding remains
mandatory even outside that full profile.

M5 proposal writes the server-selected binding/revision/digest and complete
control-version closure in the same transaction as its instruction. Approval,
preview, execution and retry verify that snapshot under the organization lock.
Replacing a binding or changing/superseding any selected or transitive control
terminally cancels its scoped unexecuted instructions/tasks in the same
transaction, clears leases and writes minimized audit/outbox records. Immutable
outcomes, including a lost-acknowledgement outcome, are excluded. A failed audit
rolls the control change and cancellations back together.

Committed-outcome reconciliation may read the immutable snapshot without
granting fresh execution. The existing primary-outcome, current authority,
identity, consent and restriction proof remains separately required. Cyclic
case/control authorization dependencies fail closed; the guard is bounded.

## Private integration contract

- `ProcessingControls(store, case_checker=...)` owns the binding lifecycle,
  current control proof, immutable instruction snapshots and exact cancellation.
- `managed_services` shares this service between the collection and execution.
  `execution.processing_controls` is available to the BFF.
- `build_processing_router(service, identity)` exposes `/processing-controls`
  and `/api/enterprise/v1/processing`. Parent `identity(request, mutation=True)`
  remains responsible for actual staff sessions, origin and CSRF. Preview is
  also a protected mutation because it records the reviewer's evidence receipt.
- Read routes include `activities`, `controls`, list/detail and paged `history`.
  Commands are create, replace, submit, preview, review and activate. Inputs are
  closed schemas with explicit revisions and command keys where applicable.
- M5's public `InstructionInput` and original instruction digest remain
  unchanged. The separate immutable snapshot is server-selected, never supplied
  or replaced by the caller.
- Migration `010_processing_controls.sql` adds mutable
  `governance_processing_bindings` and append-only
  `governance_processing_history`, `governance_processing_previews` and
  `governance_instruction_controls`. Runtime grants must forbid UPDATE/DELETE/
  TRUNCATE on those three immutable tables. Do not rename an applied migration.

The parent owns mandatory-suite registration, actual shared BFF composition,
restricted-role qualification, combined artifacts, M10 reconciliation handlers,
independent review and complete production acceptance.
