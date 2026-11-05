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
  (`payload/.claude/…`, `payload/docs/commands/…`, `payload/docs/harness/…`,
  `payload/.github/…`),
  plus `payload/.harness/settings.base.json`, which every target's
  `.claude/settings.json` is rendered from, and `payload/.harness/render.py`,
  a copy of `harness_sync/render.py` kept identical by a test, and
  `payload/.harness/agent-rules.md`, the working rules each target's
  `CLAUDE.md` is to import (this repository's root `CLAUDE.md` does; backend's
  gains the line in plan 2), whose always-loaded bytes
  `harness_sync/tests/test_always_loaded.py` holds to a budget. Not live here:
  the root is rendered from it (see *The rendered root*).
- `targets/` — each target's draft `.harness/config.json`, kept here until
  the target holds its own.
- `.harness/config.json` — this repository's own sync config; the reason it
  excludes `.github/workflows/comment-gate.yml` is in `IMPORT.md`, *Decided
  after review*.
- `IMPORT.md` — the backend commit the payload was taken from, and which file
  went to the payload and which stayed in backend, with the reason for each.
- `.github/workflows/ci.yml` — the `sync-tool` job; and `payload-suites`,
  which applies the payload to a worktree of the commit and runs the
  payload's suites there. Both are required on `main` (*Changes*).
- `.github/workflows/sync.yml` — the sync pull request a merge to `main` opens
  in each target (*The sync workflow*).

## The rendered root

This repository is its own fourth sync target (spec 5.1, *Self-hosting*), and
its sessions run under the harness it develops.

- **Rendered from `payload/`**: `.claude/**`, `docs/commands/**`,
  `docs/harness/**`, `docs/harness-boundaries.md`, the managed files under `.github/` (the gate
  directories, `ISSUE_TEMPLATE/`, and the `closure-gate`, `commit-gate` and
  `harness-drift` workflows), `.harness/render.py`,
  `.harness/settings.base.json`, `.harness/agent-rules.md` and
  `.harness/manifest.json`.
  `.harness/config.json` is the one input written by hand.
- **Its own**: `payload/**`, `harness_sync/**`, `measure/**`, `targets/`, the
  rest of `docs/`, `CLAUDE.md`, `IMPORT.md`, `README.md`,
  `.github/workflows/ci.yml`, `.github/workflows/sync.yml`, `.gitattributes` and
  `.gitignore`.
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

Two things the jobs do not cover or cannot promise:

- **Four gates have no suite to run here.** `comment-gate`, `issue-form-gate`,
  `output-gate` and `plan-size-gate` ship only their script and README: their
  suites (`test_comment_gate.py` and its three siblings) are `local` to
  blueprint-backend in `targets/blueprint-backend.config.json`, so neither this
  repository's root workflows nor `payload-suites` runs a test for them, and
  the drift gate only keeps the root copies equal to the payload's. A suite
  added to the payload under one of those names is not rendered into the
  `payload-suites` tree until this repository's own sync writes it to the root;
  from then a pull request that changes it is red on `payload-suites`, as the
  root copy cannot change in the same pull request, and a sync to backend also
  refuses while backend's copy differs. Use another name, or drop the config
  entry first. Any other `test_*.py` under a payload gate directory runs from
  its first pull request, as the *Test the gates* step reads the rendered
  tree.
