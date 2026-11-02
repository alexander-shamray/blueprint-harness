# blueprint-harness

The shared Claude Code harness for the three Blueprint repositories
(`blueprint-backend`, `blueprint-frontend`, `blueprint-admin`): the hooks,
scripts, commands and workflows they have in common live here once, and a sync
tool renders them into each target through an ordinary pull request.

## Layout so far

- `targets.json` — the repositories a sync reaches.
- `harness_sync/` — the sync tool, Python 3.12 standard library only; its
  tests are in `harness_sync/tests/`.
- `measure/` — the stop counter (`stops.py`) and its tests; `docs/` holds the
  November baseline it produced.
- `payload/` — the managed files, laid out as a target repository is
  (`payload/.claude/…`, `payload/docs/commands/…`, `payload/.github/…`), plus
  `payload/.harness/settings.base.json`, which every target's
  `.claude/settings.json` is rendered from, and `payload/.harness/render.py`,
  a copy of `harness_sync/render.py` kept identical by a test. Not live here:
  this repository's own sessions do not run under it.
- `targets/` — each target's draft `.harness/config.json`, kept here until
  the target holds its own.
- `IMPORT.md` — the backend commit the payload was taken from, and which file
  went to the payload and which stayed in backend, with the reason for each.
- `.github/workflows/ci.yml` — the `sync-tool` job, the required check on
  `main`; and `payload-suites`, which applies the payload to a worktree of
  the commit and runs the payload's suites there.

## Tests

```bash
py -3.12 -m unittest discover -s harness_sync/tests -t .
py -3.12 -m unittest discover -s measure -t .
```

Use `py -3.12`, not `python`: CI pins 3.12 and a local default may be newer.

The payload's suites run as the `payload-suites` job runs them, in a worktree
with the payload applied (Git Bash; `bash`, `grep`, `git` and `jq` on PATH):

```bash
git worktree add --detach ../rendered HEAD
mkdir -p ../rendered/.harness
cp targets/blueprint-backend.config.json ../rendered/.harness/config.json
py -3.12 -m harness_sync apply --payload payload --target ../rendered --commit "$(git rev-parse HEAD)"
(cd ../rendered && py -3.12 -m unittest discover -s .claude/scripts)
```

## Changes

`main` takes changes only through pull requests: deletion, force pushes and
direct pushes are refused, `sync-tool` must pass, and nobody bypasses it.
