# M0 branch CI infrastructure blocker

Date: 2026-11-02. Source commit: `9711d795130c1fb81aae05f93ab2d185a014573d`.

The feature branch was pushed without rewriting checkpoint or main history.
The CI run [41343629141](https://github.com/clytie0x/thai-pii-redaction/actions/runs/41343629141)
and cross-platform run
[41343629134](https://github.com/clytie0x/thai-pii-redaction/actions/runs/41343629134)
failed before their jobs started. Their jobs have no executed steps.

GitHub check annotations for both runs state that recent account payments
failed or the spending limit must be increased and direct the account owner to
Billing & plans. This is an infrastructure/account gate, not a test failure or
proof that the pushed source passes hosted CI.

Owner action: resolve the GitHub Actions account/billing restriction, then rerun
the exact branch candidate and inspect every required job. No payment, account
permission change, workflow bypass or main promotion was performed by the agent.

Continue independent local engineering. Do not squash/promote this branch while
required CI remains unexecuted. Local Windows Rust also remains blocked by the
missing MSVC linker, so runner evidence is especially necessary before landing.

## M3 exact-candidate recheck

The later staff application checkpoint `a5b6f6423dff63c80248d471d80d868373f2153b`
was pushed under the same feature-branch workflow. Its
[CI run 41357959936](https://github.com/clytie0x/thai-pii-redaction/actions/runs/41357959936)
has 16 failed jobs with zero executed steps, including the new mandatory
enterprise/PostgreSQL job. Its
[cross-platform run 41357959927](https://github.com/clytie0x/thai-pii-redaction/actions/runs/41357959927)
has one failed job with zero steps. Both sampled check annotations repeat the
same account-payment/spending-limit reason. This is fresh evidence of an
unexecuted infrastructure gate, not 17 observed source/test failures. Main was
not changed; every job still needs a real successful rerun on the exact candidate.

## M1 CI preparation and requested visibility change

Checkpoint `55b48da7a1878b01c350d42be1dca94add2ac3c4` declares 26 jobs across
[Imported checks](https://github.com/clytie0x/thai-pii-redaction/actions/runs/41386314317)
(9), [CI](https://github.com/clytie0x/thai-pii-redaction/actions/runs/41386314333)
(16) and [cross-platform smoke](https://github.com/clytie0x/thai-pii-redaction/actions/runs/41386314419)
(1). All completed as failures with zero executed steps. Sampled annotations in
all three repeat the billing/payment/spending-limit reason.

The owner subsequently authorized making this product repository public to
enable standard public runners. Preflight found two committed private screenshots
in the imported Hosted attachment directory, including a private conversation;
they are also present in remote history. The owner then explicitly authorized a
private backup, removal of only those screenshots from all branches/tags and a
force-push before changing visibility. The isolated mirror passed independent
full-history review, then an atomic push with explicit old-SHA leases updated
all 19 branches and one tag. Every writable remote ref was checked afterward.
The first push failed with HTTP 408 without ref changes; its log was retained
and the bounded second attempt succeeded.

The repository is still private. Authenticated Git Blobs API requests after the
rewrite still returned both old image objects. GitHub's read-only PR refs/cached
views need a server-side purge before public visibility. A private Support request
is prepared for the owner; none was sent. See the
[cleanup record](M00-public-visibility.md) and [manifest](M00-public-cleanup-manifest.json).
The YRSS documentation repository remains private.

A verified private mirror and bundle preserve all original refs and signed
objects. The full mirror includes 681 commits with PR refs, compared with the
initial 615-commit branch/tag-only scan. Both redacted Gitleaks 8.30.1 scans
reported the same 43 generic-key matches: 42 source/evidence hashes and one
documentation sentence. No credential finding was confirmed by those scans.
This does not certify binary artifacts, hidden credentials or private-image
publication safety.
