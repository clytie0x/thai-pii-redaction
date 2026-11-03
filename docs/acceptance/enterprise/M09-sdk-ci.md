# M9 SDK CI evidence, bounded candidate

Observed on 2026-11-03 Asia/Bangkok. Candidate:
`b468592ac4a0b106116eda9119f4f9401b7cd73c`. The
[Imported product checks run](https://github.com/clytie0x/thai-pii-redaction/actions/runs/41515857505)
is **failed overall** because Hosted checks stop before their image build.
This record qualifies only the completed SDK jobs below. It does not close M9.

## Observed jobs

All seven SDK profile jobs pass: Ubuntu/Python 3.11 and 3.13 core and server/MCP,
Windows/Python 3.13 core and server/MCP, and Ubuntu/Python 3.13 server-only.
The bare/server-only absence checks, frozen lock, source contracts/lint/metadata
and supplied-pair outside-source install checks execute in their applicable
profiles. Conditional steps skipped in other profiles are not extra coverage.

The [SDK image job](https://github.com/clytie0x/thai-pii-redaction/actions/runs/41515857505/job/125519126254)
builds the supplied wheel pair and runs network-isolated containers. Its
downloaded report binds the image to the candidate revision:

`sha256:3b2b27925ff3ca9fa9c04279aab80826b01e4f79ef2c3e76d257424c661b8a25`

The observed smoke rejects startup without an API key, returns 401 for missing
and wrong route keys, verifies synthetic phone sanitization and exact session
restoration without a mapping field, and returns healthy v2 capability metadata.
The owned containers and private test-key file are removed successfully.

The applicable server profile also runs the owned loopback API collection:
8 requests, 9 assertions and 4 script tests pass, with the expected eight 200
statuses, verified listener ownership and successful server cleanup. This uses
a fake provider; no live-provider acceptance follows from it.

## Retained reports

Reports were downloaded from that exact run into ignored local evidence paths:

| Report | Artifact ID | SHA-256 of downloaded JSON |
| --- | --- | --- |
| `sdk-container-summary.json` | `13175805177` | `f77c3ae6b2a20a7e2534ced63176ee4235362e49e72457375ba390446f2e41e4` |
| `sdk-api-summary.json` | `13175890377` | `4254ccef5b6b9c5b073cd5b48aba75dff348e1e5bc5ff00ec901b4cdf3c5c86b` |

Local parent directory:
`.superpowers/sdd/parallel-s-m/ci/`, with `b468592-sdk-image/` and
`b468592-sdk-api/` subdirectories. GitHub artifact retention is finite; the
downloaded reports remain retained locally. These files contain fixed statuses,
digests, counts and limits rather than request, mapping, credential or answer
content.

## Limits and next gate

The existing SDK image has floating base/build inputs. Its actual image ID and
revision are verified; reproducible builds, host-port exposure, external MCP
hosts, live providers and production acceptance are not established. The
collection report's generic "not CI" limit describes its local harness scope;
the run/job above independently establishes that this instance executed in CI.
Neither evidence level proves deployment or an organization pilot.

The [Windows frozen-pair record](M01-combined-artifacts.md) remains separate and
bound to its own six artifact hashes and source base. Changes to affected
runtime, configuration, dependencies or package resources require rebinding.
M3's existing performance hold, baseline and 20% time/15% RSS budgets remain
unchanged. Root/Hosted CI failures, remaining host/image qualifications and
M10-M12 gates must be closed before production readiness.

The separate [macOS smoke run](https://github.com/clytie0x/thai-pii-redaction/actions/runs/41515857357)
fails before package build: Slice 4 records 14 passed, 1 failed and 5 ignored
when an immediate health assertion receives nonterminal `broker_busy`. It does
not establish the lock owner or a production runtime defect. The candidate
test correction uses existing bounded health readiness, retries only valid
nonterminal busy, and tests the deadline and terminal-error paths. Local Rust
compilation stops at missing MSVC `link.exe`; execution and current macOS package
acceptance remain pending CI. The failed log and run metadata are retained as
`smoke-b468-macos.log` and `smoke-b468-run.json` in the same ignored CI directory.
