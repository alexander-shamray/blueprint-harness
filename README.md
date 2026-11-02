# blueprint-harness

The shared Claude Code harness for the three Blueprint repositories
(`blueprint-backend`, `blueprint-frontend`, `blueprint-admin`): the hooks,
scripts, commands and workflows they have in common live here once, and a sync
tool renders them into each target through an ordinary pull request.

## Layout so far

- `targets.json` — the repositories a sync reaches.
- `harness_sync/` — the sync tool, Python 3.12 standard library only; its
  tests are in `harness_sync/tests/`.
- `.github/workflows/ci.yml` — the `sync-tool` job, the required check on
  `main`.

## Tests

```bash
py -3.12 -m unittest discover -s harness_sync/tests -t .
```

Use `py -3.12`, not `python`: CI pins 3.12 and a local default may be newer.

## Changes

`main` takes changes only through pull requests: deletion, force pushes and
direct pushes are refused, `sync-tool` must pass, and nobody bypasses it.
