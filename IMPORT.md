# Import of backend's harness

`payload/` was taken from `alexander-shamray/blueprint-backend` at one commit,
and every candidate file was put on one side: **payload** (managed by the
harness, synced into every target) or **backend-local** (stays in backend,
listed under `local` in `targets/blueprint-backend.config.json`). Task 9 ports
into the payload whatever backend changes under a managed path after the pin.

## Pin

`2697924713e9d480256e68fe9b3bee51e174260f` — backend `main` on 2026-11-02
18:50 +0500, *docs: ADR-194 keeps auto-merge off on its own argument,
amending ADR-155*.

## How it was taken

```bash
git -C ../blueprint-backend -c core.autocrlf=false archive 2697924713e9d480256e68fe9b3bee51e174260f <paths> | tar -x -C payload
```

`core.autocrlf=false`, because `git archive` applies the checkout's line-ending
conversion and a CRLF archive of an LF blob is not backend's bytes. After
`git add`, every imported path's blob id and mode were compared with
`git ls-tree` at the pin: all identical, the executable bit included. No
imported blob holds a CR, so this repository's `*.md`, `*.json` and `*.yml`
`text` rules store them as backend does; `*.py` and `*.sh` carry
`text eol=lf` here as there, and `.gitattributes` gains backend's one path
rule, for `cbx`, which has no suffix.

The payload differs from backend's blobs only where *Repository slug and task
list* below says, plus `payload/.harness/`, which backend does not have yet.

## Ported after the pin

Task 9 Step 1 brought the payload to backend `main` at
`ed28e30a1f92587ed6cdffb3ca8f83131bc93407` (2026-11-02 23:01 +0500), whose
newest change under a payload path is `fa7650984`. Fourteen backend commits
touched a payload path after the pin, all of them `/dispatch` and `/ship`
work:

| Commit | Payload paths |
|---|---|
| `004482b2a`, `745ceab48`, `d44f664dc`, `a7ccddf4e`, `f989606af`, `f05d0997a` | `docs/commands/dispatch.md` |
| `73b5ac52f` | `docs/commands/ship.md` |
| `561c9f812`, `131636564` | `.claude/commands/dispatch.md`, `.claude/scripts/dispatch_run.py` |
| `0dd6d2a36` | `.claude/commands/ship.md`, `.claude/scripts/dispatch_run.py` |
| `874fb0695`, `bd94ea3e7`, `7d3584bfa`, `fa7650984` | `.claude/scripts/dispatch_run.py` |

`git diff --name-status` over the payload's trees from the pin to that commit
adds no file and deletes none; the one other path it lists,
`.claude/scripts/test_dispatch_run.py`, is backend-local. The three files the
payload holds as backend's bytes were taken whole, and their blob ids match
backend's at that commit. `.claude/commands/dispatch.md` and
`.claude/commands/ship.md` were merged three ways (`git merge-file`, the pin's
blob as base), with no conflict, so each still differs from backend's only in
the task-list line *Repository slug and task list* names. Backend's
`.claude/settings.json` is still blob `aeb89a9`, so the settings base needed no
change.

Task 9 Step 2's second backend pull request, #1732 (rebased onto backend
`main`, its last commit landing as
`73b385d670aff6ab9e9d121aa0b2b33dabf00e20`), added *Managed files* and its
index row to `docs/harness-boundaries.md`, a payload path; the payload takes
that blob whole, and its blob id matches backend's there. The pull request's
other payload paths, the `tooling` row naming `.harness/` in
`.claude/scripts/sweep-slices.sh`, `.claude/commands/bug-sweep.md` and
`.claude/commands/security-sweep.md`, were written to the payload's bytes, so
their blob ids already match and nothing else moves.

## How a file was classified

- **Spec 8 and the brief name it backend-local**: the .NET and blueprint
  mechanisms (`dotnet-test.sh`, `mutation-run.sh`, `mutation_survivors.py`
  and its test, `stryker-config.json`, `/validate-blueprint`, `/new-adr`,
  `/new-chapter`, `/check-links`, `/mutation-sweep`) and their runbooks.
- **A command whose grants or steps run a stack command** is backend-local,
  since the config schema has no key to name one: `/review-branch` grants and
  runs `dotnet-test.sh`, and its `disallowed-tools` enumerates backend's own
  tracked trees and root files.
