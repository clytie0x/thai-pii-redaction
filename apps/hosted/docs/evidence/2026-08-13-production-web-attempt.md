# Production Web pipeline #36033

Date: 2026-08-13

Candidate: `0c10f7ed222a7840cc6af8db2fbd455be7f8c53b`

Pipeline #36033 was created from the GitLab UI on protected `main` without
temporary pipeline variables. The `check` and `deploy` jobs passed on the
organizer `team-08` runner. Mandatory acceptance then failed, and its error
trap restored the previous exact release
`72e18bbe723adaf54c847e4b17c2177dfa60dd68`; all three restored services were
reported healthy. Ops jobs did not execute.

The repository-controlled incompatibility was the PDPA report probe transport:
the productionized core root is intentionally read-only, while acceptance still
used `docker cp` to write the tracked probe under `/app`. The same operation was
reproduced against the exact local candidate with Docker's fixed read-only-root
error. The correction streams the tracked probe on stdin to `python -` inside
the container. It does not materialize or retrieve an application credential,
does not make the container writable, and does not alter product behavior.

This record is rollback and CI evidence only. It does not claim that
`0c10f7ed...` passed production acceptance or remained deployed.
