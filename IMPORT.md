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
aside. A site is written as its path, a hash and an anchor, the anchor a
space-free run of the listed line's own text, so an edit elsewhere in the file
does not move it; the same file refuses a listed site no line carries any more.
A shape those names cannot see, such as a C# sample, rests on review.

- `.github/output-gate/` — the gate itself checks .NET build output against
  `Platform.slnx`. Delivered only where a .NET build runs: a target without
  one puts `.github/output-gate/**` under `exclude` in its config, as this
  repository does. #85 moves it backend-local.
- `.github/comment-gate/README.md#.yaml` and
  `.github/comment-gate/README.md#CDATA` — `MSBuild` as a file kind the gate
  reads: true in any target.
- Test fixtures that use a `dotnet` command line as a sample string
  (`test_git_argv_guard.py`, `test_index_search_hint.py`,
  `test_watch_session.py`, `test_cbx.py`) — data, right in any
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
suite. A third passage of `docs/harness-boundaries.md` only backend's tree
makes true, the ninth entry's argument on a build tool's grants, went later to
backend's own *Residuals*, three moved in all; blueprint-backend#1773 carries
them.

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
| `.claude/scripts/test_sweep_slices.py` | payload, split by #5 | partitions repositories it builds, and since #73 each checkout's own tree by its own `.harness/sweep-rows.tsv`; backend's `test_sweep_slices_backend.py` holds `TheRealTree` until a backend pull request drops it, once the sync carrying that case has landed there |
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
| git-worktree-fork.sh:116; also docs/commands/branch.md:88 | Fork seeds the worktree's index; no hook present starts nothing | .claude/scripts/git-worktree-fork.sh:117 | covered |  | Seeds through the worktree's refresh-index.py; the launcher route goes with *Decisions*'s index-refresh.py and run-guard rows. | test_the_fork_starts_the_new_worktrees_index_refresh,test_a_checkout_without_the_hook_still_forks_and_starts_nothing |
| test_git_worktree_fork.py:227 | A checkout with no local settings forks silently | .claude/scripts/git-worktree-fork.sh:86 | covered |  | Same -f test on the settings file; only the separate case is gone. | test_a_checkout_with_no_local_settings_forks_and_says_nothing |
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
| gh-pr-create.sh:75; also test_harness_helpers.py:1891, 1901, 2158, 2197, commands/pr.md:188, docs/commands/ship.md:466, docs/harness-boundaries.md:747 | PR create pins repo, head and base; title and body from untracked, unlinked files | .claude/scripts/gh-pr-create.sh:74 | ported #153 | 3 | Per *Decisions*, Task 3 Step 2's form: title and body as path arguments, so no `.gitignore` line. Swap the grant in pr.md and ship.md. | test_the_create_helper_refuses_a_body_it_should_not_publish, test_the_create_helper_leaves_no_body_behind_and_takes_none_tracked |
| pr-for-branch.sh:157; also pr-for-branch.sh:156, test_harness_helpers.py:2362, 2424, commands/ship.md:81, docs/commands/ship.md:115 | MERGED row dropped when its merge commit is an ancestor of the local tip | .claude/commands/ship.md:92 | ported #127 | 2 | A branch name reused from main stops /ship at the merged row. Request mergeCommit and restore the drop, checking dispatch_run's lookup by number. | test_a_merged_pr_behind_the_reused_branch_is_not_its_pr, test_the_reuse_drop_still_answers_after_a_rebase_merge |
| pr-for-branch.sh:97; also pr-for-branch.sh:97, test_harness_helpers.py:2599 | Only pull requests into main count as the branch's PR | .claude/commands/pr.md:160 | ported #127 | 2 | Payload /pr stops on any OPEN row, so a PR into develop blocks main's. Read only baseRefName main rows in pr.md and ship.md. | test_a_newer_pr_into_another_base_does_not_mask_the_main_pr |
| pr-for-branch.sh:84; also pr-for-branch.sh:85, gh-label-ensure.sh:71, test_harness_helpers.py:2315, 2628, 2638, docs/commands/ship.md:159 | Listing read with --limit 1000 and refused, exit 4, at the cap | .claude/scripts/pr-for-branch.sh:39 | ported #127 | 2 | gh's default 30 rows are cut before the fork filter, so the landed row can vanish. Restore --limit and the refusal at it. | test_a_listing_that_fills_the_page_is_refused |
| gh-label-ensure.sh:68 | Label listing bounded with --limit and refused at the cap | .claude/scripts/gh-label-ensure.sh:46 | ported #127 | 2 | Payload reads gh's default 30 rows as the whole set, at both reads; restore labels_matching with its limit and refusal. | test_the_capped_listings_detect_their_cap |
| pr-locality.sh:103; also pr-locality.sh:103, test_harness_helpers.py:1212, 1235, 1434 | Touch-set tokens admit @ and +, with + escaped in the regex | .claude/scripts/pr-locality.sh:68 | ported #127 | 2 | Payload refuses src/app/@types/** with exit 3 though changed paths admit @ and +. Widen grammars at :68 and :108, escape + in to_regex. | test_a_touch_set_may_spell_what_a_changed_path_may, test_a_plus_in_a_token_is_a_character_and_not_a_quantifier |
| pr-locality.sh:127; also pr-locality.sh:127, test_harness_helpers.py:1473, 1532 | Empty brace alternative in a touch-set token is refused | .claude/scripts/pr-locality.sh:80 | ported #127 | 2 | Payload passes {} and {a,} into an ERE, undefined by POSIX, so GNU and BSD grep disagree. Restore the case refusal after the boundary check. | test_an_empty_brace_alternative_is_refused_on_every_platform |
| pr-locality.sh:154; also pr-locality.sh:154, test_harness_helpers.py:1250 | Globstar placeholder is portable and no token can spell it | .claude/scripts/pr-locality.sh:18 | ported #127 | 2 | BSD sed reads \x01 as literal x01, so a token holding x01 mistranslates on frontend's macOS leg. Use %%GLOBSTAR%% in to_regex. | test_the_globstar_placeholder_cannot_be_spelled_by_a_token |
| pr-locality.sh:213; also pr-locality.sh:189, test_harness_helpers.py:1632 | One grep per pattern over all paths; path check spawns no process | .claude/scripts/pr-locality.sh:154 | ported #127 | 2 | Payload spawns a grep per path per pattern, doubled for class patterns, the #61 hang on Windows. Restore the batched match and case check. | test_the_spawn_count_does_not_grow_with_the_changed_paths |
| sweep-slices.sh:109; also commands/bug-sweep.md:201, docs/commands/bug-sweep.md:670 | Rows partition frontend's tree: e2e, public, android, ios, .vscode, src/app/core | .claude/scripts/sweep-slices.sh:41 | ported #150 | 4 | Payload's backend rows own none of those, so both sweeps exit 3. Make rows target-supplied, or hold frontend's row_of and tables local. | test_each_row_a_sweep_owns_gets_its_files |
| sweep-slices.sh:108; also docs/harness-boundaries.md:1827 | Slicing helper runs on bash 3.2, which macOS ships | .claude/scripts/sweep-slices.sh:90 | ported #150 | 4 | mapfile and declare -A fail on the macOS leg (ci.yml:253); pr-locality.sh:91 too. Restore the awk classification, or drop that leg deliberately. | test_no_helper_here_uses_a_bash_4_construct |
| pr-locality.sh:159 | Verdict needs no class map; frontend's tree has none | .claude/scripts/pr-locality.sh:90 | local |  | A frontend tree fact: `.github/locality-gate/classes.yml` lands with its config before the first sync. |  |
| test_sweep_slices.py:131 | Partition and budget asserted over frontend's own tree | - | local |  | Holds frontend's paths and rows; payload's docstring leaves this to a target suite. Keep it as a local suite. | test_every_tracked_path_is_listed_or_counted_and_every_slice_fits |
| sweep-slices.sh:102 | A tracked name with a carriage return refuses the run | .claude/scripts/sweep-slices.sh:106 | covered |  | Payload refuses line breaks and CR; a tab needs no refusal because it splits on the first tab only. |  |
| test_sweep_slices.py:248 | Refused run leaves no slices directory | .claude/scripts/sweep-slices.sh:85 | covered |  | The trap removes the directory; payload's suite dropped the case, so carry it into frontend's local suite. | test_a_refused_run_leaves_no_slices_behind |
| test_sweep_slices.py:310 | Closed records are counted and not read | .claude/scripts/sweep-slices.sh:116 | covered |  | The case arm counts them; payload's suite dropped the case, so carry it into frontend's local suite. | test_the_closed_records_are_counted_and_not_read |
| test_sweep_slices.py:317 | Row cut at budget; one oversize file stands alone | .claude/scripts/sweep-slices.sh:160 | covered |  | The flush holds the budget; payload's suite dropped the case, so carry it into frontend's local suite. | test_a_row_is_cut_at_the_budget_and_one_large_file_stands_alone |

#### D, index

| Frontend | Behaviour | Payload | Verdict | Task | Reason and fix | Frontend's test |
|---|---|---|---|---|---|---|
| hooks/index-refresh.py:1112 | Compacts a bloated index on a copy, after a successful update, under the lock | - | ported #154 | 3 | *Decisions* row 1: port compact and helpers; its copy lives in state_dir, so the state-directory row below goes first. | test_a_bloated_index_is_compacted |
| hooks/index-refresh.py:711 | Keeps lock and pending marker in the git directory, not a branch-writable tree | - | ported #132 | 2 | Not in decisions. refresh-index.py:208 writes through a tracked link, truncating its target. Move state; update git-worktree-remove.sh:31 and test_refresh_index.py:338. | test_the_hooks_state_lives_where_no_branch_can_redirect_it |
| hooks/index-refresh.py:460; also docs/harness-boundaries.md:1880 | Refuses an index with a link, a rollback journal or a non-WAL header | - | ported #154 | 3 | *Decisions* row 1: ask at target, seed source and seed target; refresh-index.py:140 checks only the source's leaf link. | test_only_an_index_at_rest_in_wal_mode_may_be_opened |
| hooks/index-refresh.py:227 | Refuses a forged worktree: links, hard links, admin directory outside common | - | ported #154 | 3 | *Decisions* row 1: port registered; refresh-index.py:122 trusts commondir unchecked, so the seed source needs it too. | test_an_admin_directory_outside_the_repository_is_refused |
| hooks/index-refresh.py:390 | Refuses a root whose git common directory is not this repository's | - | ported #132 | 2 | Not in decisions. refresh-index.py:153-157 refreshes any repository or submodule holding a cache directory. Compare common directories; registered needs the owner's anyway. | test_another_repository_is_refused |
| hooks/index-refresh.py:314 | Refuses a sweep's checkout by folded prefix, through an alias too | - | ported #154 | 3 | *Decisions* row 1: call swept on the target and on the main checkout before seeding from it. | test_a_sweep_checkout_is_refused_in_any_case |
| hooks/index-refresh.py:528 | Seeds only where git reports the index path ignored | - | ported #154 | 3 | *Decisions* row 1: port with its cache; work must ask before the git budget ends, as test_the_worker_asks_before_its_git_budget_is_spent holds. | test_a_path_the_branch_stopped_ignoring_is_never_seeded |
| hooks/index-refresh.py:848 | A marker that will not go costs bounded retries, never a spin | - | ported #132 | 2 | Not in decisions. take_request:218 answers False, work:352 sees the file and loops unpaused forever; a directory there triggers it. Return None, bound retries. | test_a_marker_that_never_goes_costs_a_bounded_number_of_tries |
| hooks/index-refresh.py:594 | No update runs without a written index, so nothing is built | - | ported #132 | 2 | Not in decisions. refresh-index.py:156 admits any cache directory and work:344-345 updates after a failed seed. Require a written index, as refreshable and refresh do. | test_nothing_is_seeded_or_built_without_a_main_index |
| hooks/index-refresh.py:1355 | Worker judges its root again at entry and before every refresh | - | ported #132 | 2 | Not in decisions. refresh-index.py:358 trusts argv, and a link landing mid-drain goes unjudged. Judge in main and before each update; the update asks for the repository and a written index, and the link half arrives with Task 3's refusal. | test_the_worker_entry_point_judges_its_root_again |
| skills/codebase-index/gate-index.py:47; also docs/harness-boundaries.md:2094 | CLI refuses to start over an unopenable index; no Python refuses too | - | ported #154 | 3 | *Decisions* gate row: port gate-index.py and gate.sh, call from cbx; HOOK at gate-index.py:32 must name refresh-index.py, which needs index_openable. | test_both_wrappers_start_the_cli_on_a_clean_index_and_not_on_a_refused_one |
| hooks/index-query-hint.py:41; also docs/harness-boundaries.md:2320 | Index terms are single-quoted, so bash expands nothing inside them | .claude/hooks/guard-index-argv.py:293 | ported #132 | 2 | Guard refuses `$(…)` and backticks, not `$VAR`: `cbx refs "$event"` silently asks about nothing. Single-quote the routes, table, references and search hint. | test_no_command_double_quotes_the_term |
| hooks/index-refresh.py:685 | A seed copy lacking a WAL header is never renamed onto the index | - | ported #132 | 2 | refresh-index.py:195 renames unchecked; once index_openable is ported, such a copy refuses that root for good. Check the header first. | test_a_copy_without_a_wal_header_is_never_renamed_in |
| hooks/index-refresh.py:901 | Worker stands off while a killed worker's recorded indexer still runs | - | ported #132 | 2 | Not in decisions. Payload keeps no pid record, so a second update overlaps the orphan; refresh-index.py:309 only retries. Port the record and stand-off. | test_an_indexer_left_running_by_a_killed_worker_keeps_the_tree |
| hooks/index-refresh.py:108 | Sets NoDefaultCurrentDirectoryInExePath for everything the hook starts | - | ported #132 | 2 | Payload's own starts use full paths, but the CLI runs with cwd=root, relying on the launcher's variable. Set it in refresh's environment. | test_a_program_planted_in_the_working_directory_is_never_run |
| hooks/index-refresh.py:665 | The next seed removes a killed worker's partial copy and sidecars | - | ported #132 | 2 | refresh-index.py:176 names the partial by pid and removes only its own. Sweep `index.sqlite.seed.*` under the lock. | test_a_killed_workers_partial_is_removed_by_the_next_seed |
| hooks/index-refresh.py:1311 | POSIX worker runs in its own session, Windows in a new process group | - | ported #132 | 2 | refresh-index.py:383-390 passes CREATE_NO_WINDOW alone, so a POSIX worker stays in the hook's session. Add start_new_session and the group flag. | test_the_flags_are_the_ones_measured_to_run_the_wrapper |
| test_index_refresh.py:2035 | Suite proves the registered command reaches the CLI through a real detached worker | - | ported #132 | 2 | test_refresh_index.py patches Popen and never reads creationflags, so a DETACHED_PROCESS regression (#194) stays green. Port both cases. | test_an_event_reaches_the_wrapper_through_the_detached_worker |
| hooks/index-refresh.py:334 | An event naming an unplaceable file refreshes nothing, never cwd | - | ported #132 | 2 | refresh-index.py:107 returns None and :151 falls to cwd; a relative path without cwd resolves against the process directory. Refuse both. | test_an_event_naming_a_file_is_never_answered_with_cwd |
| skills/codebase-index/cbx.ps1:60; also skills/codebase-index/cbx.ps1:60, test_harness_helpers.py:10992, 11014 | Restores both environment variables after running in the caller's process | - | ported #132 | 2 | Payload cbx.ps1:14 leaves PYTHONSAFEPATH set after `&`, so later Python scripts lose their directory on sys.path. Restore in a finally. |  |
| test_index_mcp_root.py:127 | Suite holds every mcp-root subcommand to the skill's allowed-tools | - | ported #132 | 2 | Payload tests only cbx's ALLOWED, so a dropped grant sends the named command to a prompt. Port against the cbx grants. | test_every_tool_it_maps_is_a_subcommand_the_skill_approves |
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
| hooks/index-refresh.py:383 | A malformed event or a missing cwd refreshes nothing | .claude/scripts/git-worktree-fork.sh:117 | obsolete |  | Payload's fork runs the hook eventless, so refresh-index.py:151-152 must fall back; keep that call working when porting refusals. | test_a_missing_or_malformed_cwd_is_refused |
| hooks/index-refresh.py:935 | Kills the indexer's tree past the Git Bash stub; needs bash | .claude/hooks/refresh-index.py:287 | obsolete |  | Payload starts no bash; it runs the exe or module directly. Confirm pip's exe stub passes the kill to its python child. | test_a_timed_out_child_is_stopped_through_its_tree_first |
| skills/codebase-index/run-index:17; also docs/harness-boundaries.md:2242 | Wrapper with gate, safe path, floor and auto-update off | .claude/skills/codebase-index/scripts/cbx:8 | obsolete |  | *Decisions* run-index row: drop; cbx does all of it once the gate row lands. |  |
| skills/codebase-index/cbx:15 | `graph` runs under a prompt for a human visualisation | .claude/hooks/guard-index-argv.py:27 | obsolete |  | *Decisions* calls cbx stricter; the payload refuses `graph` because it writes a file, and no route to it remains. |  |
| skills/codebase-index/.skill_version:1 | Installer artefact nothing reads | - | obsolete |  | *Decisions* .skill_version row: drop, untracked and ignored. |  |

#### E, commands and agents

