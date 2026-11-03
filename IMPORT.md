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
`.claude/settings.json` is still blob `aeb89a9`, so the settings base and the
Task 3 fixture needed no change.

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
  to read it from there; each stays backend-local, whole, so that its bytes
  stay backend's and backend's CI keeps running every case. The row names
  the cases that read backend's tree. They were found by running the suites
  in a rendered worktree (the `payload-suites` job's procedure), not by
  reading.
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
the pin, whole (blob `aeb89a9`, the same blob as at `f61a0932f`, so the
Task 3 fixture `harness_sync/tests/fixtures/backend-settings.json` needed no
update). The config's `settings` additions are empty.

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

`dump_settings(render_settings(base, backend config))` is byte-identical to
backend's file today; `test_backend_render_equivalent` holds the weaker
property Task 9 needs — the same `allow`, `deny` and `hooks` as multisets and
the same `env` — so a later reorder of the base does not fail it.

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
- `.claude/scripts/test_dispatch_run.py:1576-1577` — a path fixture for
  `project_slug`.
- `.github/closure-gate/test_closure_gate.py:17` — the repository fixture the
  gate's parser is called with.
- `docs/commands/bug-sweep.md:519`, `docs/commands/security-sweep.md:352` —
  history: what backend's run of 2026-10-21 filed.
- `docs/commands/security-sweep.md:366` — cites *The guards' threat model* in
  blueprint-backend's `docs/harness-boundaries.md`, its owner today (spec 6
  moves that citation to the harness).

## Stack mentions left verbatim

Payload files that name a backend stack value in prose or in a step, kept as
backend has them because the config schema has no key for a stack command and
backend's sync diff should be empty (spec 7, step 2). Each needs a config key
or a rewording before the first sibling's sync (spec 7, step 3). This
section and the next are an inventory only: the payload text stays as backend
has it. Both were found by grepping `payload/` for `dotnet`, `Platform.slnx`,
each backend-local command's name and each backend-only document's path, and
every line number was read back from the file.

- `.claude/commands/bug-sweep.md:108`, `.claude/commands/security-sweep.md:52`
  — the readable-root proof globs `$work/Platform.slnx`; its argument in the
  runbooks, `docs/commands/bug-sweep.md:218,260,287-288,328` and
  `docs/commands/security-sweep.md:75,117,144-145,168`.
- `.claude/commands/pr.md:149-150` — "once `Platform.slnx` exists, state the
  `dotnet build` / `dotnet test` result".
- `.claude/commands/style-pass.md:98` — `dotnet format` and Roslyn as the
  formatter.
- `docs/commands/branch.md:239` — "`dotnet test` … runs there";
  `docs/commands/bug-sweep.md:90` — "`dotnet test`" as what a build runs.
- `.github/output-gate/` — the gate itself checks .NET build output against
  `Platform.slnx`; `output_gate.py:18,24` and `README.md:3,5,12,18` name
  backend's trees and solution. Payload by the brief.
- `.claude/scripts/sweep-slices.sh:47` — slices `tools/` as tooling, a
  backend tree; `.claude/scripts/gh-label-ensure.sh:30` — the `code` label's
  description names `src/`, `tests/`, `tools/`, `deploy/`;
  `.claude/scripts/dispatch_run.py:27` — cites
  `tools/quality-sets/quality_sets.py` as the owner of four counts.
- `docs/harness-boundaries.md:24,1124,1164-1180,1395,1444-1445` — `dotnet`
  and `Platform.slnx`; spec 5.2 splits this document into common boundaries
  and backend's residuals.
- Test fixtures that use a `dotnet` command line as a sample string
  (`test_git_argv_guard.py:241-246`, `test_index_search_hint.py:118`,
  `test_watch_session.py:28-29`, `test_cbx.py:54`) — data, right in any
  target.

## References to backend-local commands and documents

Payload files that name a command backend keeps local, or cite a document
only backend has. Right in backend; in another target each points at nothing
until that target has its own or the reference is reworded.

Backend-local commands:

- `.claude/commands/ship.md:257-259,303` — `/validate-blueprint` after Class
  C and `/check-links` (with `docs/change-locality.md` §5).
- `.claude/commands/pr.md:102` — `/review-branch`; `pr.md:157` —
  `/validate-blueprint` and `/check-links`.
- `.claude/commands/bug-sweep.md:22-23` — `/validate-blueprint`,
  `/review-branch` in the table of neighbouring commands.
- `.claude/agents/branch-reviewer.md:42` — takes its bar from
  `.claude/commands/review-branch.md`'s *What counts as a finding*.