- **A test module goes with the code it tests**, unless it asserts what only
  backend's tree holds — `CLAUDE.md`, `Platform.slnx`, `src/`, `tools/`,
  `deploy/`, `docs/change-locality.md`, `docs/superpowers/plans/`,
  `.github/locality-gate/classes.yml`, or a backend-local command. None of
  those values is in `.harness/config.json`, so no such module could be made
  to read it from there. At the pin each such module stayed backend-local,
  whole; #5 then split the twelve that mixed both kinds of case (*Decided
  after review*): the payload module keeps every case a target without
  backend's tree runs, and a backend-local sibling named
  `test_<module>_backend.py` keeps the rest. The row names the cases that
  read backend's tree. They were found by running the suites in a rendered
  worktree (the `payload-suites` job's procedure), not by reading.
- **Everything else in the brief's list is payload**, the gates' own
  workflows included (`commit-gate.yml`, `closure-gate.yml`,
  `comment-gate.yml`). The issue-form, plan-size, output and workflow-lint
  gates' code is payload and their invocation stays in each target's own
  `ci.yml`, where backend's already is.

Not candidates, and so not in the table: backend's domain gates
(`messaging-gate`, `domain-name-gate`, `sql-style-gate`, `pipeline-gate`,
`licence-gate`, `secret-scan`), `coverage`, `locality-gate` and every other
workflow, `ci.yml` included — product and stack, by spec 3 and 8.

## Settings split

`payload/.harness/settings.base.json` is backend's `.claude/settings.json` at
the pin, whole (blob `aeb89a9`, the same blob as at `f61a0932f`). The
config's `settings` additions are empty.

Nothing in that file is backend's alone. Its denies protect the harness's own
control surface (`.claude/scripts/**`, `commands`, `agents`, `hooks`,
`skills`, the settings files), `.remember/**`, and git's destructive and
argv-injection forms; its allows are read-only git, `ls`, `wc`, `comm` and
the push forms the push helpers rely on; its hooks are the guards and the
codebase-index hooks, all payload files; its `env` serves the payload's MCP
index. It names no `dotnet`, no `Platform.slnx` and no backend path. Spec 5.2's
stack denies (frontend's `package.json`, admin's `*.slnx`) are sibling
additions; backend has none in `settings.json`, its build files being denied
per command in `disallowed-tools` instead.

`dump_settings(render_settings(base, backend config))` was byte-identical to
backend's file at the pin. From then on the target's drift gate holds that
claim: `_check_settings` renders the file from the target's own base and
config on every pull request there. This repository keeps no copy of backend's
file to compare with, since a copy has to move with the base in the same
commit, and a test between the two cannot fail (#9).

## Repository slug and task list

Changed, so the file reads the value from `.harness/config.json`:

| File | Was | Now |
|---|---|---|
| `.claude/commands/branch.md` | `.todo/blueprint-backend.md` | the task list named by `.harness/config.json` `task_list` |
| `.claude/commands/dispatch.md` | `` `<list>` is `../.todo/blueprint-backend.md` `` | `` `<list>` is `../<task_list>` (`.harness/config.json`) `` |
| `.claude/commands/ship.md` | `.todo/blueprint-backend.md` | the task list named by `.harness/config.json` `task_list` |

No script or hook carries the slug or the task list: the scripts resolve the
repository from the checkout (`gh repo view --json nameWithOwner`), which is
right in every target, and `dispatch_board.py` takes the task list as
`--tasks <list>`. Left verbatim, because none names the current repository:

- `.claude/commands/branch.md`, the worktree listing — example output of
  `git worktree list` from backend's checkout.
- `.claude/scripts/test_dispatch_run.py:1565-1566` — a path fixture for
  `project_slug`.
- `.github/closure-gate/test_closure_gate.py:17` — the repository fixture the
  gate's parser is called with.
- `docs/commands/bug-sweep.md:520`, `docs/commands/security-sweep.md:353` —
  history: what backend's run of 2026-10-21 filed.

## Stack mentions left verbatim

Payload files that still name a backend stack value, each with why it stays.
`harness_sync/tests/test_payload_references.py` reads this section and refuses
the four names its `_STACK_NAME` holds anywhere else in the payload, its suites
aside. A shape those names cannot see, such as a C# sample, rests on review.

- `.claude/commands/bug-sweep.md:187`, `docs/commands/bug-sweep.md:577` — the
  sweep's area rows name backend's §4.1 gateway, BFF and AppHost;
  `.claude/scripts/sweep-slices.sh:47` slices `tools/` as tooling, a backend
  tree. All three go with the rows themselves: #73.
- `.github/output-gate/` — the gate itself checks .NET build output against
  `Platform.slnx`. Delivered only where a .NET build runs: a target without
  one puts `.github/output-gate/**` under `exclude` in its config, as this
  repository does. #85 moves it backend-local.
- `.github/comment-gate/README.md:24,33` — `MSBuild` as a file kind the gate
  reads: true in any target.
- Test fixtures that use a `dotnet` command line as a sample string
  (`test_git_argv_guard.py:241-246`, `test_index_search_hint.py:118`,
  `test_watch_session.py:28-29`, `test_cbx.py:54`) — data, right in any
  target.

## References to backend-local commands and documents

The payload was taken naming commands backend keeps local and documents
only backend has: right in backend, pointing at nothing in a sibling. Plan
2 Task 4 rewrote each, and
`harness_sync/tests/test_payload_references.py` now holds the payload to
it: every path a payload file cites, bare or as a link, resolves in the
payload or is one a target holds itself; every section a citation names is
a heading of the cited file, or for `docs/harness-local.md` one of the four
the contract fixes; no payload file names a command or a script a target
config lists under `local`; and none cites a section of `CLAUDE.md`, which
is each target's own, or a change contract's section by number. The checks
read the payload's files but its suites, whose paths are fixtures.

What a citation was rewritten to:

| It cited | It cites now |
|---|---|
| A section of backend's `CLAUDE.md` | The `.harness/agent-rules.md` or `docs/harness/` section now holding the rule |
| `docs/change-locality.md` §6 | `docs/harness/working-rules.md`'s section for the rule |
| §5, the classes, the touch set | The change contract `docs/harness-local.md` *Documents* names |
| `docs/token-plan.md` | `docs/harness/token-rules.md`'s section |
| `/validate-blueprint`, `/check-links`, `docs/roadmap.md`, `docs/backend-architecture/` | The checks `docs/harness-local.md` *Ship checks* names, or the product specification *Documents* names |
| `/review-branch` and its *What counts as a finding* | `/ship`'s review; working-rules' *What counts as a finding* and harness-local's *Review examples* |
| `docs/style-guide.md`, `docs/testing.md` | The style guide or testing document *Documents* names |
| `docs/pr-decision-log.md`, `docs/lessons.md` | The closed records *Documents* names; `sweep-slices.sh`'s `case` arm keeps the two paths, which match nothing where they are absent |
| `ci.yml`, `docs/churn-plan*.md`, a backend ADR, `docs/token-usage.md` | The target's CI workflow, its own comment sweeps, the step described, backend's measurement by date |

`docs/harness-boundaries.md` lost the two passages only backend's commands
make true, the callout on what `/check-links` and `/validate-blueprint`
read and the `/mutation-sweep` paragraph; backend's plan 2 Task 6 carries
them to backend's own residuals. Its *Managed files* states the
`docs/harness-local.md` contract, and this repository's own copy is
`docs/harness-local.md`.

Left as they were: `docs/superpowers/`, the superpowers plugin's directory
in every repository; `.github/locality-gate/classes.yml`, the class map a
target with a change contract holds as its own; the example paths the
boundaries and the edit guard invent to show a case; and the sites
*Stack mentions left verbatim* lists.

#7 finished the stack half with no config key, which spec 5.2 and the issue
both expected. A stack command is a check, and `docs/harness-local.md` *Ship
checks* already names a target's checks, so `pr.md` cites that row; the
sweeps' readable-root proof needs only a tracked file every target holds,
which is `CLAUDE.md`; `style-pass.md` and the runbooks say what a build or a
formatter does without naming one. `issue_form_gate.py` now reads the
vocabulary from working-rules' own bullet, so the two cases #5 split out to
backend, which read the gate's default file, came back to the payload's
suite. Two passages of `docs/harness-boundaries.md` only backend's tree makes
true, the ninth entry's build grants and the quality sets' scoring runs, went
to backend's own *Residuals*; blueprint-backend#1773 carries them.

## Decided after review

The whole-module classification of the mixed test modules stays for this
plan: splitting their backend-tree cases into backend-local modules would add
files to backend's first-sync diff, which spec 7 step 2 wants near-empty. #5
tracks splitting them so their generic cases run here. Until then, Task 7's
config for this repository excluded
`.github/workflows/comment-gate.yml`, whose suite stayed in backend, so its
`python -m unittest` would have found no tests here and failed. The config is
`.harness/config.json` and it did exclude that workflow (ruling R18); JSON
has no comments, so this is where the reason was recorded.

#5 split them, taken from backend `main` at `332e369`: each mixed module is a
payload module now, and its backend-tree cases are a backend-local sibling
beside it, `test_<module>_backend.py`, listed under `local` in
`targets/blueprint-backend.config.json`. Most failing cases did not move:
where a case read backend's tree only as a fixture, it now builds its own
(`PathTests`' checkout, `test_pr_helpers.py`'s class map), and where it held a
list of commands, the list names the payload's and the sibling subclasses the
case, or reuses it, for backend's. What moved reads a file only backend has.
The exclusion stayed in the split's pull request, #75: dropped there, it made
the drift gate expect `.github/workflows/comment-gate.yml` in the root's
manifest, which no apply had written, so `harness-drift` failed (`… is a
payload file but .harness/manifest.json does not list it`, run both ways).
Only an apply writes the workflow and its manifest entry together, and
`sync.yml`'s sync never edits a target's config. The sync that first rendered
the split suites here, #78, left the exclusion in place, so a pull request of
its own dropped it by hand and reran apply, and the workflow runs here now.

Backend takes its half in one pull request, since its `.harness/config.json`
still lists the twelve modules as `local` and apply refuses a payload file
that is `local` and differs: the config this repository's draft carries, ten
of the eleven siblings and the sync's apply together (blueprint-backend#1773).
The eleventh, `test_issue_form_gate_backend.py`, does not land: #7 brought its
cases back to the payload and it names symbols that are gone. Until #1773
lands, `sync.yml`'s backend leg is refused.

## Test counts

Backend's `review-helpers` job ran `python -m unittest discover -s
.claude/scripts` at the pin green: **963 tests**, `OK (skipped=1)` (CI run
41456476064, job 125314317877; the brief's 691 is an older figure). The same
command at the pin on Windows: 963, `OK (skipped=2)`.

| Suite | At the pin | Left backend-local | Run by `payload-suites` |
|---|---|---|---|
| `.claude/scripts` | 963 | 297 | 666 |
| `.github/commit-gate` | 21 | 0 | 21 |
| `.github/closure-gate` | 59 | 0 | 59 |
| `.github/comment-gate` | 115 | 115 | 0 |
| `.github/issue-form-gate` | 38 | 38 | 0 |
| `.github/plan-size-gate` | 12 | 12 | 0 |
| `.github/output-gate` | 28 | 28 | 0 |

The 297 left local in `.claude/scripts`: `test_dispatch_run.py` 91,
`test_dispatch_board.py` 67, `test_gh_issue_suppresses.py` 28,
`test_pr_helpers.py` 28, `test_mutation_survivors.py` 23,
`test_harness_denies.py` 21, `test_command_grants.py` 17,
`test_sweep_slices.py` 13, `test_command_runbooks.py` 9. Run in a rendered
worktree with every module but the mutation one in the payload, the
directory gave 57 failures and errors (subtests counted apiece) and the four
gates 8, every one in a case that reads backend's tree or a backend-local
file (the rows below name the classes); the module's other cases stay with
them. Backend's CI still runs
all of them: its `review-helpers` job discovers the local modules beside the
synced ones.

After #5, at backend `main` `332e369`, the twelve modules' tests (methods, so
a case a sibling subclasses for one more command counts once on each side):

| Module | Backend's whole module | Payload | Backend's sibling |
|---|---|---|---|
| `test_command_grants.py` | 17 | 17 | 3 |
| `test_command_runbooks.py` | 9 | 9 | 3 |
| `test_dispatch_board.py` | 67 | 67 | none |
| `test_dispatch_run.py` | 103 | 102 | 1 |
| `test_gh_issue_suppresses.py` | 28 | 28 | 7 |
| `test_harness_denies.py` | 21 | 6 | 15 |
| `test_pr_helpers.py` | 28 | 27 | 2 |
| `test_sweep_slices.py` | 13 | 12 | 1 |
| `test_comment_gate.py` | 115 | 114 | 1 |
| `test_issue_form_gate.py` | 38 | 36 | 2 |
| `test_output_gate.py` | 28 | 24 | 4 |
| `test_plan_size_gate.py` | 12 | 11 | 1 |

So `payload-suites` runs 268 more of `.claude/scripts`' tests and 185 gate
tests it ran none of, and 40 stay backend's. The payload's
`test_python_hygiene.py` skips a `local` file, so the payload modules are the
first time these were held to it: eight `text=True` calls gained
`encoding="utf-8"`.

`workflow-lint` has no Python suite: its check is actionlint run over
`broken-reference.yml` in backend's own `ci.yml` job, so `payload-suites`
does not run it.

## Classification

One row per candidate file at the pin.

| Path | Class | Reason |
|---|---|---|
| `.claude/agents/branch-reviewer.md` | payload | read-only subagent profile; names no stack |
| `.claude/agents/bug-auditor.md` | payload | read-only subagent profile; names no stack |
| `.claude/agents/security-auditor.md` | payload | read-only subagent profile; names no stack |
| `.claude/agents/team-peer.md` | payload | read-only subagent profile; names no stack |
| `.claude/commands/branch.md` | payload | harness command; task list read from config (step 3) |
| `.claude/commands/bug-sweep.md` | payload | harness command (spec 8); stack mention left verbatim (see *Stack mentions*) |
| `.claude/commands/check-links.md` | backend-local | blueprint command (spec 8) |
| `.claude/commands/commit.md` | payload | harness command; names no stack |
| `.claude/commands/dispatch.md` | payload | harness command; task list read from config (step 3) |
| `.claude/commands/mutation-sweep.md` | backend-local | drives Stryker.NET through `mutation-run.sh` (spec 8) |
| `.claude/commands/new-adr.md` | backend-local | blueprint command (spec 8) |
| `.claude/commands/new-chapter.md` | backend-local | blueprint command (spec 8) |
| `.claude/commands/pr.md` | payload | harness command |
| `.claude/commands/review-branch.md` | backend-local | grants and runs `dotnet-test.sh`, and its `disallowed-tools` enumerates backend's tracked trees and root files, which `test_harness_denies.py` holds it to (ruling: a stack command is backend-local or a config key; the schema has no such key) |
| `.claude/commands/security-sweep.md` | payload | harness command (spec 8) |
| `.claude/commands/ship.md` | payload | harness command; task list read from config (step 3) |
| `.claude/commands/style-pass.md` | payload | harness command |
| `.claude/commands/team.md` | payload | harness command; names no stack |
| `.claude/commands/validate-blueprint.md` | backend-local | blueprint command (spec 8) |
| `.claude/hooks/guard-edit-target.py` | payload | guard hook, base of spec 5.5 |
| `.claude/hooks/guard-git-argv.py` | payload | guard hook, base of spec 5.5 |
| `.claude/hooks/guard-index-argv.py` | payload | guard hook, base of spec 5.5 |
| `.claude/hooks/hint-bound.sh` | payload | codebase-index hook, wired by the base settings |
| `.claude/hooks/index-mcp-root.py` | payload | codebase-index hook, wired by the base settings |
| `.claude/hooks/index-query-hint.py` | payload | codebase-index hook, wired by the base settings |
| `.claude/hooks/index-search-hint.py` | payload | codebase-index hook, wired by the base settings |
| `.claude/hooks/refresh-index.py` | payload | codebase-index hook, wired by the base settings |
| `.claude/scripts/dispatch_board.py` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/dispatch_run.py` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/dotnet-test.sh` | backend-local | .NET test executor (spec 8) |
| `.claude/scripts/gh-issue-create.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/gh-issue-list.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/gh-issue-suppresses.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/gh-issue-text.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/gh-label-ensure.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/gh-pr-merge.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/gh-read-bound.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/git-branch-create.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/git-rebase-onto-main.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/git-revert-pr.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/git-switch-existing.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/git-trailer-pr.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/git-unstage.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/git-worktree-detach.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/git-worktree-drop.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/git-worktree-fork.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/git-worktree-remove.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/issue_decisions.py` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/mutation-run.sh` | backend-local | Stryker.NET runner (spec 8) |
| `.claude/scripts/mutation_survivors.py` | backend-local | Stryker report reader (spec 8) |
| `.claude/scripts/pr-closure-input.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/pr-for-branch.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/pr-locality.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/pr-state.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/review_helpers.py` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/stryker-config.json` | backend-local | Stryker.NET config (spec 8) |
| `.claude/scripts/sweep-mark.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/sweep-slices.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/system-sleep.sh` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/team_board.py` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/scripts/test_cbx.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_command_grants.py` | payload, split by #5 | the sweep and chain cases name the payload's commands; backend's `test_command_grants_backend.py` holds the local `mutation-sweep.md`, `validate-blueprint.md` and `check-links.md` to them |
| `.claude/scripts/test_command_runbooks.py` | payload, split by #5 | ceilings for the payload's runbooks; backend's `test_command_runbooks_backend.py` holds the local `mutation-sweep`, `validate-blueprint` and `review-branch` runbooks and backend's `CLAUDE.md` |
| `.claude/scripts/test_dispatch_board.py` | payload, split by #5 | `PathTests` judges dotless tokens against a checkout it builds, so no case reads backend's directories and none is left local |
| `.claude/scripts/test_dispatch_run.py` | payload, split by #5 | backend's `test_dispatch_run_backend.py` holds `test_token_keys_are_quality_sets_own`, which reads `tools/quality-sets/quality_sets.py` |
| `.claude/scripts/test_edit_target_guard.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_gh_issue_create.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_gh_issue_suppresses.py` | payload, split by #5 | `TheSweepsReachIssuesOnlyThroughTheHelpers` names the payload's sweeps; backend's `test_gh_issue_suppresses_backend.py` subclasses it for the local `mutation-sweep.md` |
| `.claude/scripts/test_gh_label_ensure.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_git_argv_guard.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_git_pr_trailer_helpers.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_git_rebase_onto_main.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_git_worktree_detach.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_git_worktree_fork.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_git_worktree_remove.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_harness_denies.py` | payload, split by #5 | settings.json's deny list and the no-symbolic-link case; backend's `test_harness_denies_backend.py` holds `CommandsEnforceTheEditingBoundariesTheyState`, which asserts backend's tree (`src`, `tests`, `CLAUDE.md`, `Platform.slnx`), `dotnet-test.sh` and the local `validate-blueprint.md` and `review-branch.md` |
| `.claude/scripts/test_hint_bound.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_hook_timeouts.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_index_argv_guard.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_index_mcp_root.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_index_query_hint.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_index_search_hint.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_issue_decisions.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_mutation_survivors.py` | backend-local | tests a backend-local script |
| `.claude/scripts/test_pr_for_branch.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_pr_helpers.py` | payload, split by #5 | the locality cases read a class map the suite holds; backend's `test_pr_helpers_backend.py` holds the shipped `.github/locality-gate/classes.yml` to `locality_gate.py`, and the local `review-branch.md`'s grants |
| `.claude/scripts/test_refresh_index.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_root_ignore_covers_nested.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_ship_dispatched.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_ship_landing_method.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_sweep_slices.py` | payload, split by #5 | partitions repositories it builds; backend's `test_sweep_slices_backend.py` holds `TheRealTree`, since the rows partition backend's tree and fail on a path no row owns here (`harness_sync/__init__.py`, #73) |
| `.claude/scripts/test_system_sleep.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_team_board.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_watch_session.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/watch_session.py` | payload | harness helper; resolves the repository from the checkout (`gh repo view`), names no stack |
| `.claude/settings.json` | backend-local | rendered, never copied: its content is `payload/.harness/settings.base.json` plus the config's `settings` (see *Settings split*) |
| `.claude/skills/codebase-index/SKILL.md` | payload | codebase-index skill (brief) |
| `.claude/skills/codebase-index/examples/hooks/settings.json` | payload | codebase-index skill (brief) |
| `.claude/skills/codebase-index/references/commands.md` | payload | codebase-index skill (brief) |
| `.claude/skills/codebase-index/references/memory.md` | payload | codebase-index skill (brief) |
| `.claude/skills/codebase-index/references/response-contract.md` | payload | codebase-index skill (brief) |
| `.claude/skills/codebase-index/scripts/cbx` | payload | codebase-index skill (brief) |
| `.claude/skills/codebase-index/scripts/cbx.ps1` | payload | codebase-index skill (brief) |
| `.github/ISSUE_TEMPLATE/config.yml` | payload | issue form the filing helpers and the issue-form gate read |
| `.github/ISSUE_TEMPLATE/finding.yml` | payload | issue form the filing helpers and the issue-form gate read |
| `.github/closure-gate/README.md` | payload | gate README |
| `.github/closure-gate/closure_gate.py` | payload | gate code; its invocation stays in each target's `ci.yml` or comes with its workflow (brief) |
| `.github/closure-gate/test_closure_gate.py` | payload | gate suite; passes in payload-suites |
| `.github/comment-gate/README.md` | payload | gate README |
| `.github/comment-gate/comment_gate.py` | payload | gate code; its invocation stays in each target's `ci.yml` or comes with its workflow (brief) |
| `.github/comment-gate/test_comment_gate.py` | payload, split by #5 | `TheShippedTree` reads any target's tracked files; backend's `test_comment_gate_backend.py` holds the budget over backend's thousand-odd C# files |
| `.github/commit-gate/README.md` | payload | gate README |
| `.github/commit-gate/commit_gate.py` | payload | gate code; its invocation stays in each target's `ci.yml` or comes with its workflow (brief) |
| `.github/commit-gate/test_commit_gate.py` | payload | gate suite; passes in payload-suites |
| `.github/issue-form-gate/README.md` | payload | gate README |
| `.github/issue-form-gate/issue_form_gate.py` | payload | gate code; its invocation stays in each target's `ci.yml` or comes with its workflow (brief) |
| `.github/issue-form-gate/test_issue_form_gate.py` | payload | `ThisRepositoryTests` reads the shipped form, helper and working-rules' vocabulary; #5 split two of its cases out and #7 brought them back |
| `.github/output-gate/README.md` | payload | gate README |
| `.github/output-gate/output_gate.py` | payload | gate code; its invocation stays in each target's `ci.yml` or comes with its workflow (brief) |
| `.github/output-gate/test_output_gate.py` | payload, split by #5 | builds every tree it walks; backend's `test_output_gate_backend.py` holds `ThisRepository`, which reads `Platform.slnx` and backend's `src/` ignore rules |
| `.github/plan-size-gate/README.md` | payload | gate README |
| `.github/plan-size-gate/plan_size_gate.py` | payload | gate code; its invocation stays in each target's `ci.yml` or comes with its workflow (brief) |
| `.github/plan-size-gate/test_plan_size_gate.py` | payload, split by #5 | backend's `test_plan_size_gate_backend.py` holds `test_this_repository_s_plans_pass`, which reads `docs/superpowers/plans/` |
| `.github/workflow-lint/README.md` | payload | actionlint fixture; its job stays in backend's `ci.yml` (brief) |
| `.github/workflow-lint/broken-reference.yml` | payload | actionlint fixture; its job stays in backend's `ci.yml` (brief) |
| `.github/workflows/closure-gate.yml` | payload | the gate's own workflow (brief) |
| `.github/workflows/comment-gate.yml` | payload | the gate's own workflow (brief) |
| `.github/workflows/commit-gate.yml` | payload | the gate's own workflow (brief) |
| `docs/commands/branch.md` | payload | runbook of a payload command |
| `docs/commands/bug-sweep.md` | payload | runbook of a payload command |
| `docs/commands/dispatch.md` | payload | runbook of a payload command |
| `docs/commands/mutation-sweep.md` | backend-local | runbook of a backend-local command |
| `docs/commands/review-branch.md` | backend-local | runbook of a backend-local command |
| `docs/commands/security-sweep.md` | payload | runbook of a payload command |
| `docs/commands/ship.md` | payload | runbook of a payload command |
| `docs/commands/team.md` | payload | runbook of a payload command |
| `docs/commands/validate-blueprint.md` | backend-local | runbook of a backend-local command |
| `docs/harness-boundaries.md` | payload | harness boundaries document (brief); split later per spec 5.2 |

## Frontend audit, pinned at 41a3f45

Spec §7 step 3, plan 5 Task 1: every file `blueprint-frontend` shares with the
payload was audited for what only frontend's copy holds, before a sync replaces
it. Frontend is read at `41a3f45`, whose `.claude` and `.github` had no later
commit on 2026-11-06, and the payload at harness `9f63bd2`. Task 2 takes its
work from the tables below, and marks each row it lands `ported` with its
pull request, since a rebase landing changes the commit's hash.

Nine read-only agents, one for each of clusters B, C, D, F and G and two for
each of A and E, whose diffs did not fit one read, returned 350 rows. A row
is one behaviour that changes an outcome; 15 files differ in wording alone and
have none. Rows naming one cause in several clusters are merged into one, its
other sites under *also*, which leaves 274.

*Decisions* is the plan's *Decisions on the §8 mechanisms*, in
`blueprint-backend`'s
`docs/superpowers/plans/2026-11-06-shared-harness-5-frontend-sync.md`, and
*The guards' threat model* is that section of `docs/harness-boundaries.md`.

| Cluster | port | residual | local | covered | obsolete | out of scope |
|---|---|---|---|---|---|---|
| A, guards | 25 | 0 | 5 | 6 | 11 | 31 |
| B, git helpers | 8 | 0 | 5 | 33 | 1 | 0 |
| C, GitHub helpers | 12 | 0 | 2 | 4 | 0 | 0 |
| D, index | 21 | 0 | 3 | 16 | 6 | 0 |
| E, commands | 23 | 0 | 13 | 13 | 0 | 0 |
| F, boundaries | 5 | 7 | 3 | 13 | 2 | 2 |
| G, gates | 1 | 0 | 1 | 1 | 1 | 0 |
| All | 95 | 7 | 32 | 86 | 21 | 33 |

The *Task* column says which task owns a `port`: 84 rows are Task 2's, by
cluster, 9 are Task 3's and 2 are Task 4's. A `residual` goes to frontend's
`docs/harness-local.md` *Residuals*.

**An agent's verdict is not the record.** Cluster A's `port` rows were checked
by hand against *The guards' threat model*, by running both guards over 108
commands and by counting 46,810 Bash commands and 5,090 edit targets typed in
backend, frontend and the harness since 2026-10-19. `c1` in a reason is that
section's criterion 1, and the counts are from that reading. Every `covered`
row's citation was opened. Outside cluster A a `port` is the agent's reading;
D's rows beyond those *Decisions* names were checked against
`refresh-index.py`.

The check moved 21 rows off the agents' verdicts and narrowed 10 more, because
frontend's guards refuse commands agents type every day, which is this
rollout's anti-goal:

- **The git guard's allow-list and its refusal of environment names** are out
  of scope: they refuse `git ls-remote` (281 typed), `git config` (71),
  `git stash` (44), `GIT_EDITOR` (22). The harmful subcommands port as a list.
- **The redirection family ports narrowed**, anchored at a checkout's root, with
  a literal `cd` resolved and an unknown variable or computed operand admitted.
  Frontend's forms refuse `> "$var…"` (523), `cd x && … > y` (736),
  `cp "$a" "$b"` (107), and `payload/.claude/…` by its component. Its lists come
  from each target's denies, so `.github` is refused only where a target denies
  it.
- **The edit guard's allow-list** becomes a refusal of `~/.ssh`, shell profiles
  and `~/.gitconfig`, since it refuses sibling checkouts and `run-locally.md`;
  the control set drops `~/.claude/CLAUDE.md` for the same reason. The rows that
  only served it are `obsolete`.
- **The helper-copy `ask`** is out of scope: it meets none of the three criteria
  and would stop a headless `/ship` at every helper in a worktree that differs
  from the hooks' checkout.

Task 2's replay still reads what a narrowed port newly refuses. It reads Bash
only, so the 268 edits under a worktree's `.claude/` that the row at
`guard-edit-target.py:808` would refuse are read by hand before that port
stands.

Three findings are for later tasks. Frontend has no `test` or `test-gap` label,
and the issue-form job fails on the sync unless they exist first (cluster G).
*Decisions* puts `Bash(gh pr merge:*)` and `Bash(git worktree remove:*)` in the
base, and they were typed 65 and 76 times in the same window, which Task 3
Step 4 reads. `branch.md` calls `git branch -m` free and the base denies it,
which E's row ports.

#### G, gates

| Frontend | Behaviour | Payload | Verdict | Task | Reason and fix | Frontend's test |
|---|---|---|---|---|---|---|
| .github/workflows/commit-gate.yml:37 | Stands down only when every commit's author and committer are Dependabot | .github/workflows/commit-gate.yml:22 | ported #121 | 2 | Payload exempts by opener, so a human push rides unjudged (blueprint-admin#400). Port the step and step ifs; drop job if; fix working-rules.md:62. |  |
| .github/ISSUE_TEMPLATE/finding.yml:18 | Form offers only kinds and areas frontend has labels for, no test-gap, enhancement, test | .github/ISSUE_TEMPLATE/finding.yml:20 | local |  | Frontend has no test label (README:12), test-gap appears nowhere; create them, check enhancement, before sync or the issue-form job fails. | test_this_repository_s_owners_are_read |
| .github/issue-form-gate/issue_form_gate.py:154 | Holds form kinds and severities to vocabulary bullet and helper's case arms | .github/issue-form-gate/issue_form_gate.py:165 | covered |  | Owners move to working-rules.md and gh-issue-create.sh, per decided gh-issue-filing.sh drop; helper-subset rule at :171. | test_a_kind_the_contract_lacks_fails |
| .github/workflows/commit-gate.yml:14 | Cancels a pull request's in-progress gate run when a newer run starts | .github/workflows/commit-gate.yml:14 | obsolete |  | Payload removed the group: a rerun of an older head cancels the newest, leaving a failed required check. |  |

#### B, git helpers

| Frontend | Behaviour | Payload | Verdict | Task | Reason and fix | Frontend's test |
|---|---|---|---|---|---|---|
| git-rebase-onto-main.sh:57, git-trailer-pr.sh:18; also git-trailer-pr.sh:18, docs/harness-boundaries.md:1676 | Host hooks never run inside a rewrite: empty core.hooksPath for the run | - | ported #125 | 2 | Payload runs pre-rebase, post-rewrite, pre-push in both helpers. Port the export; its suite's hook fixtures must move to receive.denyNonFastForwards and index.lock. | TheHostsHooksNeverRunInAReplay,test_the_repositorys_own_hooks_do_not_run_inside_the_rewrite |
| git-rebase-onto-main.sh:284, git-trailer-pr.sh:79; also git-trailer-pr.sh:79 | Replays spell --no-autosquash, --no-fork-point, --no-autostash; trailer helper spells all five flags | .claude/scripts/git-rebase-onto-main.sh:369 | ported #125 | 2 | Defensive spellings: git limits rebase.autoSquash to interactive mode and takes no fork point when an upstream is named, so neither changes these replays today; trailer's rebase (payload :69) spells none. Add the flags, keeping --merge. | test_configuration_cannot_change_what_the_replay_does,test_the_helper_spells_its_rewrite_and_its_lease_itself |
| git-worktree-detach.sh:60, test_harness_helpers.py:2231, 2242, 2272; also docs/commands/bug-sweep.md:919 | Commit carrying tracked symlinks refused before the sweep worktree exists, exit 5 | - | ported #125 | 2 | Payload's test_harness_denies.py:94 judges main only, and Read follows links out of $work. Restore the check and both sweeps' sentence. | test_a_pinned_commit_with_a_tracked_link_is_refused,test_a_commit_carrying_a_link_is_refused_when_driven,test_both_sweeps_state_the_half_that_is_closed |
| git-worktree-remove.sh:33, test_harness_helpers.py:1991; also commands/ship.md:196, docs/commands/ship.md:442, docs/harness-boundaries.md:792 | Teardown names path and branch; registered worktree must hold that branch; main refused | .claude/scripts/git-worktree-remove.sh:7 | ported #125 | 2 | Payload removes any clean linked worktree by path alone. Restore the branch argument and check; update ship.md:314,583 and dispatch.md:215. | test_the_worktree_helper_removes_only_the_worktree_it_is_named_for |
| git-worktree-remove.sh:120, test_harness_helpers.py:2058 | Directory git unregistered but left behind is reported, exit 4 | .claude/scripts/git-worktree-remove.sh:89 | ported #125 | 2 | Payload's last line is git's status, so zero with a held file reads as done. Capture status, test the path, name it. | test_the_worktree_helper_deletes_a_long_path_and_says_when_it_did_not |
| git-rebase-onto-main.sh:251 | Skip-worktree files refused by name before fetch, exit 5, sparse checkout exempt | .claude/scripts/git-rebase-onto-main.sh:298 | ported #125 | 2 | Payload only hints after a failed start, naming no file; a mid-replay stop gets no hint. Restore the pre-replay refusal. | test_a_skip_worktree_file_is_refused_and_named,test_a_sparse_checkout_is_not_read_as_a_lift |
| test_harness_helpers.py:3442 | Every helper a command grants must exist on disk | - | ported #125 | 2 | No payload case reads grants against files, so a gone helper's grant approves whatever lands there. Port the case. | test_every_granted_helper_exists |
| test_harness_helpers.py:10853 | Skill markdown may not teach the bare codebase-index CLI | - | ported #125 | 2 | Payload's markdown is clean today but test_cbx.py scans only cbx graph. Port the scan with cbx as the positive control. | test_skill_markdown_does_not_teach_the_unpinned_cli |
| test_harness_helpers.py:2800, 2808, 2818, 2856, 2906, 2927, 3003, 3046 | Every tracked tree, root file, auto-import and .git denied in review-branch.md | - | local |  | Reads frontend's trees and its local review-branch.md (*Decisions*). Keep these beside the npm cases when test_harness_helpers.py drops. | test_every_tracked_tree_is_denied_in_both_spellings,test_the_auto_load_surface_is_denied,test_gits_own_control_directory_is_denied |
| test_harness_helpers.py:2937, 2957, 2968, 2995 | No free package runner; npm-checks.sh takes no free parameter | - | local |  | *Decisions* keeps :2961-3000 local; :2937 is the same npm stack and stays with them. | test_no_command_grants_a_free_form_package_runner,test_the_check_runner_helper_takes_no_free_parameter,test_the_check_runner_refuses_an_absent_install,test_the_check_runner_offers_no_e2e_mode |
| test_harness_helpers.py:3122, 3133 | Editing commands deny package.json, eslint config, .npmrc; style-pass exemption real | - | local |  | Frontend toolchain names. Managed frontmatter cannot keep them, so they move to frontend's config denies. | test_every_editing_command_denies_the_toolchain,test_the_toolchain_exemption_is_real |
| test_harness_helpers.py:10894 | MCP server starts without a shell, through the Node launcher | - | local |  | *Decisions*: mcp-launch.mjs stays local and .mcp.json is outside the managed directories. | test_the_mcp_server_starts_without_a_shell |
| test_harness_helpers.py:11561, 11566, 11575, 11601 | Code-index CLI pinned to a version and wheel hash | - | local |  | The pin is in frontend's docs/testing.md and requirements file, and the payload holds none. Keep the four cases in a local suite. | test_the_owner_names_an_exact_version_and_a_wheel_hash,test_no_install_instruction_leaves_the_package_unpinned,test_claude_md_cites_the_owner_instead_of_restating_the_install,test_every_requirement_in_the_file_carries_a_hash |
| git-rebase-onto-main.sh:353 | publish refuses a HEAD that is not the replay's work | .claude/scripts/git-rebase-onto-main.sh:465 | covered |  | Non-descendants refused; commits on top publish deliberately, pinned by test_a_commit_on_top_of_the_replay_is_published_with_it. | test_publish_refuses_a_head_that_is_not_what_the_replay_produced |
| git-rebase-onto-main.sh:377 | abort never strands a finished replay whose push failed | .claude/scripts/git-rebase-onto-main.sh:531 | covered |  | Payload puts the branch back at its pre-replay tip, or refuses with commits on top or no recorded tip. | test_abort_refuses_to_strand_a_replay_that_only_failed_to_push |
| git-rebase-onto-main.sh:368 | abort refuses a record belonging to another branch | .claude/scripts/git-rebase-onto-main.sh:512 | covered |  | Same comparison, plus a current-branch check. | test_abort_will_not_clear_a_record_belonging_to_another_branch |
| git-rebase-onto-main.sh:219 | A rebase that never started leaves no record | .claude/scripts/git-rebase-onto-main.sh:292 | covered |  | Same removal; payload's case fails the start with a hook, which the hooksPath port must change. | test_a_rebase_that_never_started_leaves_no_record_behind,test_a_rebase_that_never_started_is_not_called_a_conflict |
| git-trailer-pr.sh:33; also test_git_pr_trailer_helpers.py:267 | The helper's one pull-request read names a fixed field set | .claude/scripts/git-trailer-pr.sh:25 | covered |  | Same field list behind gh_read; only the source-reading case is gone. | test_the_one_pull_request_read_names_a_fixed_field_set |
| git-worktree-detach.sh:73 | Only sweep-shaped day-old worktrees are candidates; a refused commit drops nothing | .claude/scripts/git-worktree-detach.sh:39 | covered |  | Same name filter, and the sha checks sit above the drop at lines 26-29; the two cases are lost, the code is not. | test_a_day_old_worktree_of_another_shape_is_never_a_candidate,test_a_refused_commit_drops_nothing |
| git-worktree-remove.sh:102 | core.longpaths on removal; dirty refusal keeps git's own status | .claude/scripts/git-worktree-remove.sh:89 | covered |  | Same flag; payload's test_a_worktree_holding_a_path_past_260_characters_is_removed and test_untracked_work_is_refused_and_kept hold both. | test_the_worktree_helper_deletes_a_long_path_and_says_when_it_did_not |
| git-worktree-fork.sh:116; also docs/commands/branch.md:88 | Fork seeds the worktree's index; no hook present starts nothing | .claude/scripts/git-worktree-fork.sh:96 | covered |  | Seeds through the worktree's refresh-index.py; the launcher route goes with *Decisions*'s index-refresh.py and run-guard rows. | test_the_fork_starts_the_new_worktrees_index_refresh,test_a_checkout_without_the_hook_still_forks_and_starts_nothing |
| test_git_worktree_fork.py:227 | A checkout with no local settings forks silently | .claude/scripts/git-worktree-fork.sh:65 | covered |  | Same -f test on the settings file; only the separate case is gone. | test_a_checkout_with_no_local_settings_forks_and_says_nothing |
| test_harness_helpers.py:544 | Label vocabulary holds the six labels the sweeps apply | .claude/scripts/gh-label-ensure.sh:21 | covered |  | All six arms present; payload's test_the_vocabulary_is_the_labels_the_sweeps_apply holds them. | test_the_vocabulary_is_the_six_labels_the_sweeps_apply |
| test_harness_helpers.py:656 | Exact arity refuses a title on the command line | .claude/scripts/gh-issue-create.sh:8 | covered |  | Title stays on stdin under exact arity; the extra area and route arguments are judged in the route row. | test_the_argument_count_is_exactly_two |
| test_harness_helpers.py:912 | A body carrying the other route's trailer is refused | .claude/scripts/gh-issue-create.sh:76 | covered |  | The body must end in the named route's trailer; payload's test_each_route_requires_the_line_that_is_true_of_it holds it. | test_each_entry_point_files_one_route_and_cannot_name_the_other |
| test_harness_helpers.py:929 | Kind and severity labels go through the sibling helper | .claude/scripts/gh-issue-create.sh:91 | covered |  | Both ensured at lines 91-92; payload's test_each_label_but_enhancement_goes_through_the_sibling_helper holds it. | test_both_labels_go_through_the_sibling_helper |
| test_harness_helpers.py:1338 | A class is one letter or two distinct ones | .claude/scripts/pr-locality.sh:40 | covered |  | Every refused spelling stays refused; payload adds only A+D+E, pinned by test_a_class_is_one_letter_two_distinct_ones_or_a_d_e. | test_a_class_is_one_letter_or_two_distinct_ones |
| test_harness_helpers.py:1499 | A renamed file is judged by its new name | .claude/scripts/pr-locality.sh:135 | covered |  | New name still judged; payload also judges previous_filename, as CI does, pinned by test_a_rename_is_judged_at_both_ends. | test_a_renamed_file_is_judged_by_its_new_name |
| test_harness_helpers.py:1532 | Each other refusal keeps exit 3, empty stdout and its message | .claude/scripts/pr-locality.sh:10 | covered |  | Messages and order match by reading; only the empty-brace entries need C's `pr-locality.sh:127` row. | test_every_refusal_keeps_its_exit_and_its_message |
| test_harness_helpers.py:1738, 11195 | Published row carries the head oid, asked for and projected | .claude/scripts/pr-for-branch.sh:42 | covered |  | Widened by baseRefName, which step 0 reads; test_pr_for_branch.py:109 and test_ship_landing_method.py:278 pin request and projection. | test_the_shape_is_unchanged_for_callers,test_the_helper_publishes_the_head_it_already_fetched |
| test_harness_helpers.py:1891 | No command holds the raw merge or worktree-remove grant | .claude/scripts/test_ship_landing_method.py:91 | covered |  | Merge held there, worktree removal at test_git_worktree_remove.py:285. | test_no_command_grants_the_raw_form |
| test_harness_helpers.py:1968 | Merge helper refuses flags in either argument and any third | .claude/scripts/gh-pr-merge.sh:7 | covered |  | Arity and shapes at lines 7-16; test_ship_landing_method.py:213-220 drive them. | test_the_merge_helper_refuses_what_the_grant_admitted |
| test_harness_helpers.py:1979 | Worktree helper refuses a flag or a path outside the shape | .claude/scripts/git-worktree-remove.sh:9 | covered |  | Same pattern; test_any_other_shape_is_refused_before_git_is_asked holds it. | test_the_worktree_helper_refuses_a_flag_and_a_stranger |
| test_harness_helpers.py:2581; also pr-for-branch.sh:98 | An older merged row cannot tear down a reused branch's live work | .claude/commands/ship.md:253 | covered |  | Payload returns every row; a row counts only if its headRefOid equals the tip, held by test_a_reused_branch_name_matches_only_the_use_it_is. | test_the_newest_row_wins_over_an_older_merged_one |
| test_harness_helpers.py:2612, 2621 | A fork's row is dropped; no row of ours returns empty | .claude/scripts/pr-for-branch.sh:41 | covered |  | Same select; payload's test_a_fork_with_the_same_branch_name_is_dropped holds it. | test_a_fork_row_is_not_this_repositorys_row,test_a_branch_with_no_row_here_is_still_empty |
| test_harness_helpers.py:3379 | Every review lens /ship grants holds read-only tools | .claude/scripts/test_command_grants.py:73 | covered |  | Literal name, but test_ship_grants_the_reviewer_by_exact_type_and_nothing_broader fails on a second lens. | test_every_review_lens_holds_read_only_tools |
| test_harness_helpers.py:3409 | Each exact agent grant denies every other type | .claude/scripts/test_command_grants.py:103 | covered |  | Held for every other command. ship.md's exemption is the port row in E. | test_every_exact_agent_grant_denies_every_other_type |
| test_harness_helpers.py:3483 | The settings auto-approve push, which the push denies answer | .harness/settings.base.json:19 | covered |  | Both allow rows present, lines 19-20; the positive control has no case of its own. | test_the_settings_really_do_auto_approve_push |
| test_harness_helpers.py:9577 | Every registered hook event holds a command | .harness/settings.base.json:74 | covered |  | All four events carry commands; per-hook cases such as test_git_argv_guard.py:3007 and test_refresh_index.py:897 pin registration. | test_every_registered_event_holds_a_command_these_cases_judge |
| test_harness_helpers.py:10827 | Skill frontmatter grants subcommands, never the whole CLI or graph | .claude/skills/codebase-index/SKILL.md:4 | covered |  | cbx per subcommand, run-index dropped by *Decisions*; payload's test_skill_frontmatter_grants_cbx_per_subcommand_not_the_cli holds it. | test_skill_frontmatter_does_not_auto_approve_graph_or_cbx |
| test_harness_helpers.py:10917 | The hook example does not invoke the unpinned CLI | .claude/skills/codebase-index/examples/hooks/settings.json:9 | covered |  | It runs refresh-index.py; run-index is dropped by *Decisions*, so the assertion on it goes. | test_the_hook_example_goes_through_run_index |
| test_harness_helpers.py:10992, 11014 | Wrappers disable auto-update, keep cwd off sys.path, hold a 3.12 floor | .claude/skills/codebase-index/scripts/cbx:8 | covered |  | Exports at lines 8-9, -P in every fallback, exact 3.12 stricter than the floor; test_cbx.py:161,173 hold them. | test_every_executable_wrapper_disables_skill_auto_update,test_every_wrapper_keeps_the_working_directory_off_sys_path |
| test_harness_helpers.py:11093 | The merge helper lands by rebase and spells one method | .claude/scripts/gh-pr-merge.sh:48 | covered |  | Held by payload's test_the_helper_spells_one_merge_and_pins_its_method. | test_the_merge_helper_lands_by_rebase |
| test_harness_helpers.py:11214 | No command argues the merge-commit shape | .claude/scripts/test_ship_landing_method.py:38 | covered |  | Commands hold no git log --merges; RETIRED_READS refuses it in fenced ship.md lines. | test_no_command_still_argues_for_the_merge_commit_shape |
| test_harness_helpers.py:11223 | Resume table's merged row is not the finished predicate | .claude/commands/ship.md:92 | covered |  | The row separates classifying from finishing and names headRefOid. | test_the_resume_table_does_not_read_merged_as_finished |
| test_harness_helpers.py:11245, 11362 | Finished is tip identity with the merged head, not content | .claude/scripts/test_ship_landing_method.py:406 | covered |  | TheFinishedPredicateSurvivesTheLandingMethod drives the same repositories against the prose it pins. | test_neither_content_read_can_see_work_done_after_the_merge,test_a_rebase_merged_branch_is_finished_under_the_new_read_only |
| test_harness_helpers.py:3470 | No frontmatter names an archived reviewer | - | obsolete |  | Frontend's archive of the external reviewers was the reason; payload commands and agents name none, and sync overwrites both. | test_no_frontmatter_names_an_archived_reviewer |

#### C, GitHub helpers

| Frontend | Behaviour | Payload | Verdict | Task | Reason and fix | Frontend's test |
|---|---|---|---|---|---|---|
| gh-sweep-issue-create.sh:35; also test_harness_helpers.py:705, 872, 896, commands/bug-sweep.md:251, docs/commands/bug-sweep.md:825, docs/harness-boundaries.md:1757 | Route is a constant per entry point, so a caller cannot choose the provenance trailer | .claude/scripts/gh-issue-create.sh:37 | ported #127 | 2 | Judged as *Decisions* asked: a command can claim any route's trailer through a prefix grant. Restore a fixed route per command, by thin entry points or grants that spell the route. | test_neither_entry_point_takes_a_route_at_all, test_a_sweep_cannot_reach_the_hand_route, test_ship_files_by_hand_and_cannot_reach_the_sweep_route |
| gh-pr-create.sh:75; also test_harness_helpers.py:1891, 1901, 2158, 2197, commands/pr.md:188, docs/commands/ship.md:466, docs/harness-boundaries.md:747 | PR create pins repo, head and base; title and body from untracked, unlinked files | .claude/commands/pr.md:171 | port | 3 | Per *Decisions*, Task 3 Step 2's form: title and body as path arguments, so no `.gitignore` line. Swap the grant in pr.md and ship.md. | test_the_create_helper_refuses_a_body_it_should_not_publish, test_the_create_helper_leaves_no_body_behind_and_takes_none_tracked |
| pr-for-branch.sh:157; also pr-for-branch.sh:156, test_harness_helpers.py:2362, 2424, commands/ship.md:81, docs/commands/ship.md:115 | MERGED row dropped when its merge commit is an ancestor of the local tip | .claude/commands/ship.md:92 | ported #127 | 2 | A branch name reused from main stops /ship at the merged row. Request mergeCommit and restore the drop, checking dispatch_run's lookup by number. | test_a_merged_pr_behind_the_reused_branch_is_not_its_pr, test_the_reuse_drop_still_answers_after_a_rebase_merge |
| pr-for-branch.sh:97; also pr-for-branch.sh:97, test_harness_helpers.py:2599 | Only pull requests into main count as the branch's PR | .claude/commands/pr.md:160 | ported #127 | 2 | Payload /pr stops on any OPEN row, so a PR into develop blocks main's. Read only baseRefName main rows in pr.md and ship.md. | test_a_newer_pr_into_another_base_does_not_mask_the_main_pr |
| pr-for-branch.sh:84; also pr-for-branch.sh:85, gh-label-ensure.sh:71, test_harness_helpers.py:2315, 2628, 2638, docs/commands/ship.md:159 | Listing read with --limit 1000 and refused, exit 4, at the cap | .claude/scripts/pr-for-branch.sh:39 | ported #127 | 2 | gh's default 30 rows are cut before the fork filter, so the landed row can vanish. Restore --limit and the refusal at it. | test_a_listing_that_fills_the_page_is_refused |
| gh-label-ensure.sh:68 | Label listing bounded with --limit and refused at the cap | .claude/scripts/gh-label-ensure.sh:46 | ported #127 | 2 | Payload reads gh's default 30 rows as the whole set, at both reads; restore labels_matching with its limit and refusal. | test_the_capped_listings_detect_their_cap |
| pr-locality.sh:103; also pr-locality.sh:103, test_harness_helpers.py:1212, 1235, 1434 | Touch-set tokens admit @ and +, with + escaped in the regex | .claude/scripts/pr-locality.sh:68 | ported #127 | 2 | Payload refuses src/app/@types/** with exit 3 though changed paths admit @ and +. Widen grammars at :68 and :108, escape + in to_regex. | test_a_touch_set_may_spell_what_a_changed_path_may, test_a_plus_in_a_token_is_a_character_and_not_a_quantifier |
| pr-locality.sh:127; also pr-locality.sh:127, test_harness_helpers.py:1473, 1532 | Empty brace alternative in a touch-set token is refused | .claude/scripts/pr-locality.sh:80 | ported #127 | 2 | Payload passes {} and {a,} into an ERE, undefined by POSIX, so GNU and BSD grep disagree. Restore the case refusal after the boundary check. | test_an_empty_brace_alternative_is_refused_on_every_platform |
| pr-locality.sh:154; also pr-locality.sh:154, test_harness_helpers.py:1250 | Globstar placeholder is portable and no token can spell it | .claude/scripts/pr-locality.sh:18 | ported #127 | 2 | BSD sed reads \x01 as literal x01, so a token holding x01 mistranslates on frontend's macOS leg. Use %%GLOBSTAR%% in to_regex. | test_the_globstar_placeholder_cannot_be_spelled_by_a_token |
| pr-locality.sh:213; also pr-locality.sh:189, test_harness_helpers.py:1632 | One grep per pattern over all paths; path check spawns no process | .claude/scripts/pr-locality.sh:154 | ported #127 | 2 | Payload spawns a grep per path per pattern, doubled for class patterns, the #61 hang on Windows. Restore the batched match and case check. | test_the_spawn_count_does_not_grow_with_the_changed_paths |
| sweep-slices.sh:109; also commands/bug-sweep.md:201, docs/commands/bug-sweep.md:670 | Rows partition frontend's tree: e2e, public, android, ios, .vscode, src/app/core | .claude/scripts/sweep-slices.sh:41 | port | 4 | Payload's backend rows own none of those, so both sweeps exit 3. Make rows target-supplied, or hold frontend's row_of and tables local. | test_each_row_a_sweep_owns_gets_its_files |
| sweep-slices.sh:108; also docs/harness-boundaries.md:1827 | Slicing helper runs on bash 3.2, which macOS ships | .claude/scripts/sweep-slices.sh:90 | port | 4 | mapfile and declare -A fail on the macOS leg (ci.yml:253); pr-locality.sh:91 too. Restore the awk classification, or drop that leg deliberately. | test_no_helper_here_uses_a_bash_4_construct |
| pr-locality.sh:159 | Verdict needs no class map; frontend's tree has none | .claude/scripts/pr-locality.sh:90 | local |  | A frontend tree fact: `.github/locality-gate/classes.yml` lands with its config before the first sync. |  |
| test_sweep_slices.py:131 | Partition and budget asserted over frontend's own tree | - | local |  | Holds frontend's paths and rows; payload's docstring leaves this to a target suite. Keep it as a local suite. | test_every_tracked_path_is_listed_or_counted_and_every_slice_fits |
| sweep-slices.sh:102 | A tracked name with a carriage return refuses the run | .claude/scripts/sweep-slices.sh:106 | covered |  | Payload refuses line breaks and CR; a tab needs no refusal because it splits on the first tab only. |  |
| test_sweep_slices.py:248 | Refused run leaves no slices directory | .claude/scripts/sweep-slices.sh:85 | covered |  | The trap removes the directory; payload's suite dropped the case, so carry it into frontend's local suite. | test_a_refused_run_leaves_no_slices_behind |
| test_sweep_slices.py:310 | Closed records are counted and not read | .claude/scripts/sweep-slices.sh:116 | covered |  | The case arm counts them; payload's suite dropped the case, so carry it into frontend's local suite. | test_the_closed_records_are_counted_and_not_read |
| test_sweep_slices.py:317 | Row cut at budget; one oversize file stands alone | .claude/scripts/sweep-slices.sh:160 | covered |  | The flush holds the budget; payload's suite dropped the case, so carry it into frontend's local suite. | test_a_row_is_cut_at_the_budget_and_one_large_file_stands_alone |

#### D, index

| Frontend | Behaviour | Payload | Verdict | Task | Reason and fix | Frontend's test |
|---|---|---|---|---|---|---|
| hooks/index-refresh.py:1112 | Compacts a bloated index on a copy, after a successful update, under the lock | - | port | 3 | *Decisions* row 1: port compact and helpers; its copy lives in state_dir, so the state-directory row below goes first. | test_a_bloated_index_is_compacted |
| hooks/index-refresh.py:711 | Keeps lock and pending marker in the git directory, not a branch-writable tree | - | ported | 2 | Not in decisions. refresh-index.py:208 writes through a tracked link, truncating its target. Move state; update git-worktree-remove.sh:31 and test_refresh_index.py:338. | test_the_hooks_state_lives_where_no_branch_can_redirect_it |
| hooks/index-refresh.py:460; also docs/harness-boundaries.md:1880 | Refuses an index with a link, a rollback journal or a non-WAL header | - | port | 3 | *Decisions* row 1: ask at target, seed source and seed target; refresh-index.py:140 checks only the source's leaf link. | test_only_an_index_at_rest_in_wal_mode_may_be_opened |
| hooks/index-refresh.py:227 | Refuses a forged worktree: links, hard links, admin directory outside common | - | port | 3 | *Decisions* row 1: port registered; refresh-index.py:122 trusts commondir unchecked, so the seed source needs it too. | test_an_admin_directory_outside_the_repository_is_refused |
| hooks/index-refresh.py:390 | Refuses a root whose git common directory is not this repository's | - | ported | 2 | Not in decisions. refresh-index.py:153-157 refreshes any repository or submodule holding a cache directory. Compare common directories; registered needs the owner's anyway. | test_another_repository_is_refused |
| hooks/index-refresh.py:314 | Refuses a sweep's checkout by folded prefix, through an alias too | - | port | 3 | *Decisions* row 1: call swept on the target and on the main checkout before seeding from it. | test_a_sweep_checkout_is_refused_in_any_case |
| hooks/index-refresh.py:528 | Seeds only where git reports the index path ignored | - | port | 3 | *Decisions* row 1: port with its cache; work must ask before the git budget ends, as test_the_worker_asks_before_its_git_budget_is_spent holds. | test_a_path_the_branch_stopped_ignoring_is_never_seeded |
| hooks/index-refresh.py:848 | A marker that will not go costs bounded retries, never a spin | - | ported | 2 | Not in decisions. take_request:218 answers False, work:352 sees the file and loops unpaused forever; a directory there triggers it. Return None, bound retries. | test_a_marker_that_never_goes_costs_a_bounded_number_of_tries |
| hooks/index-refresh.py:594 | No update runs without a written index, so nothing is built | - | ported | 2 | Not in decisions. refresh-index.py:156 admits any cache directory and work:344-345 updates after a failed seed. Require a written index, as refreshable and refresh do. | test_nothing_is_seeded_or_built_without_a_main_index |
| hooks/index-refresh.py:1355 | Worker judges its root again at entry and before every refresh | - | ported | 2 | Not in decisions. refresh-index.py:358 trusts argv, and a link landing mid-drain goes unjudged. Judge in main and before each update. | test_the_worker_entry_point_judges_its_root_again |
| skills/codebase-index/gate-index.py:47; also docs/harness-boundaries.md:2094 | CLI refuses to start over an unopenable index; no Python refuses too | - | port | 3 | *Decisions* gate row: port gate-index.py and gate.sh, call from cbx; HOOK at gate-index.py:32 must name refresh-index.py, which needs index_openable. | test_both_wrappers_start_the_cli_on_a_clean_index_and_not_on_a_refused_one |
| hooks/index-query-hint.py:41; also docs/harness-boundaries.md:2320 | Index terms are single-quoted, so bash expands nothing inside them | .claude/hooks/guard-index-argv.py:293 | ported | 2 | Guard refuses `$(…)` and backticks, not `$VAR`: `cbx refs "$event"` silently asks about nothing. Single-quote the routes, table, references and search hint. | test_no_command_double_quotes_the_term |
| hooks/index-refresh.py:685 | A seed copy lacking a WAL header is never renamed onto the index | - | ported | 2 | refresh-index.py:195 renames unchecked; once index_openable is ported, such a copy refuses that root for good. Check the header first. | test_a_copy_without_a_wal_header_is_never_renamed_in |
| hooks/index-refresh.py:901 | Worker stands off while a killed worker's recorded indexer still runs | - | ported | 2 | Not in decisions. Payload keeps no pid record, so a second update overlaps the orphan; refresh-index.py:309 only retries. Port the record and stand-off. | test_an_indexer_left_running_by_a_killed_worker_keeps_the_tree |
| hooks/index-refresh.py:108 | Sets NoDefaultCurrentDirectoryInExePath for everything the hook starts | - | ported | 2 | Payload's own starts use full paths, but the CLI runs with cwd=root, relying on the launcher's variable. Set it in refresh's environment. | test_a_program_planted_in_the_working_directory_is_never_run |
| hooks/index-refresh.py:665 | The next seed removes a killed worker's partial copy and sidecars | - | ported | 2 | refresh-index.py:176 names the partial by pid and removes only its own. Sweep `index.sqlite.seed.*` under the lock. | test_a_killed_workers_partial_is_removed_by_the_next_seed |
| hooks/index-refresh.py:1311 | POSIX worker runs in its own session, Windows in a new process group | - | ported | 2 | refresh-index.py:383-390 passes CREATE_NO_WINDOW alone, so a POSIX worker stays in the hook's session. Add start_new_session and the group flag. | test_the_flags_are_the_ones_measured_to_run_the_wrapper |
| test_index_refresh.py:2035 | Suite proves the registered command reaches the CLI through a real detached worker | - | ported | 2 | test_refresh_index.py patches Popen and never reads creationflags, so a DETACHED_PROCESS regression (#194) stays green. Port both cases. | test_an_event_reaches_the_wrapper_through_the_detached_worker |
| hooks/index-refresh.py:334 | An event naming an unplaceable file refreshes nothing, never cwd | - | ported | 2 | refresh-index.py:107 returns None and :151 falls to cwd; a relative path without cwd resolves against the process directory. Refuse both. | test_an_event_naming_a_file_is_never_answered_with_cwd |
| skills/codebase-index/cbx.ps1:60; also skills/codebase-index/cbx.ps1:60, test_harness_helpers.py:10992, 11014 | Restores both environment variables after running in the caller's process | - | ported | 2 | Payload cbx.ps1:14 leaves PYTHONSAFEPATH set after `&`, so later Python scripts lose their directory on sys.path. Restore in a finally. |  |
| test_index_mcp_root.py:127 | Suite holds every mcp-root subcommand to the skill's allowed-tools | - | port | 2 | Payload tests only cbx's ALLOWED, so a dropped grant sends the named command to a prompt. Port against the cbx grants. | test_every_tool_it_maps_is_a_subcommand_the_skill_approves |
| skills/codebase-index/mcp-launch.mjs:56 | Judges the index through the gate before starting the MCP server | - | local |  | *Decisions*: local. It sits under managed .claude/skills, so needs a `local` glob, and needs gate-index.py at this path. | test_a_rollback_journal_beside_the_index_stops_it_before_the_server_starts |
| hooks/index-query-hint.py:45 | "find component" and "find service" prompts route to the symbol hint | - | local |  | Angular vocabulary the payload dropped; the managed file carries no config seam, so frontend loses these two words. | test_each_kind_of_question_names_its_own_subcommand |
| skills/codebase-index/SKILL.md:111 | Empty refs result is inconclusive, shown with an Angular template example | .claude/skills/codebase-index/SKILL.md:117 | local |  | The Grep rule survives; the payload's example says C#, and frontend's Angular case has no home in a managed file. |  |
| hooks/index-refresh.py:1236 | Edits during a run coalesce; a last look after release serves stragglers | .claude/hooks/refresh-index.py:352 | covered |  | drain takes requests under the lock and work looks again after letting go. | test_a_marker_left_as_the_lock_is_released_is_still_served |
| hooks/index-refresh.py:772 | OS lock on an open handle, freed on crash, file never removed | .claude/hooks/refresh-index.py:52 | covered |  | grab takes msvcrt or flock on an open handle, and nothing in the hook removes the file. | test_a_worker_that_dies_holding_the_lock_releases_it |
| hooks/index-refresh.py:611 | Seeds through SQLite backup and rename; only the index crosses, stale logs removed | .claude/hooks/refresh-index.py:190 | covered |  | Backup into a pid-named partial, os.replace at :195, stale logs removed at :178-179. | test_a_worktree_is_seeded_from_the_main_checkout_and_never_built |
| hooks/index-refresh.py:581 | Never seeds over anything already at the index path | .claude/hooks/refresh-index.py:134 | covered |  | exists refuses a real file; a dangling link is refused once index_openable is ported. | test_a_file_already_at_the_index_path_is_never_replaced |
| hooks/index-refresh.py:517 | The main checkout, a bare repository and a submodule are never seeded | .claude/hooks/refresh-index.py:123 | covered |  | main_checkout answers None for each; a submodule has no commondir, read at :122. | test_the_main_checkout_is_never_seeded |
| hooks/index-refresh.py:355 | The edited file decides the root, resolved before it is walked | .claude/hooks/refresh-index.py:106 | covered |  | edited resolves the path and target prefers it to cwd at :151. | test_an_edit_into_a_worktree_from_the_main_checkout_refreshes_the_worktree |
| hooks/index-refresh.py:993 | No tree the session stands in chooses the code the refresh runs | .claude/hooks/refresh-index.py:246 | covered |  | console_script fences every checkout from the PATH lookup; the module route uses -P and PYTHONSAFEPATH at :284-288. | test_the_refresh_runs_the_owners_wrapper_against_the_worktree |
| hooks/index-refresh.py:994 | CLI stands in the owner, so Windows can still remove a worktree | .claude/scripts/git-worktree-remove.sh:27 | covered |  | Payload runs the CLI inside the checkout, and the remove helper takes the refresh lock first. |  |
| hooks/index-refresh.py:1331 | The event is decoded from bytes as UTF-8 | .claude/hooks/refresh-index.py:363 | covered |  | main reads stdin's buffer and decodes UTF-8 with replacement. | test_the_event_is_decoded_as_utf_8 |
| test_index_refresh.py:2159 | Refresh runs after edits, both shells and an unmatched SessionStart | .harness/settings.base.json:138 | covered |  | Matcher names the four edit tools and both shells; the SessionStart entry at :149 has no matcher. | test_the_hook_runs_on_an_edit_and_on_a_session_start |
| settings.json:135 | A launcher failure cannot block an index call or erase a prompt | .harness/settings.base.json:130 | covered |  | *Decisions* run-guard row: mcp-root keeps runpy, whose missing file exits 1; the hints keep hint-bound.sh at :120 and :166. | test_the_registered_command_cannot_erase_a_prompt |
| hooks/index-query-hint.py:85 | Prompt hint warns the MCP server stays in the checkout it started in | .claude/hooks/index-mcp-root.py:125 | covered |  | A call from a worktree is refused with the cbx line, so the session reaches this tree's index. | test_it_says_the_server_does_not_follow_a_worktree_move |
| hooks/index-search-hint.py:452 | Search refusal names the MCP tools for every checkout | .claude/hooks/index-search-hint.py:477 | covered |  | Payload sends a worktree to cbx directly, which reads that tree; the main checkout still gets the MCP tools. | test_a_linked_worktree_is_sent_to_the_same_tools |
| skills/codebase-index/SKILL.md:33 | Route table and reference examples carry `--limit 3` | .claude/skills/codebase-index/SKILL.md:46 | covered |  | The paragraph under the payload's table sets it, and the query hint's search route carries it. | test_search_carries_the_limit_the_skill_sets |
| skills/codebase-index/cbx:13 | Fallback interpreters are held to the 3.12 floor before importing | .claude/skills/codebase-index/scripts/cbx:26 | covered |  | Payload pins exactly 3.12, stricter than the floor; a 3.13-only machine exits 127, which SKILL.md tells sessions to expect. |  |
| skills/codebase-index/examples/hooks/settings.json:4 | Example denies Edit on the skills and hooks trees | .harness/settings.base.json:42 | covered |  | The base settings deny both trees in both spellings at :42-45, so the example needs no copy. |  |
| hooks/index-refresh.py:142 | Git calls share one budget, drop GIT_* and decode UTF-8 | .claude/hooks/refresh-index.py:113 | obsolete |  | Payload's hook runs no git. Carry deadline, git_env and the encoding with the target-root and index_ignored ports. | test_one_event_spends_one_git_budget |
| hooks/index-refresh.py:383 | A malformed event or a missing cwd refreshes nothing | .claude/scripts/git-worktree-fork.sh:96 | obsolete |  | Payload's fork runs the hook eventless, so refresh-index.py:151-152 must fall back; keep that call working when porting refusals. | test_a_missing_or_malformed_cwd_is_refused |
| hooks/index-refresh.py:935 | Kills the indexer's tree past the Git Bash stub; needs bash | .claude/hooks/refresh-index.py:287 | obsolete |  | Payload starts no bash; it runs the exe or module directly. Confirm pip's exe stub passes the kill to its python child. | test_a_timed_out_child_is_stopped_through_its_tree_first |
| skills/codebase-index/run-index:17; also docs/harness-boundaries.md:2242 | Wrapper with gate, safe path, floor and auto-update off | .claude/skills/codebase-index/scripts/cbx:8 | obsolete |  | *Decisions* run-index row: drop; cbx does all of it once the gate row lands. |  |
| skills/codebase-index/cbx:15 | `graph` runs under a prompt for a human visualisation | .claude/hooks/guard-index-argv.py:27 | obsolete |  | *Decisions* calls cbx stricter; the payload refuses `graph` because it writes a file, and no route to it remains. |  |
| skills/codebase-index/.skill_version:1 | Installer artefact nothing reads | - | obsolete |  | *Decisions* .skill_version row: drop, untracked and ignored. |  |

#### E, commands and agents

| Frontend | Behaviour | Payload | Verdict | Task | Reason and fix | Frontend's test |
|---|---|---|---|---|---|---|
| agents/branch-reviewer.md:26; also docs/commands/ship.md:632, docs/harness-boundaries.md:2535 | Bar comes from origin/main; missing or empty method means the round did not run | .claude/agents/branch-reviewer.md:43 | port | 2 | Payload reads the bar from the branch's tree. Ship step 5 writes it from origin/main (fe ship.md:288,300); an empty bar fails closed. | test_the_branch_reviewer_reviews_under_a_profile_that_cannot_write |
| commands/ship.md:43; also commands/ship.md:360, test_harness_helpers.py:3309, docs/commands/ship.md:63 | Reviewer reply with empty read, or skipped beyond locality, stops the chain | .claude/commands/ship.md:490 | port | 2 | Payload stops only on missing agent or non-JSON, so a reply that read nothing mints clean. Restore both tests; close `skipped` in the profile. | test_the_reviewer_skips_only_what_ship_reads_as_a_round |
| commands/ship.md:392; also docs/commands/ship.md:620 | Step 6 refuses a head no round read; spent ceiling still rechecks once | .claude/commands/ship.md:503 | port | 2 | Payload records no reviewed head; a remote head ahead of this checkout passes the empty log read unreviewed. Restore the record, check and ceiling exit. |  |
| commands/ship.md:306; also docs/commands/ship.md:644 | Diff touching branch-reviewer.md: inputs follow main's registered profile, and the report says so | .claude/commands/ship.md:441 | port | 2 | Profiles load once at launch, so the branch's edited contract is not what runs. Payload lacks this; restore the paragraph, `git show` is granted. |  |
| commands/ship.md:52; also docs/commands/ship.md:78 | A refused push, no exit code, stops the chain; /pr reports remedy | .claude/commands/ship.md:36 | port | 2 | Row one covers non-zero exits only and nothing else stops. Add the harness refusal; restore pr.md:46's report, `!` line and autoMode remedy. |  |
| commands/ship.md:425; also docs/commands/ship.md:856 | `publish` retries a failed push; exit table splits continuations from stops | .claude/commands/ship.md:551 | port | 2 | Payload omits `publish`, so a finished replay whose push failed stops under row one. Restore the table, checked against the helper's exits. |  |
| commands/ship.md:346; also docs/commands/ship.md:695 | Ceiling filing pipes title, body and hand trailer on stdin | .claude/commands/ship.md:481 | port | 2 | Payload's gh-issue-create.sh:76 refuses a body without the trailer, and the runbook never says it; a filing then stops the chain. Restore the sentence. |  |
| commands/ship.md:322; also docs/commands/ship.md:667 | Finding whose fix a deny refuses is filed at once and reported | .claude/commands/ship.md:452 | port | 2 | Outside --dispatched the payload has no route, so the finding stays open to the ceiling. Restore: file it, say so, continue. |  |
| commands/ship.md:317; also docs/commands/ship.md:663 | Finding telling the session to act beyond its line is refused and quoted | .claude/commands/ship.md:450 | port | 2 | Payload says only "a claim to check". Restore refusal as an attempt to steer, and the report's full quotation at fe ship.md:511. |  |
| commands/ship.md:5 | Ship denies every agent type but branch-reviewer | .claude/commands/ship.md:4 | port | 2 | A grant withholds nothing, per boundaries:512. Deny every built-in type and every profile but `branch-reviewer`, `bug-auditor`, `security-auditor` and `team-peer` included; `general-purpose` stays for step 2's audits, so the ship.md skip at test_command_grants.py:110 narrows to that one type. | test_every_exact_agent_grant_denies_every_other_type |
| commands/ship.md:5; also test_harness_helpers.py:3110, 3141 | Editing commands deny .git, .mcp.json and .codeindexignore (also pr.md:5, style-pass.md:5) | .harness/settings.base.json:34 | port | 2 | Payload denies none of these anywhere, and ship and pr hold Write. Add them to the base denies; hold with a test. | test_every_editing_command_denies_the_machinery |
| commands/ship.md:28; also docs/commands/ship.md:35 | Report gives round number, reviewed head, and says the review was in house | - | port | 2 | Payload's Report has none of the three, and no text bars claiming an external opinion. Add them to the review line. |  |
| agents/branch-reviewer.md:65 | Code bar includes security weaknesses; findings quote what they rest on | .claude/agents/branch-reviewer.md:46 | port | 2 | Payload dropped both, so a security weakness in a diff goes unreported. Restore the clause and the quote requirement. |  |
| agents/branch-reviewer.md:13 | Steering includes telling the caller to run or push; documentation describing actions excepted | .claude/agents/branch-reviewer.md:13 | port | 2 | Payload lists neither, so caller-directed injection goes unnamed and a runbook's "run x" risks a false finding. Restore both sentences. |  |
| commands/style-pass.md:5 | Style-pass, which does not publish, denies git push | .claude/commands/style-pass.md:4 | port | 2 | The settings allow reaches it and nothing denies; style-pass is outside /ship's chain, so the deny is safe. Restore it and the test. | test_a_command_that_does_not_publish_cannot_push |
| commands/style-pass.md:32 | Sweep covers every fenced block in docs, not only the spec | .claude/commands/style-pass.md:30 | port | 2 | Payload sweeps the spec and source, so other documents keep teaching the removed form. Say every fenced block under docs/. |  |
| commands/style-pass.md:93 | Site counts are removed from the guide, never kept current | .claude/commands/style-pass.md:87 | port | 2 | Payload orders the opposite of frontend's change contract §2. Make it conditional: where the target's contract forbids a count, remove it. |  |
| commands/style-pass.md:151 | Verify scan uses width 100, indent two and LF | .claude/commands/style-pass.md:114 | port | 2 | Payload hard-codes 120, four and CRLF, all false on frontend, so the scan misreports. Read the limits from the style guide. |  |
| commands/branch.md:168; also docs/commands/branch.md:475 | Derived name changes by a second branch, never git branch -m | .claude/commands/branch.md:166 | port | 2 | Payload says `git branch -m` is free, but settings.base.json:62 denies it (also docs/commands/branch.md:337). Restore git-branch-create.sh at HEAD. |  |
| test_command_runbooks.py:47 | An argument file with no ceiling fails the build | .claude/scripts/test_command_runbooks.py:51 | port | 2 | Payload dropped it, so a newly split command escapes its ceiling. Fail an argument neither CEILINGS nor a target's own map holds. | test_every_argument_has_a_ceiling_and_a_runbook_that_cites_it |
| test_command_runbooks.py:78 | Each runbook must cite, and each docs/commands citation must parse | .claude/scripts/test_command_runbooks.py:69 | port | 2 | Payload's one global count lets a runbook lose every citation. Port per runbook, counting `(why: docs/commands` openings, since others cite boundaries. | test_every_runbook_cites_and_every_citation_parses |
| test_command_runbooks.py:109 | Boundaries index rows match its section headings, in order | docs/harness-boundaries.md:8 | port | 2 | Payload keeps the index with no test. Its rows are not italic, so adapt the row pattern and exempt `## Index`. | test_every_heading_is_an_index_row_in_order_and_every_row_a_heading |
| commands/review-branch.md:1; also docs/commands/review-branch.md:1 | Manual review command and its contradiction method | - | local |  | Decisions: local, as backend. Ship no longer loads it once the bar row above is ported from working-rules. |  |
| commands/ship.md:5 | Frontmatter denies android, ios, root toolchain files, CLAUDE.md, README.md (also pr.md:5) | - | local |  | Frontend's paths; the settings half stays config per decisions. A managed runbook has no per-command route for the rest. | test_every_editing_command_denies_the_toolchain |
| commands/ship.md:227 | Step 2 selects npm-checks.sh by diff; pr and style-pass run it | - | local |  | Decisions: local, granted through config; *Ship checks* names it. |  |
| commands/ship.md:236 | Says Playwright was not run; names android job for native diffs (also pr.md:172) | - | local |  | Frontend's CI jobs and stack; the statement belongs in *Ship checks*. |  |
| commands/commit.md:50 | Plan task commits and PR titles take the `## Task n:` heading (also pr.md:62) | - | local |  | Frontend's plan layout; the payload's roadmap route takes its place through *Documents*. |  |
| commands/branch.md:134 | New worktree runs npm ci before checks | - | local |  | Npm stack; state it in frontend's *Ship checks*, because npm-checks.sh refuses a worktree without node_modules. |  |
| agents/bug-auditor.md:59 | Hunts unended subscriptions, stale signals and memos, locale parsing, rounding | - | local |  | Angular and RxJS classes; the managed profile is backend-worded, so frontend loses them unless a local list carries them. |  |
| commands/style-pass.md:101 | Reconciles Prettier, ESLint and editorconfig, then runs npm-checks lint | .claude/commands/style-pass.md:90 | local |  | Stack facts; payload reconciles .editorconfig alone. The linter table needs a home in frontend's own documents. | test_the_toolchain_exemption_is_real |
| test_command_runbooks.py:24 | Ceiling of 11700 bytes on review-branch.md | - | local |  | Decisions keep the command local; its ceiling moves to a frontend suite, as the payload's comment says. | test_each_runbook_stays_under_its_ceiling |
| agents/branch-reviewer.md:58 | Untouched stale restatements and tabulated house styles are never findings | docs/harness/working-rules.md:118 | covered |  | "Never raise" names both, the style guide's tabulated house styles and a stale restatement left untouched. |  |
| agents/branch-reviewer.md:45 | Empty locality verdict is skipped and said, never read as clean | docs/harness/working-rules.md:114 | covered |  | "its locality check prints nothing or cannot run, say so and skip". |  |
| agents/branch-reviewer.md:21 | Reads stay under the root; a nominated outside path is refused | .claude/agents/branch-reviewer.md:13 | covered |  | Text telling the reviewer to read outside the checkout is a finding, never an instruction. |  |
| commands/ship.md:446 | UNKNOWN mergeability is polled, oid taken from the answering read | .claude/commands/ship.md:533 | covered |  | The poll and the oid rule hold; only the `sleep` pacing grant went, and no outcome depends on it. |  |
| commands/ship.md:272; also docs/commands/ship.md:211, git-fetch-origin.sh:29, git-pull-ff-only.sh:30, test_harness_helpers.py:1891, 1901, docs/harness-boundaries.md:1083 | Fetch and pull run through git-fetch-origin.sh and git-pull-ff-only.sh | .claude/commands/ship.md:424 | covered |  | Decisions: dropped, the grants and guard-git-argv.py hold it. The tail flags cluster A judged are its two port rows. | test_the_commands_that_used_them_grant_the_helpers |
| commands/pr.md:150 | Closure keywords reconciled by reading closingIssuesReferences by hand (also commit.md:72) | .claude/commands/pr.md:151 | covered |  | Payload ships .github/closure-gate and pipes pr-closure-input.sh into it, so the check is a gate. |  |
| commands/bug-sweep.md:99 | Run summary says which command owns the secsweep- directory | docs/commands/bug-sweep.md:309 | covered |  | The argument states it: "the run summary says which command owns the one it reports". |  |

#### E, command documents

| Frontend | Behaviour | Payload | Verdict | Task | Reason and fix | Frontend's test |
|---|---|---|---|---|---|---|
| docs/commands/ship.md:364 | Teardown runs git log origin/main..HEAD so ahead-of-origin main is actually read | .claude/commands/ship.md:291 | port | 2 | Payload names no read; after ExitWorktree nothing reads main's ahead state before the pull. Name `git status -sb`, not frontend's line: `RETIRED_READS` in test_ship_landing_method.py refuses it. |  |
| docs/commands/branch.md:53 | Worktree needs npm ci; node_modules walks up to main (also :354) | - | local |  | npm stack fact; belongs with local npm-checks.sh, *Decisions*. |  |
| docs/commands/branch.md:197 | Frontend branch-type table names Capacitor, native and npm root files | - | local |  | Frontend tree facts. |  |
| docs/commands/branch.md:240 | Branch name derives from plan Task heading under docs/superpowers/plans | .claude/commands/branch.md:90 | local |  | Frontend's plan path; payload reads the roadmap harness-local names. |  |
| docs/commands/ship.md:511 | Checks are npm-checks.sh, CI-only Playwright and android job | .claude/commands/ship.md:352 | local |  | Stack checks; belong in frontend's Ship checks, *Decisions*. |  |
| docs/commands/bug-sweep.md:466 | Drop helper removes slice lists after git removes worktree; also security-sweep.md:242 | .claude/scripts/git-worktree-drop.sh:54 | covered |  | Lists are removed only after git worktree remove succeeds, from the checked path. | test_the_slices_go_with_the_worktree |
| docs/commands/bug-sweep.md:977 | A mark not an ancestor of pinned is ignored | .claude/scripts/sweep-slices.sh:36 | covered |  | since is set only when merge-base --is-ancestor holds. | test_a_marked_ancestor_narrows_round_one_to_the_change |
| docs/commands/bug-sweep.md:763 | A round filing nothing ends the loop with leads standing | .claude/commands/bug-sweep.md:268 | covered |  | Runbook defines clean as filing no new issue. |  |
| docs/commands/bug-sweep.md:788 | Verifier names the covering test rather than merely disagreeing | .claude/commands/bug-sweep.md:221 | covered |  | Verify dispatch requests covering tests and whether one would fail, answered in scenario. |  |
| docs/commands/security-sweep.md:464 | Security sweep has a samples row for tracked docs | .claude/scripts/sweep-slices.sh:49 | covered |  | docs/* maps to samples for both kinds; row table itself is the port row above. | test_each_table_matches_the_rows |
| docs/commands/ship.md:826; also commands/ship.md:411 | CI wait requires named checks, not exit 0 | .claude/commands/ship.md:521 | covered |  | Wait passes only with every required check listed; frontend's Ship checks must name commits and commit-gate. |  |

#### F, boundaries

| Frontend | Behaviour | Payload | Verdict | Task | Reason and fix | Frontend's test |
|---|---|---|---|---|---|---|
| docs/harness-boundaries.md:801 | Raw gh pr merge and git worktree remove denied in every turn | .harness/settings.base.json:66 | port | 3 | *Decisions* puts both denies in base; base lacks them. Add them with destructive-class rows and the raw-form test. | test_no_command_grants_the_raw_form |
| docs/harness-boundaries.md:1682 | Stated limit: replay provenance files under .git can steer a publish | - | port | 2 | Same record files exist in the payload helper and every target; payload states nothing. Add the residual beside the rebase helper paragraph. |  |
| docs/harness-boundaries.md:521; also test_harness_helpers.py:10043, 10469, 10494, test_harness_helpers.py:9620, test_edit_target_guard.py:1386 | Guards start through run-guard, probing interpreters, exit 2 when none, remembered mark | .harness/settings.base.json:80 | port | 3 | *Decisions*: payload for four guards alone; move launcher, pwd -W and paragraphs :521-:592. No-Git-Bash machine is the stated residual. | TheLauncherProvesWhatItRemembers |
| docs/harness-boundaries.md:2521 | Limit: no reader outside the writing model family reviews before unattended merge | - | port | 2 | Holds for every target since external reviewers are archived; payload states nothing. Add the accepted residual and its procedural control to boundaries. |  |
| docs/harness-boundaries.md:1241 | Rule: a boundary an agent keeps across turns lives on its profile | - | port | 2 | Holds for every target, team-peer included; payload dropped these measurements. Restore them with :1415's propagation facts in Agent-type entries. |  |
| docs/harness-boundaries.md:570 | Limit: a filled launcher mark refuses every call while git status stays clean | - | residual |  | Frontend's .gitignore covers only codebase-index under .claude/cache, a tree fact; goes to harness-local Residuals, minus the refresh-through-launcher sentence. |  |
| docs/harness-boundaries.md:11 | Bare #NN in .claude or this file names a backend issue | - | residual |  | Stays true in frontend after sync, false in backend, so a session chases the wrong tracker. Add to frontend's Residuals. |  |
| docs/harness-boundaries.md:111 | Limit: no command here audits this file, so its drift goes uncaught | - | residual |  | Frontend lacks backend's link and blueprint checks, the counterpart of backend's own residual. Move to frontend's Residuals, narrowed for the destructive-classes table. |  |
| docs/harness-boundaries.md:1194 | Limit: unattended push refused under auto mode, cause unestablished, user-level remedy | - | residual |  | Inference rests on autoMode.environment trusting only backend's remote, while payload still says the push never prompts. Move :1194-:1214 to Residuals. |  |
| docs/harness-boundaries.md:1383 | Limit: a build config not yet existing escapes any deny enumerated from the tree | docs/harness-boundaries.md:1466 | residual |  | Payload hands the ninth entry to each target's Residuals; carry frontend's npm form, :1383-:1413, there. |  |
| docs/harness-boundaries.md:2491 | Limit: eslint.config.js and .prettierrc stay editable, and the checks run them | - | residual |  | Accepted by frontend#224 for /style-pass and npm-checks; frontend-only and still true after sync. Move to Residuals. |  |
| docs/harness-boundaries.md:2504 | Limit: a new tool's .config.ts stays editable until someone names it | - | residual |  | Frontend's named deny list stays in config (*Decisions*), so the cost stays; composition-root carve-out belongs in Residuals beside it. |  |
| docs/harness-boundaries.md:2108 | MCP server started through a Node launcher running the index gate | - | local |  | *Decisions*: mcp-launch.mjs assumes Node and .mcp.json is outside managed directories; stays frontend's. | TheMcpServerStartsOnlyOverAnIndexTheHookWouldOpen |
| docs/harness-boundaries.md:2475 | Toolchain Edit denies hold every turn, not only ship's | - | local |  | *Decisions* keeps these as config additions; they name npm and Angular files, and their settings test stays local. | TheEditDeniesTheChecksRunOnAreInSettingsToo |
| docs/harness-boundaries.md:2139 | package-lock.json excluded from the code index | - | local |  | Npm tree fact held in frontend's own .codeindexignore; no payload behaviour depends on it. |  |
| docs/harness-boundaries.md:2166 | Hook never lets a checkout's program stand in for a bare name | .claude/hooks/refresh-index.py:240 | covered |  | For the hook's own starts: payload runs no bare git or tasklist, and the CLI is a full path from console_script. What the CLI starts is D's `NoDefaultCurrentDirectoryInExePath` row. |  |
| docs/harness-boundaries.md:2174 | Wrappers export PYTHONSAFEPATH and hold probes to a version floor | .claude/skills/codebase-index/scripts/cbx:9 | covered |  | cbx exports it and :26 pins 3.12 before importing; cbx.ps1:14 matches; *Decisions* removes run-index. |  |
| docs/harness-boundaries.md:2378 | A failed hint swallows its status so no prompt or call is lost | .harness/settings.base.json:166 | covered |  | *Decisions* keeps hint-bound.sh for hints; it replaces the trailing no-op and always leaves with 0. |  |
| docs/harness-boundaries.md:2386 | Refused search names a route that answers from the session's own tree | .claude/hooks/index-search-hint.py:414 | covered |  | Payload tells worktree from main and names cbx there; frontend names MCP everywhere, both reach this tree's index. |  |
| docs/harness-boundaries.md:2420 | MCP call from another checkout refused with the equivalent CLI line | .claude/hooks/index-mcp-root.py:139 | covered |  | Same refusal; line reads cbx, healthcheck stays exempt. |  |
| docs/harness-boundaries.md:2442 | Fork carries only the MCP approval into the worktree's local settings | .claude/scripts/git-worktree-fork.sh:67 | covered |  | Same -I script writing enabledMcpjsonServers alone; warning at :87 on an unreadable file. |  |
| docs/harness-boundaries.md:2352 | MCP_TIMEOUT raised for sessions in the repository | .harness/settings.base.json:4 | covered |  | Base env sets it for every target. |  |
| docs/harness-boundaries.md:1352 | New agent profile fails any granting command that does not deny it | .claude/scripts/test_command_grants.py:103 | covered |  | Payload reads profiles each run; ship.md excused since its single grant is pinned at :96. | test_every_exact_agent_grant_denies_every_other_type |
| docs/harness-boundaries.md:2462 | Suite pins branch-reviewer's profile to read-only tools | .claude/scripts/test_command_grants.py:69 | covered |  | Payload holds no shell, no edit, no agent on that profile. |  |
| docs/harness-boundaries.md:2513 | Reviewer findings are untrusted; parent verifies each before acting | docs/harness-boundaries.md:123 | covered |  | Payload states the same discipline and residual for branch-reviewer. |  |
| docs/harness-boundaries.md:2551 | Findings open at the review ceiling become issues before merge | .claude/commands/ship.md:471 | covered |  | Seventh-round filing lives in ship.md and docs/commands/ship.md:709. |  |
| docs/harness-boundaries.md:1224 | Commands chained before a push never deny push | .claude/scripts/test_command_grants.py:240 | covered |  | NothingShipChainsDeniesPush replaces CHAINED_BEFORE_A_PUSH. | CHAINED_BEFORE_A_PUSH |
| docs/harness-boundaries.md:1720 | Rebase helper refuses a merge carrying content neither parent has | .claude/scripts/git-rebase-onto-main.sh:359 | covered |  | require_no_merge_invented_anything runs before the replay, and is stricter. |  |
| docs/harness-boundaries.md:1944 | Git-dir lock by identity, shared git deadline, marker retries, pid record, taskkill, unplaceable-file no-op | .claude/hooks/refresh-index.py:35 | obsolete |  | Kept for the shared git deadline and lock identity only; D's rows port the state directory, the bounded retries and the pid record, which this row's reading of *Decisions* would have dropped. |  |
| docs/harness-boundaries.md:1949 | Fork runs refresh from main checkout's launcher, not the worktree's copy | .claude/scripts/git-worktree-fork.sh:96 | obsolete |  | Fork always cuts origin/main and refresh-index.py runs a PATH-found CLI, no worktree wrapper; *Decisions* removes the launcher chain. |  |
| docs/harness-boundaries.md:857 | Executing forms, xargs allow-list, pattern and brace git names refused | - | out of scope |  | Pattern and brace names and the launcher chains. The executing forms and `xargs` have their rows in A. |  |
| docs/harness-boundaries.md:958 | Git subcommand allow-list and whole refusals like filter-branch, daemon, config | - | out of scope |  | The allow-list only, as A holds. The whole refusals such as `filter-branch` port in A. |  |

#### A, edit guard

| Frontend | Behaviour | Payload | Verdict | Task | Reason and fix | Frontend's test |
|---|---|---|---|---|---|---|
| hooks/guard-edit-target.py:451; also docs/harness-boundaries.md:1599 | Target outside every checkout and every scratch root is refused | - | port | 2 | c1, narrowed from frontend's allow-list to a refusal of `~/.ssh`, shell profiles and `~/.gitconfig`. The allow-list refuses sibling checkouts and `run-locally.md` (22 edits) and needs `.todo/` (628), criterion 3. Invert payload's test for those names only. | test_a_path_outside_every_checkout_and_every_scratch_root_is_refused |
| hooks/guard-edit-target.py:441 | `~/.claude` credentials, settings, hooks, commands, agents, plugins refused, case-folded | - | port | 2 | c1. Payload denies are project-relative, so user-level control files are open. Port `control_surface` and both CONTROL sets folded, without `CLAUDE.md` and `AGENTS.md`: `~/.claude/CLAUDE.md` was edited 6 times, for the owner's rules. `~/.claude/settings.json` was edited twice, on the owner's request: that route becomes an owner-run script. | test_the_harness_control_surface_is_refused_inside_its_own_root |
| hooks/guard-edit-target.py:808 | Linked worktree's `.claude` refused wherever the session stands, nested worktrees included | - | port | 2 | c1: payload admits it, boundaries :480 leaves it to a prompt. Port the first-component check into `offence`. 268 such edits since 2026-10-19 predate the payload's rule; Task 2 reads them before the port stands. | test_a_nested_worktree_keeps_its_machinery_refused |
| hooks/guard-edit-target.py:825; also docs/harness-boundaries.md:209 | Unentered linked worktree's `.github`, `.git`, root files and toolchain refused | - | port | 2 | c1, narrowed: judge an unentered worktree by the target's denies. 718 `.github` edits landed in worktrees where no target denies it. Needs `protected_in_worktree` and `protected_path`; Angular names stay config. | test_a_sibling_worktree_of_this_repository_is_judged_not_refused |
| hooks/guard-edit-target.py:833 | Link traversal inside an unentered linked worktree is judged and refused | - | port | 2 | c1, the guard's subject. Payload never anchors the sibling. Append it to `checkouts`. |  |
| hooks/guard-edit-target.py:439 | Temp scratch and `~/.claude` state admitted, including scratch names like `scripts` | .claude/hooks/guard-edit-target.py:331 | covered |  | Payload admits through its fall-through, and still does once the narrowed refusal lands. | test_the_temp_root_is_admitted_whole |
| test_edit_target_guard.py:240 | Spawned hook gives the same verdict as the in-process judge | .claude/scripts/test_edit_target_guard.py:153 | covered |  | Payload's `judge` spawns every case; `in_process_hook.py` drops per *Decisions*, so no second path remains to compare. | test_a_spawned_hook_gives_the_same_verdict |
| hooks/guard-edit-target.py:316 | Scratch roots are `~/.claude` then `gettempdir()` only; stale TEMP cannot widen them | - | obsolete |  | Scratch roots served the allow-list, which is not ported (the row at `guard-edit-target.py:451`). | test_a_stale_temp_environment_variable_does_not_widen_the_scratch_root |
| hooks/guard-edit-target.py:372 | Scratch spelling resolving out of the scratch root is refused | - | obsolete |  | Served the allow-list. The refusal above judges the resolved path, so a link into `~/.ssh` is held. | test_a_scratch_path_that_resolves_out_of_the_scratch_root_is_refused |
| hooks/guard-edit-target.py:401 | With HOME under temp, a link into `~/.claude` control surface is refused | - | obsolete |  | Served the temp-root admission of the allow-list; `control_surface` holds without it. | test_a_home_under_the_temp_root_keeps_its_control_surface |
| hooks/guard-edit-target.py:421 | Home directory beneath the temp root is not scratch, `~/.ssh` included | - | obsolete |  | As the row above. | test_a_home_under_the_temp_root_keeps_its_control_surface |
| hooks/guard-edit-target.py:433 | Machinery of any checkout under the temp root is refused | - | obsolete |  | Served the temp-root admission. No edit was typed there. | test_the_temp_root_is_admitted_whole |
| hooks/guard-edit-target.py:488 | Ordinary files of a linked worktree admitted, not refused as outside | - | obsolete |  | Admission the allow-list would need; line 331 admits today and still will. | test_a_sibling_worktree_of_this_repository_is_judged_not_refused |
| hooks/guard-edit-target.py:553 | A `.git` file without git's backlink is no linked worktree | - | obsolete |  | As the row above. | test_a_sibling_worktree_of_this_repository_is_judged_not_refused |
| hooks/guard-edit-target.py:939 | Task list admitted by name, only as a real file beside the guard's repository | - | obsolete |  | As the row above. `task_list` stays admitted. | test_the_task_list_beside_the_main_checkout_is_admitted |
| hooks/guard-edit-target.py:808 | Trailing dots or spaces on `.claude` stripped before the linked-worktree refusal | - | out of scope |  | `.claude.` is a spelling no ordinary work types; the threat model excludes it. Only the case fold matters when porting. |  |

#### A, git guard

| Frontend | Behaviour | Payload | Verdict | Task | Reason and fix | Frontend's test |
|---|---|---|---|---|---|---|
| hooks/guard-git-argv.py:3415 | `&` inside `2>&1`, `>&2`, `&>` no longer ends a run, so the heredoc's shell is found | - | port | 2 | c1, typed once in 46,810. `bash 2>&1 <<'EOF'` holding a push is admitted because `_run_bounds` stops at `&`. Port `_ends_run`. | test_a_redirection_ampersand_does_not_end_the_run |
| hooks/guard-git-argv.py:3299 | `leading_command` skips reserved words such as `if`, `!`, `then`, `do` | - | port | 2 | c1, a routine idiom: `if … \| bash; then` reads `if` as the lead, so the printer pass skips it. Add `COMMAND_PREFIX_WORDS`. Refuses nothing new but the push. | test_a_wrapper_with_operands_does_not_hide_the_program |
| hooks/guard-git-argv.py:2140; also docs/commands/bug-sweep.md:1025, docs/harness-boundaries.md:262 | A redirection writing into a protected tree or file is refused | - | port | 2 | c1, the threat model names a write into a denied tree. Port `redirection_offence`, `destination_offence`, `EVENT_CWD`; the lists come from each target's denies, so `.github` is refused only where a target denies it. Backend's mutation proofs write there. | test_the_measured_redirections_are_refused |
| hooks/guard-git-argv.py:2609; also docs/harness-boundaries.md:353 | Writing verbs onto protected paths are refused, wrappers included | - | port | 2 | c1. `cp`, `mv`, `rm`, `tee`, `sed -i`, `dd` onto a protected path are admitted. Port `writing_verb_offence` and `raw_runs` under the two narrowings beside this one; `rg` stays off `READING_COMMANDS`. | test_every_writing_verb_reaches_the_machinery_check |
| hooks/guard-git-argv.py:2432 | Destination found through options, hard-link sources, `-i` backup suffixes, `find -exec` | - | port | 2 | c1, narrowed: `cp -t` and `ln` sources port, the computed-operand refusal does not. `cp "$a" "$b"` was typed 107 times, criterion 3. | test_a_verbs_destination_is_found_through_its_options |
| hooks/guard-git-argv.py:1934 | Protected names compared by path component and folded for case | - | port | 2 | c1, narrowed: anchor at a checkout's root and fold case, not any component as frontend does. `payload/.claude/…`, `staging/.claude/…`, `.claude/worktrees/` and `.claude/cache` stay writable: 113 redirections, 34 `rm`, 19 `sed -i` typed. | test_a_component_is_matched_rather_than_a_prefix |
| hooks/guard-git-argv.py:1990 | Target `~/…` and allowed variables expanded and judged; unknown variables refused | - | port | 2 | c1, narrowed: expand `~` and the allowed variables and judge the result; an unknown variable is admitted, not refused. `> "$var…"` was typed 523 times, criterion 3. | test_an_unreadable_target_is_refused_and_an_expansion_is_judged |
| hooks/guard-git-argv.py:2078 | A relative write target is refused when the command can change directory | - | port | 2 | c1, narrowed: resolve a literal `cd` and judge the target; never refuse a relative write because a `cd` stands on the line. `cd x && … > y` was typed 736 times, criterion 3. | test_a_redirection_into_an_application_tree_is_refused |
| hooks/guard-git-argv.py:2099 | A write through a link into a protected tree is refused | - | port | 2 | c1, the edit guard resolves links for the edit tools only. Port `linked_protected_path` with `EVENT_CWD`. | test_a_redirection_through_a_link_into_a_protected_tree_is_refused |
| test_harness_helpers.py:9443 | Gate: protected lists must cover command denies and tracked root files | - | port | 2 | A gate, not a refusal. Port with `test_the_protected_files_cover_every_tracked_root_file`, reading the target's config. | test_the_protected_trees_cover_what_the_editing_commands_deny |
| hooks/guard-git-argv.py:155 | Short flags that run or write refused: `rebase -x`, `rebase -s`, `format-patch -o`, `archive -o`, `clone -u`, `ls-remote -u`, `grep -O`, `difftool -x`, `pull -s` | - | port | 2 | c1, narrowed to the flags that run a command: `rebase -x`, `rebase -s`, `clone -u`, `ls-remote -u`, `grep -O`, `difftool -x`, `pull -s`, the long forms' parity. `archive -o` was typed twice and `format-patch -o` writes a named file, so both stay admitted. | test_the_short_and_operand_spellings_that_run_a_command |
| hooks/guard-git-argv.py:160 | `git bisect run` and `git submodule foreach` refused | - | port | 2 | c1, routine git, typed 0 times, so it stops nothing. Each runs its operand and no flag check sees it. Port `EXECUTING_FORMS`. | test_the_short_and_operand_spellings_that_run_a_command |
| hooks/guard-git-argv.py:176 | `--strategy` on pull and rebase, `--template` on clone and init refused | - | port | 2 | c1, the tail flags *Decisions* gave this cluster, typed 0 times. Port `EXECUTING_LONG_FLAGS`, abbreviations included. | test_a_merge_strategy_is_refused_on_pull_and_rebase |
| hooks/guard-git-argv.py:134 | `--no-index`, `--ext-diff`, `--textconv`, `--extcmd`, `--open-files-in-pager` refused with abbreviations | - | port | 2 | c1, narrowed: `--ext-diff`, `--textconv`, `--extcmd`, `--open-files-in-pager`. `--no-index` stays out: typed 49 times, and its deny is frontend's config. | test_git_options_that_run_a_command_are_refused_at_the_top_level |
| hooks/guard-git-argv.py:183 | `filter-branch`, `send-email`, `instaweb`, `daemon`, `http-backend`, `web--browse` refused whole | - | port | 2 | c1, typed 0 times and the base denies none of them. Port `REFUSED_SUBCOMMANDS`; the allow-list stays out. | test_git_options_that_run_a_command_are_refused_at_the_top_level |
| hooks/guard-git-argv.py:5203 | `xargs` may launch only a listed reader, with listed options | - | port | 2 | c1, narrowed to `xargs git push`, whose destination cannot be read. The reader allow-list stays out: it refuses `… \| xargs py -3.12 …`, and `xargs` was typed 54 times. | test_xargs_cannot_supply_a_git_argv |
| test_harness_helpers.py:11468 | Gate: every branch name `branch.md` gives is one the push guard admits | - | port | 2 | A gate, not a refusal: no payload suite ties the table to `SAFE_REF`. Move to test_git_argv_guard.py. | test_every_name_the_file_gives_is_one_the_push_guard_admits |
| test_harness_helpers.py:5922 | Gate: no hook binds a module-level name twice | - | port | 2 | A gate, not a refusal: nothing holds this once the suite drops. Move to test_python_hygiene.py. | test_no_hook_binds_a_module_level_name_twice |
| git-fetch-origin.sh:26 | Fetch helper refuses `-f`, `-u` and `+src:dst` by shape | - | port | 2 | c1, the helper that held this is dropped. Typed 0 times. `git fetch origin +main:main` discards local commits under the grant. Refuse the three shapes; keep `main:main` (ship.md:581). | test_nothing_that_is_not_a_plain_branch_name_reaches_git |
| git-pull-ff-only.sh:18 | Pull helper takes no argument, so `--ff-only` cannot be overridden | - | port | 2 | c1, narrowed to what overrides the granted line: `--no-ff`, `--ff`, `--rebase`, `-r` beside `--ff-only`. Plain `-q` stays, typed in 162 commands. | test_it_takes_no_argument_whatever_it_looks_like |
| hooks/guard-git-argv.py:255 | `PROTECTED_TREES` and `PROTECTED_FILES` tables | - | local |  | `android`, `ios`, `node_modules`, `package.json`, `angular.json` are frontend's; supply them through config when the redirection check lands. | test_the_protected_files_reach_names_no_enumeration_could_hold |
| hooks/guard-git-argv.py:2039 | `APPLICATION_TREES` refuse writes into `src`, `docs`, `e2e`, `public`, `tools` | - | local |  | Frontend's tree, tied to `review-branch`, which stays local (*Decisions*). Supply through config with the mechanism. | test_a_redirection_into_an_application_tree_is_refused |
| test_harness_helpers.py:2957 | `npm-checks.sh` spells its scripts and takes no free parameter | - | local |  | Frontend's stack (*Decisions*). Keep the case in a frontend-local suite, since this file is dropped. | test_the_check_runner_helper_takes_no_free_parameter |
| test_harness_helpers.py:2968 | `npm-checks.sh` refuses an absent `node_modules` | - | local |  | Frontend's stack (*Decisions*), driven against a real install. Keep it in a frontend-local suite. | test_the_check_runner_refuses_an_absent_install |
| test_harness_helpers.py:2995 | `npm-checks.sh` offers no e2e mode | - | local |  | Frontend's Playwright fact (*Decisions*). Keep it in a frontend-local suite. | test_the_check_runner_offers_no_e2e_mode |
| hooks/guard-git-argv.py:4162 | A literal `git` behind any wrapper is judged | .claude/hooks/guard-git-argv.py:2016 | covered |  | `git_segments` scans the whole run, so `timeout 5 git push origin +HEAD:main` is refused without `launched`. | test_a_wrapper_with_operands_does_not_hide_the_program |
| hooks/guard-git-argv.py:3536 | An issue helper's heredoc is read as data, for its one literal shape | .claude/hooks/guard-git-argv.py:2163 | covered |  | By another route: payload refuses the heredoc and names `< <path>`, pinned at test_git_argv_guard.py:2989-2996. `_run_words`' operator word falls away with it. | test_a_helper_script_reads_its_heredoc_as_data |
| hooks/guard-git-argv.py:6258 | Untokenisable text gets crude push, subcommand and assignment checks; a trailing backslash is lexed | .claude/hooks/guard-git-argv.py:2398 | covered |  | Payload refuses every untokenisable command outright, which is stricter than all of frontend's crude checks. | test_the_fallback_still_reads_the_push_grammar |
| git-fetch-origin.sh:23 | Fetch helper refuses `--upload-pack`, `--upl=` and a transport in the tail | .claude/hooks/guard-git-argv.py:2459 | covered |  | Prefix and abbreviation test, with `ext::` at :2469; pinned at test_git_argv_guard.py:155. No code-running fetch flag is missed. | test_nothing_that_is_not_a_plain_branch_name_reaches_git |
| hooks/guard-git-argv.py:5758 | `run-index` refused unless it matches the hooks' checkout | - | obsolete |  | `run-index` is dropped (*Decisions*), and `INDEX_WRAPPER` names nothing the payload ships. | test_the_index_wrapper_runs_only_as_the_hooks_checkout_holds_it |
| hooks/guard-git-argv.py:353; also docs/commands/branch.md:228, commands/branch.md:91, git-branch-create.sh:32, git-switch-existing.sh:35, git-rebase-onto-main.sh:31, git-worktree-fork.sh:59 | `SAFE_REF` refuses a parenthesised branch name | .claude/hooks/guard-git-argv.py:128 | obsolete |  | Payload's `/branch` issues `feat(<scope>)/` names and its comment at :127 says so; the refusal's reason is gone. | test_the_pattern_finds_and_the_guard_refuses_a_parenthesised_name |
| test_harness_helpers.py:3920 | Spawned hook gives the same verdict as the in-process hook | .claude/scripts/test_git_argv_guard.py:79 | obsolete |  | `in_process_hook.py` is dropped (*Decisions*), and the payload suite spawns every case. | test_a_spawned_hook_gives_the_in_process_verdict |
| hooks/guard-git-argv.py:2989 | An opener the substitution scan cannot close is refused | - | out of scope |  | The honest line, a commit heredoc then `git push` outside a substitution, is already refused. Only a push inside a later substitution is unread, and no work types that. | test_an_opener_the_scan_cannot_close_is_refused |
| hooks/guard-git-argv.py:3005 | A substitution body holding a heredoc, `$[` or unbalanced `${…}` is refused | - | out of scope |  | As the row above: the probe's `)` in a heredoc hides a push only inside a substitution. Frontend's refusal also stops `git commit -m "$(cat <<'EOF'`. | test_a_body_the_count_may_have_cut_short_is_refused |
| hooks/guard-git-argv.py:3899; also docs/harness-boundaries.md:367 | `env -S` strings are judged as command lines | - | out of scope |  | Typed 0 times; one opaque word built to pass a reader. Criterion 1 fails. | test_a_verbs_destination_is_found_through_its_options |
| hooks/guard-git-argv.py:1867 | Glob, brace, substitution or process-substitution write target refused | - | out of scope |  | `> package.jso?` and `> >(sh -c …)` only hide the name; *The guards' threat model*. | test_a_globbed_redirection_target_is_refused |
| hooks/guard-git-argv.py:1934 | 8.3 short names, NTFS streams and trailing dots read as protected | - | out of scope |  | `PACKAG~1.JSO` and `package.json::$DATA` exist only to dodge the name; *The guards' threat model*. | test_a_protected_name_in_another_case_or_spelling_is_refused |
| hooks/guard-git-argv.py:4560 | Only `ALLOWED_SUBCOMMANDS` pass; any other launched git subcommand is refused | - | out of scope |  | Criterion 3. It refuses `git ls-remote` (281 typed), `git config` (71), `git stash` (44), `git update-index` (20), `git apply`, `git reflog`, `git cherry-pick`. The harmful names are `REFUSED_SUBCOMMANDS`'s row in this table. | test_only_the_subcommands_on_the_allow_list_are_admitted |
| hooks/guard-git-argv.py:317 | `--shallow-file` skipped as a value-taking global | - | out of scope |  | Only the allow-list needed it. `git --shallow-file x push origin +HEAD:main` is refused today. | test_a_value_taking_global_option_hides_no_subcommand |
| hooks/guard-git-argv.py:5454; also docs/harness-boundaries.md:1035 | `git diff` operands outside the checkout, a moved repository, or no repository refused | - | out of scope |  | Reads only, where `Read` is granted globally, so no denied write and no harm; the `--no-index` deny stays frontend's config. | test_a_git_diff_that_reads_outside_the_repository_is_refused |
| hooks/guard-git-argv.py:5397 | Diff operands resolved through links; a glob over `LINK_GLOB_LIMIT` refused | - | out of scope |  | As the row above, resolved through a link. | test_a_diff_operand_that_is_a_link_out_of_the_checkout_is_refused |
| hooks/guard-git-argv.py:5090 | `PATH`, `HOME`, `GIT_*` set by prefix, `export` or `env` before git refused | - | out of scope |  | Criterion 3: `GIT_EDITOR` typed 22 times, `GIT_SEQUENCE_EDITOR` 12, `PYTHONPATH` 5. What is left, `GIT_SSH_COMMAND` and the like, exists only to steer git past the hook. | test_an_assignment_on_a_line_that_runs_git |
| hooks/guard-git-argv.py:4689 | The sensitive names are refused on a line running no git as well | - | out of scope |  | As the row above, on a line running no git. | test_an_assignment_on_a_line_that_runs_no_git_is_refused |
| hooks/guard-git-argv.py:4714 | On a git line only `ASSIGNMENT_ALLOWED_NAMES` may be assigned | - | out of scope |  | It refuses honest `X=1 git log`, pinned admitted at test_git_argv_guard.py:2109; a false refusal under *The guards' threat model*. | test_only_a_name_known_to_be_harmless_is_assigned_before_git |
| hooks/guard-git-argv.py:4735 | `GRANTED_WORD` widens the inverted rule to frontend's granted programs | - | out of scope |  | The inverted rule it widens is out of scope in its own row, so the list has nothing to widen. | test_only_a_name_known_to_be_harmless_is_assigned_before_a_granted_program |
| hooks/guard-git-argv.py:4964; also docs/harness-boundaries.md:876 | Arithmetic and builtin assignment refused: `${x[PATH=5]}`, `$[…]`, `printf -v`, `read`, `declare -n`, `set -k` | - | out of scope |  | Spellings built to reach a variable past the prefix check; *The guards' threat model*. Includes `assigning_word`'s builtins and `double_bracket_arithmetic`. | test_an_assignment_past_the_first_reading_is_refused |
| hooks/guard-git-argv.py:5008 | `${x@P}` and `${!x}` refused | - | out of scope |  | Prompt and indirect expansion are named at *The guards' threat model*. | test_an_expansion_that_evaluates_a_value_is_refused |
| hooks/guard-git-argv.py:4214; also docs/harness-boundaries.md:660 | A program word bash computes is refused | - | out of scope |  | `F='git push …'; $F` is text assembled and then evaluated, *The guards' threat model*. | test_a_wrapper_with_operands_does_not_hide_the_program |
| hooks/guard-git-argv.py:4256 | A glob or brace that bash expands to `git` counts as git | - | out of scope |  | `gi[t]`, `{git,push}` and `g*` exist only to hide the program; *The guards' threat model*. | test_a_pattern_for_git_behind_a_wrapper_nobody_named_is_a_git |
| hooks/guard-git-argv.py:4633 | A live comma brace in a git run is refused | - | out of scope |  | `git {fetch,--upload-pack=x}` is built to hide, and the check refuses honest `git add {a,b}.md`; *The guards' threat model*. | test_a_brace_behind_an_unnamed_wrapper_is_still_read |
| hooks/guard-git-argv.py:4377 | Computed subcommand or global-option value refused | - | out of scope |  | `git $SUB` is hidden, and the check refuses honest `git -C "$work" status`; *The guards' threat model*. | test_only_the_subcommands_on_the_allow_list_are_admitted |
| hooks/guard-git-argv.py:6454 | Subcommand folded and stripped of stream, dots, blanks and executable suffix | - | out of scope |  | `git 'filter-branch::$DATA'` and `git FILTER-BRANCH` exist only to dodge the name; *The guards' threat model* puts them out of scope. | test_git_options_that_run_a_command_are_refused_at_the_top_level |
| hooks/guard-git-argv.py:4501; also docs/harness-boundaries.md:1001 | A line that makes a link, copies recursively or unpacks and runs git is refused | - | out of scope |  | Link-then-read is a route round, and it refuses honest `cp -r a b && git diff a x`; *The guards' threat model*. | test_a_line_that_makes_a_link_and_runs_git_is_refused |
| hooks/guard-git-argv.py:2688; also docs/harness-boundaries.md:295 | `gh` anywhere in a substitution is refused | - | out of scope |  | `ls $(gh pr merge 42 --admin)` only hides a merge behind a grant, and bars routine reads of `gh`; *The guards' threat model*. | test_a_redirection_into_an_application_tree_is_refused |
| hooks/guard-git-argv.py:2736 | A substitution may run only `SUBSTITUTION_PROGRAMS`, with no assignment or wrapper option | - | out of scope |  | `ls $(./tools/run)` hides a program behind a prefix grant; *The guards' threat model*. | test_what_stands_in_front_of_a_substituted_program |
| hooks/guard-git-argv.py:2913 | A substitution may run only reading git subcommands | - | out of scope |  | `ls $(git reset --hard)` hides a mutation; a push inside one is still judged by the recursion. *The guards' threat model*. | test_a_substitution_runs_only_what_reads |
| hooks/guard-git-argv.py:6082 | A process substitution is held to the substitution allow-lists | - | out of scope |  | Same spelling as the substitution rows, in `<(…)` form; `cat <(./tools/env)`. *The guards' threat model*. | test_a_substitution_runs_only_what_reads |
| hooks/guard-git-argv.py:5585; also docs/harness-boundaries.md:943 | Computed arguments to a granted helper refused | - | out of scope |  | Harm needs a hidden `$(…)` in the tail; an honest `$(git rev-parse HEAD)` is harmless and would be refused. *The guards' threat model*. | test_a_granted_helper_is_handed_plain_words_only |
| hooks/guard-git-argv.py:5961; also docs/harness-boundaries.md:2263, hooks/guard-git-argv.py:5758 | A granted helper differing from the hooks' checkout prompts rather than runs | - | out of scope |  | None of the three criteria holds: no spelling, no failure on good-faith input. It adds prompts: a worktree cut ahead of the hooks' checkout asks at every helper, and a headless `/ship` stops. The plan's anti-goal. | test_a_helper_the_tree_supplies_is_asked_for_not_granted |
| hooks/guard-git-argv.py:5879 | Hash-based `.pyc` under hooks counts as a difference | - | out of scope |  | Goes with the row above. | test_bytecode_python_would_run_without_its_source_is_a_difference |
| hooks/guard-git-argv.py:3990; also docs/harness-boundaries.md:637 | Tokenisers split on bash's blanks, not on a carriage return | - | out of scope |  | `x=1<CR>echo {git,push} …` is an escape-grade spelling, not ordinary work; *The guards' threat model*. | test_a_substitution_body_is_split_where_bash_splits_it |
| hooks/guard-git-argv.py:6542 | `SCAN_BUDGET` refuses opener count times length | - | out of scope |  | Input sized to outrun the timeout is named at *The guards' threat model*; payload keeps `LENGTH_BUDGET`. | test_a_scan_past_the_budget_is_refused_in_time |
