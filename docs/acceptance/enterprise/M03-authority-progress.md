# M3 staff application evidence and remaining gates

Date: 2026-11-02. State: **locally functional; acceptance held**.
M0 source baseline is `9711d79`. The subsequent source, test, dependency and
artifact fingerprints are in [the M3 manifest](M03-runtime-manifest.json).
This is Stage 1 inventory/authority evidence, not consent, execution, production
TLS, deployed service or a completed M0-M12 program.

## Completed component checks

### Signed identity

`app/enterprise/identity.py` uses installed Authlib 1.9.1 and joserfc 1.7.7.
joserfc was already a hash-locked transitive dependency and is now declared
directly; the enterprise lock was regenerated offline without version upgrades.

- Explicit fixed RS256 algorithms and configured JWKS, issuer and audience.
- Mandatory expected nonce, authorized-party rules and valid issue/expiry dates.
- `max_token_age` bounds `iat` age. It is not an OIDC `auth_time`/reauthentication
  or MFA policy; production identity requirements remain separately reviewed.
- A present `at_hash` cannot bypass verification by omitting the access token.
- Only issuer/subject become a trusted domain identity. Browser/token role,
  display-name and email claims do not grant authority.
- Invalid provider input produces a constant error outside the underlying
  exception context. No ID/access token or provider body is logged.

Thirty-two signed synthetic identity cases pass. The independent reviewer
verified wrong algorithms, attacker key/URL headers, wrong keys and malformed
JWKS. Its NumericDate overflow finding was reproduced as three failing tests,
then normalized to the constant error and all cases passed. The complete
application subsequently exchanged actual synthetic Keycloak codes and validated
the signed tokens, as recorded below.

### Persistent login attempts and sessions

`003_staff_sessions.sql` adds browser-bound, expiring, single-use login state and
hash-only staff cookies/CSRF records. `StaffPrincipal` is a backend-only type;
the session ID is not itself the bearer cookie and must never be projected to
the browser as a mutation authority. Domain permissions recheck its session and
membership revision inside each actual domain transaction.

- A wrong browser binding cannot consume another attempt; concurrent callbacks
  have one successful consumer.
- Sessions require an enabled pre-enrolled issuer/subject. Login does not create
  membership or adopt token roles.
- Revocation and membership revision changes invalidate existing cookies and
  already resolved principals before a subsequent domain action.
- CSRF must match the stored hash. Repeated logout has one audit outcome.
- Required audit failure rolls back session publication.
- The chosen expiry invariant rejects renewal after the idle or absolute
  deadline at the locked renewal point. An in-flight request may need to log in
  again rather than resurrect expired authority.

The independent session reviewer reproduced a wait-on-read-lock race that
previously renewed an expired session. Parent wrote idle/absolute deadline tests
and observed both fail, then locked the session row and rechecked deadlines in
the renewal update before returning a principal. The corrected focused run
passed **91 tests** at that component checkpoint: 32 identity, 15 real-PostgreSQL
session and 44 existing governance cases. The later whole-stage review found
the same class of expiry race in domain authorization. Idle/absolute deadline
tests both failed before the fix; permissions now recheck the database clock
after acquiring the session lock. All 17 current session tests execute against
actual PostgreSQL. No earlier successful resolve can outlive that domain check.

These sessions are separate from local redaction-vault sessions. They do not
store reversible mappings, provider credentials or JWTs. PKCE nonce/verifier
state is short-lived backend data. The actual application and installed-wheel
checks below use a restricted runtime role; the migration test fixtures require
their own disposable administrative account. Production storage, retention and
key policy remain later acceptance gates.

## Complete caller path and observed local evidence

The operator guide is [enterprise/README.md](../../enterprise/README.md).
Offline `migrate` and one-time `enroll` commands are distinct from `serve` and
`check`. Startup/readiness never executes privileged DDL. The browser uses the
shared governance commands through `/api/enterprise/v1/`; it cannot declare
its own identity, issuer, roles or authoritative department scope.

The OIDC transport binds discovery, authorization, token and JWKS endpoints to
the configured issuer origin, limits decoded bodies to 64 KiB, disallows
compression/redirects and applies transport/total timeouts. Browser mutations
require the current hash-only session, matching CSRF and exact origin. Host
authority includes IPv6/port checks. Production cookies use `__Host-`, Secure,
HttpOnly for the session and Strict SameSite; loopback development is explicitly
separate. Authentication callback query values are not written to access logs.

The scoped Thai console implements drafts, notices, independent reviews,
membership proposals/approvals, suspension and minimized audit. It handles
pending, empty, error, conflict and expiry states without browser storage.
Forms bind to the selected record/revision. Principal changes clear previous
data, outstanding requests and drafts. UI tests cover cross-tab replacement,
late selection responses, revisions, categories and explicit enable/suspend
effects in confirmation.