- `docs/commands/ship.md:427-428,442,468` — `/check-links`,
  `/validate-blueprint` and its runbook `docs/commands/validate-blueprint.md`.
- `.claude/scripts/git-worktree-drop.sh:50` — a comment naming
  `mutation-run.sh`'s reports.
- `docs/harness-boundaries.md:24,79-81,901,1164-1185,1434-1447` —
  `/review-branch`, `/check-links`, `/validate-blueprint`, `/mutation-sweep`,
  `dotnet-test.sh`, `mutation-run.sh`.

Backend-only documents:

- `docs/change-locality.md` — `.claude/commands/bug-sweep.md:249`,
  `commit.md:77`, `dispatch.md:118`, `pr.md:86`, `security-sweep.md:199`,
  `ship.md:257,272,388`, `team.md:90`; `.claude/scripts/gh-issue-create.sh:18`;
  `.github/issue-form-gate/README.md:7` (and `issue_form_gate.py`'s default
  contract); `docs/commands/bug-sweep.md:696`, `security-sweep.md:505`,
  `ship.md:446,546`, `team.md:18,106`.
- `docs/testing.md` — `.claude/commands/ship.md:259`;
  `.claude/scripts/review_helpers.py:19`;
  `.claude/skills/codebase-index/SKILL.md:12`;
  `.github/closure-gate/closure_gate.py:4`, `closure-gate/README.md:59`,
  `comment-gate/README.md:162`, `commit-gate/README.md:32`,
  `output-gate/README.md:38`; `docs/harness-boundaries.md:809`.
