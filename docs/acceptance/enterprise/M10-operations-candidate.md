# M10 operations candidate: local evidence and integration boundary

This retained worker checkpoint predates the combined M7-M10 corrections. Its
test totals and integration limitations describe that earlier source only. See
the [combined integration record](M07-M10-integration-progress.md) and current
[operator runbook](../../enterprise/operations.md) for the later caller paths,
independent reviews and remaining gates.

Date: 2026-11-03. Base verified read-only before writes:
`b468592ac4a0b106116eda9119f4f9401b7cd73c`, including applied migration sources
004/005/006 and existing consent, managed recovery and holds paths.

Status: **private local candidate; M10 NOT ACCEPTED; no production promotion**.
No subagents, new dependencies, external witness/provider calls, model/corpus
work, owner-lab DB, real data, production key rotation, push or merge was used.

## Delivered scope

- Production liveness separated from mandatory readiness. Missing explicit
  profile, incompatible source/schema, bad enrollment/key/audit/sink/restore or
  IdP blocks production requests and the production worker command.
- Private migration `007_operations.sql`: whole-DB quarantine plus transactional
  production mutation/key-version fences. Parent must renumber it after the
  independently developed M7/M8 migrations and test the combined schema.
- Ed25519 signed HTTP checkpoint adapter and separately operated witness command.
  Every retained witness head is checked, including an adversarial case where
  a compromised submit credential publishes a newer head after rewriting history.
- Bounded AES-GCM streaming pg_dump archive, authenticated manifest/end marker,
  read-only validation, exact-artifact/schema rollback compatibility, and restore
  only into a newly created explicitly confirmed quarantine database. Operational
  ready state is excluded from the archive; a restore crash cannot resurrect it.
- Additive key preparation/activation, retained old keys/ciphertext/snapshot
  manifests, decrypt probes, stale-runtime-key denial and session/approval fencing.
- Parameterized Compose/TLS proxy/profile assets and [operator runbook](../../enterprise/operations.md).

## Observed checks

All PostgreSQL evidence uses PostgreSQL **18.6** in a new owned loopback cluster,
marked `synthetic_enterprise_tests`, with forced source imports. Each completed
drill stopped its owned cluster. Cache interpreters/dependencies were reused;
no dependencies were installed. JavaScript resolves the existing read-only
`node_modules` cache through `NODE_PATH`, while the tested code is this checkout.

| Check | Observed result |
| --- | --- |
| Tests first | RED for absent modules and DB-down liveness; then GREEN |
| Complete existing enterprise suites plus operations | **350 passed, 0 failures, 0 skips**, two existing dependency deprecation warnings |
| Final focused operations/readiness/checkpoint gate | **29 passed, 0 failures, 0 skips**, two existing dependency deprecation warnings |
| Root lint and formatting | Pass, 395 files formatted consistently |
| `git diff --check` | Pass |
| Version source and enterprise settings tests | 36 passed |
| `scripts/check_version.py` | Pass, unchanged 0.1.0 |
| Performance budget | **HELD**: detect 6.32 ms, sanitize 16.84 ms, restore 0.36 ms, PDF 74.43 ms; sanitize +67% and restore +29% against the unchanged baseline exceed 20%. RSS unmeasured because the permitted cache lacks psutil; no dependency installed and the 15% RSS gate is unverified |

The complete 350-case report is retained locally at
`.superpowers/m10-fb60e75ef96a465f8bcc1bd42bbd3f66/results.xml`.
The final 29-case focused report is
`.superpowers/m10-93b71935c98d4f0c90ba9b56eb4d463d/results.xml`.
Eight owned drill clusters were checked with their exact `pg_ctl -D` targets;
none remained running. The five-iteration performance output is retained at
`.superpowers/m10-perf-final.json` (exit 1). No detector/sanitize/restore/PDF hot
path or performance baseline was changed. The pre-existing parent performance
hold remains; this is a private checkpoint, not permission to land or a waiver.
The later focused gate includes an added real least-privilege-role readiness
composition test. That test explicitly uses synthetic acceptance references;
it does not prove actual infrastructure/owner acceptance or independently qualify
restore release. BFF auth/route tests isolate their operational prerequisite gate;
the dedicated operations suites test that gate directly.

Negative evidence is retained locally. One full run failed because the checkout
did not resolve the existing jsdom cache and its auth fixture still assumed the
old readiness contract. A subsequent 346-pass/1-fail run exposed a pre-existing
probabilistic tamper test that replaced a random final byte with zero. If it was
already zero no tamper occurred; the fixture now always flips a bit. No protection
was weakened to make either run pass.

## Limits that block acceptance

1. **Restore release is blocked.** M7 case/export revocation is absent on this
   branch, so no mandatory rights handler is registered. Four existing control
   handlers compare current authoritative managed/consent/hold/outcome histories;
   they refuse changed scope rather than invent a merge. Parent must implement
   and review current-authority replay/cutover with M7 and requalify the combined
   source before any serve/release. Unknown source, missing handler or divergent
   controls cannot be marked reconciled. M5 collection recovery is preserved.
2. No actual production host, TLS, IdP, independent witness custodian/retention,
   key/backup custody or image was accepted. Docker is unavailable locally.
   Profile evidence references are declarations, not proof of human acceptance.
3. No workload/RPO/RTO/lock/backlog/storage-growth acceptance was measured on
   agreed production hardware. Existing parent performance holds remain in force.
4. Actual child application/worker process kill, DB backend termination,
   committed/uncommitted restart behavior, crypto tamper/key loss and localhost
   sink failures are tested. Disk-full is injected as an I/O failure; actual host
   volume-full/power-loss and complete staging outage drills remain pending.
5. Rotation does not re-encrypt historical immutable versions or retire keys.
   Physical erasure/WAL/replica/backup disposal requires a separately reviewed
   cryptographic data/custody design. No physical-erasure claim is made.
6. Witness verification is bounded to 2,048 retained heads per check and fails
   closed beyond that limit. Larger history/retention and request-cost acceptance
   require review. The witness reference server is not a qualified public service.
7. Source-layout artifact binding is implemented; installed-wheel/image layout,
   inventory, exact images and every declared storefront's host remain separate
   gates. No storefront was removed from release scope.
8. This task prohibited subagents. A distinct adversarial self-review improved
   the interrupted-backup/restore boundary and historical checkpoint verification;
   it is **not** an independent reviewer sign-off. Parent must obtain that review.

The safe next step is parent integration/review of the private checkpoint,
followed by combined M7/M8/recovery qualification. No deploy, release, real-data
action or outward message is authorized by this evidence.