| Evidence | Observed result | Boundary |
| --- | --- | --- |
| Full Python gate | 3,035 passed, 34 skipped, 2 warnings | Current source; optional dependency/host/live exclusions below |
| Mandatory enterprise gate | 156 passed, no skips, 13 required files | Actual PostgreSQL 18.6, Authlib and enterprise dependencies; missing setup fails the gate |
| Root JavaScript | 178 passed across 21 files, including 15 enterprise UI cases | Vitest; explicit enterprise discovery |
| Static/version/whitespace | Ruff clean; 331 files formatted; source version 0.1.0 matches; diff clean | No version bump or release created |
| Real IdP/API | Three synthetic staff code/PKCE logins, replay denial, inventory/notice/independent review, scope denial and logout | Actual Keycloak 26.8.1 and PostgreSQL, restricted runtime role, in-process ASGI caller |
| Actual Chrome | 12 workflow checks passed, browser 156.0.8078.80; all owned contexts closed | Real application, Keycloak and PostgreSQL on synthetic loopback development HTTP |
| Desktop/mobile | 1440 px and 390 px; font load, keyboard entry, no overflow/browser storage; screenshots visually inspected | Synthetic console; not a full assistive-technology certification |
| Real restart | Graceful owned PostgreSQL and app restart preserved the real staff cookie and exact activity IDs/revisions/states; consumed callback still denied; logout still revokes | Durable local state; not crash/backup restoration or production identity acceptance |
| Migration safety | Populated schema 2 to 3 preserves authority/audit; simultaneous migrators publish one complete schema; failed upgrade rolls back new DDL and preserves existing data | Actual disposable PostgreSQL schemas |
| Wheel | Pinned setuptools 83.0.0 build; resource validator and fresh isolated `-I` installed imports/readiness/HTML/JS/font checks passed | Imported outside source under restricted database role; not a published distribution |

Chrome also demonstrated that an unapproved IdP identity cannot self-enroll,
a distinct reviewer must approve enrollment/reactivation, suspension clears
visible staff state, and reactivation does not resurrect the old session.
Production cookie flags have a separate explicit test; development HTTP is not
evidence that a real TLS reverse proxy is configured correctly.

The 34 full-suite skips are: numpy 17, cv2 5, transformers 3,
sentence-transformers 1, optional ML-profile cases 4, Unix-only cases 3 and live
Tokenmind 1. The two warnings concern upstream HTTPX integration deprecation;
they are not silently removed. No paid/live-provider request was made.

## Independent adversarial reviews and verified fixes

Fresh separate-context reviewers checked identity, sessions, OIDC/API, UI and
the whole Stage 1 change. Their findings were verified against the code before
fixing. Material findings included NumericDate overflow; renewal/domain reads
after lock waits; callback log/IPv6 handling; stale principal data; form/record
binding; invisible category/enabled-state information; and readiness accepting
a corrupt audit chain. Each behavior fix has an observed failing regression
before the correction and a passing focused run afterward.

The final whole-stage review's audit-corruption probe returned ready/200 before
the fix. `Store.check_ready()` now verifies the existing local audit chain, and
the API returns a fixed failure/503 on corruption. This does not establish
independent, externally checkpointed audit integrity, which remains M10.
The independent UI recheck ran all 15 UI cases and found no further material
issue in its bounded source/local-synthetic scope. Reviews do not replace CI or
production acceptance.

## Performance evidence: hold, not a pass

The baseline remains unchanged. Three alternating five-iteration control/M3
pairs had aggregate median changes: detect +1.658%, sanitize +3.422%, restore
0%, PDF -2.145%, RSS -0.982%. However, the original third pair measured detect
**6.03 to 15.72 ms (+160.697%)** and sanitize **15.87 to 19.67 ms (+23.945%)**.
Those exceed the 20% time budget and are retained in the evidence.

A single bounded diagnosis compared 35 actually loaded core module hashes,
sample text/PDF, performance script, baseline and CRF model bytes: all matched
between arms, with no cross-arm source import. Three additional instrumented
pairs stayed within the relative time/RSS budgets. Some slow PDF samples also
consumed extra process cycles, and Windows CPU clocks were quantized at
15.625 ms. The original outlier had no CPU telemetry. These observations rule
out loaded-source/model drift but do not identify its cause; no blanket
scheduler explanation or rerun-until-green claim is justified.

All formal runs exit 1 against the pre-existing sanitizer anchor in
`perf/baseline.json`; both the control and candidate exceed that old anchor.
No performance baseline was moved. On 2 November the owner explicitly chose to
**keep M3 held until a controlled-environment measurement**. No timing exception
was granted. A branch checkpoint is not performance acceptance or main promotion.

## Open gates

Update 2026-11-03: [the new exact-main comparison](M03-controlled-performance.md)
passes all five controlled-process relative pairs, with an independent review
clearing the narrow incremental-performance disposition. The historical outlier
and absolute-anchor failures above are unchanged; they are not relabelled passes.
This does not accept M3 as a whole or an exclusive/production host.

- Main integration still needs its reviewed exact tree and complete CI. The
  earlier billing restriction is historical, retained in
  [the CI blocker](M00-ci-blocker.md); `40cf18e` now executes and passes all 26
  jobs without a payment/workflow bypass.
- Local Windows Rust execution remains unavailable; actual cross-platform Rust
  and packaged Windows/macOS CI on `40cf18e` pass. Local Python/JS is not used
  as native proof.
- Actual production issuer policy/MFA, TLS, encrypted storage, independent audit
  checkpoints, backup recovery and named human pilot remain their later gates.
- No release, deployment, real-data operation, public publication or main merge
  is accepted by this record.

Primary implementation references checked against installed/tagged source:
[Authlib OAuth2 client](https://github.com/authlib/authlib/blob/v1.9.1/authlib/oauth2/client.py),
[OIDC claims](https://github.com/authlib/authlib/blob/v1.9.1/authlib/oidc/core/claims.py),
[HTTPX integration](https://github.com/authlib/authlib/blob/v1.9.1/authlib/integrations/httpx_client/oauth2_client.py)
and [joserfc JWT](https://github.com/authlib/joserfc/blob/1.7.7/src/joserfc/jwt.py).
Library state helpers do not replace the application-owned browser binding,
transactional single use, TTL or current membership checks.