| Frontend | Behaviour | Payload | Verdict | Task | Reason and fix | Frontend's test |
|---|---|---|---|---|---|---|
| agents/branch-reviewer.md:26; also docs/commands/ship.md:632, docs/harness-boundaries.md:2535 | Bar comes from origin/main; missing or empty method means the round did not run | .claude/agents/branch-reviewer.md:43 | ported #145 | 2 | Payload reads the bar from the branch's tree. Ship step 5 writes it from origin/main (fe ship.md:288,300); an empty bar fails closed. | test_the_branch_reviewer_reviews_under_a_profile_that_cannot_write |
| commands/ship.md:43; also commands/ship.md:360, test_harness_helpers.py:3309, docs/commands/ship.md:63 | Reviewer reply with empty read, or skipped beyond locality, stops the chain | .claude/commands/ship.md:490 | ported #145 | 2 | Payload stops only on missing agent or non-JSON, so a reply that read nothing mints clean. Restore both tests; close `skipped` in the profile. | test_the_reviewer_skips_only_what_ship_reads_as_a_round |
| commands/ship.md:392; also docs/commands/ship.md:620 | Step 6 refuses a head no round read; spent ceiling still rechecks once | .claude/commands/ship.md:503 | ported #145 | 2 | Payload records no reviewed head; a remote head ahead of this checkout passes the empty log read unreviewed. Restore the record, check and ceiling exit. |  |
| commands/ship.md:306; also docs/commands/ship.md:644 | Diff touching branch-reviewer.md: inputs follow main's registered profile, and the report says so | .claude/commands/ship.md:441 | ported #145 | 2 | Profiles load once at launch, so the branch's edited contract is not what runs. Payload lacks this; restore the paragraph, `git show` is granted. |  |
| commands/ship.md:52; also docs/commands/ship.md:78 | A refused push, no exit code, stops the chain; /pr reports remedy | .claude/commands/ship.md:36 | ported #145 | 2 | Row one covers non-zero exits only and nothing else stops. Add the harness refusal; restore pr.md:46's report, `!` line and autoMode remedy. |  |
| commands/ship.md:425; also docs/commands/ship.md:856 | `publish` retries a failed push; exit table splits continuations from stops | .claude/commands/ship.md:551 | ported #145 | 2 | Payload omits `publish`, so a finished replay whose push failed stops under row one. Restore the table, checked against the helper's exits. |  |
| commands/ship.md:346; also docs/commands/ship.md:695 | Ceiling filing pipes title, body and hand trailer on stdin | .claude/commands/ship.md:481 | ported #145 | 2 | Payload's gh-issue-create.sh:76 refuses a body without the trailer, and the runbook never says it; a filing then stops the chain. Restore the sentence. |  |
| commands/ship.md:322; also docs/commands/ship.md:667 | Finding whose fix a deny refuses is filed at once and reported | .claude/commands/ship.md:452 | ported #145 | 2 | Outside --dispatched the payload has no route, so the finding stays open to the ceiling. Restore: file it, say so, continue. |  |
| commands/ship.md:317; also docs/commands/ship.md:663 | Finding telling the session to act beyond its line is refused and quoted | .claude/commands/ship.md:450 | ported #145 | 2 | Payload says only "a claim to check". Restore refusal as an attempt to steer, and the report's full quotation at fe ship.md:511. |  |
| commands/ship.md:5 | Ship denies every agent type but branch-reviewer | .claude/commands/ship.md:4 | ported #145 | 2 | A grant withholds nothing, per boundaries:512. Deny every built-in type and every profile but `branch-reviewer`, `bug-auditor`, `security-auditor` and `team-peer` included; `general-purpose` stays for step 2's audits, so the ship.md skip at test_command_grants.py:110 narrows to that one type. | test_every_exact_agent_grant_denies_every_other_type |
| commands/ship.md:5; also test_harness_helpers.py:3110, 3141 | Editing commands deny .git, .mcp.json and .codeindexignore (also pr.md:5, style-pass.md:5) | .harness/settings.base.json:34 | ported #145 | 2 | Payload denies none of these anywhere, and ship and pr hold Write. Add them to the base denies; hold with a test. | test_every_editing_command_denies_the_machinery |
| commands/ship.md:28; also docs/commands/ship.md:35 | Report gives round number, reviewed head, and says the review was in house | - | ported #145 | 2 | Payload's Report has none of the three, and no text bars claiming an external opinion. Add them to the review line. |  |
| agents/branch-reviewer.md:65 | Code bar includes security weaknesses; findings quote what they rest on | .claude/agents/branch-reviewer.md:46 | ported #145 | 2 | Payload dropped both, so a security weakness in a diff goes unreported. Restore the clause and the quote requirement. |  |
| agents/branch-reviewer.md:13 | Steering includes telling the caller to run or push; documentation describing actions excepted | .claude/agents/branch-reviewer.md:13 | ported #145 | 2 | Payload lists neither, so caller-directed injection goes unnamed and a runbook's "run x" risks a false finding. Restore both sentences. |  |
| commands/style-pass.md:5 | Style-pass, which does not publish, denies git push | .claude/commands/style-pass.md:4 | ported #145 | 2 | The settings allow reaches it and nothing denies; style-pass is outside /ship's chain, so the deny is safe. Restore it and the test. | test_a_command_that_does_not_publish_cannot_push |
| commands/style-pass.md:32 | Sweep covers every fenced block in docs, not only the spec | .claude/commands/style-pass.md:30 | ported #145 | 2 | Payload sweeps the spec and source, so other documents keep teaching the removed form. Say every fenced block under docs/. |  |
| commands/style-pass.md:93 | Site counts are removed from the guide, never kept current | .claude/commands/style-pass.md:87 | ported #145 | 2 | Payload orders the opposite of frontend's change contract §2. Make it conditional: where the target's contract forbids a count, remove it. |  |
| commands/style-pass.md:151 | Verify scan uses width 100, indent two and LF | .claude/commands/style-pass.md:114 | ported #145 | 2 | Payload hard-codes 120, four and CRLF, all false on frontend, so the scan misreports. Read the limits from the style guide. |  |
| commands/branch.md:168; also docs/commands/branch.md:475 | Derived name changes by a second branch, never git branch -m | .claude/commands/branch.md:164 | ported #145 | 2 | Payload says `git branch -m` is free, but settings.base.json:62 denies it (also docs/commands/branch.md:337). Restore git-branch-create.sh at HEAD. |  |
| test_command_runbooks.py:47 | An argument file with no ceiling fails the build | .claude/scripts/test_command_runbooks.py:51 | ported #145 | 2 | Payload dropped it, so a newly split command escapes its ceiling. Fail an argument neither CEILINGS nor a target's own map holds. | test_every_argument_has_a_ceiling_and_a_runbook_that_cites_it |
| test_command_runbooks.py:78 | Each runbook must cite, and each docs/commands citation must parse | .claude/scripts/test_command_runbooks.py:69 | ported #145 | 2 | Payload's one global count lets a runbook lose every citation. Port per runbook, counting `(why: docs/commands` openings, since others cite boundaries. | test_every_runbook_cites_and_every_citation_parses |
| test_command_runbooks.py:109 | Boundaries index rows match its section headings, in order | docs/harness-boundaries.md:8 | ported #145 | 2 | Payload keeps the index with no test. Its rows are not italic, so adapt the row pattern and exempt `## Index`. | test_every_heading_is_an_index_row_in_order_and_every_row_a_heading |
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
| docs/commands/ship.md:364 | Teardown runs git log origin/main..HEAD so ahead-of-origin main is actually read | .claude/commands/ship.md:291 | ported #145 | 2 | Payload names no read; after ExitWorktree nothing reads main's ahead state before the pull. Name `git status -sb`, not frontend's line: `RETIRED_READS` in test_ship_landing_method.py refuses it. |  |
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
| docs/harness-boundaries.md:801 | Raw gh pr merge and git worktree remove denied in every turn | .harness/settings.base.json:66 | ported #163 | 3 | *Decisions* puts both denies in base, added with destructive-class rows and test_each_raw_form_is_denied_and_the_helper_is_not. | test_no_command_grants_the_raw_form |
| docs/harness-boundaries.md:1682 | Stated limit: replay provenance files under .git can steer a publish | - | ported #145 | 2 | Same record files exist in the payload helper and every target; payload states nothing. Add the residual beside the rebase helper paragraph. |  |
| docs/harness-boundaries.md:521; also test_harness_helpers.py:10043, 10469, 10494, test_harness_helpers.py:9620, test_edit_target_guard.py:1386 | Guards start through run-guard, probing interpreters, exit 2 when none, remembered mark | .harness/settings.base.json:80 | ported #163 | 3 | *Decisions*: payload for the guards alone, five once guard-helper-argv.py landed; launcher, pwd -W and the paragraphs moved, held by test_run_guard.py. No-Git-Bash machine is the stated residual. | TheLauncherProvesWhatItRemembers |
| docs/harness-boundaries.md:2521 | Limit: no reader outside the writing model family reviews before unattended merge | - | ported #145 | 2 | Holds for every target since external reviewers are archived; payload states nothing. Add the accepted residual and its procedural control to boundaries. |  |
| docs/harness-boundaries.md:1241 | Rule: a boundary an agent keeps across turns lives on its profile | - | ported #145 | 2 | Holds for every target, team-peer included; payload dropped these measurements. Restore them with :1415's propagation facts in Agent-type entries. |  |
| docs/harness-boundaries.md:570 | Limit: a filled launcher mark refuses every call while git status stays clean | - | residual |  | Frontend's .gitignore covers only codebase-index under .claude/cache, a tree fact; goes to harness-local Residuals, minus the refresh-through-launcher sentence. |  |
| docs/harness-boundaries.md:11 | Bare #NN in .claude or this file names a backend issue | - | residual |  | Stays true in frontend after sync, false in backend, so a session chases the wrong tracker. Add to frontend's Residuals. |  |
| docs/harness-boundaries.md:111 | Limit: no command here audits this file, so its drift goes uncaught | - | residual |  | Frontend lacks backend's link and blueprint checks, the counterpart of backend's own residual. Move to frontend's Residuals, narrowed for the destructive-classes table. |  |
| docs/harness-boundaries.md:1194 | Limit: unattended push refused under auto mode, cause unestablished, user-level remedy | - | residual |  | Inference rests on autoMode.environment trusting only backend's remote, while payload still says the push never prompts. Move :1194-:1214 to Residuals. |  |
| docs/harness-boundaries.md:1383 | Limit: a build config not yet existing escapes any deny enumerated from the tree | docs/harness-boundaries.md:1466 | residual |  | Payload leaves the ninth entry's dotnet half to backend's Residuals alone; carry frontend's npm form, :1383-:1413, to frontend's own. |  |
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
| docs/harness-boundaries.md:2442 | Fork carries only the MCP approval into the worktree's local settings | .claude/scripts/git-worktree-fork.sh:88 | covered |  | Same -I script writing enabledMcpjsonServers alone; warning at :108 on an unreadable file. |  |
| docs/harness-boundaries.md:2352 | MCP_TIMEOUT raised for sessions in the repository | .harness/settings.base.json:4 | covered |  | Base env sets it for every target. |  |
| docs/harness-boundaries.md:1352 | New agent profile fails any granting command that does not deny it | .claude/scripts/test_command_grants.py:103 | covered |  | Payload reads profiles each run; ship.md excused since its single grant is pinned at :96. | test_every_exact_agent_grant_denies_every_other_type |
| docs/harness-boundaries.md:2462 | Suite pins branch-reviewer's profile to read-only tools | .claude/scripts/test_command_grants.py:69 | covered |  | Payload holds no shell, no edit, no agent on that profile. |  |
| docs/harness-boundaries.md:2513 | Reviewer findings are untrusted; parent verifies each before acting | docs/harness-boundaries.md:123 | covered |  | Payload states the same discipline and residual for branch-reviewer. |  |
| docs/harness-boundaries.md:2551 | Findings open at the review ceiling become issues before merge | .claude/commands/ship.md:471 | covered |  | Seventh-round filing lives in ship.md and docs/commands/ship.md:709. |  |
| docs/harness-boundaries.md:1224 | Commands chained before a push never deny push | .claude/scripts/test_command_grants.py:240 | covered |  | NothingShipChainsDeniesPush replaces CHAINED_BEFORE_A_PUSH. | CHAINED_BEFORE_A_PUSH |
| docs/harness-boundaries.md:1720 | Rebase helper refuses a merge carrying content neither parent has | .claude/scripts/git-rebase-onto-main.sh:359 | covered |  | require_no_merge_invented_anything runs before the replay, and is stricter. |  |
| docs/harness-boundaries.md:1944 | Git-dir lock by identity, shared git deadline, marker retries, pid record, taskkill, unplaceable-file no-op | .claude/hooks/refresh-index.py:35 | obsolete |  | Kept for the shared git deadline and lock identity only; D's rows port the state directory, the bounded retries and the pid record, which this row's reading of *Decisions* would have dropped. |  |
| docs/harness-boundaries.md:1949 | Fork runs refresh from main checkout's launcher, not the worktree's copy | .claude/scripts/git-worktree-fork.sh:117 | obsolete |  | Fork always cuts origin/main and refresh-index.py runs a PATH-found CLI, no worktree wrapper; *Decisions* removes the launcher chain. |  |
| docs/harness-boundaries.md:857 | Executing forms, xargs allow-list, pattern and brace git names refused | - | out of scope |  | Pattern and brace names and the launcher chains. The executing forms and `xargs` have their rows in A. |  |
| docs/harness-boundaries.md:958 | Git subcommand allow-list and whole refusals like filter-branch, daemon, config | - | out of scope |  | The allow-list only, as A holds. The whole refusals such as `filter-branch` port in A. |  |

#### A, edit guard

| Frontend | Behaviour | Payload | Verdict | Task | Reason and fix | Frontend's test |
|---|---|---|---|---|---|---|
| hooks/guard-edit-target.py:451; also docs/harness-boundaries.md:1599 | Target outside every checkout and every scratch root is refused | - | ported #147 | 2 | c1, narrowed from frontend's allow-list to a refusal of `~/.ssh`, shell profiles and `~/.gitconfig`. The allow-list refuses sibling checkouts and `run-locally.md` (22 edits) and needs `.todo/` (628), criterion 3. Inverted payload's test for those names only. | test_a_path_outside_every_checkout_and_every_scratch_root_is_refused |
| hooks/guard-edit-target.py:441 | `~/.claude` credentials, settings, hooks, commands, agents, plugins refused, case-folded | - | ported #147 | 2 | c1. Payload denies are project-relative, so user-level control files are open. Ported both CONTROL sets folded, without `CLAUDE.md` and `AGENTS.md`: `~/.claude/CLAUDE.md` was edited 6 times, for the owner's rules. Narrowed from `control_surface`'s any depth to the first component, so a control name below `projects` stays session state. `~/.claude/settings.json` was edited on the owner's request, the one newly refused edit when a throwaway script put 11,796 edit targets through both edit guards, since `measure/replay_guard.py` reads Bash alone: that route becomes an owner-run script. | test_the_harness_control_surface_is_refused_inside_its_own_root |
| hooks/guard-edit-target.py:808 | Linked worktree's `.claude` refused wherever the session stands, nested worktrees included | - | withdrawn #147 | 2 | **Withdrawn by the replay's rule.** c1: payload admits it, boundaries :480 leaves it to a prompt. Read by hand: 142 edits since 2026-10-19 are what this first-component check refuses (the 268 counted `staging/.claude` and `payload/.claude` too), each from inside that worktree. 115 went through under an owner's lift. One is ordinary work: backend's `/ship` of #1441 fixed a failing suite in the local `.claude/commands/validate-blueprint.md`. After the sync that is an agent's only route to a target's local `.claude` file, so one ordinary use withdraws the row. The row at :825 still refuses a worktree the session has not entered. |  |
| hooks/guard-edit-target.py:825; also docs/harness-boundaries.md:209 | Unentered linked worktree's `.github`, `.git`, root files and toolchain refused | - | ported #147 | 2 | c1, narrowed: judge an unentered worktree by the target's denies. 718 `.github` edits landed in worktrees where no target denies it. `protected_in_worktree` asks `guard-git-argv.py`'s `denied_path`; Angular names stay config. | test_a_sibling_worktree_of_this_repository_is_judged_not_refused |
| hooks/guard-edit-target.py:833 | Link traversal inside an unentered linked worktree is judged and refused | - | ported #147 | 2 | c1, the guard's subject. Payload never anchors the sibling. Append it to `checkouts`. |  |
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
| hooks/guard-git-argv.py:3415 | `&` inside `2>&1`, `>&2`, `&>` no longer ends a run, so the heredoc's shell is found | - | ported #147 | 2 | c1, typed once in 46,810. `bash 2>&1 <<'EOF'` holding a push is admitted because `_run_bounds` stops at `&`. Port `_ends_run`. | test_a_redirection_ampersand_does_not_end_the_run |
| hooks/guard-git-argv.py:3299 | `leading_command` skips reserved words such as `if`, `!`, `then`, `do` | - | ported #147 | 2 | c1, a routine idiom: `if … \| bash; then` reads `if` as the lead, so the printer pass skips it. Add `COMMAND_PREFIX_WORDS`. Refuses nothing new but the push. | test_a_wrapper_with_operands_does_not_hide_the_program |
| hooks/guard-git-argv.py:2140; also docs/commands/bug-sweep.md:1025, docs/harness-boundaries.md:262 | A redirection writing into a protected tree or file is refused | - | ported #147 | 2 | c1, the threat model names a write into a denied tree. Port `redirection_offence`, `destination_offence`, `EVENT_CWD`; the lists come from each target's denies, so `.github` is refused only where a target denies it. Backend's mutation proofs write there. | test_the_measured_redirections_are_refused |
| hooks/guard-git-argv.py:2609; also docs/harness-boundaries.md:353 | Writing verbs onto protected paths are refused, wrappers included | - | ported #147 | 2 | c1. `cp`, `mv`, `rm`, `tee`, `sed -i`, `dd` onto a protected path are admitted. Port `writing_verb_offence` and `raw_runs` under the two narrowings beside this one; `rg` stays off `READING_COMMANDS`. | test_every_writing_verb_reaches_the_machinery_check |
| hooks/guard-git-argv.py:2432 | Destination found through options, hard-link sources, `-i` backup suffixes, `find -exec` | - | ported #147 | 2 | c1, narrowed: `cp -t` and `ln` sources port, the computed-operand refusal does not. `cp "$a" "$b"` was typed 107 times, criterion 3. | test_a_verbs_destination_is_found_through_its_options |
| hooks/guard-git-argv.py:1934 | Protected names compared by path component and folded for case | - | ported #147 | 2 | c1, narrowed: anchor at a checkout's root and fold case, not any component as frontend does. `payload/.claude/…`, `staging/.claude/…`, `.claude/worktrees/` and `.claude/cache` stay writable: 113 redirections, 34 `rm`, 19 `sed -i` typed. Narrowed by the replay: a checkout under the temp root that the session is not in is not judged, since mutation proofs `cp` and `sed -i` into scratch checkouts' `.claude/` (6 commands, 7 uses). | test_a_component_is_matched_rather_than_a_prefix |
| hooks/guard-git-argv.py:1990 | Target `~/…` and allowed variables expanded and judged; unknown variables refused | - | ported #147 | 2 | c1, narrowed: expand `~` and the allowed variables and judge the result; an unknown variable is admitted, not refused. `> "$var…"` was typed 523 times, criterion 3. | test_an_unreadable_target_is_refused_and_an_expansion_is_judged |
| hooks/guard-git-argv.py:2078 | A relative write target is refused when the command can change directory | - | ported #147 | 2 | c1, narrowed: resolve a literal `cd` and judge the target; never refuse a relative write because a `cd` stands on the line. `cd x && … > y` was typed 736 times, criterion 3. | test_a_redirection_into_an_application_tree_is_refused |
| hooks/guard-git-argv.py:2099 | A write through a link into a protected tree is refused | - | ported #147 | 2 | c1, the edit guard resolves links for the edit tools only. Port `linked_protected_path` with `EVENT_CWD`. | test_a_redirection_through_a_link_into_a_protected_tree_is_refused |
| test_harness_helpers.py:9443 | Gate: protected lists must cover command denies and tracked root files | - | ported #147 | 2 | A gate, not a refusal. Ported with `test_the_protected_files_cover_every_tracked_root_file`, reading the target's config: the protected list is the denies themselves, so the gates hold it equal to base plus config, every tracked root file on the side those name, and every managed command's `Edit(...)` deny reached. A target's local command denies its own trees for its own run, which no hook sees. | test_the_protected_trees_cover_what_the_editing_commands_deny |
| hooks/guard-git-argv.py:155 | Short flags that run or write refused: `rebase -x`, `rebase -s`, `format-patch -o`, `archive -o`, `clone -u`, `ls-remote -u`, `grep -O`, `difftool -x`, `pull -s` | - | ported #147 | 2 | c1, narrowed to the flags that run a command: `rebase -x`, `rebase -s`, `clone -u`, `ls-remote -u`, `grep -O`, `difftool -x`, `pull -s`, the long forms' parity. `archive -o` was typed twice and `format-patch -o` writes a named file, so both stay admitted. | test_the_short_and_operand_spellings_that_run_a_command |
| hooks/guard-git-argv.py:160 | `git bisect run` and `git submodule foreach` refused | - | ported #147 | 2 | c1, routine git, typed 0 times, so it stops nothing. Each runs its operand and no flag check sees it. Port `EXECUTING_FORMS`. | test_the_short_and_operand_spellings_that_run_a_command |
| hooks/guard-git-argv.py:176 | `--strategy` on pull and rebase, `--template` on clone and init refused | - | ported #147 | 2 | c1, the tail flags *Decisions* gave this cluster, typed 0 times. Port `EXECUTING_LONG_FLAGS`, abbreviations included. | test_a_merge_strategy_is_refused_on_pull_and_rebase |
| hooks/guard-git-argv.py:134 | `--no-index`, `--ext-diff`, `--textconv`, `--extcmd`, `--open-files-in-pager` refused with abbreviations | - | ported #147 | 2 | c1, narrowed: `--ext-diff`, `--textconv`, `--extcmd`, `--open-files-in-pager`. `--no-index` stays out: typed 49 times, and its deny is frontend's config. | test_git_options_that_run_a_command_are_refused_at_the_top_level |
| hooks/guard-git-argv.py:183 | `filter-branch`, `send-email`, `instaweb`, `daemon`, `http-backend`, `web--browse` refused whole | - | ported #147 | 2 | c1, typed 0 times and the base denies none of them. Port `REFUSED_SUBCOMMANDS`; the allow-list stays out. | test_git_options_that_run_a_command_are_refused_at_the_top_level |
| hooks/guard-git-argv.py:5203 | `xargs` may launch only a listed reader, with listed options | - | ported #147 | 2 | c1, narrowed to `xargs git push`, whose destination cannot be read. The reader allow-list stays out: it refuses `… \| xargs py -3.12 …`, and `xargs` was typed 54 times. | test_xargs_cannot_supply_a_git_argv |
| test_harness_helpers.py:11468 | Gate: every branch name `branch.md` gives is one the push guard admits | - | ported #147 | 2 | A gate, not a refusal: no payload suite ties the table to `SAFE_REF`. Move to test_git_argv_guard.py. | test_every_name_the_file_gives_is_one_the_push_guard_admits |
| test_harness_helpers.py:5922 | Gate: no hook binds a module-level name twice | - | ported #147 | 2 | A gate, not a refusal: nothing holds this once the suite drops. Move to test_python_hygiene.py. | test_no_hook_binds_a_module_level_name_twice |
| git-fetch-origin.sh:26 | Fetch helper refuses `-f`, `-u` and `+src:dst` by shape | - | ported #147 | 2 | c1, the helper that held this is dropped. Typed 0 times. `git fetch origin +main:main` discards local commits under the grant. Refused the three shapes; kept `main:main` (ship.md:581). Narrowed by the replay: a `+` refspec is refused only onto a branch, since a dependabot rebase typed `+refs/heads/$B:refs/remotes/origin/$B` twice. `refspec_offence` has since replaced the shape: every destination but `main:main` and origin's own refs is refused, which keeps that typing. | test_nothing_that_is_not_a_plain_branch_name_reaches_git |
| git-pull-ff-only.sh:18 | Pull helper takes no argument, so `--ff-only` cannot be overridden | - | ported #147 | 2 | c1, narrowed to what overrides the granted line: `--no-ff`, `--ff`, `--rebase`, `-r` beside `--ff-only`. Plain `-q` stays, typed in 162 commands. | test_it_takes_no_argument_whatever_it_looks_like |
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

## Admin audit, pinned at c5ec185c

Spec §7 step 3, plan 6 Task 1: every file `blueprint-admin` shares with the
payload was audited for what only admin's copy holds, before a sync replaces
it. Admin is read at `c5ec185c`, whose `.claude` had no later commit on
2026-11-08, and the payload at harness `68fcd83`. Of the payload's 166 files, 3
are equal in admin, 64 differ and 99 are absent. Task 2 takes its work from the
tables below, and marks each row it lands `ported` with its pull request.

