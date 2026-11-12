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
- `.harness/config.json` — this repository's own sync config.
- `IMPORT.md` — the backend commit the payload was taken from, and which file
  went to the payload and which stayed in backend, with the reason for each.
- `.github/workflows/ci.yml` — the `sync-tool` job; and `payload-suites`,
  which applies the payload to a worktree of the commit and runs the
  payload's suites there. Both are required on `main` (*Changes*). Each of
  its three legs runs the whole `.claude/scripts` suite; the gates run on
  Linux, and Windows adds the comment gate's suite for its fixture. A pull
  request that reaches nothing the windows and macos legs test skips their
  test steps and still reports the check; `harness_sync/legs.py` owns what
  reaches them. On a push to `main` that does not pass, its `main-red` job
  files `main is red: ci`, the issue `/ship` step 6 stops on.
  A red push run of `rulesets.yml`, or a red `sync.yml` run, files none, on
  purpose: that issue stops every landing and opens by asking for a revert,
  which does not answer a ruleset changed by hand or a failure on a target's
  side. A live
  ruleset that differs turns every pull request's required `rulesets` check red
  anyway, and its scheduled run files an issue of its own; a red sync leaves the
  targets behind until a rerun or the next scheduled run, which stopping
  landings would not bring nearer, and it too files one of its own (*The sync
  workflow*). A defect in `harness_sync` that turns either
  red is seen in that run and is reverted as any other. A `ci.yml` GitHub cannot
  start reports no required check, so its pull request cannot land.
- `.github/workflows/sync.yml` — the sync pull request `main`'s payload opens
  in each target, every four hours or on dispatch (*The sync workflow*).

## The rendered root

This repository is its own fourth sync target (spec 5.1, *Self-hosting*), and
its sessions run under the harness it develops.

- **Rendered from `payload/`**: `.claude/**`, `docs/commands/**`,
  `docs/harness/**`, `docs/harness-boundaries.md`, the managed files under `.github/` (the gate
  directories but `output-gate`, a .NET gate `.harness/config.json` excludes
  here, `ISSUE_TEMPLATE/`, and `gates.yml`, the one workflow running the
  closure, comment, commit and drift gates), `.harness/render.py`,
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

To run the comment gate over a branch, which it reads as committed:

```bash
py -3.12 .github/comment-gate/comment_gate.py --base origin/main --head HEAD
```

The payload's suites run in a tree that starts with this repository's own
rendered root and has backend's config applied over it; the
`payload-suites` job in `.github/workflows/ci.yml` is the reference, gate
suites included, and applies the payload to a worktree of the commit. Its
first steps, locally (Git Bash; `bash`, `grep`, `git` and `jq` on PATH), take
a scratch clone instead, because the settings deny `git worktree remove`,
whose `-f` discards work, and a clone needs none to clear away. The clone
goes under the temp root, which the git argv guard exempts: beside this
checkout, a literal `../rendered/.harness/config.json` is a copy it refuses
under the `.harness/**` Edit deny.

```bash
rendered="$(mktemp -d)"
git clone --quiet . "$rendered"
mkdir -p "$rendered/.harness"
cp targets/blueprint-backend.config.json "$rendered/.harness/config.json"
py -3.12 -m harness_sync apply --payload payload --target "$rendered" --commit "$(git rev-parse HEAD)"
(cd "$rendered" && py -3.12 -m unittest discover -s .claude/scripts)
rm -rf "$rendered"
```

The job's three legs run that suite through
`.claude/scripts/shard-harness-suite.py` instead, which a local run can too;
its `--selective` runs only the classes the branch reaches, and each leg uploads
the times its run recorded as the `harness-timings-<os>` artefact, which
`harness_timings.py report` reads (`docs/harness-boundaries.md`, *The suite's
shard runner*).

Two things the jobs do not cover or cannot promise:

