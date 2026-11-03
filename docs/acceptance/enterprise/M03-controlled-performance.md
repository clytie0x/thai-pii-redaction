# Exact-main incremental performance evidence

Observed 2026-11-03. This record compares main `38b235f` with candidate
`40cf18e`. The fixed series passes every **relative** time/RSS budget. It does
not turn the older absolute-anchor failures into passes or accept the complete
M3 application, production environment or M0-M12 program.

The [compact record](M03-controlled-performance.json) binds the results below.
All earlier outliers, profiles and failed checkpoint measurements remain
retained. No baseline, tolerance, token identity or privacy guard was changed.

## Why the old anchor and main are different controls

`perf/baseline.json` was introduced at `9117a3e` on 29 July and never changed.
It records no dependency/model/CPU identity. The later `8fb1b82` security cutover,
already in main, introduced a 25-character namespace and 20-character nonce,
adding 47 characters to each token. Its commit records the then-owner-accepted
sanitize cost of +56.2%, with the baseline left unchanged. That historical
decision is not a waiver of November's M3 hold.

The new exact-main/current untimed traces agree: input length 339, six identical
entity types, masked length 557, and NER windows of 339, 557 and 491 characters.
The two outbound windows differ and both remain enabled. Namespace expansion
explains a concrete, pre-existing extra-window mechanism; it does not reconstruct
all causes of July's timings or excuse the old unexplained noisy pair.

## Fixed controlled-process comparison

Main was exported directly from 73 Git blobs, not copied from the different
`6f1e63f` control. Both arms use the same immutable public text/PDF bytes,
CPython 3.13.12, dependencies and preprovisioned CRF model. The runner freezes and
rechecks 5,943 dependency/interpreter files, two model files, both measurement
inputs and 256 current artifact inputs. Loaded product and dependency origins
are checked before accepting an arm. No ambient product import is allowed.

Before timing, one two-second CPU sample selected logical CPU 18 according to
the fixed least-busy rule. All arm processes were pinned to that CPU at normal
priority. No user application, system setting or service was changed. This
controls the measured process on a shared Windows host; it is not an exclusive
host or a production capacity test.

Exactly five pairs ran in order AB, BA, AB, BA, AB, using the unchanged official
`measure(iterations=5)` and its warmups in ten fresh processes. Raw timing tuples
were captured only after the existing timer returned, without changing its result.
Full-precision medians decide relative budgets; rounded official results and all
absolute-anchor findings are retained. Every operation and RSS must be present,
finite and positive. No failed pair was discarded and no series was repeated.

| Metric | Median paired change | Worst paired change | Allowed increase |
| --- | ---: | ---: | ---: |
| Detect | +2.648% | +6.136% | 20% |
| Sanitize | +0.865% | +3.652% | 20% |
| Restore | +14.813% | +16.406% | 20% |
| PDF | -0.343% | +0.266% | 20% |
| RSS | +0.010% | +0.224% | 15% |

Every pair passes. The full selected-CPU accounting remains diagnostic: Windows
CPU clocks are quantized, and estimated unowned CPU execution reaches 31.25 ms.
It is not used to discard or excuse a sample.

Both main and candidate still return absolute-anchor exit 1 in all ten arms.
Their absolute medians are specific to the pinned process and cannot be treated
as interchangeable with previous unpinned checkpoints. The old 14.49/0.35 ms
candidate checkpoint also remains exit 1. No absolute pass, baseline movement
or new historical timing exception is claimed.

## Integration disposition

The evidence supports the current main-to-candidate incremental performance
condition: all five pairs meet the existing relative budgets, while the old
anchor mismatch is also present on main and the earlier security trade remains
explicit. Independent review clears this narrow incremental-performance
disposition under the existing explained-trade rule. The complete M3 application
and production gates remain separate from this
incremental comparison. Exact integration-tree CI is still required.

The measured runtime is unchanged from `40cf18e`, whose 26 CI jobs pass, including
mandatory PostgreSQL, Rust and Windows/macOS packaged lifecycles. Its root/SDK
source, three installed profiles and PDF evidence remain bound to the same
256 artifact inputs. A documentation/provenance-only consolidation does not
make a new runtime or invalidate those bytes; its own exact CI remains mandatory.

The initial fixture preparation rejected Git archive newline conversion before
any timing. Its partial fixture is retained; raw `git cat-file --batch` export
then verifies every Git blob. The first two prepared inventories predate review
strengthening and were never used for measurements. Only the final v3 inventory
and frozen runner produced this one ten-arm series.

Raw protocol, runner, freezes and metadata are retained under
`.superpowers/sdd/perf-closure-20261103/` and the owned
`aiguard-perf-main-5nqcedrf` temporary workspace. They contain no raw fixture
text, entity values, mappings, pseudonyms or provider bodies. No external network
attempt occurred. Legal, pilot, actual-host and GitHub hidden-cache purge gates
are not closed by this record.
