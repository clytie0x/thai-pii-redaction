# M1 installed receipt packaging follow-up

Observed 2026-11-03. The [machine record](M01-receipt-artifacts.json) and
[255 input hashes](M01-receipt-artifact-inputs.json) bind the receipt-only follow-up
to held governance checkpoint `2dec40d`. Its checkout binding is
`c200a85dac93be8d28f6b8956b294405a760d759108b007e13b950ec7e5a8f12`.
Compared with the [V2 pair](M01-integrated-artifacts.md), only `receipt.py` and
`receipt_pdf.py` change among those inputs. Product version remains 0.1.0.

Installed receipts now read the package's own hashed VERSION resource, ahead of
an unrelated parent directory's VERSION. Frozen builds keep their first-choice
resource and source checkouts keep their existing fallback. Missing resources
remain explicitly unknown. The PDF names the existing installed Python API and
labels the root CLI as source-checkout only. It does not introduce an installed CLI.

| Check | Observed result |
| --- | --- |
| Receipt source tests | 43 passed, no skips; installed resource, ambient conflict and PDF guidance regressions observed RED then GREEN |
| Complete root core+web profile | 3,356 passed, 80 explicit optional/platform/live skips, one warning; 184 source hashes unchanged |
| Core/SDK direct wheels, sdists and rebuilt wheels | Six artifacts; direct/rebuilt wheels equal every compressed byte |
| Three fresh Python 3.13.12 profiles | Checker, installed identity and public runtime pass; receipt version 0.1.0 checked in every profile |
| Installed adapter tests | 214 passed without skips/errors/failures |
| Artifact negatives | Six checker rejections and 20 identity/cache rejections |
| Python 3.11.15/3.12.12 | Actual installed identity/cache-format proof only; full dependency/model profiles remain unqualified here |

The independent source review and exact-artifact/evidence review are CLEAR.
The latter verified all 255 inputs, six artifacts, 66 command/log records,
installed bytes/origins, exact archive allowlists and preserved earlier evidence.
It did not rerun tests. The [current installed PDF proof](M02-receipt-installed-pdf.md)
separately verifies receipt version, recomputation, rendering and guidance.

The workspace is `C:/Users/teera/AppData/Local/Temp/aiguard-receipt-v3-f_fyedoc`.
Manifest SHA256 is `051e5dcf6b341b7ae19b7380cad39b8a9a7dcea81ea8e1fbad8242654b1ca82a`.
One aggregator failure remains retained: a copied driver expected an explicit
archive-audit record that had been generated separately in V2. The parent ran
and saved the exact allowlist/metadata audit, then reused verified completed
commands in a new final record. No product, artifact or test was changed or
rebuilt for that harness correction. Its original partial records remain intact.

Old b4/batch1/V1/V2 evidence remains unchanged. Git attributes preserve exact
JSON evidence bytes; the earlier newline-only index mismatch and corrected
index hashes are retained separately. Dependency/model caches were reused
without public-index fallback or new versions.

This is bounded Windows installed qualification. It provides no exact-source
CI/image, actual host/provider/Office/OCR, custody, legal or pilot acceptance.
The local checkpoint performance gate remains HELD against the unchanged
baseline; the existing controlled-environment M3 hold is not waived.
