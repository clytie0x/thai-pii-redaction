# AI Guard AIFT Agent Instructions

Read `README.md` and `STATE.md` before changing product claims, deployment, API,
privacy, or production-web behavior.

For landing-page and brand work, read and continuously update
`docs/production-web-redesign.md`. That document is the durable source of truth
for scope, decisions, open issues, and verification evidence. Do not create a
second competing redesign brief.

The files `web/home-concept-c.html` and `web/logo-preview.html` are design
prototypes. They are not deployed by `web/Dockerfile` and must not be described
as production. The current SVG marks under `web/assets/` are rejected work in
progress, retained only to preserve the latest exploration.

Concept C applies to this hosted public-web redesign. Do not silently impose it
on the sibling Desktop, Extension, or Office surfaces. Use only synthetic data
in prototypes, tests, screenshots, and review artifacts.

Production static assets require the full serving path:

1. Copy the asset explicitly in `web/Dockerfile`.
2. Add an exact allowlisted route in `web/nginx.conf`.
3. Keep the CSP and privacy constraints intact.
4. Update relevant tests and production acceptance checks.
5. Verify the built image and the public caller-facing path, not only the source
   file or a local ad hoc server.

For every nontrivial UI deliverable, run real-browser checks at the viewports
listed in `docs/production-web-redesign.md`, including keyboard, reduced motion,
and responsive behavior. Then request independent adversarial reviews for art
direction, frontend/product integrity, and UX/accessibility. Verify their claims,
fix material blockers, and repeat until there is no material disagreement.
