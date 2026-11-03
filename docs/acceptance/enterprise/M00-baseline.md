# M0 baseline and adversarial review

Date: 2026-11-02. State: **passed for engineering baseline/reconciliation**.
Rust/CI landing and runtime/organization release gates remain open below.
No production acceptance is claimed.

## Identity and preservation

- Canonical design checkout started at `87c7125`, with the caller's uncommitted
  M0-M12 plan preserved there.
- Existing linked implementation branch started clean at checkpoint `1677e60`.
  Logical commits `4d31d76`, `03b8aa3` and checkpoint evidence remain intact.
- Fetched main is `2480757`; its four missing commits include broker fix
  `8a4aef3`. A local no-commit merge completed without conflicts. No protected
  evaluation corpus was opened, scored, decrypted or rewritten during M0.
- Detailed logs and local runtime data remain under the ignored Stage 1
  execution workspace. Secret-file contents and DSNs were not printed.

## Observed verification

| Check | Observation | Level / limit |
|---|---|---|
| Preserved PostgreSQL | Version 18.6, loopback-only, statement logging disabled; existing data preserved | E2 local synthetic service |
| Original checkpoint governance tests | 44 passed in 9.80 seconds | E2 before integrating main |
| Combined-tree full Python suite | Initial 2,920 passed; final optimized source 2,922 passed, 34 skipped, one existing warning; 89.16 seconds | E1/E2 including all 44 real-database governance tests, no governance skips |
| Ruff lint and format | Passed; 311 Python files already formatted | Static only |
| Version consistency | Passed; product source 0.1.0 | Metadata only |
| Whitespace | `git diff --check` passed after document reconciliation and source optimization | Final source-bound log digest in manifest |
| Rust broker tests | Blocked before tests: `link.exe` unavailable, cargo exit 101 | No Rust test pass is claimed; needs a qualified Windows build environment or CI |
| Keycloak startup diagnosis | Official launcher fails without `OS`; works with process-local `OS=Windows_NT`; real local discovery returned HTTP 200 with the expected issuer | E2 server discovery only; staff application/code flow is still open |

Interpreter: existing separately locked enterprise Python 3.13.12, Authlib
1.9.1 and psycopg 3.3.6. This reuses previously installed project-local tools;
it does not install a global Java/compiler or weaken optional dependency gates.

Exact runtime-file identities, lock digests, interpreter paths, commands and
ignored-output digests are in [the runtime manifest](M00-runtime-manifest.json).
It binds runtime source independently of this document, avoiding a recursive
self-hash. The integration commit preserves both recorded parents. Document-only
edits after the final full test run do not change its runtime fingerprint.

All 44 governance tests executed (authority 10, models 12, registry 13, store 9).
The 34 remaining skips are: numpy 17, cv2 5, transformers 3, sentence-transformers
1, optional ML requirements 4, Unix-only-on-Windows 3 and opt-in live provider 1.
Those skipped features are not accepted. Detailed reasons/log fingerprints are
preserved without copying test/runtime secrets into this record.

## Performance diagnosis and correction

Merging main initially introduced a reproducible restore regression: 0.26 to
0.35 ms in alternating controls. Profiling traced 96.7% of the added cumulative
time to the new unconditional folded-digit normalization called by the restore
audit. A focused test first failed because unchanged text entered the Python
character loop. A C-translation identity check plus space-run boundary check
now avoids that loop only when output/indices cannot change.

The separate adversarial reviewer compared 117,942 in-memory synthetic cases
against main's original normalizer, including all 808 Unicode `isdigit` points,
all removed zero-width marks, folds, spaces/hyphens and mixed seeded strings.
No normalized-text or origin-index mismatch was found. Focused protection tests
passed 151/151 before the final full suite.

Final controls use the same root Python 3.13.12/psutil 7.2.2, three alternating
five-iteration runs, with no baseline change:

| Operation | Unchanged checkpoint control | Final integrated candidate | Relative change |
|---|---:|---:|---:|
| Detect | 5.96 ms | 5.93 ms | -0.50% |
| Sanitize | 15.36 ms | 15.76 ms | +2.60% |
| Restore | 0.26 ms | 0.30 ms | +15.38% |
| PDF | 70.80 ms | 71.33 ms | +0.75% |
| RSS | 151.3 MiB | 151.6 MiB | +0.20% |

Every pair meets the 20% time/15% RSS relative budgets; restore pairs were
+15.38%, +15.38%, +19.23%. All six formal script exits remain 1 because both
arms exceed the old sanitizer anchor. That existing anchor failure is preserved,
not converted into a formal green gate. The measured trade keeps main's folded-
digit recall behavior while reducing redundant unchanged-text work.

## Independent adversarial findings and disposition

Fresh-context read-only reviewer `m0_adversarial_review` inspected the design,
checkpoint, code, CI and operating documents. Parent verified all findings:

1. **CI can skip enterprise:** ordinary locked CI lacks psycopg and the optional
   import can skip the entire suite. This remains explicitly open until M3's
   dedicated real-PostgreSQL job proves mandatory execution and setup failure.
2. **Status/version/Hosted contradictions:** current-source capability register
   now separates 0.1.0 source, archived releases and recorded Hosted deployment.
   No fresh production claim is made from `STATE.md` alone.
3. **Release/workflow contradictions:** operating release instructions and the
   repository workflow skill must agree with the accepted reset, actual
   Windows/macOS matrix and root no-PR delivery loop.
4. **Main integration:** preserve the branch's logical commits and merge the
   missing main changes; rerun evidence on that combined tree, as above.
5. **Unproven gates:** real OIDC/browser, runtime-role/no-DDL and populated-schema
   upgrade, registry wheel and final performance/host checks stay open. Passing
   domain tests with synthetic trusted principals is not staff authentication.

## Independent closure and remaining gates

- Fresh-context M0 recheck verified branch preservation, the version/platform
  matrix, workflow alignment and owner authorization; its final evidence-binding
  finding is addressed by the runtime manifest and exact commands above.
- Independent normalizer adversarial review found no compatibility blocker;
  performance and final full-suite results remain separate observed evidence.
- Recorded Windows Rust setup gap and release-only human inputs in
  [release scope](../../enterprise/release-scope.md).

M0 closes only its engineering baseline/reconciliation scope. It retains
these limitations and cannot declare M3, M9, a pilot or a production release done.