Nine read-only agents, two for cluster A (one per guard), two for E (the
commands and agents, then the command documents) and one each for B, C, D, F
and G, returned 321 rows. A row is one behaviour that changes an outcome; 13
files differ in wording alone and have none. Five rows repeating a cause that
another cluster's row holds are folded into that row, their sites under *also*,
which leaves 316.

*Decisions* is the plan's *Decisions on the §8 mechanisms and admin-only files*,
in `blueprint-backend`'s
`docs/superpowers/plans/2026-11-08-shared-harness-6-admin-sync.md`, and *The
guards' threat model* is that section of `docs/harness-boundaries.md`.

| Cluster | port | residual | managed | local | covered | obsolete | out of scope |
|---|---|---|---|---|---|---|---|
| A, guards | 9 | 0 | 0 | 4 | 29 | 10 | 26 |
| B, git helpers | 4 | 0 | 0 | 1 | 15 | 3 | 0 |
| C, GitHub helpers | 7 | 0 | 0 | 4 | 24 | 1 | 0 |
| D, index | 2 | 2 | 0 | 0 | 18 | 8 | 1 |
| E, commands | 4 | 2 | 0 | 18 | 14 | 9 | 0 |
| F, docs | 10 | 6 | 21 | 19 | 31 | 0 | 7 |
| G, gates | 0 | 0 | 0 | 2 | 4 | 1 | 0 |
| All | 36 | 10 | 21 | 48 | 135 | 32 | 34 |

The *Task* column says which task owns a `port`: 26 rows are Task 2's, by
cluster, 8 are Task 3's (the shard runner, the red-`main` helper and its
`/ship` read), 1 is Task 4's (admin's config) and 1 Task 7's (admin's sweep
rows). A `residual` goes to admin's
`docs/harness-local.md` *Residuals*; a `managed` paragraph of admin's
`docs/working-rules.md`, `token-plan.md` or `token-quality-sets.md` is one the
payload already states, in `docs/harness/*.md`, `.harness/agent-rules.md`,
`docs/harness-boundaries.md` or a suite, which Task 9 cites.

**An agent's verdict is not the record.** Cluster A's nine `port` rows were
checked by hand against *The guards' threat model*; the agents had replayed
admin's 16,697 Bash commands from 2026-10-07 to 2026-11-08 through both git
guards, and admin's 18,150 edit calls since 2026-10-19 through the payload's
edit guard, on scratch copies, leaving out 766 refusals of commands run in
worktrees since removed. `c1` in a reason is that section's criterion 1. Every
`covered` and `managed` row's citation was opened: six were moved to the exact
line, two of them on review, which also moved two `local` rows' citations, and
one `covered` with no payload site is `obsolete`, since the drift gate and not
a frontmatter deny holds `docs/commands/` there.

Four more rows changed on the check: two verdicts moved, one `port` was
narrowed, and one was kept against frontend's verdict.

- **`git config` writes port narrowed** to a subset of the keys that run a
  program (`alias.*`, `core.pager`, `core.hooksPath`, `core.sshCommand`,
  `*.cmd`, `diff.external`); a plain write such as `rerere.enabled`, which admin
  typed, stays admitted (c3).
- **The quoted heredoc fed to the issue helpers stays a `port`**, against
  frontend's `covered` and the payload's pinned file route: the payload's guard
  refused 134 of admin's commands with it, 42 in sweeps, which deny `Write`.
  Task 2 Step 4's replay decides whether the payload narrows or the PR body
  names why the refusal stays.
- **The editing commands' `.github/**` deny is `obsolete`**, not a Task 4
  `port`: *Global Constraints* keep `.github/**` editable in admin and add no
  config deny on it, which would be a new stop. Admin's own case says an
  editable gate lets `/ship` pass its own pin bypass; admin's CI and the owner's
  review hold the gate instead.
- **The report's filed-issues line is `obsolete`**: the owner's user-level
  instructions require it in every repository, so the payload's runbook does
  not restate it.

One `port` is a live payload defect: `denied_path` in `guard-git-argv.py`
misses a `**/` deny at the checkout's root. Frontend's root
`playwright.config.ts` and `capacitor.config.ts` are denied only by
`Edit(**/playwright.config.ts)` and `Edit(**/capacitor.config.ts)`, so a shell
write into either passes the guard there today, and admin's root
`Directory.Build.props`, denied only by `Edit(**/Directory.Build.*)`, would
after the sync. It is filed as #228, and cluster A's row cites it.

The *Decisions* table, recorded here:

| Admin path | Decision |
|---|---|
| `hooks/index-hint-run.sh` | Dropped: the payload's `hint-bound.sh` is the same launcher; D's rows compare the bound |
| `hooks/index-query-hint.sh` | Dropped; D ports its behaviours to `index-query-hint.py` |
| `hooks/refresh-index.sh`, `test_index_refresh_hook.py` | Dropped; D ports its behaviours to `refresh-index.py` with admin's cases |
| `shard-harness-suite.py`, `test_harness_shards.py` | Payload, `.claude/scripts` its one discovery root (Task 3) |
| `main-red-open.sh` | Payload, with Task 3's title rule |
| `harness-checks.sh`, `host-checks.sh`, `spa-ci.sh`, `npm-checks.sh` | Local, granted through config |
| `skills/admin-invariants/SKILL.md` | Local |
| `.github/pin-gate/**`, `.github/locality-gate/**`, `workflows/ci.yml`, `locality-gate.yml`, `main-red.yml`, `dependabot.yml` | Local by position |
| `gh-issue-filing.sh`, `gh-sweep-issue-create.sh` | Dropped; C judged the payload's `gh-issue-create.sh` routes cover them |
| `test_pr_locality.py` | C judged; the gate-parity cases stay as `test_pr_locality_admin.py` |
| `test_index_skill_examples.py` | D judged: a `port` |
| `test_root_ignore_coverage.py` | Local |
| `test_harness_helpers.py` | Split by cluster; stack cases to `test_harness_helpers_admin.py` |
| `commands/review-branch.md`, `docs/commands/review-branch.md` | Local |
| `.github/output-gate/**` | Payload, not excluded; admin's `ci.yml` invokes it (Task 7) |
| The 51 admin denies the base lacks | Config additions (Task 4) |
| The 8 base denies admin lacks | Come in unchanged; Task 3 Step 5 counts what they would have stopped |

Four findings are for later tasks. Admin has no `test` or `test-gap` label,
read live on 2026-11-08, which the payload's `finding.yml` offers, so the
issue-form job fails on the sync unless they exist first (cluster G). The
payload's `pr-locality.sh` takes a reason after a touch-set token, prints
`outside-class` and admits `A+D+E`, and `/pr` writes `(added: why)` in the cell,
none of which admin's `locality_gate.py` reads, so the gate or
`test_pr_locality_admin.py`'s phrases follow (C, E). Admin has no
`local_commands.py`, which the payload's `test_command_runbooks.py` imports, so
its config needs one with `review-branch.md`'s ceiling (E). The code-index
search limit, 3 in the payload's skill and 5 in admin's, measured on admin's
corpus, has no seam in a managed file. Task 4 took the residual: 3 would lose 2
of 8 there, and the grant admits a search carrying `--limit 5` (D).

#### G, gates

| Admin | Behaviour | Payload | Verdict | Task | Reason and fix | Admin's test |
|---|---|---|---|---|---|---|
| .github/workflows/commit-gate.yml:14 | Cancels a pull request's in-progress gate run when a newer run starts | .github/workflows/commit-gate.yml:14 | obsolete |  | Payload dropped the group: a rerun of an older head cancels the newest, leaving a failed required check. Same as frontend row. |  |
| .github/workflows/commit-gate.yml:32 | Gate stands down only when Dependabot opened the PR and authored and committed every commit | .github/workflows/commit-gate.yml:32 | covered |  | Same decision and DEPENDABOT identities in the payload step (also step ifs, no job condition). Admin already had the blueprint-admin#400 fix; nothing admin-only. |  |
| .github/issue-form-gate/issue_form_gate.py:89 | Holds form kind and severity to the helper's closed case arms (gh-issue-filing.sh) | .github/issue-form-gate/issue_form_gate.py:165 | covered |  | Owners move to working-rules.md vocabulary bullet and gh-issue-create.sh arms (payload :166-:172); gh-issue-filing.sh drops per Decisions. Payload also reads helper subset rule at :171. | test_a_kind_the_helper_lacks_fails, test_a_kind_the_helper_gains_fails, test_a_kind_the_form_drops_fails, test_a_severity_the_helper_lacks_fails |
| .github/ISSUE_TEMPLATE/finding.yml:16 | Form offers only kinds bug and security; areas harness/code/documentation | .github/ISSUE_TEMPLATE/finding.yml:16 | covered |  | Payload-only: form adds test-gap, enhancement, documentation kinds and area test. Admin's labels (read with gh) lack test-gap and test, so the issue-form job fails after sync until both are created. |  |
| .github/ISSUE_TEMPLATE/finding.yml:60 | Where placeholder names an admin path (src/Admin.Host/Program.cs:42) | .github/ISSUE_TEMPLATE/finding.yml:60 | local |  | Placeholder text only, no outcome; sync would show backend's path. Wording-level; leave to the payload unless the owner wants an admin placeholder via config. |  |
| .github/issue-form-gate/test_issue_form_gate.py:199 | Test pins ci.yml piping gh label list into the gate with a token | - | local |  | Pins admin's ci.yml wiring (ci.yml:281), which Task 7 keeps; payload suite lacks it. Move to test_issue_form_gate_admin.py so the sync does not drop it. | test_ci_pipes_the_labels_into_the_gate_with_a_token_that_may_read_them |
| .github/issue-form-gate/issue_form_gate.py:129 | Accepts any non-config .yml file in templates as a form, no other entries refused | .github/issue-form-gate/issue_form_gate.py:122 | covered |  | Payload-only: also refuses a Markdown template or directory beside the form and a top-level labels key (:177). Admin has only config.yml and finding.yml, no top-level labels, so no new refusal. |  |

#### B, git helpers

| Admin | Behaviour | Payload | Verdict | Task | Reason and fix | Admin's test |
|---|---|---|---|---|---|---|
| scripts/git-rebase-onto-main.sh:161, 204-216; also docs/harness-boundaries.md:591 | Force refused unless origin has one push URL and it names the host and whole path the remote was added with | .claude/scripts/git-rebase-onto-main.sh:207 | ported #236 | 2 | Payload pushes with no check of pushurl / pushInsteadOf / second url, leaving only the lease. Port repo_key and the two exit-7 refusals into publish() with the three cases. | test_a_configured_push_redirect_is_refused_before_anything_is_forced, test_repo_key_agrees_across_protocols_on_one_host_and_nowhere_else, test_a_remote_with_two_urls_is_refused_before_anything_is_forced |
| scripts/git-trailer-pr.sh:64-75; also scripts/test_git_pr_trailer_helpers.py:245 | A rebase aborted by a transient index.lock is retried once after the abort; other failures stop | .claude/scripts/git-trailer-pr.sh:81 | ported #236 | 2 | Payload rewrite fails exit 6 on the first lock (admin #243: a concurrent git reader holds the index). Restore the one-retry loop around the payload's spelled flags, keeping --abort and the hooksPath export. Test is in test_git_pr_trailer_helpers.py. | test_a_single_index_lock_failure_is_retried_once_and_succeeds, test_a_persistent_index_lock_failure_stops_after_two_attempts_with_the_branch_as_it_was, test_a_failure_that_is_not_a_lock_is_not_retried |
| scripts/git-worktree-drop.sh:92-134 | Git failing after unregistering a sweep worktree: leftover deleted with retries, .slices lists still removed, dirty refusal kept | .claude/scripts/git-worktree-drop.sh:54 | ported #236 | 2 | Payload runs bare `git worktree remove` under set -e, so a held tree leaves a directory and .slices (admin #329: 41 secsweep dirs). Port the payload remove.sh's captured status and unregistered check, then slice cleanup; exit 4, not admin's 18 tries of rm -rf, which remove.sh also replaced. | test_a_removal_git_left_half_done_is_finished_and_the_slice_lists_go_too |
| scripts/test_git_rebase_onto_main.py:1040 | Every helper testing "$branch" must carry the identical branch-name pattern, makers among them | .claude/scripts/test_git_rebase_onto_main.py:446 | ported #236 | 2 | Payload keeps the pattern in seven helpers with no scan (admin #181 / #192: feat(scope)/ branches stranded at one helper). Add the cross-helper scan, naming the maker helpers as positive controls. | test_every_helper_that_takes_a_branch_takes_the_same_names |
| scripts/git-rebase-onto-main.sh:278-286 | Merge commits holding content in neither parent stop the replay (exit 10) | .claude/scripts/git-rebase-onto-main.sh:252 | covered | | Payload keeps the --cc scan and adds a merge-tree comparison with clean-hunk check, which is stricter. | test_a_merge_carrying_its_own_content_stops_the_run, test_an_ordinary_merge_forward_is_flattened_without_complaint |
| scripts/git-rebase-onto-main.sh:223 | Force push spells both refspec sides so remote.origin.push cannot redirect it | .claude/scripts/git-rebase-onto-main.sh:170 | covered | | Payload spells refs/heads/$branch on both sides with the lease. | test_a_configured_push_redirect_is_refused_before_anything_is_forced |
| scripts/git-rebase-onto-main.sh:55 | Branch names with feat(scope)/ parentheses are accepted | .claude/scripts/git-rebase-onto-main.sh:34 | covered | | Same class at the payload line; payload case at test_git_rebase_onto_main.py:971 holds it. | test_a_scoped_feature_branch_is_replayed_and_published |
| scripts/git-rebase-onto-main.sh:357-530 | abort refuses a record publish could finish; abort and publish check record against branch and lease | .claude/scripts/git-rebase-onto-main.sh:531 | covered | | Payload resets to the pre-replay tip or refuses; it asks origin by ls-remote rather than the tracking ref, which is stricter. | test_abort_refuses_a_replay_that_publish_can_still_finish, test_publish_refuses_a_head_that_is_not_the_one_replayed, test_abort_clears_a_record_whose_remote_ref_is_gone |
| scripts/git-rebase-onto-main.sh:439-440 | Apply-backend replay drops a commit the caller emptied, only after a reported conflict, bounded, nothing staged or unstaged | .claude/scripts/git-rebase-onto-main.sh:25 | obsolete | | Payload spells --merge, which drops an emptied commit itself, and has no skip at all; continue refuses an apply-backend replay (payload :456). Frontend audit made the same call. | test_an_empty_resolution_is_dropped_rather_than_called_a_conflict, test_a_stop_that_reported_no_conflict_is_not_called_an_empty_commit, test_unstaged_work_is_not_discarded_by_the_drop, test_a_conflict_after_the_drop_is_reported_rather_than_skipped_too, test_the_empty_commit_is_the_only_thing_the_drop_loses, test_the_state_this_backend_leaves_is_the_one_the_helper_finds |
| scripts/git-rebase-onto-main.sh:482 | Replay spells --no-rebase-merges and --no-update-refs so config cannot change it | .claude/scripts/git-rebase-onto-main.sh:391 | covered | | Payload spells those plus --merge, --no-autosquash, --no-fork-point, --no-autostash. | test_it_takes_a_branch_and_a_mode |
| scripts/git-worktree-remove.sh:95-134 | Unregistered leftover directory deleted with 18 tries, 5 s apart; env-tunable | .claude/scripts/git-worktree-remove.sh:89-120 | obsolete | | Payload replaced it deliberately: status captured, an empty directory is rmdir'ed, any other reported exit 4 for hand removal; no recursive delete. Admin's test_harness_helpers.py:1487 case goes with the file. | test_the_worktree_helper_finishes_a_removal_git_left_half_done_and_keeps_a_refusal |
| scripts/git-worktree-remove.sh:33-75 | Teardown takes path and branch; registered worktree must hold that branch; flags and main refused | .claude/scripts/git-worktree-remove.sh:9-45 | covered | | Same binding; payload also folds case for main and rejects `..` in the branch, and asks symbolic-ref rather than comparing spellings. | test_the_worktree_helper_removes_only_the_worktree_it_is_named_for, test_the_worktree_helper_refuses_a_flag_and_a_stranger, test_the_helpers_spell_the_flags_they_replaced |
| scripts/git-worktree-detach.sh:60-66 | Commit carrying a tracked symlink refused before any worktree is dropped or made, exit 5 | .claude/scripts/git-worktree-detach.sh:35 | covered | | Same refusal and position; payload names at most five links via awk. Cases at test_git_worktree_detach.py:247-296. | test_a_pinned_commit_with_a_tracked_link_is_refused, test_a_commit_carrying_a_link_is_refused_when_driven, test_both_sweeps_state_the_half_that_is_closed |
| scripts/git-worktree-detach.sh:73-87 | Sweep start drops day-old sweep-shaped worktrees through the drop helper, then prunes | .claude/scripts/git-worktree-detach.sh:39-48 | covered | | Identical loop and filter; payload's StaleSweepWorktrees cases at test_git_worktree_detach.py:147-215. | test_a_day_old_sweep_worktree_goes_and_a_fresh_one_stays, test_a_stale_worktree_holding_a_file_is_left_standing_and_named, test_a_registration_whose_directory_went_is_pruned |
| scripts/git-worktree-detach.sh:96-140 | Path made here, direct-child and basename shape checks, stdout is the path only | .claude/scripts/git-worktree-detach.sh:56-90 | covered | | Same code; payload's SweepWorktreeShape holds all five cases. | test_a_nested_path_under_a_sweep_shaped_parent_is_refused, test_the_prefix_and_length_controls_still_refuse, test_the_detach_helper_takes_a_commit_and_nothing_else, test_a_bad_commit_creates_no_directory, test_the_helper_returns_only_the_path_on_stdout |
| scripts/git-worktree-fork.sh:105 | Fork seeds the new worktree's index through hooks/refresh-index.sh, detached | .claude/scripts/git-worktree-fork.sh:117 | obsolete | | Plan Decisions drop refresh-index.sh; the payload runs refresh-index.py when present and starts nothing otherwise. Admin's `py -3` becomes the payload's `py -3.12`. | |
| scripts/git-worktree-fork.sh:73-97 | MCP approval crosses as names only, never the file; approve-all expands; disabled not approved; bad shape warns | .claude/scripts/git-worktree-fork.sh:94-110 | covered | | Same embedded script; payload cases at test_git_worktree_fork.py:104-187 hold each (names differ). | test_the_mcp_approval_crosses_as_names_and_never_as_the_file, test_an_approve_all_crosses_as_the_servers_defined_now, test_a_disabled_server_is_never_approved_in_the_worktree, test_a_shape_it_cannot_copy_warns_and_leaves_the_fork_done, test_no_approval_in_the_main_checkout_writes_nothing |
| scripts/git-worktree-fork.sh:53-57 | Fork refuses an existing branch (no -B), an unignored path, a linked worktree, a subdirectory | .claude/scripts/git-worktree-fork.sh:44-56 | covered | | Same checks, same exit codes. | test_an_existing_branch_is_refused_rather_than_reset, test_an_unignored_path_is_refused, test_a_linked_worktree_is_refused |
| scripts/test_harness_helpers.py:1677 | Positive control: admin's own HEAD has no tracked symlink for the sweeps to refuse | - | local | | Reads admin's tree; stays in test_harness_helpers_admin.py beside the stack cases. | test_this_repository_has_no_tracked_link_to_refuse |
| scripts/git-rebase-onto-main.sh:57 | Payload-only: host hooks (pre-rebase, post-rewrite, pre-push) never run inside the replay | .claude/scripts/git-rebase-onto-main.sh:57 | covered | | Payload-only: empty core.hooksPath; also in git-trailer-pr.sh:19. Admin has no repo hook that rewrites history, so agents see no change. | |
| scripts/git-rebase-onto-main.sh:469 | Payload-only: tracked skip-worktree files refused by name before fetch (exit 5), sparse checkout exempt | .claude/scripts/git-rebase-onto-main.sh:371 | covered | | Payload-only: new refusal; admin sets no skip-worktree flags, and the message names the file and the command to clear it. | |
| scripts/git-worktree-remove.sh:95 | Payload-only: teardown waits up to 30 s for the worktree's code-index refresh lock, else exit 5 | .claude/scripts/git-worktree-remove.sh:50-90 | covered | | Payload-only: teardown may now pause or refuse once, where admin's removed at once. It follows admin's adoption of refresh-index.py (cluster D); retry succeeds when the refresh ends. | |
| scripts/git-rebase-onto-main.sh:84 | Payload-only: a git am session in rebase-apply is refused by name (exit 9) in every mode | .claude/scripts/git-rebase-onto-main.sh:84 | covered | | Payload-only: only changes the message for a state agents do not enter. | |

#### C, GitHub helpers

