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
  (`payload/.claude/…`, `payload/docs/commands/…`, `payload/.github/…`),
  plus `payload/.harness/settings.base.json`, which every target's
  `.claude/settings.json` is rendered from, and `payload/.harness/render.py`,
  a copy of `harness_sync/render.py` kept identical by a test. Not live here:
  the root is rendered from it (see *The rendered root*).
- `targets/` — each target's draft `.harness/config.json`, kept here until
  the target holds its own.
- `.harness/config.json` — this repository's own sync config; the reason it
  excludes `.github/workflows/comment-gate.yml` is in `IMPORT.md`, *Decided
  after review*.
- `IMPORT.md` — the backend commit the payload was taken from, and which file
  went to the payload and which stayed in backend, with the reason for each.
- `.github/workflows/ci.yml` — the `sync-tool` job, the required check on
  `main`; and `payload-suites`, which applies the payload to a worktree of
  the commit and runs the payload's suites there.

## The rendered root

This repository is its own fourth sync target (spec 5.1, *Self-hosting*), and
its sessions run under the harness it develops.

- **Rendered from `payload/`**: `.claude/**`, `docs/commands/**`,
  `docs/harness-boundaries.md`, the managed files under `.github/` (the gate
  directories, `ISSUE_TEMPLATE/`, and the `closure-gate`, `commit-gate` and
  `harness-drift` workflows), `.harness/render.py`,
  `.harness/settings.base.json` and `.harness/manifest.json`.
  `.harness/config.json` is the one input written by hand.
- **Its own**: `payload/**`, `harness_sync/**`, `measure/**`, `targets/`,
  the rest of `docs/`, `IMPORT.md`, `README.md`, `.github/workflows/ci.yml`
  and `.gitattributes`.
- **Change a harness file under `payload/`**, never at the root. The root copy
  reaches `main` only through a sync pull request (`py -3.12 -m harness_sync
  apply --payload payload --target . --commit <main sha>`), never as a direct
  edit, and the drift gate refuses a root file that differs from the payload
  at the commit the manifest names.
- **Relaunch the session** after a sync merges: hooks, denies and commands are
  read at launch, so a running session keeps the harness it started with.

## Tests

```bash
py -3.12 -m unittest discover -s harness_sync/tests -t .
py -3.12 -m unittest discover -s measure -t .
```

Use `py -3.12`, not `python`: CI pins 3.12 and a local default may be newer.

To run the drift gate against a target, from this repository:

```bash
py -3.12 -m harness_sync check --target <dir>
```

The payload's suites run in a worktree that starts with this repository's own
rendered root and has backend's config applied over it; the
`payload-suites` job in `.github/workflows/ci.yml` is the reference, gate
suites included. Its first steps, locally (Git Bash; `bash`, `grep`, `git`
and `jq` on PATH):

```bash
git worktree remove --force ../rendered 2>/dev/null || true
git worktree add --detach ../rendered HEAD
mkdir -p ../rendered/.harness
cp targets/blueprint-backend.config.json ../rendered/.harness/config.json
py -3.12 -m harness_sync apply --payload payload --target ../rendered --commit "$(git rev-parse HEAD)"
(cd ../rendered && py -3.12 -m unittest discover -s .claude/scripts)
git worktree remove --force ../rendered
```

## Changes

`main` takes changes only through pull requests: deletion, force pushes and
direct pushes are refused, `sync-tool` must pass, and nobody bypasses it.