- `docs/roadmap.md` — `.claude/commands/ship.md:259`.
- `docs/style-guide.md` — `.claude/agents/branch-reviewer.md:46`;
  `.claude/commands/style-pass.md:2,23,73,86,122`;
  `.github/comment-gate/README.md:10`. (Each target has a style guide of its
  own by spec 3; the cited sections are backend's.)
- `docs/backend-architecture/` — `.claude/commands/ship.md:261`,
  `style-pass.md:30`; `.claude/skills/codebase-index/SKILL.md:53`;
  `.github/output-gate/README.md:5`, `workflow-lint/README.md:41`;
  `docs/commands/ship.md:427`; `docs/harness-boundaries.md:79`.
- `docs/token-plan.md` — `.claude/commands/team.md:33`;
  `docs/commands/ship.md:729`, `team.md:28,90`;
  `docs/harness-boundaries.md:498`.
- `docs/superpowers/` (backend's plans and specs) —
  `.claude/agents/branch-reviewer.md:37`; `.claude/commands/ship.md:110`;
  `.claude/scripts/sweep-slices.sh:116`; `.github/comment-gate/README.md:97`,
  `comment_gate.py:26,29`; `.github/plan-size-gate/README.md:3` (and
  `plan_size_gate.py`'s default directory); `docs/commands/bug-sweep.md:616`,
  `dispatch.md:6`, `security-sweep.md:435`, `ship.md:108,939`;
  `docs/harness-boundaries.md:1453,1472,1502`.
- Sections of backend's `CLAUDE.md` (spec 5.2 splits it) —
  `.claude/agents/branch-reviewer.md:3`; `.claude/commands/branch.md:71,83`,
  `bug-sweep.md:190`, `commit.md:27`, `style-pass.md:24,81,123`;
  `.claude/hooks/index-search-hint.py:438`;
  `.claude/scripts/sweep-slices.sh:113`;
  `.github/comment-gate/comment_gate.py:27`;
  `.github/plan-size-gate/README.md:4,25`, `plan_size_gate.py:2,20,24`;
  `docs/commands/branch.md:39-40,141`, `dispatch.md:175`,
  `ship.md:729,990`; `docs/harness-boundaries.md:10,35,46,51,53,69,83,305,808`.

## Decided after review

The whole-module classification of the mixed test modules stays for this
plan: splitting their backend-tree cases into backend-local modules would add
files to backend's first-sync diff, which spec 7 step 2 wants near-empty. #5
tracks splitting them so their generic cases run here. Until then, Task 7's
config for this repository excludes
`.github/workflows/comment-gate.yml`, whose suite stays in backend, so its
`python -m unittest` would find no tests here and fail. The config is
`.harness/config.json` and it does exclude that workflow (ruling R18); JSON
has no comments, so this is where the reason is recorded. Remove the exclusion
when #5 lands.

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
| `.claude/commands/pr.md` | payload | harness command; one stack mention left verbatim (see *Stack mentions*) |
| `.claude/commands/review-branch.md` | backend-local | grants and runs `dotnet-test.sh`, and its `disallowed-tools` enumerates backend's tracked trees and root files, which `test_harness_denies.py` holds it to (ruling: a stack command is backend-local or a config key; the schema has no such key) |
| `.claude/commands/security-sweep.md` | payload | harness command (spec 8); stack mention left verbatim (see *Stack mentions*) |
| `.claude/commands/ship.md` | payload | harness command; task list read from config (step 3) |
| `.claude/commands/style-pass.md` | payload | harness command; stack mention left verbatim (see *Stack mentions*) |
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
| `.claude/scripts/test_command_grants.py` | backend-local | `NothingShipChainsDeniesPush` and `TheSweepsDenyEveryGhCommand` read the local `validate-blueprint.md` and `mutation-sweep.md` |
| `.claude/scripts/test_command_runbooks.py` | backend-local | reads `CLAUDE.md` and expects the runbooks of the local `validate-blueprint`, `review-branch` and `mutation-sweep` |
| `.claude/scripts/test_dispatch_board.py` | backend-local | `PathTests` judges paths against the checkout's own directories (`src/Services/Ordering`, `tools/quality-sets`, `deploy/rabbitmq`) |
| `.claude/scripts/test_dispatch_run.py` | backend-local | `test_token_keys_are_quality_sets_own` reads `tools/quality-sets/quality_sets.py` |
| `.claude/scripts/test_edit_target_guard.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_gh_issue_create.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_gh_issue_suppresses.py` | backend-local | `WhatSuppressesIsDecidedByCodeNow` reads the local `mutation-sweep.md` |
| `.claude/scripts/test_gh_label_ensure.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_git_argv_guard.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_git_pr_trailer_helpers.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_git_rebase_onto_main.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_git_worktree_detach.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_git_worktree_fork.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_git_worktree_remove.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_harness_denies.py` | backend-local | asserts backend's tree: `git ls-files` must hold `src`, `tests`, `CLAUDE.md`, `Platform.slnx`; reads `dotnet-test.sh` and the local `validate-blueprint.md` and `review-branch.md` |
| `.claude/scripts/test_hint_bound.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_hook_timeouts.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_index_argv_guard.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_index_mcp_root.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_index_query_hint.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_index_search_hint.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_issue_decisions.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_mutation_survivors.py` | backend-local | tests a backend-local script |
| `.claude/scripts/test_pr_for_branch.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_pr_helpers.py` | backend-local | `NoCommandReadsAPullRequestFeedUnfiltered` reads the local `review-branch.md` and `.github/locality-gate/classes.yml` |
| `.claude/scripts/test_refresh_index.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_root_ignore_covers_nested.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_ship_dispatched.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_ship_landing_method.py` | payload | suite of payload code; passes in payload-suites |
| `.claude/scripts/test_sweep_slices.py` | backend-local | `TheRealTree` slices backend's tracked tree and fails on a path no row owns (`harness_sync/__init__.py` here) |
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
| `.github/comment-gate/test_comment_gate.py` | backend-local | `TheShippedTree` asserts backend's tracked tree (over 100 files it reads, over 1000 C# lines); the payload does not carry it |
| `.github/commit-gate/README.md` | payload | gate README |
| `.github/commit-gate/commit_gate.py` | payload | gate code; its invocation stays in each target's `ci.yml` or comes with its workflow (brief) |
| `.github/commit-gate/test_commit_gate.py` | payload | gate suite; passes in payload-suites |
| `.github/issue-form-gate/README.md` | payload | gate README |
| `.github/issue-form-gate/issue_form_gate.py` | payload | gate code; its invocation stays in each target's `ci.yml` or comes with its workflow (brief) |
| `.github/issue-form-gate/test_issue_form_gate.py` | backend-local | `ThisRepositoryTests` reads `docs/change-locality.md`, backend's document, which the payload does not carry |
| `.github/output-gate/README.md` | payload | gate README |
| `.github/output-gate/output_gate.py` | payload | gate code; its invocation stays in each target's `ci.yml` or comes with its workflow (brief) |
| `.github/output-gate/test_output_gate.py` | backend-local | `ThisRepository` reads `Platform.slnx` and backend's `src/` ignore rules, which the payload does not carry |
| `.github/plan-size-gate/README.md` | payload | gate README |
| `.github/plan-size-gate/plan_size_gate.py` | payload | gate code; its invocation stays in each target's `ci.yml` or comes with its workflow (brief) |
| `.github/plan-size-gate/test_plan_size_gate.py` | backend-local | `test_this_repository_s_plans_pass` reads `docs/superpowers/plans/`, which the payload does not carry |
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
