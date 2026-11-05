# Harness-local: blueprint-harness

What the payload's commands name by role, filled in for this repository.
The four headings are fixed by `docs/harness-boundaries.md`, *Managed
files*; this file is the repository's own and no sync writes it.

## Documents

| Role | Path |
|---|---|
| Change contract | none |
| Style guide | none |
| Testing document | `README.md`, *Tests* |
| Product specification | none |
| Roadmap | none |
| Closed records | none |
| Measurements | none |

This repository's plans and specs live in `blueprint-backend`'s
`docs/superpowers/`, so it keeps no roadmap of its own, and the token
figures behind `docs/harness/token-rules.md` are backend's measurements.

## Ship checks

None. CI runs every check the repository has: `sync-tool` over
`harness_sync/`, `payload-suites` over the payload applied to a worktree,
and the gates the sync renders.

The required checks, which `/ship` step 6's wait holds the list to: `sync-tool`,
`payload-suites (ubuntu-latest)`, `payload-suites (windows-latest)`,
`payload-suites (macos-latest)`, `harness-drift`, `closure-gate`, `commit-gate`
and `rulesets`. There is no change contract, so no `locality-gate`, and step 5
runs no locality read.

## Residuals

None beyond `docs/harness-boundaries.md`'s own.

## Review examples

- A payload line that cites a document, command or section only one target
  has: `harness_sync/tests/test_payload_references.py` names the shapes it
  catches, and a reviewer reads for the ones it cannot, such as a document
  named by its title rather than its path.
- An edit to a rendered root copy rather than to `payload/`, which the drift
  gate refuses only once the pull request reaches CI.
- A suite that reads a tree it constructed instead of the payload or the
  rendered root, so it passes whatever the shipped files say.