| Admin | Behaviour | Payload | Verdict | Task | Reason and fix | Admin's test |
|---|---|---|---|---|---|---|
| scripts/gh-sweep-issue-create.sh:35; also scripts/gh-issue-create.sh:27, scripts/gh-issue-filing.sh:119 | Route is a constant per entry point, so a caller cannot choose its provenance trailer | .claude/scripts/gh-issue-sweep.sh:13 | covered | | Drop per Decisions. Payload has thin entry points gh-issue-sweep.sh, gh-issue-hand.sh, gh-issue-mutation.sh over gh-issue-create.sh; test_command_grants.py:341 holds commands to them. | test_neither_entry_point_takes_a_route_at_all, test_a_sweep_cannot_reach_the_hand_route, test_each_entry_point_files_one_route_and_cannot_name_the_other, test_neither_sweep_instructs_a_third_filing_argument |
| scripts/gh-issue-filing.sh:128 | Kind and severity from closed sets; a word outside is refused exit 2 | .claude/scripts/gh-issue-create.sh:20 | covered | | Payload's sets are wider (test-gap, enhancement, area, route) and refused the same way. | test_a_kind_outside_the_vocabulary_is_refused, test_a_severity_outside_the_four_is_refused |
| scripts/gh-issue-filing.sh:153 | Empty title, missing blank line or stdin ending early is refused before filing | .claude/scripts/gh-issue-create.sh:61 | covered | | Same refusals; payload also refuses a title starting with a hash. | test_an_empty_title_is_refused, test_a_body_without_the_blank_separator_is_refused, test_a_stdin_that_ends_before_the_separator_is_refused |
| scripts/gh-issue-filing.sh:164 | Body's last non-blank line must equal the route's trailer, or nothing is filed | .claude/scripts/gh-issue-create.sh:74 | covered | | Same check, with two more routes (mutation, request) and the enhancement/request pairing rule. | test_a_body_without_the_trailer_is_refused, test_each_route_requires_the_line_that_is_true_of_it, test_a_hand_filing_reaches_gh_with_its_own_trailer |
| scripts/gh-issue-filing.sh:172 | Repository resolved from the checkout, never accepted; title passed with MSYS arg conversion excluded | .claude/scripts/gh-issue-create.sh:82 | covered | | Same resolve (exit 3) and MSYS2_ARG_CONV_EXCL at :103; body goes via --body-file -. | test_the_repository_is_resolved_rather_than_accepted, test_the_title_never_crosses_the_parents_command_line, test_a_valid_filing_reaches_gh_with_every_parameter_pinned, test_force_is_never_spelled |
| scripts/gh-issue-filing.sh:177 | Kind and severity labels ensured through the sibling helper before filing | .claude/scripts/gh-issue-create.sh:91 | covered | | Payload ensures kind, severity and each area label. | test_both_labels_go_through_the_sibling_helper |
| scripts/gh-issue-list.sh:44 | De-dup listing fixed field set, no arguments, refused exit 3 when the page is full | .claude/scripts/gh-issue-list.sh:22 | covered | | Same shape; payload's cap is 5000 not 1000. | test_the_listing_helper_fixes_its_field_set, test_the_listing_helper_takes_no_arguments |
| scripts/gh-issue-suppresses.sh:59 | Issue author compared to repo owner in code; unreadable owner, issue or author exits 3 | .claude/scripts/gh-issue-suppresses.sh:38 | covered | | Identical logic; wording differs only. | test_an_issue_the_owner_opened_is_tracking, test_an_issue_a_stranger_opened_is_not_tracking, test_an_unresolvable_owner_is_undetermined_and_not_tracking, test_an_unreadable_issue_is_undetermined, test_an_issue_reporting_no_author_is_undetermined |
| scripts/gh-issue-text.sh:39 | Issue text read with a fixed field set that withholds author | .claude/scripts/gh-issue-text.sh:26 | covered | | Identical. | test_the_text_helper_withholds_the_one_field_that_decides, test_the_text_helper_takes_one_issue_number_and_nothing_else |
| scripts/gh-label-ensure.sh:68 | Label listing bounded and refused at the cap; a lost create race is rechecked | .claude/scripts/gh-label-ensure.sh:50 | covered | | Same helper with more labels (test-gap, harness, code, documentation, test); the race recheck is at :71. | test_a_create_lost_to_a_concurrent_sweep_succeeds, test_a_create_that_genuinely_failed_is_reported, test_a_near_miss_on_search_is_not_a_match |
| scripts/gh-pr-create.sh:34; also scripts/gh-pr-create.sh:49 | PR title and body from caller-written files that are not symlinks and not tracked | .claude/scripts/gh-pr-create.sh:16 | covered | | Payload takes both as path arguments under artifacts/ and requires git check-ignore, a stronger form; payload-only: pr.md and ship.md grants change with it, which the sync brings. | test_the_create_helper_refuses_a_body_it_should_not_publish, test_the_create_helper_leaves_no_body_behind_and_takes_none_tracked |
| scripts/gh-pr-create.sh:63; also scripts/gh-pr-create.sh:75, scripts/gh-pr-create.sh:82 | PR create pins repo, head and base main; refuses main and detached HEAD; deletes inputs after | .claude/scripts/gh-pr-create.sh:59 | covered | | Same pins and exits at :59-62, :74, and the input removal at :79. | test_the_helpers_spell_the_flags_they_replaced |
| scripts/gh-pr-merge.sh:62 | Merge only a same-repo PR into main whose branch and head oid equal the checkout's; rebase with match-head-commit | .claude/scripts/gh-pr-merge.sh:31 | covered | | Identical logic; wording differs only. | test_the_merge_helper_refuses_what_the_grant_admitted, test_the_merge_helper_lands_by_rebase |
| scripts/pr-state.sh:27; also scripts/pr-closure-input.sh:30 | PR state and closure input read with fixed field sets | .claude/scripts/pr-state.sh:13 | covered | | Payload-only: both run gh through gh_read, a 60 s bound, and closure input adds author; neither refuses daily work. | |
| scripts/pr-for-branch.sh:87 | Branch PR listing read with a limit and refused exit 4 at the cap | .claude/scripts/pr-for-branch.sh:42 | covered | | Same limit 1000 and exit 4; payload adds exit 3 for a non-array reply. | |
| scripts/pr-for-branch.sh:98 | Only same-repo PRs into main count as the branch's PR; forks and null heads dropped | .claude/scripts/pr-for-branch.sh:51 | covered | | Payload keeps every such row and /ship step 0 reads the newest (ship.md:123), where admin returned one row. | test_only_this_checkouts_pull_requests_survive, test_a_fork_with_the_same_branch_name_is_dropped, test_a_null_head_repository_is_dropped_rather_than_crashing, test_a_prefix_of_the_owner_is_not_the_owner, test_the_shape_is_unchanged_for_callers |
| scripts/pr-for-branch.sh:128 | A MERGED row whose merge commit is an ancestor of the local tip is dropped; closed never | .claude/scripts/pr-for-branch.sh:57 | covered | | Payload drops each such MERGED row, not only the newest; absent local branch or commit keeps the row, as admin does. | test_a_reused_name_pointed_at_an_old_commit_is_not_finished, test_the_finished_predicate_is_spelled_whole |
| scripts/pr-locality.sh:123; also scripts/pr-locality.sh:332, test_pr_locality.py:152 | Files endpoint name count must equal GitHub's changedFiles, else exit 3 | - | ported #239 | 2 | Payload trusted the endpoint, so a short list read as complete and printed wrong inside lines. Reads changedFiles, counts filenames in the one read it judges, refuses "the files endpoint returned N names against changedFiles M"; keeps gh_read. | test_the_files_endpoint_disagreeing_with_changed_files_is_refused |
| scripts/pr-locality.sh:84; also scripts/pr-locality.sh:85 | Class letters spelled out, not ranged, so a locale cannot admit lower-case d | .claude/scripts/pr-locality.sh:43 | ported #239 | 2 | Measured on Windows bash under en_US.UTF-8: bash's =~ with [A-E] (:126, the map) accepts d, which the gate refuses; grep -Eq (:43, the row) refuses it. [ABCDE] spelled in both places. | test_the_class_letters_are_spelled_out_not_ranged |
| scripts/pr-locality.sh:156; also scripts/pr-locality.sh:158 | Class map read from the PR base commit, HEAD copy only when base lacks the gate dir | .claude/scripts/pr-locality.sh:116 | obsolete | | Payload reads the checkout's classes.yml on purpose and says the verdict matches CI only while the maps agree (harness-boundaries.md:1660). Admin's agents lose the base read; accept. | |
| scripts/pr-locality.sh:139; also scripts/pr-locality.sh:144, scripts/pr-locality.sh:255 | Two Class rows, one row without the other, a second cell or a trailing-junk row is refused | .claude/scripts/pr-locality.sh:37 | covered | | Same refusals at :37-47; the junk-after-pipe case stays refused because the cell keeps its text. | test_two_class_rows_and_one_row_without_the_other_are_refused, test_a_trailing_pipe_is_removed_only_when_it_ends_the_row |
| scripts/pr-locality.sh:342; also scripts/pr-locality.sh:334 | Changed paths incl. rename source JSON-quoted, plain-path grammar, anything else refuses the run | .claude/scripts/pr-locality.sh:168 | covered | | Payload judges filename and previous_filename and refuses the same paths at :177-186. | test_a_changed_path_that_is_not_a_plain_path_refuses_the_whole_run, test_both_ends_of_a_rename_are_judged |
| scripts/pr-locality.sh:299; also scripts/pr-locality.sh:264 | Touch-set row refuses brace imbalance, leading slash and dot-dot including inside braces | .claude/scripts/pr-locality.sh:68 | covered | | Same refusals at :68, :75, :100; payload also takes a parenthesised reason beside a backticked token. | test_each_refusal_is_in_the_shell_copy_and_the_gate |
| test_pr_locality.py:162 | Shell refusal phrases must also occur in admin's locality_gate.py source | - | local | | Parity of the shell copy with admin's Python gate stays as test_pr_locality_admin.py. Payload now also accepts a reason in parens, prints outside-class and takes A+D+E, so the gate or phrases must follow. | test_each_refusal_is_in_the_shell_copy_and_the_gate |
| test_pr_locality.py:97 | Verdict cases run against admin's real classes.yml (class D has no src, class A has Admin.Host) | - | local | | Holds admin's own trees and map; keep in test_pr_locality_admin.py with the parity cases. | test_a_path_in_both_the_declared_set_and_the_class_map_is_inside, test_the_declared_set_alone_is_not_enough, test_a_joined_class_is_the_union_and_a_brace_glob_is_one_token, test_the_touch_set_cell_is_never_printed |
| scripts/sweep-slices.sh:46 | Row partition of admin's tree (host, spa, suites, config, source, tooling, samples) held in row_of; unowned path refuses run | .claude/scripts/sweep-slices.sh:41 | port | 7 | Payload reads rows from .harness/sweep-rows.tsv, so without them both sweeps exit 3. Express row_of as admin's rows in that file, which no config renders, first match wins, bug and security kinds, test files before spa. | test_each_row_owns_the_paths_its_command_says, test_each_table_matches_row_of, test_a_new_source_project_refuses_the_run_rather_than_joining_a_row, test_a_top_level_directory_no_row_owns_refuses_the_run |
| scripts/sweep-slices.sh:100 | package-lock.json read as JSON: off-registry resolved, missing sha512 or invalid file refuses the sweep | - | local | | Admin's npm lockfile, nothing in the payload reads one. Keep as an admin-local check run beside the sweep. A `samples` row in admin's sweep rows counts the lockfile unread, having no fence; under any other row its 333,610 bytes are a one-file slice in both sweeps, as the rehearsal's first draft showed. | test_a_lockfile_resolving_off_the_registry_or_missing_an_integrity_refuses_the_run, test_a_lockfile_is_read_as_json_so_its_whitespace_cannot_hide_an_entry, test_the_lockfile_is_owned_and_counted_not_read |
| scripts/sweep-slices.sh:182 | A binary file outside a known asset extension list refuses the run by name | .claude/scripts/sweep-slices.sh:179 | covered | | Payload names every binary file in binary.txt for the plan to point at, so none is dropped unsaid. Different mechanism, same coverage. | test_a_binary_asset_is_counted_and_a_binary_code_file_refuses_the_run |
| scripts/sweep-slices.sh:194 | Frozen docs/superpowers/plans are counted as records, not read | .claude/scripts/sweep-slices.sh:166 | covered | | Payload counts all of docs/superpowers/ plus pr-decision-log and lessons. | |
| scripts/sweep-slices.sh:18 | Sweep path must be a secsweep-NNNNNN directory directly under the temp root; slices dir exists means refuse | .claude/scripts/sweep-slices.sh:18 | covered | | Identical checks at :18-28. | test_its_sweeps_land_in_its_own_temp_root, test_a_path_not_shaped_like_a_sweep_worktree_is_refused, test_kind_and_mode_are_closed_sets, test_the_slices_go_with_the_worktree |
| scripts/sweep-slices.sh:131; also scripts/sweep-slices.sh:177 | Tracked name with a line break refused; per-file loop spawns no process | .claude/scripts/sweep-slices.sh:102 | covered | | Payload refuses line breaks, tab and CR (:102, :125) and reads with awk; its suite pins the no-substitution loop. | test_the_loop_holds_no_command_substitution |
| test_sweep_slices.py:112 | Partition and budget asserted over admin's own tracked tree | - | local | | Holds admin's paths and rows; payload's docstring leaves this to a target suite. Keep as test_sweep_slices_admin.py. | test_every_tracked_path_is_listed_or_counted_and_every_slice_fits |
| scripts/main-red-open.sh:26 | Open issue titled exactly "main is red" stops the landing: prints number and url, exits 3 | .claude/scripts/main-red-open.sh:25 | ported #265 | 3 | Payload had no red-main read; a PR's checks stay green when main turns red. Took the script with Task 3's title rule, and /ship step 6 and its exact grant. | test_an_open_bare_title_exits_3, test_a_workflow_suffixed_title_exits_3, test_a_title_that_only_contains_the_phrase_exits_0, test_no_open_issue_exits_0_printing_nothing |
| scripts/main-red-open.sh:29 | Failed listing or a full page of 100 exits 2, never reads as green | .claude/scripts/main-red-open.sh:16 | ported #265 | 3 | Fail closed: every exit but 0 stops the chain. Same script; keep the LIMIT=100 refusal. | test_a_failed_listing_exits_2, test_a_full_page_exits_2 |
| scripts/main-red-open.sh:23 | Takes no argument; one is refused exit 2 before gh runs | .claude/scripts/main-red-open.sh:9 | ported #265 | 3 | The caller chooses no field, so the exact grant reaches no issue body. Same script. | test_an_argument_is_refused_before_gh_runs, test_ship_runs_the_helper_bare |
| scripts/main-red-open.sh:26; also test_harness_helpers.py:10482 | Helper's TITLE and query equal the workflow's, held by a test | harness_sync/tests/test_main_red_job.py:54 | ported #265 | 3 | Task 3's title rule replaces equality with one workflow, and no payload test reads a target's workflow. This repository's job is fed to the helper; the other three targets' titles are read in the PR body. | test_the_title_and_the_label_are_ones_the_helper_stops_on |

#### D, index