- **`payload-suites (macos-latest)` can sit in the runner queue.** Its
  `timeout-minutes` bounds the run, not the wait for a runner, so a leg that
  GitHub cancels from the queue with no step run (seen on #11 and #15) is a
  runner shortage, not a failure of the change. Rerun the run's failed
  jobs (`gh run rerun <run id> --failed`); the check is required, so the pull
  request waits for it.

## The sync workflow

`.github/workflows/sync.yml` runs on every push to `main` that touches
`payload/**` or `harness_sync/**`, and on dispatch from `main`. For each
repository in `targets.json`, this one included, it checks the target out and
runs `python -m harness_sync open-pr`. That applies the payload at `main`'s
tip as the run starts, not the commit that triggered it, so a queued or rerun
old run cannot sync an older payload. It opens one pull request,
`chore/harness-sync-<short sha>`, in the house form with a `PR: #<n>` trailer
on its commit. Any older sync pull request still open there is closed with a
comment naming the new one, and its branch deleted. A rerun for the same
commit finds its own pull request and opens no second one. A commit older than
the target's manifest, or than a sync already open, is refused.

It needs `HARNESS_SYNC_TOKEN`: a fine-grained token with Contents, Pull
requests and Workflows read-write on every repository in `targets.json`, this
one included (four once frontend and admin are listed). Workflows, because the
payload ships `.github/workflows/` files and GitHub refuses a push that
changes one without it. The workflow's own `GITHUB_TOKEN` cannot stand in,
because a pull request it opens starts none of the target's required checks.
Until the secret is set, each target is skipped with a notice and the run
stays green.

The token is a secret of the `harness-sync` environment, never of the
repository. The first `sync.yml` run on `main` creates a missing environment
with no branch rule, so the owner creates it first, restricted to `main`, and
only then stores the secret:

```bash
gh api -X PUT repos/alexander-shamray/blueprint-harness/environments/harness-sync \
  --input - <<< '{"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}'
gh api -X POST repos/alexander-shamray/blueprint-harness/environments/harness-sync/deployment-branch-policies \
  -f name=main -f type=branch
gh secret set HARNESS_SYNC_TOKEN --env harness-sync --repo alexander-shamray/blueprint-harness
```

**Why an environment.** A `pull_request` run from a branch of this
repository gets the repository's secrets and runs that branch's workflow
files. So a branch that edits `ci.yml` or `sync.yml` could use a repository
secret, or print it. An environment secret reaches only a job that names the
environment. `harness-sync` deploys from `main` alone, so only workflow code
already on `main` gets the token, and only the `sync` job names it.

Inside that job the token is not kept after the checkout that uses it.
Both checkouts set `persist-credentials: false`, so `target/.git/config` holds
no credential while `setup-python` and later steps run. The step that runs
open-pr hands git the authorisation header through `GIT_CONFIG_*` variables in
its own environment, for the target's `ls-remote`, fetch and pushes, and masks
the header's base64 form.

A target is **current** when applying the payload writes and deletes no
managed path: only the manifest's commit would move, so no pull request is
opened, the target keeps the commit its manifest names, and any sync pull
request still open there is closed as stale. A target with no
`.harness/config.json` is not onboarded yet and is skipped the same way.

A target's own `.gitignore` must ignore `.claude/worktrees/`: `/branch` and
`/dispatch` fork worktrees there, and `git-worktree-fork.sh` refuses a path
git would see as untracked. This repository carries the line; a sibling adds
it before its first sync.

A sibling also lands its closure gate before its first sync. The payload's
`closure-gate.yml` takes the enforcing gate from the pull request's *base*
commit and refuses a fallback to the head copy, so the pull request that first
brings `.github/closure-gate/closure_gate.py` into a repository whose `main`
lacks it is red. Confirm the sibling's `main` already has that file, or land it
there in a pull request of its own, before making `closure-gate` required; the
alternative is the owner merging that first sync with the check red, as #11 was
for this repository's first target.

## Changes

`main` takes changes only through pull requests: deletion, force pushes and
direct pushes are refused, and nobody bypasses it. Seven checks must pass:
`sync-tool` and `payload-suites` on its three runners (`ubuntu-latest`,
`windows-latest`, `macos-latest`) from `ci.yml`, and `commit-gate`,
`closure-gate` and `harness-drift` from the workflows the root renders.

`rulesets/main.json` owns the seven required checks, and the floor every
repository's `main` ruleset meets: the rules, no bypass and no approval
required. `py -3.12 -m harness_sync ruleset-check [--effective] [<repo>...]`
reads each live ruleset and exits 1 with a line per difference, and
`ruleset-apply <repo>` applies the data to one repository and then runs the
check. `--effective` reads the rules in force on `main`, which any token can
read, and compares rules and checks only; without it the ruleset is read whole,
bypass actors included, which needs admin. Both exit 2 when they refuse: a
repository outside the data, data below the floor, or two rulesets with a name
in the data.

`rulesets.yml` runs `ruleset-check --effective` on every pull request, on
pushes to `main` and daily. A branch that changes `rulesets/main.json` is red
until the change is live, so its order is: the `/ship` loop ends with no open
finding, `ruleset-apply <repo>` runs from the branch, the `rulesets` job is
rerun, and the pull request merges. The floor refusal is what stops an unmerged
branch from taking `main` below the floor: data without a floor rule or with no
required check is refused before anything is applied. A dropped or renamed
required check is caught only by the review loop that precedes the apply. A scheduled run that is red, a ruleset changed by hand, files a
`harness`, `high` issue with the differences, or comments on the open one.