- **A case that reads one target's own tree is that target's.** The payload's
  suites hold what any target runs; a case that reads a file only backend has
  (its solution, its class map, a backend-local command) is in a
  backend-local sibling, `test_<module>_backend.py`, listed under `local` in
  `targets/blueprint-backend.config.json`, so `payload-suites` never renders
  it. A payload suite that read such a file would be red here, or pass
  vacuously; build the fixture in the case instead (`IMPORT.md`, *Decided
  after review*). Where a payload case has to know a target's own commands —
  the ones its *Ship checks* chain before a push, and its split commands'
  runbook ceilings — the target names them in `CHAINED_BEFORE_A_PUSH` and
  `CEILINGS` in `.claude/scripts/local_commands.py`, also under `local`, and
  the payload's cases read them through `review_helpers.py`'s `LOCAL`; a
  target with none keeps no such file. Every `test_*.py` under a payload gate
  directory runs from its first pull request, as the *Test the gates* step
  reads the rendered tree.
- **`payload-suites (macos-latest)` can sit in the runner queue.** Its
  `timeout-minutes` bounds the run, not the wait for a runner, so a leg that
  GitHub cancels from the queue with no step run (seen on #11 and #15) is a
  runner shortage, not a failure of the change. Rerun the run's failed
  jobs (`gh run rerun <run id> --failed`); the check is required, so the pull
  request waits for it.

## The sync workflow

`.github/workflows/sync.yml` runs every four hours, at 17 minutes past, and on
dispatch from `main`; dispatch it by hand for an urgent sync, such as a fix to
a red target. For each repository in `targets.json`, this one included, it
checks the target out and runs `python -m harness_sync open-pr`. That applies
the payload at `main`'s tip as the run starts, so a queued or rerun old run
cannot sync an older payload. It opens one pull request,
`chore/harness-sync-<short sha>`, in the house form with a `PR: #<n>` trailer
on its commit. Any older sync pull request still open there is closed with a
comment naming the new one, and its branch deleted. A rerun for the same
commit finds its own pull request and opens no second one. A commit older than
the target's manifest, or than a sync already open, is refused.

A run opens nothing where it has nothing new. A target the payload leaves
current gets no pull request, and any open sync there is closed as stale. An
open sync for an older commit on `main` whose manifest maps every managed file
to the hash this run renders already carries this run's change, so it stays
open and nothing else opens. The rendered tree is the test, not the payload's
commit, so a change to the target's own `.harness/config.json` still opens a
sync. A payload change merged after the open sync's commit is synced by the
next scheduled run, normally no more than four hours on: GitHub may delay or
drop a scheduled run under load, and a red run syncs nothing until it is
rerun.

**Why a schedule, not every merge.** Spec 5.3 first had the trigger as the
builder's call, automatic on merge. On 2026-11-09 that opened 29 syncs in
blueprint-backend and closed 27 of them unmerged, each after a full CI run in
its target, and two `/dispatch` executors were paid for syncs superseded
before they merged (#380). The owner approved changing the trigger on
2026-11-10, and the spec is left as written; this section is the record. Of
the three options #380 weighs, the schedule was taken:

- **Taken: a schedule plus dispatch.** At most six scheduled syncs a day per
  target, plus any dispatched; a payload change normally reaches a sync within
  four hours, and an urgent sync is one dispatch away.
- **Rejected: a debounce on push.** A run started by a merge always sees that
  merge as the newest payload commit, so it can only defer, never open, unless
  it holds a runner through the quiet period. The scheduled run that picks up
  what it defers is then the trigger, with more parts around it.
- **Rejected: a draft per merge that the takers wait out.** It still opens a
  pull request, and starts the target's checks, on every merge, which is the
  cost #380 is about; and it moves the waiting into `/dispatch` and `/ship`,
  in every target.

It needs `HARNESS_SYNC_TOKEN`: a fine-grained token with Contents, Pull
requests and Workflows read-write on every repository in `targets.json`, this
one included. Workflows, because the payload ships `.github/workflows/` files
and GitHub refuses a push that changes one without it. The workflow's own
`GITHUB_TOKEN` cannot stand in, because a pull request it opens starts none of
the target's required checks. Until the secret is set, each target is skipped
with a notice and the run stays green.

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

**A red run is an issue.** A target that failed stays behind the payload, and
the run is the only other record of it. So the `sync-issue` job opens one issue
under a title of its own, or comments on the one already open, with the
workflow's own token and no environment, since it writes only this repository's
issues. The title does not match `main-red-open.sh`'s rule, so it stops no
landing. Every step of `targets` and `sync` has a timeout and each job's add up
to less than its limit, since a step past its own fails. A hang outside a step,
in the runner's set-up or post-run work, can still reach the job's limit, and
the job then reads as cancelled. So does a waiting job: a concurrency group
keeps one, so a newer run cancels a waiting one and syncs `main`'s tip itself.
The `sync-red` job tells them apart. A failed job is red with no read. Else it
reads the run's jobs: a cancelled job that ran steps is red, and one that ran
none is red unless its check run's annotations say a higher priority waiting
request cancelled it, which is how run 42575459566 recorded a superseded job.
A leg GitHub cancels from the runner queue ran none either, and its check run
says something else, so it files. Only a `sync-red` that read red files. It
tries each read three times; one still unread fails `sync-red`, which makes
the run red and files nothing, since no answer could be for a run with nothing
red. It holds no concurrency group, so a run it read as having nothing red
cannot take a red run's waiting place in `sync-issue`'s, and a run somebody
cancels whole files nothing, because the job's `!cancelled()` is false only
there.

None of this has met a real hang yet: the scratch runs echoed in place of
filing, so the filing rests on the stub in `test_sync_issue_job.py`. The first
red `Sync` run from a job past its limit shows whether an issue was filed.

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
`gates.yml` takes the enforcing closure gate from the pull request's *base*
commit and refuses a fallback to the head copy, so the pull request that first
brings `.github/closure-gate/closure_gate.py` into a repository whose `main`
lacks it is red. Confirm the sibling's `main` already has that file, or land it
there in a pull request of its own, before making `closure-gate` required; the
alternative is the owner merging that first sync with the check red, as #11 was
for this repository's first target.

## Changes

`main` takes changes only through pull requests: deletion, force pushes and
direct pushes are refused, and nobody bypasses it. Eight checks must pass:
`sync-tool` and `payload-suites` on its three runners (`ubuntu-latest`,
`windows-latest`, `macos-latest`) from `ci.yml`, and `commit-gate`,
`closure-gate` and `harness-drift` from the workflows the root renders, and
`rulesets` from `rulesets.yml`.

`comment-gate` runs on every pull request too and is not among them; backend
does not require it either.

`rulesets/main.json` owns the eight required checks, and the floor every
repository's `main` ruleset meets: the rules, no bypass and no approval
required. `py -3.12 -m harness_sync ruleset-check [--effective] [<repo>...]`
reads each live ruleset and exits 1 with a line per difference, and
`ruleset-apply <repo>` applies the data to one repository and then runs the
check. `--effective` reads the rules in force on `main`, which any token can
read, and compares rules and checks only; without it the ruleset is read whole,
bypass actors included, which needs admin. Both exit 2 when they refuse: a
repository outside the data, data below the floor, or two rulesets with a name
in the data.

`rulesets.yml` runs `ruleset-check --effective` on every pull request, on pushes
to `main` and daily. A branch that changes `rulesets/main.json` is red until the
change is live, so its order is: the `/ship` loop ends with no open finding,
`ruleset-apply <repo>` runs from the branch, the `rulesets` job is rerun, and
the pull request merges. Between the apply and the merge the live ruleset holds
the new list and `main` the old one, so another pull request pushed in that
window reads red in the required `rulesets` job though nothing is wrong with it,
and a new push after the merge clears it. The floor refusal is what stops an
unmerged branch from taking `main` below the floor: data without a floor rule or
with no required check is refused before anything is applied. A dropped or
renamed required check is caught only by the review loop that precedes the
apply. A scheduled run that is red, a difference such as a ruleset changed by
hand or a failed read-back, files a `harness`, `high` issue whose body says
which, or comments on the open one.