| Admin | Behaviour | Payload | Verdict | Task | Reason and fix | Admin's test |
|---|---|---|---|---|---|---|
| hooks/index-search-hint.py:447 | MCP-or-CLI route chosen by comparing cwd checkout with CLAUDE_PROJECT_DIR; no project dir falls back to worktree test | .claude/hooks/index-search-hint.py:520 | ported #238 | 2 | Payload sends any linked worktree to cbx, though index-mcp-root.py:117-122 lets the MCP call run when the session started there, and refuses it from the main checkout after a move. Port off_server so the hint and the refusal agree. | test_a_session_started_in_the_worktree_is_served_by_it, test_with_no_project_dir_a_linked_worktree_is_taken_to_be_off_it, test_from_the_checkout_the_session_started_in_it_names_the_mcp_tools |
| hooks/index-search-hint.py:503 | Refusal names the CLI as bare `codebase-index` with double-quoted terms | .claude/hooks/index-search-hint.py:473 | obsolete | | Payload names the cbx wrapper (the grant) and single-quotes the term via single(), so bash expands nothing. Admin's bare console script is not granted by the payload skill. | test_from_a_worktree_entered_mid_session_it_names_the_cli_alone |
| hooks/index-search-hint.py:1 | Refuses a first name search once per session; prose, text, one file and pipes pass; subagents never refused | .claude/hooks/index-search-hint.py:418 | covered | | Same once-per-session refusal, rerun passes, prose and text pass (:85-90); payload tests hold each case. | test_the_same_search_rerun_passes, test_prose_is_not_a_question_the_index_answers, test_a_subagent_is_never_refused, test_a_single_file_is_a_read |
| hooks/index-hint-run.sh:41 | Search-hint launcher runs the hook under a 10 s bound and exits 0 on every path, printing a note | .claude/hooks/hint-bound.sh:13 | covered | | Same bound (HINT_BOUND_SECONDS 10), exit 0 at :25, same note line at :20-23. Payload also has a watchdog where no timeout exists (:6). | test_its_own_bound_still_ends_a_slow_hook_with_a_note, test_an_interpreter_that_cannot_find_the_hook_says_so_and_exits_zero, test_it_goes_through_the_launcher_that_cannot_block_a_call |
| hooks/index-hint-run.sh:32 | Launcher refuses any hook name or event but index-search-hint.py under PreToolUse | .claude/hooks/hint-bound.sh:9 | out of scope | | Payload runs any named hook under hooks/. Only settings, which an agent cannot edit, names it; a spelling built to reach another script through the wiring fails the threat model. No fix. | test_it_runs_only_the_one_hook_it_names |
| hooks/index-hint-run.sh:37 | Picks py -3, python3 or python once; never a fallback chain | .claude/hooks/hint-bound.sh:15 | obsolete | | Payload pins py -3.12 per agent-rules Hard rules, also one attempt, no chain. | test_the_wiring_reaches_the_hook_through_the_launcher |
| hooks/index-query-hint.sh:90 | Locate prompt routes to search with `--limit 5`; payload says 3 | .claude/hooks/index-query-hint.py:29 | residual | | Five is admin's measured number (SKILL.md row below); a managed hint carries one value and no seam exists, so docs/harness-local.md says a search here carries 5. | test_a_locate_question_is_pointed_at_a_tagged_search |
| hooks/index-query-hint.sh:87 | Hint names the bare `codebase-index` command with double-quoted X | .claude/hooks/index-query-hint.py:22 | obsolete | | Payload names the cbx wrapper, single-quoted (#132), because the skill grants cbx. Bare form is ungranted there. | test_every_command_it_emits_is_a_row_of_the_route_table, test_every_subcommand_it_names_is_one_the_skill_approves |
| hooks/index-query-hint.sh:48 | Hint warns the MCP server reads the checkout the session started in | .claude/hooks/index-mcp-root.py:125 | covered | | Same as frontend row: the MCP call from a moved checkout is refused with the cbx line, so the sentence is not needed in the hint. | |
| hooks/index-query-hint.sh:103 | Routes: five kinds, /ship and /branch read for their task, other slash silent, 4096 cap, JSON decode, fail open | .claude/hooks/index-query-hint.py:20 | covered | | Identical five routes in order (:20-31), TASKS (:44), CAP (:14), json.loads with UTF-8 (:77), broad except returns 0 (:84). | test_ship_and_branch_are_read_for_the_task_they_carry, test_every_other_slash_command_is_silent_whatever_follows_it, test_a_long_prompt_is_read_as_far_as_the_cap, test_input_it_cannot_read_is_silent_and_never_blocks, test_it_runs_under_plain_sh_and_cannot_hold_a_prompt |
| hooks/refresh-index.sh:91 | Last call wins: atomic token to refresh.pending, 2 s wait, earlier calls exit, no lock | .claude/hooks/refresh-index.py:534 | obsolete | | Payload coalesces under an OS lock with a request marker and a last look after release (frontend row, covered). Admin's token scheme has no equivalent to port. | test_a_later_call_makes_an_earlier_one_stand_down, test_a_burst_of_edits_runs_one_update_and_it_is_the_last_calls, test_an_edit_during_an_update_gets_an_update_after_it |
| hooks/refresh-index.sh:150 | A failing update is retried three times, two seconds apart | .claude/hooks/refresh-index.py:60 | covered | | REFRESH_ATTEMPTS 3 with RETRY_PAUSE 5, root rejudged each try (:842-856). | test_a_failed_update_is_retried, test_a_failure_that_persists_gives_up |
| hooks/refresh-index.sh:128 | Runs update with CBX_NO_SKILL_AUTO_UPDATE=1 so the CLI never rewrites the tracked skill | .claude/hooks/refresh-index.py:687 | covered | | refresh builds its environment with the guard, PYTHONSAFEPATH and the exe-path variable. | test_it_runs_update_once_with_the_guard_and_leaves_only_the_mark |
| hooks/refresh-index.sh:113 | A linked worktree with no index is seeded from main's, never built; bare repository gets nothing | .claude/hooks/refresh-index.py:400 | covered | | seed_source and refreshable refuse the main checkout, a bare repository, a missing main index and a cache with no index. | test_a_worktree_with_no_index_is_seeded_from_main_then_updated, test_a_worktree_whose_main_has_no_index_gets_nothing, test_a_worktree_of_a_bare_repository_gets_nothing, test_a_cache_without_an_index_and_nothing_to_seed_gets_nothing |
| hooks/refresh-index.sh:144 | Only index.sqlite crosses; stale WAL and shm removed before a fresh seed; existing index untouched | .claude/hooks/refresh-index.py:466 | covered | | SQLite backup into a pid-named partial, -wal/-shm removed at :489, os.replace only if the path is still empty. | test_a_stale_wal_does_not_meet_a_fresh_seed, test_an_existing_worktree_index_is_left_alone |
| hooks/refresh-index.sh:158 | A seed update cannot open is deleted after three failures so the next call copies again | .claude/hooks/refresh-index.py:466 | obsolete | | The marker guarded a cp torn mid-checkpoint; payload copies by SQLite backup and checks the WAL header (:496), so a torn seed is not made. A failed update leaves the request marker. | test_a_seed_update_cannot_open_is_removed_for_the_next_call, test_a_later_caller_that_fails_on_a_seed_removes_it, test_a_failed_seed_stays_while_a_later_call_may_be_using_it, test_its_own_index_survives_a_failed_update |
| hooks/refresh-index.sh:21 | The edited file (file_path or notebook_path) names the checkout; cwd is the fallback; a gone directory falls back | .claude/hooks/refresh-index.py:217 | covered | | named_file/edited resolve the file first (:204-240) and target falls to cwd; a path inside tool output is not a key since JSON is parsed. | test_an_edit_refreshes_the_checkout_of_the_file_it_names, test_a_notebook_edit_names_its_file_the_same_way, test_a_path_through_a_worktree_into_main_refreshes_main, test_a_file_whose_directory_has_gone_falls_back_to_the_events_cwd, test_a_cwd_inside_a_tool_output_is_not_the_key |
| hooks/refresh-index.sh:84 | The hook returns while the update is held; refresh runs detached | .claude/hooks/refresh-index.py:920 | covered | | main starts a detached worker and returns; payload test_refresh_index.py holds it through a real detached worker. | test_the_hook_returns_while_the_update_is_held |
| hooks/refresh-index.sh:3 | Runs after every writing tool including Bash, and at SessionStart, both silenced; no other event | .harness/settings.base.json:151 | covered | | PostToolUse matcher names the edit tools and both shells; SessionStart at :164 has none. | test_it_runs_after_every_tool_that_writes, test_it_also_runs_when_a_session_starts, test_no_other_event_runs_it, test_it_is_silenced_and_reads_its_event |
| hooks/refresh-index.sh:98 | A cache directory with no index and no seed source gets no update | .claude/hooks/refresh-index.py:419 | covered | | refreshable requires a written index; frontend row `refresh-index.py:156` ported #154. | test_no_index_means_no_update |
| skills/codebase-index/SKILL.md:22 | Search carries `--limit 5`, measured on admin's corpus (3 loses 2 of 8); read to rank five before re-asking | .claude/skills/codebase-index/SKILL.md:54 | residual | | Corpus number; the payload's 3 is backend's measurement and the managed file has no seam. Admin keeps a residual noting 5, in place of taking 3 and re-measuring. Same value in commands.md query examples. | test_every_example_passes_the_owned_limit |
| skills/codebase-index/SKILL.md:32 | A `graph` row runs under a prompt, not auto-approved; wrappers whitelist graph | .claude/hooks/guard-index-argv.py:10 | obsolete | | Payload refuses graph (it writes a file) in cbx, cbx.ps1, the guard and commands.md:46; also admin's commands.md graph paragraph and cbx/cbx.ps1 ALLOWED lists. Same as frontend row. | test_skill_frontmatter_does_not_auto_approve_graph_or_cbx |
| skills/codebase-index/SKILL.md:2 | allowed-tools grants bare `codebase-index <sub>:*`, never cbx | .claude/skills/codebase-index/SKILL.md:4 | obsolete | | Payload grants `bash ...cbx <sub>:*` behind guard-index-argv.py, which refuses `$(...)`, redirection, chains. Admin's case asserts no `cbx:*`; the payload's test_cbx and test_index_argv_guard pin the new grant. | test_skill_frontmatter_does_not_auto_approve_graph_or_cbx |
| skills/codebase-index/SKILL.md:105 | Empty refs/impact result is inconclusive, with an admin DI-registration example | .claude/skills/codebase-index/SKILL.md:117 | covered | | The Grep-before-absence rule is the same; the example names a C# registration of another class (wording). | |
| skills/codebase-index/examples/hooks/settings.json:8 | Shipped example runs `CBX_NO_SKILL_AUTO_UPDATE=1 codebase-index update` backgrounded, timeout 5 | .claude/skills/codebase-index/examples/hooks/settings.json:9 | obsolete | | Payload's example runs refresh-index.py and test_refresh_index.py:28 holds it to the registered hook. | test_the_shipped_example_is_a_self_contained_guarded_refresh, test_the_shipped_example_runs_backgrounded_and_silenced |
| skills/codebase-index/scripts/cbx:18 | Fallback interpreter is python3/python/py -3.12 with no version floor, no -P, no index gate | .claude/skills/codebase-index/scripts/cbx:18 | covered | | Payload-only: cbx runs gate.sh first (exit 3 refused index, 4 no Python 3.12) and then a 3.12-only fallback with -P. A 3.13-only machine exits 127. Daily admin use refused only on a bad index or non-3.12 host. | |
| skills/codebase-index/scripts/cbx.ps1:21 | Windows wrapper runs PATH CLI, py -3.12, python; leaves PYTHONSAFEPATH unset and sets no auto-update guard | .claude/skills/codebase-index/scripts/cbx.ps1:30 | covered | | Payload-only: gate-index.py first, safe path, guard set and both variables restored in finally; same exit codes as cbx. Admin loses nothing. | |
| scripts/test_index_skill_examples.py:1 | Every `search` example under the skill carries the one limit SKILL.md owns, read from it | - | ported #238 | 2 | Payload has no such gate: test_index_query_hint.py:239 checks only SKILL.md and the hint, and references/commands.md search examples carry no `--limit 3`. Port it reading `search takes --limit N` and the `bash ...cbx search` lines; add the limit to the examples. | test_the_skill_owns_a_limit, test_there_are_examples_to_check, test_the_owner_is_read_by_the_rule_it_owns, test_a_substring_of_the_value_is_not_the_value, test_every_example_passes_the_owned_limit |
| scripts/test_index_query_hint.py:348 | Settings env sets CBX_NO_SKILL_AUTO_UPDATE=1 for every agent Bash call | .harness/settings.base.json:5 | covered | | Base env carries it; test_cbx.py:232 pins it. | test_every_session_runs_the_cli_with_the_auto_update_off |
| scripts/test_index_query_hint.py:143 | Prompt hook runs on every prompt under UserPromptSubmit only, through a launcher that cannot erase a prompt | .harness/settings.base.json:176 | covered | | Payload test_index_query_hint.py:99-133 holds the event, launcher and no-matcher entry. | test_it_runs_on_every_prompt_and_under_no_other_event, test_it_runs_under_plain_sh_and_cannot_hold_a_prompt |
| scripts/test_index_search_hint.py:1 | Search hint is wired to PreToolUse Grep and Bash only, through the launcher | .harness/settings.base.json:131 | covered |  | Payload test_index_search_hint.py holds the wiring; its matcher also names PowerShell (payload-only, harmless to admin). | test_it_runs_before_a_search_and_under_no_other_event, test_the_wiring_reaches_the_hook_through_the_launcher, test_every_subcommand_it_maps_is_a_row_of_the_skill_route_table, test_the_prompt_hint_carries_the_same_map_as_this_hook |

#### E, commands and agents

| Admin | Behaviour | Payload | Verdict | Task | Reason and fix | Admin's test |
|---|---|---|---|---|---|---|
| commands/ship.md:5 | Ship denies Agent(general-purpose) | .claude/commands/ship.md:5 | obsolete | | Payload's step 2 dispatches its audits as `general-purpose` and test_command_grants.py:131 asserts the type stays undenied. Admin's deny goes with the replaced file; the other profiles stay denied there. | |
| commands/ship.md:5; also commands/pr.md:5, commands/style-pass.md:5 | Editing commands deny Edit of .claude/**, .remember, .git, .mcp.json, .codeindexignore | .harness/settings.base.json:34-57 | covered | | Base settings deny these for every session (`.claude` subtrees, not the worktree root). Admin's rules/ and output-styles denies are settings cluster. After sync the case must read settings, not frontmatter. | test_every_editing_command_denies_the_machinery, test_gits_own_control_directory_is_denied |
| commands/ship.md:5; also commands/pr.md:5, commands/style-pass.md:5 | Editing commands deny Edit of .github/** (pin-gate, locality-gate, ci.yml), so a chain cannot edit the gate judging its own project file | - | obsolete |  | Not ported: plan 6 *Global Constraints* keep `.github/**` editable in admin and add no config deny on it, a new stop; admin's pin-gate and locality-gate stay held by CI and review. Named in the PR body. | test_ship_edits_project_files_and_style_pass_does_not, test_every_editing_command_denies_the_machinery |
| commands/ship.md:5; also commands/pr.md:5 | Ship and pr deny Edit(docs/commands/**), the arguments of the runbooks | .harness/agent-rules.md:37 | obsolete |  | Under payload `docs/commands/` is managed: the drift gate refuses a changed copy and agent-rules.md:37 sends the edit to payload/. A frontmatter deny adds nothing. |  |
| commands/ship.md:5; also commands/pr.md:5, commands/style-pass.md:5 | Editing commands deny the SPA toolchain: package.json, .npmrc, tsconfig, angular.json, eslint/prettier/playwright/capacitor/ionic configs, `**/*.config.*`, AGENTS.md, node_modules, android, ios | - | residual | | Admin's stack, as frontend's row at IMPORT.md:706. A managed runbook has no per-command route, and a config deny would stop the 25 edits of package.json, angular.json and the eslint and prettier configs in admin's transcripts since 2026-10-19, so only .npmrc, which no session edited and which moves the registry `spa-ci.sh` installs from, and AGENTS.md are config denies. package.json and the tool configs stay editable and executable by the granted npm-checks.sh, which docs/harness-local.md names. CLAUDE.md, .editorconfig, .gitignore stay unlisted since style-pass edits them. | test_every_editing_command_denies_the_toolchain, test_the_auto_load_surface_is_denied, test_the_toolchain_exemption_is_real |
| commands/ship.md:5; also commands/pr.md:5, commands/style-pass.md:5 | Editing commands deny MSBuild/NuGet auto-imports, Directory.*, global.json, slnx targets, obj, csproj.user | - | local | | .NET host stack; admin's settings.json already denies the same 40 names, so the config keeps them. The frontmatter case must be cut to the settings case at test_settings_denies_the_msbuild_and_nuget_auto_imports. | test_every_editing_command_denies_the_msbuild_and_nuget_auto_imports, test_settings_denies_the_msbuild_and_nuget_auto_imports |
| commands/style-pass.md:5 | Style-pass denies Edit(**/*.csproj) while ship may edit project files | - | residual | | A project file is MSBuild that host-checks.sh runs. Payload style-pass denies only git push, and a config deny would also stop /ship, so admin's harness-local.md residuals name the loss. | test_ship_edits_project_files_and_style_pass_does_not |
| commands/ship.md:4; also commands/pr.md:4 | Prefix-free grant `gh-pr-create.sh` exact; `:*` form refused by test | .claude/commands/ship.md:4 | obsolete | | Payload's helper takes the title and body paths (pr.md:178), so it is granted `:*`. Argument validation is cluster C's (test_gh_pr_create.py); drop the exactness assertion with the replaced file. | test_the_helpers_exist_and_are_granted_where_they_are_used |
| commands/ship.md:4; also commands/pr.md:4 | No command grants raw gh pr create/merge or git worktree remove; helpers granted | .claude/commands/ship.md:4 | covered | | Payload ship grants only gh-pr-merge.sh, gh-pr-create.sh and git-worktree-remove.sh. The raw denies come from base settings in Task 3. | test_no_command_grants_the_raw_form |
| commands/ship.md:4; also commands/pr.md:4, commands/style-pass.md:4, commands/branch.md:4 | No command grants npm/npx/node/ng/yarn/pnpm; npm-checks.sh is the closed-set runner | .claude/commands/ship.md:4 | covered | | Payload commands grant none of these. The npm-checks.sh, host-checks.sh, harness-checks.sh and spa-ci.sh grants leave frontmatter for the config `allow`, as frontend's. | test_no_command_grants_a_free_form_package_runner, test_the_check_runner_helper_takes_no_free_parameter |
| commands/ship.md:4; also docs/commands/ship.md:1132, docs/commands/ship.md:1152, commands/ship.md:389 | Ship grants main-red-open.sh and step 6 reads an open `main is red` issue as a red check | .claude/commands/ship.md:4, 39, 569, 599; docs/commands/ship.md:1004, 1025 | ported #265 | 3 | Payload step 6 read only the PR's checks (ship.md:44, 568), so a red `main` read green (admin #531). Ported the grant, the exit 0/2/3 paragraph and the `/ship #<n>` exception with Task 3's title rule. | test_ship_runs_the_helper_bare, test_the_read_follows_the_checks_wait_and_stops_the_chain |
| commands/ship.md:259; also commands/ship.md:321-327, agents/branch-reviewer.md:26, scripts/test_index_query_hint.py:299, docs/commands/ship.md:795 | Step 1 locates the change by codebase-index; step 5 writes a diff-impact `.impact` file the reviewer reads | .claude/commands/ship.md, steps 1 and 5 | ported #254 | 2 | Ported through `cbx` rather than the bare CLI, with the four reads and `git merge-base origin/main HEAD` granted. A full pass writes the file, since a recheck reads nothing else, and a `cbx` that cannot answer is no stop, since a target may have no index. | TheShipChainReadsTheIndex |
| commands/ship.md:266-275 | Step 2 selects host/npm/harness checks by diff; names Playwright as CI's `smoke`, not run | .claude/commands/ship.md:372 | local | | Payload step 2 reads `docs/harness-local.md` *Ship checks*. Admin's selection and its Playwright statement move there; the grants move to config allow. | |
| commands/pr.md:178-191; also commands/style-pass.md:159 | Pr and style-pass run host-checks.sh/npm-checks.sh and state Playwright was not run | .claude/commands/pr.md:165 | local | | Payload names *Ship checks* instead. Stack facts go in admin's harness-local.md; harness-checks.sh when the diff reaches .claude, locality-gate or tools belongs there too. | |
| commands/branch.md:143-147; also commands/branch.md:4, commands/branch.md:32 | Branch runs spa-ci.sh (npm ci) when src/Admin.Web/node_modules is absent or package files dirty | - | local | | Npm stack, as frontend's row at IMPORT.md:711. State it in *Ship checks*; grant spa-ci.sh through config allow. | |
| commands/branch.md:84-85 | Branch type table maps admin trees (Admin.Host, Admin.Mcp, Admin.Web, tools, package.json, eslint, .prettierrc) to types | .claude/commands/branch.md:60 | local | | Payload table is generic ("solution code", "repo config"). Admin's path list goes in harness-local.md or the change contract. | |
| commands/branch.md:102; also commands/commit.md:50, commands/pr.md:66 | Branch, commit and PR titles take the plan's `## Task n:` heading | .claude/commands/branch.md:90 | local | | Payload names the roadmap `docs/harness-local.md` *Documents* lists. Admin's plan route goes into its *Documents*, as frontend's row at IMPORT.md:712. | |
| commands/branch.md:174 | Report offers `git branch -m` as free until push | .claude/commands/branch.md:164 | covered | | Payload-only: second branch via git-branch-create.sh HEAD, since the base denies `git branch -m`. Admin's text sends agents into a refusal. | |
| commands/commit.md:62-72; also commands/pr.md:157-176 | Admin has no closure gate; /pr and /commit reconcile `Closes` by reading | .claude/commands/pr.md:148 | obsolete | | Payload-only: /pr pipes pr-closure-input.sh into `.github/closure-gate/` and commit.md:71 cites it. Sync brings the gate and its workflow (cluster G); admin's "gap" paragraphs go. | |
| commands/pr.md:99-119 | Touch-set cell holds paths only; an added file's reason sits below the table (change-locality.md §3) | .claude/commands/pr.md:116 | local | | Payload writes `` `x` (added: why) `` in the cell. Admin's locality_gate.py reads cells as paths, so the payload form would go red; cluster C must make the gate parse `(added:` first. | test_pr_locality.py parity cases |
| commands/pr.md:198-217 | Pr writes pr-title.txt and pr-body.md at checkout root, then runs gh-pr-create.sh without arguments | .claude/commands/pr.md:178 | obsolete | | Payload helper takes artifacts/pr/title.txt and body.md. Helper and its tests are cluster C's; admin's gitignore for the root files then has no use. | |
| commands/style-pass.md:103-157 | Style-pass reconciles .prettierrc, eslint.config.js and .editorconfig, then runs npm-checks.sh lint; scan uses printWidth, quotes, LF | .claude/commands/style-pass.md:90 | local | | Payload reconciles .editorconfig alone and reads limits from the guide (style-pass.md:114). The linter table belongs in admin's style guide and *Ship checks*, as frontend's row at IMPORT.md:714. | test_the_toolchain_exemption_is_real |
| commands/style-pass.md:31, 95 | Sweep covers every fenced block in docs; site counts removed, never kept | .claude/commands/style-pass.md:30, 87 | covered | | Payload sweeps every fenced block under docs/ and removes counts where the target's contract forbids them. Admin's change-locality.md §2 forbids them, so *Documents* must name it. | |
| commands/bug-sweep.md:5; also commands/security-sweep.md:5 | Sweeps grant gh-sweep-issue-create.sh and deny gh-issue-create.sh by name | .claude/commands/bug-sweep.md:4-5 | covered | | Payload grants gh-issue-sweep.sh and denies create, hand, harness, mutation and `gh:*`. Payload-only: tighter denies, nothing admin's sweeps use. Rewrite the two cases to the new name. | test_a_sweep_cannot_reach_the_hand_route, test_neither_sweep_instructs_a_third_filing_argument |
| commands/bug-sweep.md:216-221; also commands/security-sweep.md:151-154 | Sweep slice rows: host, spa, suites, tooling, config, samples (bug); tooling, source, config, samples (security) | .claude/commands/bug-sweep.md:184 | local | | Payload reads rows from `.harness/sweep-rows.tsv`. Admin's two row sets move into that file; sweep-slices.sh exits 3 on any unowned tracked path. | |
| commands/bug-sweep.md:47, 66 | Vacuous gate ranked critical, naming admin's gates; no build grant for npm ci, angular.json, eslint, Vitest | .claude/commands/bug-sweep.md:41, 63 | local | | Payload carries both rules without the stack names. Admin's gate list (locality-gate, harness job, dotnet test, npm, smoke) goes in harness-local.md. | |
| agents/bug-auditor.md:127 | Verdict reports covering tests; a covering test that cannot fail is its own finding | .claude/commands/bug-sweep.md:66, 219 | covered | | Payload moves it from the agent into the command's step 2 request and "tests are evidence" section. The agent contract is silent, so the dispatching prompt carries it. | |
| agents/branch-reviewer.md:42 | Reviewer's bar is review-branch.md's *What counts as a finding* | .claude/agents/branch-reviewer.md:43 | obsolete | | Payload takes the bar from `docs/harness/working-rules.md` as origin/main carries it, written under artifacts/review/, empty bar fails closed (ported #145). Admin's review-branch.md stays local, one row. | |
| commands/review-branch.md:1 | Manual review command and its contradiction method | - | local | | Decisions: local, as backend and frontend. Its grants, denies and 12200-byte ceiling stay admin's, as does `docs/commands/review-branch.md`. | test_each_runbook_stays_under_its_ceiling |
| scripts/test_command_runbooks.py:19 | CEILINGS holds review-branch.md at 12200 | .claude/scripts/test_command_runbooks.py:41 | local | | Payload reads a target's own ceilings from `LOCAL.ceilings` in `local_commands.py` (review_helpers import). Admin has neither file: add `local_commands.py` with `{"review-branch.md": 12200}`. | test_each_runbook_stays_under_its_ceiling |
| scripts/test_command_runbooks.py:34-62 | PINNED phrases other suites read from runbooks (owner-opened issues, `files normally`, is-ancestor, `refs/pull/<n>/head`) | .claude/scripts/test_command_runbooks.py:96 | obsolete | | Payload text lacks several of these phrases and pins its own ship rules in ShipStopsAndContinuesWhereTheHelpersSay. Drop PINNED; cases elsewhere in admin that read them go with their clusters. | test_pinned_text_stays_in_the_runbook |
| scripts/test_command_runbooks.py:53 | Citations counted globally across all runbooks | .claude/scripts/test_command_runbooks.py:93 | covered | | Payload-only: each runbook must cite and every citation parse, plus the boundaries index and no positional `$1`. Admin's commit.md and pr.md use `$1`, now `$ARGUMENTS`; admin's local review-branch.md must carry the same. | |

#### E, command documents

| Admin | Behaviour | Payload | Verdict | Task | Reason and fix | Admin's test |
|---|---|---|---|---|---|---|
| docs/commands/ship.md:105; also commands/ship.md:48, docs/commands/ship.md:1170 | A refused merge (auto-mode classifier, no exit code) is a chain stop that hands over the `! bash gh-pr-merge.sh <n> <oid>` line | .claude/commands/ship.md, the list under the stop table | ported #254 | 2 | Beside the refused push, so the count of seven holds; the argument cites blueprint-admin#613, whose measurement the `docs/harness-boundaries.md:297` row keeps in admin. Keeps the no-branch-update rule and the already-merged resume, and adds the `--dispatched` ending. | ARefusedMergeIsAStop |
| docs/commands/ship.md:1106; also commands/ship.md:388 | The CI wait is `gh pr checks --watch --fail-fast --interval 60`, cutting repeated table output | .claude/commands/ship.md, step 6 | ported #254 | 2 | The runbook line and its argument, citing blueprint-admin#225. | TheCiWaitIsCheap |
| docs/commands/ship.md:1436; also commands/ship.md:507 | Report lists every issue filed or commented on by number; a PR's unfixed problem is an issue before the report | - | obsolete |  | The owner's user-level instructions require every report to list each issue filed or commented on, in every repository; restating it in the payload's runbook would add bytes under its ceiling and a second owner. |  |
| docs/commands/ship.md:818 | Step 2 selects host-checks, npm-checks, harness-checks by touched paths; Playwright is CI-only and said not run | .claude/commands/ship.md:372 | local | | .NET host, SPA and admin gate suites; belong in admin's Ship checks of docs/harness-local.md. The say-plainly-not-run rule is stated generally in payload. | |
| docs/commands/branch.md:56; also docs/commands/branch.md:369 | Fresh worktree has no node_modules; run spa-ci.sh (npm ci) when missing or package/lockfile dirty, before npm-checks | - | local | | npm stack fact, as frontend row branch.md:53; belongs with local spa-ci.sh/npm-checks.sh and admin's harness-local. | |
| docs/commands/branch.md:67 | Host sibling clones (Admin:BackendDir/FrontendDir) resolve against RepoRoot.MainCheckout from a worktree | - | local | | Admin product code fact about its .NET host; no session behaviour in the payload. | |
| docs/commands/branch.md:199; also docs/commands/branch.md:244 | Branch-type table names Admin.Host/Mcp/Web paths; plan Task heading under docs/superpowers/plans names the branch | .claude/commands/branch.md:90 | local | | Admin tree facts and plan path, as frontend rows branch.md:197 and :240; payload reads roles from harness-local. | |
| docs/commands/bug-sweep.md:106; also docs/commands/bug-sweep.md:139 | No build or test run in the pinned worktree (npm ci scripts, Docker, bin/obj); a green suite is not assumed | docs/commands/bug-sweep.md:126 | covered | | Payload keeps the reading-only argument and the does-not-lean-on-green rule; the npm/MSBuild/Docker examples are admin stack. | |
| docs/commands/bug-sweep.md:288; also docs/commands/security-sweep.md:141, docs/commands/bug-sweep.md:822 | No cygpath grant; title never begins with `/` (MSYS2_ARG_CONV_EXCL in the filing helper) | docs/commands/bug-sweep.md:703 | covered | | Payload docs carry cygpath, MSYS2_ARG_CONV_EXCL, ISSUE_BODY_END and the same helpers' shape checks. | |
| docs/commands/security-sweep.md:287; also docs/commands/bug-sweep.md:606 | One issue per cause, fifteen filings a run; rest ranked in summary | .claude/commands/security-sweep.md:86 | covered | | Runbooks state the cap (bug-sweep.md:140); only the docs argument (the 101-issue run) is absent, a reason with no new behaviour. | |
| docs/commands/security-sweep.md:296 | A guard-bypass spelling built only to hide a command is recorded in the summary, never filed | .claude/commands/security-sweep.md:89 | covered | | Payload runbook cites the same threat-model section. Docs argument absent, wording only. | |
| docs/commands/bug-sweep.md:923; also docs/commands/security-sweep.md:640 | Sweep reads the SPA lockfile mechanically: resolved URL off registry.npmjs.org or missing sha512 refuses the run | - | local | | npm lockfile is admin's SPA; the check lives in sweep-slices (cluster A scripts), argued here. Stays admin's config/local. | |
| docs/commands/bug-sweep.md:1005; also docs/commands/security-sweep.md:696 | unreadable-root and empty-scope reports are round errors, never clean | docs/commands/bug-sweep.md:815 | covered | | Payload Where it stops keeps Never fail open and the readable-root proof. | |
| docs/commands/bug-sweep.md:953 | Verifier runs on Sonnet; Windows pitfalls for the slices suite | docs/commands/bug-sweep.md:664 | covered | | Payload dispatches the verifier with model sonnet. The Windows pitfalls are suite notes, not session behaviour. | |
| docs/commands/review-branch.md:1 | Argument document for admin's /review-branch command | - | local | | Local by *Decisions*, as backend and frontend. | |

#### F, docs

| Admin | Behaviour | Payload | Verdict | Task | Reason and fix | Admin's test |
|---|---|---|---|---|---|---|
| docs/harness-boundaries.md:8 | Bare #NN under .claude or in this file names an admin issue; sibling cites are qualified | - | residual | | True in admin only (ported from frontend, from backend), false in the payload. Add to admin's harness-local Residuals, as frontend's :11 row did. | |
| docs/harness-boundaries.md:25 | Index table of grep lead-ins per touched area | docs/harness-boundaries.md:3 | covered | | Payload carries a section index at the top (3-32); admin's table is its own file layout and goes with the replaced file. | |
| docs/harness-boundaries.md:48 | Guards catch honest mistakes; filing follows backend's threat-model section | docs/harness-boundaries.md:799 | covered | | Payload states the threat model itself (799-830); admin's pointer to backend becomes the local section. | |
| docs/harness-boundaries.md:58 | Two toolchains: host-checks.sh and npm-checks.sh, no e2e mode, CI smoke job is that check | - | local | | Admin's .NET host and Angular SPA; check helpers and CI jobs stay admin's, named in its Ship checks (harness-local). | |
| docs/harness-boundaries.md:64 | Session-written tests, specs and tools/ modules run unjudged through granted check helpers; only review and CI stand | docs/harness-boundaries.md:824 | residual | | Stack-specific (src/tests/tools, host-checks.sh). Payload states the general bound only. Move the paragraph to admin's Residuals; protect-main required_status_checks id stays there. | |
| docs/harness-boundaries.md:79 | /pr is not narrowed to two files, since /ship applies review fixes after /pr in one user turn | docs/harness-boundaries.md:1766 | covered | | Same frontmatter-deny-holds-for-the-turn argument is stated for chained push at 1766; admin's src/tests/tools instance is a residual with the row above. | |
| docs/harness-boundaries.md:84 | *.csproj stays editable; VersionOverride or feed in a project file is refused by the pin gate in CI | - | local | | .NET supply-chain input and admin's .github/pin-gate; stays in admin's Residuals, as the style-pass row above says. | |
| docs/harness-boundaries.md:92 | Permission rules take Edit(...), never Write(...) | .harness/agent-rules.md:15 | covered |  | Hard rule, same wording. |  |
| docs/harness-boundaries.md:94 | settings.json self-locks; change lands complete and goes last; restore verified by reading | .harness/agent-rules.md:18 | covered |  | Hard rule; payload adds the permission-root section at docs/harness-boundaries.md:610. |  |
| docs/harness-boundaries.md:97 | Guards start through run-guard.sh; remembered mark is an empty dir, never exec'd, refused call removes it | docs/harness-boundaries.md:846 | covered | | Payload's guard launcher section states the same mark, the child run and the one-refused-call residual. | TheLauncherProvesWhatItRemembers, ARememberedGuardAnswersAsAProbedOne |
| docs/harness-boundaries.md:120 | Refresh hook after every writing tool and at SessionStart; resolves repo from file or cwd; seeds worktree index | docs/harness-boundaries.md:185 | covered | | Payload's refresh-index.py section covers events, cwd resolution, lock and seeding index.sqlite only (316-320). | test_index_refresh_hook.py |
| docs/harness-boundaries.md:159 | Query hint on UserPromptSubmit; one line for locate/explain questions; exits 0 always; plain sh | docs/harness-boundaries.md:434 | covered | | Payload's hint hooks section covers it (Python hook; cluster D compares behaviours). | test_index_query_hint.py |
| docs/harness-boundaries.md:180 | Search hint refuses the first symbol search once per session, naming the answering route | docs/harness-boundaries.md:463 | covered | | Payload's index-search-hint.py section states the same soft block and the worktree route (cluster D). | test_index_search_hint.py |
| docs/harness-boundaries.md:201 | Fork writes worktree settings.local.json holding only enabledMcpjsonServers | docs/harness-boundaries.md:404 | covered | | Payload states the same MCP-approval carry and the warning on an unreadable file. | test_git_worktree_fork.py |
| docs/harness-boundaries.md:210 | /ship and /review-branch grant index commands they name; loading the skill widens to update/index | docs/harness-boundaries.md:434 | covered | | Grant text lives in the payload commands; residual that the skill also approves update/index is in the hint-hook section. Cluster E compares frontmatter. | test_index_query_hint.py |
| docs/harness-boundaries.md:223 | CBX_NO_SKILL_AUTO_UPDATE set in settings env so the CLI cannot rewrite the tracked skill | docs/harness-boundaries.md:288 | covered | | Payload states it with the stamp mechanism (166-174, 288). | test_index_query_hint.py |
| docs/harness-boundaries.md:233 | MCP_TIMEOUT raised in env; plugin-server failure cached 15 minutes per machine; MCP_TOOL_TIMEOUT left | docs/harness-boundaries.md:562 | covered | | Payload has the same section and the same setting (base env). | |
| docs/harness-boundaries.md:255 | .claude/skills/** is a grant surface and denied for editing | docs/harness-boundaries.md:88 | covered | | Payload states the skills argument in Edit denies and agent self-protection. | |
| docs/harness-boundaries.md:259 | A command holding Write or Edit denies ~/.claude memory and output-styles; measured refusal; test fails when missing | docs/harness-boundaries.md, *A command that holds `Write` or `Edit`* | ported #254 | 2 | Frontmatter on `/ship`, `/pr`, `/style-pass`, `/dispatch` and `/team`, and the case over the manifest's commands, since a target's own are its to hold. The shell gap is wider than this row said: the payload's guard admits a redirect and `rm` there too, which admin's refuses, so the paragraph says so (#246). | AWritingCommandDeniesTheUsersMemoryAndOutputStyles |
| docs/harness-boundaries.md:287 | A command /ship runs before it pushes never denies push; sweeps keep their deny | docs/harness-boundaries.md:1766 | covered | | Payload states it, with NothingShipChainsDeniesPush replacing CHAINED_BEFORE_A_PUSH and a local_commands.py hook for a target's own commands. | CHAINED_BEFORE_A_PUSH |
| docs/harness-boundaries.md:297 | Auto-mode classifier refused /ship merge as Merge Without Review (#613); owner added autoMode.allow; stop and hand the line | docs/harness/pitfalls.md:145 | residual | | Measurement and remedy are admin's (its autoMode entry, #613). Payload pitfalls only says the classifier refuses outward writes. Move to admin's Residuals, with ship.md's A refused merge cite. | |
| docs/harness-boundaries.md:314 | /ship grants exactly Agent(branch-reviewer); every other profile denied by name; suite reads agents/ | docs/harness-boundaries.md:709 | covered | | Payload grant is Agent(branch-reviewer) with the other types denied in the sweeps and dispatch; test_command_grants.py reads profiles each run. | CommandsEnforceTheEditingBoundariesTheyState |
| docs/harness-boundaries.md:323 | External reviewers archived at tag archive/external-reviewers; guard rule for Grok ledger dropped | docs/harness-boundaries.md:690 | covered | | Same tag and restore command in payload Grant semantics. | |
| docs/harness-boundaries.md:336 | shard-harness-suite.py is the harness suite; reads tracked files so a new root fails until placed | docs/harness-boundaries.md:2425 | ported #240 | 3 | Plan decision: payload takes the shard runner with .claude/scripts as its one root. Payload docs state nothing of it; add this paragraph with the runner. | test_harness_shards.py |
| docs/harness-boundaries.md:343 | Runner owns every discovery root; units compared to discovery; SERIAL and TOGETHER tables fail loudly on a stale name | docs/harness-boundaries.md:2438 | ported #240 | 3 | Same runner; the never-stop-placing-a-class rule is the agent-rules gate lesson in a splitter. Port the paragraph and its tests with the runner. | test_harness_shards.py |
| docs/harness-boundaries.md:361 | One harness run at a time per user: per-user temp lock, second run waits and says so | docs/harness-boundaries.md:2460 | ported #240 | 3 | Part of the shard runner (#323). Port with the runner; payload pitfalls.md:139 says a queued runner is not a hung one but not why. | test_harness_shards.py |
| docs/harness-boundaries.md:370 | Sweeps write slice lists beside the worktree and refs/sweeps/<kind> only; residual is a wrong mark | docs/harness-boundaries.md:2207 | covered | | Payload states the same two writes, the full-SHA rule and the full-sweep fallback. | |
| docs/harness-boundaries.md:383 | A sweep start drops sweep worktrees over a day old and prunes; admin-dir loss on moved worktrees; lock exempts | docs/harness-boundaries.md:2191 | covered | | Payload has the day residual and the shape checks. Payload-only gap: it omits that prune deletes .git/worktrees admin dirs and that git worktree lock exempts; add one sentence (cheap, general). | |
| docs/harness-boundaries.md:404 | Only force push is git-rebase-onto-main.sh, granted by name in /ship; guards enumerated in script header | docs/harness-boundaries.md:1344 | covered | | Payload's grant inventory states the same helper and where the guards live. | test_git_rebase_onto_main.py |
| docs/harness-boundaries.md:429 | git-trailer-pr.sh is a second leased force push; refusals; residual is a push that fails after rewrite | docs/harness-boundaries.md:1361 | covered | | Same paragraph in payload, with main-checked-out refusal added. | |
| docs/harness-boundaries.md:446 | Worktrees sit inside the checkout; denies anchor at the worktree; from main the edit guard refuses nested .claude | docs/harness-boundaries.md:658 | covered | | Payload states the permission-root move and the sensitive-file backstop. | |
| docs/harness-boundaries.md:459 | Relative write target judged against cwd; refused after cd/pushd/source/env -C/-S/execdir; over-matching chosen | docs/harness-boundaries.md:1162 | out of scope | | Payload follows a literal cd and admits cd x then write y (736 typed). Refusing every relative target after any cd is the false refusal the threat model files. Cluster A owns the guard. | |
| docs/harness-boundaries.md:475 | Windows worktree remove can unregister then fail to delete; helpers re-ask register, bounded deletion, exit | docs/harness-boundaries.md:212 | covered | | Payload states the lock, partial removal and exit 4; pitfalls.md:108 holds the Windows fact. CLAUDE_WORKTREE_REMOVE_TRIES env is cluster B's. | |
| docs/harness-boundaries.md:485 | Edit guard judges main checkout from a worktree by protected_in_worktree inventory | docs/harness-boundaries.md:1971 | covered | | Payload judges an unentered worktree and main from linked ones by this target's own denies, read from settings, not a fixed inventory. | |
| docs/harness-boundaries.md:493 | On Windows a path component ending in dot or space is refused outright | - | out of scope | | Admin itself says whether the matcher differs is unmeasured; a trailing-dot target is not typed in ordinary work. Cluster A may port if a replay shows a bypass. | |
| docs/harness-boundaries.md:497 | Edit guard admits the task-list file beside the main checkout and nothing else outside | docs/harness-boundaries.md:1985 | covered | | Payload admits everything outside except named login files, so the task list and siblings pass; narrower than admin's one-file rule and by design (1990-1992). | |
| docs/harness-boundaries.md:512 | find judged by -fprint/-fls/-delete only; rm/rmdir/shred/mv refused on cwd, parent, / or home | docs/harness-boundaries.md:1144 | covered | | Payload refuses a tree-taking verb on a directory holding a denied path (rm -rf .claude) and admits the root itself; a guard difference for cluster A. | |
| docs/harness-boundaries.md:523 | Git-argv hook refuses what it cannot finish: brace word limit, scan and length budgets, watchdog, UTF-8 decode | docs/harness-boundaries.md:1119 | covered | | Payload decodes UTF-8 and admits non-JSON (1119-1125); budget and watchdog behaviour is cluster A's guard row, not documentation. | |
| docs/harness-boundaries.md:545 | sed judged by reading its script; -f and any expanding word refused; sed -n 1p "$FILE" refused | docs/harness-boundaries.md:2218 | out of scope | | Refusing sed with a computed operand is a false refusal agents type daily. Payload keeps only the CRLF guard for sed -i. | |
| docs/harness-boundaries.md:555 | MSBuild and NuGet auto-imported files denied by name at root and by family, in commands and settings | - | local | | .NET toolchain denies; plan keeps the 51 admin denies as config additions (Edit(AGENTS.md), MSBuild set). Residual that a Directory.Build.props above the checkout is not covered stays with them. At c5ec185c the root Directory.Build.props itself has only the family rule `**/Directory.Build.*` (A, git guard, #228). | |
| docs/harness-boundaries.md:571 | Agent(fork) denied beside built-in types; no other type named; suite asserts built-in list | .claude/commands/bug-sweep.md:5 | covered | | Payload frontmatter denies Agent(fork) in sweeps and dispatch; test_command_grants.py asserts the list. | |
| docs/harness-boundaries.md:578 | /style-pass edits eslint.config.js then runs the linter; other executed configs denied; *.config.ts not a family | - | local | | npm and Angular configs (app.config.ts is a providers file); stay in admin's Residuals, as frontend's :2491 and :2504 rows. | |
| docs/harness-boundaries.md:585 | Global deny names .claude/rules, output-styles and CLAUDE.local.md, not CLAUDE.md; each editing command denies CLAUDE.md | - | ported #298 | 4 | Payload base denies lack the three loaded-unasked paths. .harness/settings.base.json has none (checked), and the base is not widened: admin's config carries the three Edit denies. CLAUDE.md stays writable globally by design (/style-pass). | |
| docs/harness-boundaries.md:602 | git restore/checkout/clean judged by the paths they write; tree-ish and relocation variables refused | docs/harness-boundaries.md:999 | out of scope | | Payload denies reset --hard and clean -fdx and judges redirections; refusing checkout of a tree-ish, wrappers and relocation variables is the allow-list shape frontend ruled out. Cluster A ports harmful forms only. | |
| docs/harness-boundaries.md:618 | git rm and git mv held to the same relocation refusal | docs/harness-boundaries.md:1144 | out of scope | | git -C .claude rm is a spelling built to reach a protected path; the verb judging in payload covers the plain forms. Cluster A. | |
| docs/harness-boundaries.md:668 | Relocation closed by the exporting route: INERT_WRAPPERS, nameref, set -a, BASH_ENV, shells by -i/-l/--login | - | out of scope | | A closed list of bash export routes to hide git from a hook; fails criterion 1 of the threat model and trails the grammar. Not ported. | |
| docs/harness-boundaries.md:706 | Stdin channel judged by content: unclassified programs refused heredocs, here-strings, UNPLAIN; EVALUATORS/FOREIGN_SHELLS lists | docs/harness-boundaries.md:1136 | out of scope | | Admin's own replay shows 164 changes if every pipe were refused; the list exists to catch cp /bin/bash /tmp/sort. Payload refuses only a heredoc handed to a shell (1202). |  |
| docs/harness-boundaries.md:763 | Open residual bounded by #424: unquoted expansion, glob or brace into test operator, computed command word | docs/harness-boundaries.md:1105 | covered | | Payload states the bound as what has been looked for, not what is left (1105-1117). | |
| docs/harness-boundaries.md:806 | git checkout -f, reset --hard, stash, checkout-index, read-tree -u, merge, cherry-pick, rebase not judged | docs/harness-boundaries.md:999 | covered | | Payload denies reset --hard by rule (999) and judges the rest as admin does; the not-judged list is a residual statement only. | |
| docs/harness-boundaries.md:811 | A new residual is stated in this file and CLAUDE.md carries a pointer | docs/harness-boundaries.md:2437 | covered | | Payload's Residuals rule: a target states what its arguments leave open in docs/harness-local.md. | |
| docs/working-rules.md:9 | Build policy: SDK pin, exact package pins, ADR-019 warnings as errors, no pragma | - | local | | Admin's .NET and npm stack. | |
| docs/working-rules.md:18 | SPA versions exact in package.json, lockfile moves in same commit, .nvmrc pins Node | - | local | | Admin's npm stack. | |
| docs/working-rules.md:22 | Host refuses to start on wrong Admin:BackendDir or FrontendDir; does not run npm ci | - | local | | Admin's product. | |
| docs/working-rules.md:25 | A gate that silently stops covering the newest surface is the most-repeated failure | .harness/agent-rules.md:24 | managed | | Same lesson, same wording. | |
| docs/working-rules.md:30 | Style: C# from .editorconfig, Angular conventions, file-scoped namespaces, explicit types, braces, inject() | - | local | | Admin's code style; lives in its style guide (harness-local Documents). | |
| docs/working-rules.md:39 | Prose wraps at 80 columns, British spelling, identifiers keep real spelling | - | local | | Admin's style guide. Payload has no prose style rule; each target owns one. | |
| docs/working-rules.md:51 | No pragma suppressions and no real credentials (loopback passwords excepted) | - | local | | Admin's product and its spec. | |
| docs/working-rules.md:53 | A comment says why and cites the owner; a finding against a comment is closed by cutting it | docs/harness/working-rules.md:130 | managed | | Payload refuses requests to reword a true comment under the style guide's Comments rule; the comment-gate covers the rest (working-rules.md:37). | |
| docs/working-rules.md:55 | Test names are sentences with underscores (CA1707 suppressed on Tests projects) | - | local | | C# naming. | |
| docs/working-rules.md:60 | Read before you edit; Program.cs is the host composition root | - | local | | Admin's tree. | |
| docs/working-rules.md:62 | Commit messages semantic and present-tense; body argues the change; Closes in body fires on merge | docs/harness/working-rules.md:13 | managed | | Same two rules (13-20). | |
| docs/working-rules.md:67 | Every commit carries PR: #n; every intermediate commit builds; commits job builds each; revert by git-revert-pr.sh | docs/harness/working-rules.md:21 | managed | | Payload states trailer, build rule and revert helper. The commits CI job and commit-gate README are admin's ci.yml and local. | |
| docs/working-rules.md:76 | A reply is not a resolution; resolve the thread in the same act | docs/harness/working-rules.md:107 | managed | | Same rule. | |
| docs/working-rules.md:78 | Uncommitted work belongs in the PR being worked on; never revert it to clean the tree | .harness/agent-rules.md:30 | managed | | Same rule; payload drops the ask-rather-than-delete clause, which is wording. | |
| docs/working-rules.md:81 | Do not invent platform behaviour; gateway statuses pass through; fakes recorded from live service | - | local | | Admin's product (FakePlatform). | |
| docs/working-rules.md:84 | Task list at .todo/<repo>.md in main checkout's parent, outside every checkout, never committed | .harness/agent-rules.md:32 | managed | | Payload names it by config task_list in the main checkout's parent. | |
| docs/working-rules.md:88 | Row placement is a function of state: Remaining / Tracking / Paused / In progress table, re-derived at each event | docs/harness/working-rules.md:229 | ported #245 | 2 | Payload gave section order and the worktree-means-in-progress rule only. State table, abandoned-work rule and tracking-label rule ported; a pull request's row is one per issue and a row with no issue reads owed (not filed), both as dispatch_board.py parses them, /dispatch stays the one writer, and /ship step 6 re-derives rather than deletes. | test_working_rules.py |
| docs/working-rules.md:110 | Task list sits outside the checkout because isolation refuses in-checkout paths (#603); edit guard admits it | docs/harness-boundaries.md:1990 | managed | | Payload edit guard admits the list and says why (1990-1992). Admin's acceptEdits and TODO.md-link note is a residual. | |
| docs/working-rules.md:124 | Under acceptEdits the write prompts unless the user lists the directory; TODO.md link refused by edit guard | - | residual | | Machine and mode specific, tied to admin's TODO.md link. Move to admin's Residuals. | |
| docs/working-rules.md:129 | Rebuild the list from gh pr list and gh issue list --limit 1000, since the default 30 truncates | docs/harness/working-rules.md:253 | ported #245 | 2 | Payload warned of the 30-item cut for REST feeds only. The --limit 1000 rebuild advice is in the task-list bullet, and another session's In progress row stays through a rebuild. | test_working_rules.py |
| docs/working-rules.md:133 | Several sessions keep PRs open; rebase-only ruleset; no PR tested against the main it lands on | docs/harness/working-rules.md:45 | managed | | Payload states rebase-only landing and no up-to-date requirement. | |
| docs/working-rules.md:141 | Do not update an open PR because another merged; update only for conflict by the rebase helper | docs/harness/working-rules.md:45 | managed | | Same rule, same helper. Raw force-with-lease deny is in docs/harness-boundaries.md:1344. | |
| docs/working-rules.md:152 | Never force-push a branch another session owns, even through the helper | docs/harness/working-rules.md:49 | managed | | Payload: only a branch this session owns. | |
| docs/working-rules.md:154 | Each clone sets rerere.enabled true; worktrees share it; continue still follows git add | docs/harness/working-rules.md:51 | managed | | Payload states the setting; the git add after replay is detail for the helper. | |
| docs/working-rules.md:158 | Auto-merge waits only on required checks; set it only once review ended and no main-is-red issue; disable-auto on all when one opens | docs/harness/working-rules.md:165 | ported #245 | 2 | Payload said nothing of auto-merge. Rule and disable-auto step are beside the red-main bullet; /ship step 6 never sets it, and disable-auto is the owner's since the base denies gh pr merge. Step 6's stop on an open issue lands with main-red-open.sh (Task 3). | test_working_rules.py |
| docs/working-rules.md:170 | Every ci job also runs on push to main; only commit-gate and locality-gate are PR-only | - | local | | Admin's ci.yml layout. | |
| docs/working-rules.md:176 | Red main reverted first, fixed forward after; main-red issue is the signal, step 6 reads main-red-open.sh | docs/harness/working-rules.md:159 | managed | | Payload states revert-first; plan Decisions put main-red-open.sh in the payload with the title rule (Task 3). | |
| docs/working-rules.md:191 | A flake is a comment on the flaky tracker; whoever comments reruns failed jobs on main's tip; only green closes the issue | docs/harness/working-rules.md:150 | managed | | Same rule. Rerun-failed command and the step 6 stop while open: payload working-rules.md:151 closes on green. | |
| docs/working-rules.md:196 | A check red on a PR and on main belongs to main; unrelated PR waits, then is updated through the rebase helper | docs/harness/working-rules.md:159 | ported #245 | 2 | Payload lacked the rule and the update after it (a rerun reads the old merge). Its own bullet after the red-main one; the conflict rule at :45 and the red-check rule name the exception. | test_working_rules.py |
| docs/working-rules.md:202 | One owner per fact; others cite by symbol or file, never value; no gate reads CLAUDE.md | docs/harness/working-rules.md:94 | ported #245 | 2 | General rule payload lacked; agent-rules.md says the same only for its own sections. In Review, with a restatement left untouched kept under What counts as a finding. | test_working_rules.py |
| docs/working-rules.md:209 | Precedence: code and README beat spec; plans/ frozen; spec moves with a rule; .remember/ never edited | - | local | | Admin's docs/superpowers tree and spec. | |
| docs/working-rules.md:220 | Commands and skills list; no /validate-blueprint; locality gate is CI; admin-invariants skill | - | local | | Admin's commands and skill. | |
| docs/working-rules.md:234 | Read boundaries index first and only the section needed before touching .claude | .harness/agent-rules.md:115 | managed | | Payload's Where the detail is states it. | |
| docs/token-plan.md:1 | Goal: spend tokens on the change; follows backend's token plan method (measure, one PR per step, exit test) | docs/harness/token-rules.md:1 | managed | | Payload token-rules states the measure-based reasons; the plan's method is admin's history. | |
| docs/token-plan.md:14 | Baseline: main sessions are the spend; /ship context large; ship.md a third of commands | docs/harness/token-rules.md:11 | local | | Admin's measurements (token-usage.md); payload keeps figures in the target's own file by rule (token-rules.md:7). | |
| docs/token-plan.md:55 | Delegation brief, review loop, plan rule, one task per session; compact-before-a-wait retired | .harness/agent-rules.md:51 | managed | | Payload keeps the same rules and states no tool compacts (token-rules.md:28). | |
| docs/token-plan.md:91 | CLAUDE.md cut to locator and hard rules; harness-boundaries gains an index | docs/harness/token-rules.md:17 | managed | | Payload holds the managed always-loaded part under a size and keeps CLAUDE.md to product and commands; boundaries index at :3. | |
| docs/token-plan.md:105 | Local branch-reviewer replaces external loops; exit holds reviewer to baseline recall | docs/harness/token-rules.md:74 | managed | | Payload: one branch-reviewer a round, external reviewers archived. Admin's baseline figure is a residual of its quality sets. | |
| docs/token-plan.md:116 | Sweeps read in slices from lists, follow leads, keep last clean commit; verification on Sonnet | docs/harness-boundaries.md:2207 | managed | | Slices and mark are in payload (2207); Sonnet re-verification in token-rules.md:101. | |
| docs/token-plan.md:132 | Commands split into runbook and argument; test holds each runbook under a ceiling and citations to headings | .claude/scripts/test_command_runbooks.py:1 | managed | | Payload has test_command_runbooks.py and docs/commands/. | test_command_runbooks.py |
| docs/token-plan.md:145 | A cut that loses a finding is not a saving; steps hold recall against quality sets | docs/harness/token-rules.md:98 | residual | | Payload's table gates cheaper models on the target's recall sets. The no-fewer-than-baseline exit claim is admin's process; move to its Residuals, citing token-quality-sets.md. | |
| docs/token-quality-sets.md:1 | Quality sets: review set of deferred findings and sweep set; record extended by new section, never edited | docs/harness/token-rules.md:7 | local | | Admin's dated measurements and issue numbers; payload names the target's own measurements file in Documents. | |
| docs/token-quality-sets.md:48 | How to use it: check out merge base, run reviewer with candidate prompt, count found rows, no fewer than baseline | docs/harness/token-rules.md:96 | residual | | Method to claim a reviewer or prompt change; payload says only to wait for the target's recall sets. Move to admin's Residuals or keep the file local. | |
| docs/token-quality-sets.md:59 | Baseline branch-reviewer 4 of 12 (33%), unmatched findings checked 8 of 9 hold, bug-auditor reruns, 2026-10-20 sweep set | - | local | | Admin's measured data. | |

#### A, edit guard

| Admin | Behaviour | Payload | Verdict | Task | Reason and fix | Admin's test |
|---|---|---|---|---|---|---|
| hooks/guard-edit-target.py:856 | From an entered worktree (project is main), main checkout's `.claude`, `.git`, root files refused | .claude/hooks/guard-edit-target.py:405 | ported #270 | 2 | c1: EnterWorktree moves the permission root, so main's denies name nothing; payload admitted. Narrowed: when cwd is a linked worktree, main targets outside it are judged by `protected_in_worktree`'s denies. c3: of 18,945 edits in the four repositories since 2026-10-19, 56 went from a worktree into main and 0 are held; `TODO.md` (39), `artifacts` (11), `.superpowers` (5) and `payload` (1) stay admitted. | test_the_main_checkout_is_judged_from_inside_a_linked_worktree, test_the_worktree_nested_inside_main_keeps_its_own_files_admitted |
| hooks/guard-edit-target.py:410; also :277, :998 | Target outside every checkout and every scratch root is refused | .claude/hooks/guard-edit-target.py:269 | covered |  | Frontend's row, ported #147 narrowed to `~/.ssh`, shell profiles and `~/.gitconfig`. The allow-list refuses sibling checkouts and `run-locally.md` and needs `.todo/`, c3. | test_a_path_outside_every_checkout_and_every_scratch_root_is_refused |
| hooks/guard-edit-target.py:384; also :502 | `~/.claude` credentials, settings, hooks, commands, agents, plugins refused, case-folded | .claude/hooks/guard-edit-target.py:294 | covered |  | Frontend's row, ported #147: both control sets, folded, judged on the first component under `~/.claude`. | test_the_harness_control_surface_is_refused_inside_its_own_root |
| hooks/guard-edit-target.py:264; also :400 | `~/.claude/CLAUDE.md`, `AGENTS.md` and control names at any depth under `~/.claude` refused | .claude/hooks/guard-edit-target.py:294 | out of scope |  | c3: `~/.claude/CLAUDE.md` is edited for the owner's rules (6 edits), and a control name below `projects` is session state. #147 dropped both deliberately. | test_the_harness_control_surface_is_refused_inside_its_own_root |
| hooks/guard-edit-target.py:821 | Linked worktree's `.claude` refused wherever the session stands, the entered worktree included | .claude/hooks/guard-edit-target.py:406 | out of scope |  | c3, frontend's withdrawn #147 row: an edit to a target's local `.claude/commands` file from inside its worktree is ordinary work (backend #1441). The unentered case is the covered row at :845. |  |
| hooks/guard-edit-target.py:775; also :828 | Windows path component ending in a dot or space refused; `.claude.` folded in worktree check | - | out of scope |  | c1: `package.json.` is a spelling no ordinary work types; it exists only to slip a matcher (#314). Frontend's `.claude.` row was out of scope too. | test_a_component_ending_in_a_dot_or_a_space_is_refused_on_windows |
| hooks/guard-edit-target.py:845 | Unentered linked worktree's `.github`, `.git`, root files and toolchain refused | .claude/hooks/guard-edit-target.py:405 | covered |  | Frontend's row, ported #147 narrowed to the target's Edit denies through `denied_path`. Admin's .NET and `AGENTS.md` denies come in as config additions per *Decisions*; `.github` stays editable, as admin denies none. | test_a_sibling_worktree_of_this_repository_is_judged_not_refused |
| hooks/guard-edit-target.py:853 | Link traversal inside an unentered linked worktree is judged and refused | .claude/hooks/guard-edit-target.py:416 | covered |  | Frontend's row, ported #147: the sibling is appended to the anchors. | test_a_sibling_worktree_of_this_repository_is_judged_not_refused |
| hooks/guard-edit-target.py:598; also :615 | A `.git` file without git's backlink makes no linked worktree | .claude/hooks/guard-edit-target.py:182 | covered |  | `verified_gitdir` requires the backlink before a sibling or common dir is believed. | test_a_sibling_worktree_of_this_repository_is_judged_not_refused |
| hooks/guard-edit-target.py:427 | Temp scratch and `~/.claude` state admitted, scratch names like `scripts` included | .claude/hooks/guard-edit-target.py:485 | covered |  | Payload admits everything outside a checkout that `home_offence` does not name. | test_the_temp_root_is_admitted_whole, test_the_harness_state_root_is_admitted, test_a_scratch_path_outside_every_checkout_is_admitted |
| scripts/test_edit_target_guard.py:1273 | A `TODO.md` link in the checkout to the task list is refused | .claude/hooks/guard-edit-target.py:459 | covered |  | The anchor loop's link-out refusal, identical on both sides; the payload pins it as a link out of the checkout. | test_a_todo_link_in_the_checkout_is_refused_as_any_link_out_is |
| hooks/guard-edit-target.py:315 | Scratch roots are `~/.claude` then `gettempdir()` only; stale TEMP cannot widen them | - | obsolete |  | Served the allow-list, which #147 replaced with `home_offence`. | test_a_stale_temp_environment_variable_does_not_widen_the_scratch_root |
| hooks/guard-edit-target.py:434 | Scratch spelling resolving out of the scratch root is refused | - | obsolete |  | Served the allow-list; `home_offence` judges the resolution, so a link into `~/.ssh` is held. | test_a_scratch_path_that_resolves_out_of_the_scratch_root_is_refused |
| hooks/guard-edit-target.py:456 | With HOME under temp, a link into `~/.claude` control surface is refused | - | obsolete |  | Served the temp-root admission; `home_offence` judges spelling and resolution against home directly. | test_a_home_under_the_temp_root_keeps_its_control_surface |
| hooks/guard-edit-target.py:477 | Home directory beneath the temp root is not scratch | - | obsolete |  | As the row above. | test_a_home_under_the_temp_root_keeps_its_control_surface |
| hooks/guard-edit-target.py:489 | Machinery of any checkout under the temp root is refused | - | obsolete |  | Served the temp-root admission. A sweep's git worktree there is a linked worktree, judged by the covered row at :845. | test_the_temp_root_is_admitted_whole |
| hooks/guard-edit-target.py:558 | Ordinary files of a linked worktree admitted, not refused as outside | - | obsolete |  | Admission the allow-list needed; payload admits by its fall-through. | test_a_sibling_worktree_of_this_repository_is_judged_not_refused |
| hooks/guard-edit-target.py:337; also :363, :513 | Task list admitted by name, only as a real file beside the guard's main checkout | - | obsolete |  | Served the allow-list; payload admits `.todo/` with everything `home_offence` does not name. | test_the_task_list_is_admitted_from_the_main_checkout, test_and_from_a_worktree_linked_to_it_which_is_why_it_moved, test_nothing_else_beside_it_is_admitted, test_the_task_list_is_admitted_only_as_the_file_it_is_spelled_as |
| scripts/test_edit_target_guard.py:1354 | Edit guard's hook command runs through `run-guard.sh` under `CLAUDE_PROJECT_DIR` | .claude/scripts/test_edit_target_guard.py:917 | covered |  | `assert_launched_on_the_floor` pins the same wiring. | test_the_hook_runs_through_the_portable_launcher |
| scripts/test_harness_helpers.py:2127 | Suite fails on any tracked symbolic link, the edit guard's premise | .claude/scripts/test_harness_denies.py:117 | covered |  | The same case. | test_the_repository_tracks_no_symbolic_link |
| scripts/test_harness_helpers.py:8405 | `.claude/hooks/**` is Edit-denied in both spellings | .claude/scripts/test_git_argv_guard.py:3474 | covered |  | The same case. | test_the_hook_directory_is_a_control_surface_and_is_denied |
| scripts/test_harness_helpers.py:8418; also :8383 | Launcher wiring: portable, `py` first, broken candidates passed over, one exec, closed set | .claude/scripts/test_run_guard.py:206 | covered |  | Payload's class holds each case for all five guards, plus an unknown name exiting 2. | test_no_hook_command_names_a_windows_only_interpreter, test_every_hook_goes_through_the_launcher, test_the_launcher_takes_a_closed_set_of_hook_names, test_the_launcher_runs_each_hook_it_admits |
| scripts/test_harness_helpers.py:8815; also :9328 | Remembered-interpreter mark and `run-guard.py` proof statuses | .claude/scripts/test_run_guard.py:440 | covered |  | Every case is in payload's two classes at :440 and :823, by name. | test_a_remembered_interpreter_that_does_not_prove_itself_refuses_the_call, test_the_remembered_path_answers_as_the_probed_one_does |
| scripts/test_harness_helpers.py:9613 | `harness-checks.sh` probes `py -3` after `py -3.12`, as the launcher does | - | local |  | `harness-checks.sh` is admin's stack by *Decisions*; the cases go to `test_harness_helpers_admin.py`. | test_the_probe_order_matches_the_hook_launcher, test_a_py_with_only_3_13_still_runs_the_suite |

#### A, git guard

| Admin | Behaviour | Payload | Verdict | Task | Reason and fix | Admin's test |
|---|---|---|---|---|---|---|
| hooks/guard-git-argv.py:4825; also hooks/guard-git-argv.py:4486 | A quoted heredoc handed to `bash .claude/scripts/gh-issue-create.sh` is read as the helper's data | .claude/hooks/guard-git-argv.py:3089 | ported #270 | 2 | c3: the payload refused it and refused 134 of admin's 16,697 Bash commands since 2026-10-07 over Markdown backticks, 42 of them in sweeps, which deny `Write`. Admin's one literal shape, for `gh-issue-create.sh`, `-hand`, `-harness`, `-mutation` and `-sweep`, matched on the text so `bash < a.sh <<'D'` is not it. Step 4: the 44 refusals of `gh-sweep-issue-create.sh` left go with that helper. | test_a_helper_script_reads_its_heredoc_as_data |
| hooks/guard-git-argv.py:243 | A write to the root's `Directory.Build.props` is refused | .claude/hooks/guard-git-argv.py:185 | ported #270 | 2 | c1, a write into a denied file. `fnmatchcase` needs a `/` before `**/`, so admin's only deny on that tracked root file, `Edit(**/Directory.Build.*)`, misses it: `ls > Directory.Build.props` is admitted (probed). Fix: `denied_path` also tries each `**/` rule with that prefix dropped; a live payload defect (frontend's root `playwright.config.ts` has only `**/playwright.config.ts`), filed as #228. | test_the_msbuild_and_nuget_names_are_protected_files_and_untracked |
| hooks/guard-git-argv.py:225; also hooks/guard-git-argv.py:243 | Writes refused into `.github`, `.vscode`, `node_modules`, npm and Angular configs, `CLAUDE.md`, `README.md` | .claude/hooks/guard-git-argv.py:170 | local |  | The payload protects the target's `Edit(...)` denies; admin denies none of these, and the plan keeps `.github` editable. Each becomes protected only if admin's config adds its deny (Task 4), which would also stop the Edit tool, a new stop. | test_the_protected_files_cover_every_tracked_root_file, test_the_measured_redirections_are_refused |
| hooks/guard-git-argv.py:2247; also hooks/guard-git-argv.py:225 | MSBuild and NuGet auto-imports, `obj` and `*.csproj.user` refused as write targets | .claude/hooks/guard-git-argv.py:185 | covered |  | Admin's `Edit(**/obj/**)`, `Edit(**/*.csproj.user)` and MSBuild/NuGet denies stay config additions (*Decisions*) and the payload reads them: `src/Directory.Build.props`, `artifacts/obj/x`, a `.csproj.user` probed refused. The guard-table case moves to `test_harness_helpers_admin.py`, against the config. | test_the_msbuild_and_nuget_names_are_protected_files_and_untracked |
| hooks/guard-git-argv.py:2199 | Protected names matched at any path component and folded for case | .claude/hooks/guard-git-argv.py:185 | covered |  | Ported #147 narrowed, as frontend's row: anchored at the checkout's root and folded, so `payload/.claude/…` and `.claude/worktrees/` stay writable. | test_a_component_is_matched_rather_than_a_prefix, test_a_protected_name_in_another_case_or_spelling_is_refused |
| hooks/guard-git-argv.py:2236 | 8.3 short names, NTFS streams and trailing dots read as protected | - | out of scope |  | As frontend's row: `PACKAG~1.JSO` and `package.json::$DATA` exist only to dodge the name; *The guards' threat model*. | test_a_protected_name_in_another_case_or_spelling_is_refused |
| hooks/guard-git-argv.py:2536; also hooks/guard-git-argv.py:2116 | A redirection writing into a protected tree or file is refused, `>&word` included | .claude/hooks/guard-git-argv.py:2979 | covered |  | Ported #147: `write_offence` judges every writing operator, and `>&` onto a word that is not a descriptor as a file. | test_the_measured_redirections_are_refused, test_every_writing_operator_reaches_the_machinery_check, test_a_reading_redirection_is_not_a_write |
| hooks/guard-git-argv.py:3757; also hooks/guard-git-argv.py:2722, hooks/guard-git-argv.py:3947 | Writing verbs onto protected paths refused, through `-t`, hard links and `-i` backup suffixes | .claude/hooks/guard-git-argv.py:2927 | covered |  | Ported #147: `verb_destinations` at :2790 reads `-t`, `cp -l` and `ln` sources, and `backup_word` at :2780 models the `*` or `/` suffix admin refuses outright. | test_every_writing_verb_reaches_the_machinery_check, test_a_verbs_destination_is_found_through_its_options, test_the_measured_copy_is_refused |
| hooks/guard-git-argv.py:2259; also hooks/guard-git-argv.py:2623 | `~`, `~+` and five shared variables expanded and the resulting path judged | .claude/hooks/guard-git-argv.py:2610 | covered |  | Ported #147: `written_path` expands `~`, `~+` and `EXPANDABLE_VARIABLES` and judges the path. | test_an_unreadable_target_is_refused_and_an_expansion_is_judged |
| hooks/guard-git-argv.py:2639; also hooks/guard-git-argv.py:2828, hooks/guard-git-argv.py:3914, hooks/guard-git-argv.py:2623 | An unknown variable, `~-`, `~user` or computed operand as a write target refused | .claude/hooks/guard-git-argv.py:2610 | out of scope |  | c3, frontend's narrowing: the payload admits what it cannot read. Admin's guard refused 22 such targets (`> $R/x.impact`) and 12 such operands in admin's 16,697 commands. | test_an_unreadable_target_is_refused_and_an_expansion_is_judged, test_a_verb_operand_nothing_can_read_is_refused |
| hooks/guard-git-argv.py:2364; also hooks/guard-git-argv.py:2674 | A relative write target refused whenever the command can change directory | .claude/hooks/guard-git-argv.py:2960 | covered |  | Ported #147 narrowed: a literal `cd` is followed. Admin's form refused 95 of admin's commands (`cd "$TMPDIR" && sed -i …`), the c3 cost the narrowing removes. | test_the_dot_command_and_a_message_are_read_where_they_stand |
| hooks/guard-git-argv.py:2391; also hooks/guard-git-argv.py:2355 | `env -C`, `--chdir`, `find -execdir`, `source`, `.` and `eval` count as directory changes | - | out of scope |  | c1 fails: in admin's 16,697 commands each appears only in the guard's own probes. A literal `cd` is the change the payload follows. | test_a_wrapper_that_changes_directory_is_one_for_a_relative_target |
| hooks/guard-git-argv.py:2452 | A write through a link into a protected tree is refused | .claude/hooks/guard-git-argv.py:2680 | covered |  | Ported #147: `protected_target` judges the spelling and its `realpath`. | test_a_redirection_through_a_link_into_a_protected_tree_is_refused, test_a_session_whose_directory_is_a_link_into_a_protected_tree_is_refused |
| hooks/guard-git-argv.py:2493 | A relative target placed from the event's `cwd`, a session inside `.claude/hooks` included | .claude/hooks/guard-git-argv.py:2610 | covered |  | `written_path` joins the event's `cwd`, and `checkout_relative` at :2653 judges it from the checkout root. | test_a_session_already_inside_a_protected_tree_is_judged_where_it_stands |
| hooks/guard-git-argv.py:2132; also hooks/guard-git-argv.py:2588 | Glob, brace, substitution or process-substitution write target refused | - | out of scope |  | As frontend's row: `> package.jso?` and `> >(sh -c …)` only hide the name; *The guards' threat model*. | test_a_globbed_redirection_target_is_refused |
| hooks/guard-git-argv.py:2308 | Writes into `docs`, `e2e`, `public`, `src`, `tests`, `tools` at a checkout root refused | - | local |  | `/review-branch`'s trees, local by *Decisions*: its frontmatter denies bind its own run, which no hook sees. Held globally it stops implementation: admin's guard refused `cat > src/…`, `sed -i … src/…` and `cat >> docs/…` in admin's transcripts. | test_a_redirection_into_an_application_tree_is_refused |
| hooks/guard-git-argv.py:3701; also hooks/guard-git-argv.py:3667, hooks/guard-git-argv.py:2722 | `find -fprint*` and `-fls` files and `-delete` starting points judged as writes | .claude/hooks/guard-git-argv.py:2547 | ported #270 | 2 | c1, a routine idiom: `find .claude/hooks -delete` is admitted (probed). Narrowed: `find_offence` judges its `-fprint*`/`-fls` file as a redirection and `-delete` starts as `rm -r`, so `.`, no start and `-files0-from` stay admitted. Typed 0 outside probes. | test_a_find_delete_started_above_the_checkout_is_refused |
| hooks/guard-git-argv.py:3169; also hooks/guard-git-argv.py:3960, hooks/guard-git-argv.py:3212 | `rm`, `mv`, `rmdir`, `shred` or `unlink` of the working directory, a parent, `~` or `/` refused | .claude/hooks/guard-git-argv.py:2927 | ported #270 | 2 | c1: *The guards' threat model* names removing a parent of the checkout; `rm -rf ..`, `rm -rf ~`, `rm -rf /` were admitted (probed). Narrowed to a strict parent of the checkout root, `~` and `/`, a trailing `/*` read as its directory; `rm -rf .` and a move's destination stay admitted. Typed 0. | test_a_verbs_destination_is_found_through_its_options, test_an_ordinary_writing_verb_is_still_admitted |
| hooks/guard-git-argv.py:3103; also hooks/guard-git-argv.py:2973, hooks/guard-git-argv.py:3888 | `sed` scripts read for `w`, `W` and `e`; `sed -f` and a shell-expanded `sed` word refused | - | out of scope |  | c1 fails for `w` and `e`: typed only in the guard's own probes. c3 for the rest: admin's guard refused 36 of admin's commands such as `sed -n 243,305p $S`. | test_a_sed_script_is_read_for_what_it_writes_and_runs |
| hooks/guard-git-argv.py:4029 | `xargs` in front of any writing verb refused | .claude/hooks/guard-git-argv.py:2439 | out of scope |  | c3: the operands are unreadable, which the payload admits (harness-boundaries.md:1162), and piping names into `xargs rm` is a routine idiom; typed 0 in admin, so a port buys nothing. The payload keeps `xargs` before a push. | test_a_verb_operand_nothing_can_read_is_refused |
| hooks/guard-git-argv.py:3416; also hooks/guard-git-argv.py:3308, hooks/guard-git-argv.py:3982, hooks/guard-git-argv.py:131 | `git checkout <ref> -- path`, `git restore`, `git rm`, `git mv` onto a protected path refused | .claude/hooks/guard-git-argv.py:2156 | ported #270 | 2 | c1, routine git writing a denied tree: `git checkout origin/main -- .claude/settings.json` and `git rm .claude/hooks/x` were admitted (probed), `git` being a reader at :2156. Narrowed: pathspecs through `destination_offence`, a literal `-C` followed; HEAD restores and `--staged` admitted. Narrowed again by Step 3's replay, which read four such writes as ordinary work in a session's own worktree, not the 0 first counted: held in a main checkout alone, a linked worktree's write being in its pull request's diff. | test_git_restore_checkout_and_clean_are_judged_by_the_paths_they_write |
| hooks/guard-git-argv.py:3465; also hooks/guard-git-argv.py:3571, hooks/guard-git-argv.py:3313, hooks/guard-git-argv.py:3146, hooks/guard-git-argv.py:7078 | A git path writer behind a wrapper, with magic or computed pathspecs, relocated, or over the whole tree, refused | - | out of scope |  | `GIT_WORK_TREE=.claude`, `env -C`, startup shells and pathspec magic exist to move or hide the paths; threat model. c3 for `git restore .` and `git restore ../../CLAUDE.md`, which admin's guard refused; `git clean` is a base deny already. | test_git_restore_checkout_and_clean_are_judged_by_the_paths_they_write |
| hooks/guard-git-argv.py:6804 | `git config` refused unless it only reads | .claude/hooks/guard-git-argv.py:3213 | ported #270 | 2 | c1: the `git -c` the payload refuses at :3213, made persistent; `git config alias.p push` and `core.pager` were admitted (probed). Narrowed by hand to writes of keys that run a program (`alias.*`, `core.pager`, `core.hooksPath`, `core.sshCommand`, `*.cmd`, `diff.external`); other writes such as `rerere.enabled`, a read and a removal stay admitted (c3). | test_a_persistent_alias_and_a_dashed_git_executable_cannot_reach_a_protected_ref |
| hooks/guard-git-argv.py:6826; also hooks/guard-git-argv.py:6741 | A `git-<verb>` executable word refused | - | out of scope |  | `git-send-pack` exists only to hide the verb from `git_segments`, typed 0. c3: admin's guard refused 7 of admin's commands naming the worktree path `.claude/worktrees/git-guard-push`. | test_a_persistent_alias_and_a_dashed_git_executable_cannot_reach_a_protected_ref |
| hooks/guard-git-argv.py:366; also hooks/guard-git-argv.py:393, hooks/guard-git-argv.py:6964 | `send-pack`, `http-push`, `receive-pack`, `subtree` and `remote-*` refused as remote ref updates without `push` | .claude/hooks/guard-git-argv.py:96 | ported #270 | 2 | c1, as frontend's `REFUSED_SUBCOMMANDS` row: real git verbs that update a remote ref `push_offence` never reads, typed 0. Narrowed: `send-pack`, `http-push`, `receive-pack` refused whole and `subtree push`; the scan past unknown globals stays out. | test_the_plumbing_that_updates_a_remote_ref_without_push_is_refused, test_a_ref_named_send_pack_is_data_for_another_verb |
| hooks/guard-git-argv.py:126; also hooks/guard-git-argv.py:6934 | `git difftool` and `git mergetool` refused whole | .claude/hooks/guard-git-argv.py:112 | ported #270 | 2 | c1, the `--ext-diff` act by another verb: each runs the configured `diff.tool` or `merge.tool`, and the payload refuses only `difftool -x` and `--extcmd`. Typed 0, and interactive. Add both to `REFUSED_SUBCOMMANDS`. | test_the_programs_listed_as_readers_cannot_be_made_to_run_one |
| hooks/guard-git-argv.py:6946 | `git apply` and `git am` refused | - | out of scope |  | c3: admin typed `git apply` 22 times, `--cached` and `-C <clone>` among them, each refused by admin's guard. The files are in the patch, the unreadable-operand case the payload admits. | test_a_git_environment_variable_that_executes_is_refused_where_it_is_assigned |
| hooks/guard-git-argv.py:6952 | `bisect run`, `submodule foreach`, `filter-branch`, `rebase -x` and `--exec` refused | .claude/hooks/guard-git-argv.py:3224 | covered |  | Ported #147: `REFUSED_SUBCOMMANDS` at :96, `EXECUTING_FORMS` at :125, `EXECUTING_SHORT_FLAGS` at :112, and `--exec` in `FORBIDDEN_FLAGS` at :72. | test_a_persistent_alias_and_a_dashed_git_executable_cannot_reach_a_protected_ref |
| hooks/guard-git-argv.py:6970 | A git subcommand word bash computes is refused | - | out of scope |  | As frontend's row: `git $SUB` is hidden. c3: under its splitting reading admin's guard refused 4 of admin's `git -C $B log` commands. | test_a_computed_git_subcommand_is_refused |
| hooks/guard-git-argv.py:120 | `--no-index` refused with its abbreviations | .claude/hooks/guard-git-argv.py:72 | local |  | As frontend's row: it reads only, and admin's `Bash(git *--no-index*)` deny stays a config addition (*Decisions*). Admin's guard refused 5 typed `git diff --no-index`. | test_a_forbidden_flag_hidden_in_a_brace_list_is_refused |
| hooks/guard-git-argv.py:326 | `git push --follow-tags` refused | .claude/hooks/guard-git-argv.py:213 | obsolete |  | The payload lists it in `PUSH_ALLOWED_FLAGS`: a tag is not a branch the push checks protect, and the `main` ruleset backs the rest. | test_follow_tags_is_refused |
| hooks/guard-git-argv.py:378 | A subcommand folded for case, trailing dots and `.exe` before the checks | - | out of scope |  | As frontend's row: `git PUSH.` and `push.exe` exist only to dodge the name; *The guards' threat model*. |  |
| hooks/guard-git-argv.py:6652; also hooks/guard-git-argv.py:157, hooks/guard-git-argv.py:171, hooks/guard-git-argv.py:6578 | Executing or unlisted environment names before git or rg refused, `env -u` and `-i` included | - | out of scope |  | c3, as frontend's row: admin's guard refused `GIT_EDITOR=true git rebase --continue`, `MSYS_NO_PATHCONV=1 git show` and a `GIT_CONFIG_GLOBAL` run in admin's transcripts. | test_a_git_environment_variable_that_executes_is_refused_where_it_is_assigned |
| hooks/guard-git-argv.py:6539; also hooks/guard-git-argv.py:144 | `rg --pre`, `--hostname-bin` and any `sort -o` or `--compress-program` refused | - | out of scope |  | c1 fails: not git, and typed only inside the guard's own issue bodies. `sort -o` is refused whatever its target, a false refusal under c3. | test_the_programs_listed_as_readers_cannot_be_made_to_run_one, test_the_readers_still_read |
| hooks/guard-git-argv.py:4078; also hooks/guard-git-argv.py:7200, hooks/guard-git-argv.py:4115, hooks/guard-git-argv.py:6335 | `gh` or an unlisted program inside a command or process substitution refused | - | out of scope |  | As frontend's rows. c3: admin's guard refused 63 of admin's commands, such as `for id in $(gh run list …)` and a `--body "$(cat <<'EOF'` issue. | test_a_redirection_into_an_application_tree_is_refused |
| hooks/guard-git-argv.py:6516 | A program word bash computes is refused | - | out of scope |  | As frontend's row: text assembled and then run. c3: admin's guard refused 21 of admin's commands such as `bash $S <id>`. | test_a_computed_program_word_is_refused_and_a_computed_argument_is_not |
| hooks/guard-git-argv.py:6445; also hooks/guard-git-argv.py:6361, hooks/guard-git-argv.py:6351 | Brace variants of every git word judged; past 256 words refused | - | out of scope |  | As frontend's brace rows: `git {fetch,--upload-pack=x}` is built to hide, and the word limit only bounds that reading. | test_a_forbidden_flag_hidden_in_a_brace_list_is_refused, test_brace_alternatives_is_bounded_and_the_command_is_refused |
| hooks/guard-git-argv.py:6186; also hooks/guard-git-argv.py:7375 | `env -S` strings judged as command lines; a `\` or `$` in one refused | - | out of scope |  | As frontend's row: typed 0, one opaque word built to pass a reader. | test_a_verbs_destination_is_found_through_its_options |
| hooks/guard-git-argv.py:4425; also hooks/guard-git-argv.py:4450, hooks/guard-git-argv.py:4563, hooks/guard-git-argv.py:4596 | `mksh`, `ash`, `yash`, any program's `-c`, `/c` or `-Command` script read as shells; `envdir`, `chpst` refused | .claude/hooks/guard-git-argv.py:1692 | out of scope |  | A copied or unusual shell running git exists only to pass the reader; *The guards' threat model*. The payload reads `bash`, `sh`, `dash`, `zsh` and `ksh`. | test_a_shell_no_list_names_or_another_program_starts_is_judged |
| hooks/guard-git-argv.py:5945; also hooks/guard-git-argv.py:5459, hooks/guard-git-argv.py:5563, hooks/guard-git-argv.py:5610 | An unclassified program handed git-writing stdin, or a line redefining name resolution, refused | - | out of scope |  | A function, alias, `PATH` write or renamed shell exists to hide the shell; threat model. c3: admin's guard refused 18 of admin's commands, `git archive HEAD` piped into `tar -x` among them. | test_an_unclassified_program_handed_git_writers_on_stdin_is_refused |
| hooks/guard-git-argv.py:4946 | `printf` or `echo` with any backslash, piped into a shell, refused | .claude/hooks/guard-git-argv.py:1920 | out of scope |  | An escape that spells git past the reader; threat model. The payload keeps refusing `printf` with `%` and `echo -e`. | test_a_printer_that_formats_is_not_read_as_its_arguments |
| hooks/guard-git-argv.py:1109 | `#`, `<<` or `$(` inside `${…}` refused | - | out of scope |  | As frontend's substitution-body row: it hides a push only by a crafted expansion; typed once in admin, as a probe. | test_a_substitution_inside_a_parameter_expansion_does_not_blind_the_rest_of_the_command |
| hooks/guard-git-argv.py:1050 | `((` and `<<` in one command refused | .claude/hooks/guard-git-argv.py:539 | obsolete |  | Replaced by `_sums_in_group`, which reads `<<` inside arithmetic as a shift; admin's blanket form refuses honest `(( x = 1 << 2 ))`. The `$[ 1 <<EOF ]` spelling the payload admits is out of scope. | test_a_context_where_bash_reads_text_does_not_hide_the_lines_it_precedes |
| hooks/guard-git-argv.py:7335 | Untokenisable text gets a substring scan and a crude push check | .claude/hooks/guard-git-argv.py:3147 | covered |  | As frontend's row: the payload refuses every untokenisable command, stricter than the crude checks; outside issue heredocs (first row) that refused one of admin's 16,697 commands. | test_an_unparseable_command_still_gets_the_weaker_check, test_the_fallback_still_reads_the_push_grammar |
| hooks/guard-git-argv.py:7482 | `SCAN_BUDGET` refuses opener count times length | .claude/hooks/guard-git-argv.py:3290 | out of scope |  | As frontend's row. c3: it refused 3 of admin's 10,000-character `python - <<'E'` edits. The payload keeps `LENGTH_BUDGET`. | test_a_scan_past_the_budget_is_refused_in_time |
| hooks/guard-git-argv.py:7578; also hooks/guard-git-argv.py:7569 | A watchdog refuses a judgement still running after 20 seconds | - | out of scope |  | c2 needs ordinary input that times out: the payload judged each of admin's 16,697 commands in 0.14 s at most, and `LENGTH_BUDGET` bounds length; beyond that is input sized to outrun the hook. | test_a_non_ascii_event_is_judged_and_a_late_run_is_refused |
| hooks/guard-git-argv.py:7499 | `decision` split from `main` so the suite judges in process | .claude/scripts/test_git_argv_guard.py:79 | obsolete |  | As frontend's row: the payload suite spawns every case. | test_the_spawned_hook_answers_what_the_import_does |
| hooks/guard-git-argv.py:7615 | The event decoded as UTF-8, a bad byte replaced, so it is still judged | .claude/hooks/guard-git-argv.py:3351 | covered |  | The payload decodes UTF-8 and refuses an event that is not, which is stricter. | test_a_non_ascii_event_is_judged_and_a_late_run_is_refused |
| scripts/test_harness_helpers.py:8317; also scripts/test_harness_helpers.py:8355, scripts/test_harness_helpers.py:8368 | Gate: protected lists cover the editing commands' denies and every tracked root file | .claude/scripts/test_git_argv_guard.py:3811 | covered |  | Ported #147 as frontend's row, read from the config: :3811 and :3826. | test_the_protected_trees_cover_what_the_editing_commands_deny, test_the_protected_files_cover_every_tracked_root_file, test_the_protected_files_reach_names_no_enumeration_could_hold |
| scripts/test_harness_helpers.py:3517 | Gate: every branch name the naming table shows is one the push guard admits | .claude/scripts/test_git_argv_guard.py:3846 | covered |  | Ported #147 as frontend's row. | test_every_branch_name_the_naming_table_shows_is_admitted |
| scripts/test_harness_helpers.py:8383; also scripts/test_harness_helpers.py:8405 | Gate: the hook is wired for Bash and its directory is denied | .claude/scripts/test_git_argv_guard.py:3218 | covered |  | :3218 and :3474 hold both. | test_the_hook_is_registered_for_bash_in_settings, test_the_hook_directory_is_a_control_surface_and_is_denied |
| - | A piped `git push` chained by an AND or OR list without `pipefail` is refused | .claude/hooks/guard-git-argv.py:3191 | covered |  | payload-only: it newly refuses 7 of admin's 16,697 commands, a push piped into `tail` then `&& gh pr create`; the message names `set -o pipefail`. A trap refusal, kept. |  |
| - | `git update-index --cacheinfo` with a literal mode is refused unless `--add` | .claude/hooks/guard-git-argv.py:2515 | covered |  | payload-only: it newly refuses 7 of admin's commands (`--cacheinfo 100644,<sha>,src/…`); the message names `git ls-files -s`. A trap refusal, kept. |  |
| - | `git reset --soft` to a remote-tracking ref is refused | .claude/hooks/guard-git-argv.py:2518 | covered |  | payload-only: it newly refuses 3 of admin's commands (`git reset --soft origin/main`); the message names the fork point's SHA. A trap refusal, kept. |  |
