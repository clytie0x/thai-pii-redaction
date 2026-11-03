# M2 installed PDF and SDK CLI evidence

Observed 2026-11-03 on Windows 11 x64, Python 3.13.12. Result: **seven bounded
proof groups pass**, not seven full test suites and not complete M2/M9 acceptance.
The [machine record](M02-installed-pdf.json) binds commands, artifacts, versions,
output hashes and retained harness failures. A separate read-only evidence and
visual review returned **CLEAR**: driver/command/result/output hashes, installed
payload bytes and all three final PNGs matched. It did not rerun tests or extend
the candidate, host or performance qualification.

## Candidate and isolation

This uses the existing [frozen paired artifacts](M01-combined-artifacts.md), built
from `b4a8897edc277fcf6eb7f4e988b4bad83c5d6c55`, in its existing enterprise install.
The direct core wheel SHA-256 is
`ab4b7ef08c2c53d7beac38e2275853aa77ff3bd6e89f5148d74375dd52da886e`;
the SDK wheel SHA-256 is
`f75cd8d1540555603f0301e425c628b3f27c27170f33d9ae3e51e693e956b9ed`.
All 198 installed wheel payload files checked match those supplied wheels.
Application imports resolve inside that installed environment. No build,
installation, dependency change, source import or database/provider service was
performed. Runtime/config/lock paths were unchanged from that base through
`05d5d77f87afeb6b5d3d0d04b6a1737ae7166f8f`; this does not qualify later M7/M8/M10
artifacts or a complete newly integrated candidate.

The child interpreter runs with `-I -B` from a fresh temporary directory, with a
filtered environment, explicit local thainer/offline mode and preprovisioned
model files. Model hashes are unchanged after the probes. A socket guard rejects
all application connection attempts. Its only exception is the verified CPython
`socket._fallback_socketpair` call to loopback used for the Windows asyncio
internal wakeup pipe. The final run records one such internal pair and zero
other connection attempts. This is process instrumentation, not a network
namespace or operating-system firewall acceptance.

## Observed public paths

| Path | Observed result |
| --- | --- |
| Installed `extract` and `redact_pdf` | Two real text-layer PDF pages, three identical source occurrences. Two selected occurrences become solid black; the unselected occurrence remains visible. Every extracted word retains its exact source interval, and output text extraction is empty after flattening. |
| Invalid provenance | Missing source provenance raises the fixed `PdfSourceMappingError`, without the marker or exception cause/context; no output file is created. |
| Installed Thai font and extraction | Packaged Thai font renders a combining-character probe; extracted word intervals match the original character slices. No Thai OCR inference is claimed. |
| Installed `/api/redact-pdf` | Actual in-process FastAPI/ASGI request detects four synthetic phone occurrences and two emails across two pages. All six source boxes are solid black; flattened output has no extracted text or tested values in metadata. Response has neither a mapping nor a before preview. |
| PDF failure and resource paths | Non-PDF, malformed and password-protected inputs return `422 document_invalid`; absent OCR returns `503 ocr_unavailable`; a page exceeding the configured geometry cap returns `413 payload_too_large`. Endpoint temporary directories are unchanged after success and failure. |
| Installed SDK CLI | Generated `amphrang.exe --help` exits successfully. Its installed `report` handler also runs under the instrumented process and reports the type/count without echoing the synthetic value. Full external-process report execution is not claimed. |

The core and HTTP output PNGs were inspected visually: selected regions are
opaque, the safe control and unselected occurrence remain readable, and the
HTTP output covers both repeated phones and email. Pixel hashes of all three
inspected PNGs match the final launcher-inclusive run. Numerical bbox checks
and visual inspection are separate observations; neither proves detection
completeness for arbitrary documents.

## Root CLI delivery boundary

The root wheel contains no `ai_guard.py` module or root CLI entry point, and an
isolated import lookup confirms its absence. This matches the existing
[distribution migration contract](../../enterprise/distribution-migration.md),
which introduces no installed CLI command. The README's root CLI examples run
`ai_guard.py` from a source checkout. That source-only CLI was not copied into
the installed environment or relabelled installed acceptance. The SDK owns the
separate installed `amphrang` entry point tested above.

## Retained evidence and limits

Final workspace: `C:/Users/teera/AppData/Local/Temp/aiguard-installed-pdf-8dbrww0d`.
The ignored driver and command summaries are under
`.superpowers/sdd/parallel-s-m/m2-pdf/`. The machine record hashes the final
value-free result, driver, command record, redacted outputs and PNGs. Raw
synthetic inputs remain temporary local fixtures and are not committed.

Two harness setup failures are retained: the initial unconditional socket guard
blocked the Windows stdlib internal socketpair before ASGI requests. A diagnostic
captured only caller module/function names; the narrowed internal-pipe exception
then passed. They are harness negatives, not observed product failures. The
earlier successful PDF run remains retained separately from the final run that
also checks the generated CLI launcher.

OCR dependencies/inference, scanned/hybrid accuracy and coordinates, other OS or
Python profiles, external HTTP/browser/Office execution, live providers,
packaged Desktop, independent representative document quality, controlled
performance, organizational/legal review and production acceptance remain open.
No optional capability was installed or silently substituted. M3's performance
hold and unchanged baseline/budgets remain in force.
