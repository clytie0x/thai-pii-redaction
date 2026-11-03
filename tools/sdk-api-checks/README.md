# SDK API collection tooling

This private development profile runs the existing eight synthetic Bruno
requests. It is not a production SDK dependency or a general-purpose sandbox.

```powershell
npm ci --prefix tools/sdk-api-checks --ignore-scripts --no-audit --no-fund
<qualified SDK server-only Python> scripts/run_sdk_api_collection.py `
  --cli tools/sdk-api-checks/node_modules/@usebruno/cli/bin/bru.js `
  --report <fresh ignored summary path>
```

The interpreter must have the frozen SDK server extra and development tools,
including psutil. MCP is deliberately absent from this API profile. The harness
opens an owned loopback server in a fresh private working directory, checks its
listener identity, runs the collection sequentially and stops/reaps the native
process. Only allowlisted counts/statuses are retained; temporary Bruno reports
and synthetic audit files are removed after verified shutdown. Failed cleanup
retains the private runtime workspace and fails the gate.

The collection uses a fake provider. It does not prove live-provider privacy,
current product quality, Docker behavior or production acceptance.

## Dependency review

Primary registry/audit checks on 2 November 2026 identified known advisories in
the old CLI 4.0.0 graph. The current CLI 4.3.0 is pinned with its full lock and
scoped same-major fixes: axios 1.20.0, form-data 4.0.6, js-yaml 4.3.2 and yaml
2.8.3. The actual unchanged collection passed after these fixes.

The resulting npm audit is **not clean**: four high and eight moderate propagated
findings remain, including dependency major migrations. A separate adversarial
review found no Faker templates, CSV, YAML or multipart inputs in the fixed
collection. Do not use this profile to execute untrusted collections or handle
real personal data. The child environment omits operator credential/proxy
variables, but filesystem permissions and home-directory access still apply.
Neither the allowlist nor the audit count establishes zero risk.

Do not force unrelated major overrides or blindly downgrade according to an
automatic audit suggestion. Re-review source compatibility and run the real
collection after a tooling change. Product dependency locks remain separate.
