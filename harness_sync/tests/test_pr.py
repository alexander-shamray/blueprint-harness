"""Tests for the sync pull request, over real git repositories with a bare origin and a fake `gh`."""

import contextlib
import importlib.util
import io
import json
import re
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from harness_sync.__main__ import main
from harness_sync.apply import apply
from harness_sync.manifest import Manifest
from harness_sync.pr import SyncError, open_sync_pr

PAYLOAD_GATES = Path(__file__).resolve().parents[2] / "payload/.github"
RUN_URL = "https://github.com/alexander-shamray/blueprint-harness/actions/runs/123"
BASE = {"env": {}, "permissions": {"allow": [], "deny": []}, "hooks": {}}
CONFIG = {"repo": "o/r", "task_list": ".todo/r.md"}
# The test repositories commit under an identity of their own, so the sync commit's author is the tool's or nobody's.
SEED = ("-c", "user.name=Seed", "-c", "user.email=seed@example.invalid", "-c", "commit.gpgsign=false")


def _load(name: str, rel: str):
    """The gates ship in the payload and import nothing from here, so they are loaded by path."""
    spec = importlib.util.spec_from_file_location(name, PAYLOAD_GATES / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, encoding="utf-8", check=False)
    if done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {done.stderr}")
    return done.stdout


class FakeGh:
    """Answers the `gh pr` calls the sync makes; a created pull request joins the open list, as on GitHub."""

    def __init__(self, origin: Path, open_prs: list[dict] | None = None, number: int = 42, fail_after_create=False,
                 fail_on_list=False):
        self.origin = origin
        self.open_prs = list(open_prs or [])
        self.number = number
        self.fail_after_create = fail_after_create
        self.fail_on_list = fail_on_list
        self.calls: list[list[str]] = []
        self.created: dict[str, str] = {}
        self.tip_at_create: str | None = None
        self.tip_at_close: list[str] = []

    def _tip(self, branch: str) -> str:
        return git(self.origin, "rev-parse", f"refs/heads/{branch}").strip()

    def run(self, args: list[str]) -> str:
        self.calls.append(list(args))
        if args[:2] == ["pr", "list"]:
            if self.fail_on_list:
                raise SyncError("gh pr list failed: simulated")
            return json.dumps(self.open_prs)
        if args[:2] == ["pr", "create"]:
            opts = dict(zip(args[2::2], args[3::2]))
            self.created = opts
            self.tip_at_create = self._tip(opts["--head"])
            self.open_prs.append({"number": self.number, "headRefName": opts["--head"], "isCrossRepository": False})
            if self.fail_after_create:
                raise SyncError("simulated failure after the pull request was created")
            return f"https://github.com/o/r/pull/{self.number}\n"
        if args[:2] == ["pr", "close"]:
            if "--head" in self.created:
                self.tip_at_close.append(self._tip(self.created["--head"]))
            self.open_prs = [pr for pr in self.open_prs if str(pr["number"]) != args[2]]
            return ""
        raise AssertionError(f"unexpected gh call {args}")

    def closes(self) -> list[list[str]]:
        return [call for call in self.calls if call[:2] == ["pr", "close"]]


class SyncTestCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.harness, self.origin, self.target = root / "harness", root / "origin.git", root / "target"
        # The harness checkout orders commits, so it is a real repository: old, then new on top of it.
        git(root, "init", "-q", "-b", "main", str(self.harness))
        self.old = self.harness_commit("harness: old")
        self.new = self.harness_commit("harness: new")
        self.payload = self.harness / "payload"
        self.put(self.payload, ".harness/settings.base.json", json.dumps(BASE))
        self.put(self.payload, "docs/a.md", "a\n")
        self.put(self.payload, "docs/b.md", "b\n")
        self.put(self.payload, "docs/c.md", "c\n")
        git(root, "init", "-q", "--bare", "-b", "main", str(self.origin))
        git(root, "init", "-q", "-b", "main", str(self.target))
        git(self.target, "config", "core.autocrlf", "false")
        git(self.target, "remote", "add", "origin", str(self.origin))
        self.put(self.target, ".harness/config.json", json.dumps(CONFIG))
        self.put(self.target, "README.md", "target\n")

    def harness_commit(self, message: str) -> str:
        git(self.harness, *SEED, "commit", "-q", "--allow-empty", "-m", message)
        return git(self.harness, "rev-parse", "HEAD").strip()

    def side_commit(self, branch: str) -> str:
        """A commit ahead of main's tip but off main, on `branch`; the harness stays on main."""
        git(self.harness, "checkout", "-q", "-b", branch)
        sha = self.harness_commit(f"harness: {branch}")
        git(self.harness, "checkout", "-q", "main")
        return sha

    def put(self, root: Path, rel: str, text: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))

    def seed(self, synced: bool = True, at: str | None = None) -> None:
        """The target's main: onboarded and, when synced, holding the payload under a manifest naming `at`."""
        if synced:
            apply(self.payload, self.target, at or self.old)
        git(self.target, "add", "-A")
        git(self.target, *SEED, "commit", "-q", "-m", "chore: seed")
        git(self.target, "push", "-q", "origin", "main")

    def sync(self, gh: FakeGh, commit: str | None = None, run_url: str | None = RUN_URL):
        return open_sync_pr(self.target, commit or self.new, gh, payload=self.payload, run_url=run_url)

    def branch(self, commit: str | None = None) -> str:
        return f"chore/harness-sync-{(commit or self.new)[:7]}"

    def remote_tip(self, branch: str) -> str:
        return git(self.origin, "rev-parse", f"refs/heads/{branch}").strip()

    def remote_branches(self) -> list[str]:
        return git(self.origin, "for-each-ref", "--format=%(refname:short)", "refs/heads").split()

    def message(self, sha: str) -> str:
        return git(self.origin, "show", "-s", "--format=%B", sha)

    def trailers(self, sha: str) -> list[str]:
        out = subprocess.run(
            ["git", "interpret-trailers", "--parse"],
            input=self.message(sha), capture_output=True, encoding="utf-8", check=True,
        ).stdout
        return out.splitlines()

    def change_payload(self) -> None:
        """b changes, c is dropped, a is left as it was."""
        self.put(self.payload, "docs/b.md", "b, revised\n")
        (self.payload / "docs/c.md").unlink()

    def assert_clean(self) -> None:
        self.assertEqual(git(self.target, "status", "--porcelain", "--untracked-files=all"), "")


class NothingToSyncTests(SyncTestCase):
    def test_nothing_to_sync_opens_nothing(self) -> None:
        # Review Focus 5: the payload is what main already holds, so only the manifest's commit would move.
        self.seed()
        gh = FakeGh(self.origin)
        outcome = self.sync(gh)
        self.assertEqual(outcome.state, "current")
        self.assertIsNone(outcome.pr)
        self.assertEqual(outcome.superseded, [])
        self.assertIn(self.old[:7], outcome.reason)
        # It reads the open pull requests to find stale syncs (R31), and nothing more.
        self.assertEqual([call[:2] for call in gh.calls], [["pr", "list"]])
        self.assert_clean()
        self.assertEqual(Manifest.read(self.target / ".harness/manifest.json").harness_commit, self.old)
        self.assertEqual(self.remote_branches(), ["main"])
        self.assertEqual(git(self.target, "branch", "--show-current").strip(), "main")

    def test_current_closes_the_stale_syncs(self) -> None:
        # R31: a target already current makes every open sync stale; a fork's look-alike is not ours to close.
        self.seed()
        gh = FakeGh(self.origin, open_prs=[
            {"number": 5, "headRefName": self.branch(self.old), "isCrossRepository": False},
            {"number": 6, "headRefName": "chore/harness-sync-fedcba9", "isCrossRepository": False},
            {"number": 8, "headRefName": "chore/harness-sync-1111111", "isCrossRepository": True},
            {"number": 9, "headRefName": "docs/unrelated", "isCrossRepository": False},
            {"number": 10, "headRefName": "chore/harness-sync-notes", "isCrossRepository": False},
        ])
        outcome = self.sync(gh)
        self.assertEqual((outcome.state, outcome.pr, outcome.superseded), ("current", None, [5, 6]))
        closes = gh.closes()
        self.assertEqual([call[2] for call in closes], ["5", "6"])
        for call in closes:
            self.assertIn("--delete-branch", call)
            comment = call[call.index("--comment") + 1]
            self.assertIn(f"blueprint-harness {self.new[:7]} leaves this target current; this sync is stale", comment)
        self.assertFalse(any(call[:2] == ["pr", "create"] for call in gh.calls))
        self.assert_clean()

    def test_downgrade_is_refused(self) -> None:
        # R30: the target already holds the newer sync, so a run carrying the older commit opens nothing.
        self.seed(at=self.new)
        self.change_payload()
        gh = FakeGh(self.origin)
        with self.assertRaisesRegex(SyncError, "only moves forward"):
            self.sync(gh, self.old)
        self.assertEqual(gh.calls, [])
        self.assert_clean()
        self.assertEqual(self.remote_branches(), ["main"])

    def test_commit_outside_the_harness_history_is_refused(self) -> None:
        self.seed()
        self.change_payload()
        with self.assertRaisesRegex(SyncError, "not in the harness checkout"):
            self.sync(FakeGh(self.origin), "f" * 40)
        self.assert_clean()

    def test_target_without_config_is_not_onboarded(self) -> None:
        (self.target / ".harness/config.json").unlink()
        self.seed(synced=False)
        gh = FakeGh(self.origin)
        outcome = self.sync(gh)
        self.assertEqual(outcome.state, "current")
        self.assertIsNone(outcome.pr)
        self.assertEqual(outcome.superseded, [])
        self.assertIn("not onboarded", outcome.reason)
        self.assertEqual(gh.calls, [])
        self.assert_clean()
        self.assertEqual(self.remote_branches(), ["main"])

    def test_first_sync_opens_even_when_every_file_is_already_in_place(self) -> None:
        # A first manifest is the drift gate's whole input, so its arrival alone is worth a pull request.
        apply(self.payload, self.target, self.old)
        (self.target / ".harness/manifest.json").unlink()
        self.seed(synced=False)
        gh = FakeGh(self.origin)
        outcome = self.sync(gh)
        self.assertEqual((outcome.state, outcome.pr), ("opened", 42))
        row = re.search(r"^\| Touch set \| (.*) \|$", gh.created["--body"], re.MULTILINE)
        self.assertEqual(row.group(1), "`.harness/manifest.json`")

    def test_dirty_checkout_is_refused(self) -> None:
        self.seed()
        self.change_payload()
        self.put(self.target, "stray.txt", "x\n")
        with self.assertRaises(SyncError):
            self.sync(FakeGh(self.origin))


class OpenedTests(SyncTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.seed()
        self.base_sha = git(self.target, "rev-parse", "HEAD").strip()
        self.change_payload()

    def test_opened_pr_body_has_class_touch_set_closes(self) -> None:
        gh = FakeGh(self.origin)
        outcome = self.sync(gh)
        self.assertEqual(outcome.state, "opened")
        self.assertEqual(outcome.pr, 42)
        body = gh.created["--body"]
        self.assertEqual(gh.created["--title"], f"chore(harness): sync to blueprint-harness {self.new[:7]}")
        self.assertEqual(gh.created["--head"], self.branch())
        self.assertEqual(gh.created["--base"], "main")
        self.assertIn("| | |\n|---|---|\n| Class | D |\n| Touch set | ", body)
        self.assertIn("\n| Closes | — |\n", body)
        self.assertIn(f"https://github.com/alexander-shamray/blueprint-harness/commit/{self.new}", body)
        self.assertIn("## What changed", body)
        self.assertIn("`docs/b.md`", body.split("## What changed", 1)[1])
        self.assertIn("`docs/c.md`", body.split("## What changed", 1)[1])
        # The run that opened it, not a session: no session writes a sync.
        self.assertTrue(body.endswith(f"\n\nOpened by the blueprint-harness sync workflow, in run {RUN_URL}.\n"))
        self.assertNotIn("claude.ai/code/session", body)

    def test_body_without_a_run_names_the_workflow_alone(self) -> None:
        gh = FakeGh(self.origin)
        self.sync(gh, run_url=None)
        self.assertTrue(gh.created["--body"].endswith("\n\nOpened by the blueprint-harness sync workflow.\n"))
        self.assertNotIn("actions/runs", gh.created["--body"])

    def test_touch_set_lists_only_changed_paths(self) -> None:
        gh = FakeGh(self.origin)
        self.sync(gh)
        row = re.search(r"^\| Touch set \| (.*) \|$", gh.created["--body"], re.MULTILINE)
        self.assertIsNotNone(row)
        self.assertEqual(row.group(1), "`.harness/manifest.json`, `docs/b.md`, `docs/c.md`")

    def test_trailer_added_after_create(self) -> None:
        gh = FakeGh(self.origin)
        self.sync(gh)
        tip = self.remote_tip(self.branch())
        # What `gh pr create` saw had no trailer yet; what origin holds now names the pull request, last.
        self.assertFalse(any(line.startswith("PR:") for line in self.trailers(gh.tip_at_create)))
        self.assertNotEqual(tip, gh.tip_at_create)
        self.assertEqual(self.trailers(tip)[-1], "PR: #42")
        tree = git(self.origin, "rev-parse", f"{tip}^{{tree}}")
        self.assertEqual(tree, git(self.origin, "rev-parse", f"{gh.tip_at_create}^{{tree}}"))
        self.assertEqual(git(self.origin, "rev-parse", f"{tip}^").strip(), self.base_sha)
        self.assertEqual(git(self.origin, "rev-parse", "refs/heads/main").strip(), self.base_sha)

    def test_commit_carries_what_apply_changed_and_nothing_else(self) -> None:
        self.sync(FakeGh(self.origin))
        tip = self.remote_tip(self.branch())
        changed = git(self.origin, "diff", "--name-status", self.base_sha, tip).splitlines()
        self.assertEqual(changed, ["M\t.harness/manifest.json", "M\tdocs/b.md", "D\tdocs/c.md"])
        author = git(self.origin, "show", "-s", "--format=%an <%ae>|%cn <%ce>", tip).strip()
        bot = "github-actions[bot] <41898+github-actions[bot]@users.noreply.github.com>"
        self.assertEqual(author, f"{bot}|{bot}")
        self.assertIn(self.new, self.message(tip))
        # The checkout is left as it was found: on its branch, clean, the sync branch pushed rather than held.
        self.assert_clean()
        self.assertEqual(git(self.target, "branch", "--show-current").strip(), "main")

    def test_older_sync_pr_closed(self) -> None:
        # Review Focus 4: the older sync and nothing else; a fork's look-alike branch is not ours to close.
        gh = FakeGh(self.origin, open_prs=[
            {"number": 9, "headRefName": "chore/harness-sync-0123456", "isCrossRepository": False},
            {"number": 5, "headRefName": "chore/harness-sync-fedcba9", "isCrossRepository": False},
            {"number": 7, "headRefName": "feat(x)/unrelated", "isCrossRepository": False},
            {"number": 8, "headRefName": "chore/harness-sync-1111111", "isCrossRepository": True},
        ])
        outcome = self.sync(gh)
        self.assertEqual(outcome.superseded, [5, 9])
        closes = gh.closes()
        self.assertEqual(sorted(call[2] for call in closes), ["5", "9"])
        for call in closes:
            comment = call[call.index("--comment") + 1]
            self.assertIn("Superseded by #42", comment)
            self.assertIn(self.new, comment)
            self.assertIn("--delete-branch", call)
        # Closed only once the new pull request exists and its trailer is on origin.
        creates = [i for i, call in enumerate(gh.calls) if call[:2] == ["pr", "create"]]
        self.assertLess(creates[0], gh.calls.index(closes[0]))
        for tip in gh.tip_at_close:
            self.assertEqual(self.trailers(tip)[-1], "PR: #42")

    def test_rerun_finds_its_own_pr_and_opens_no_second(self) -> None:
        gh = FakeGh(self.origin)
        self.sync(gh)
        tip = self.remote_tip(self.branch())
        gh.open_prs.append({"number": 3, "headRefName": "chore/harness-sync-0000000", "isCrossRepository": False})
        outcome = self.sync(gh)
        self.assertEqual((outcome.state, outcome.pr, outcome.superseded), ("opened", 42, [3]))
        self.assertEqual(sum(call[:2] == ["pr", "create"] for call in gh.calls), 1)
        self.assertEqual(self.remote_tip(self.branch()), tip)
        self.assert_clean()

    def test_rerun_after_a_failure_past_create_adds_the_missing_trailer(self) -> None:
        with self.assertRaises(SyncError):
            self.sync(FakeGh(self.origin, fail_after_create=True))
        bare = self.remote_tip(self.branch())
        self.assertFalse(any(line.startswith("PR:") for line in self.trailers(bare)))
        # A rerun in CI starts from a fresh checkout of main.
        git(self.target, "checkout", "-q", "main")
        gh = FakeGh(self.origin, open_prs=[
            {"number": 42, "headRefName": self.branch(), "isCrossRepository": False},
        ])
        outcome = self.sync(gh)
        self.assertEqual((outcome.state, outcome.pr), ("opened", 42))
        self.assertEqual(self.trailers(self.remote_tip(self.branch()))[-1], "PR: #42")

    def test_old_run_syncs_the_tip_and_reuses_the_newer_pr(self) -> None:
        # R30: a queued or rerun old run takes harness main's tip at run time, as sync.yml does, so it finds the
        # newer sync already open and reuses it rather than replacing it with its own older commit.
        gh = FakeGh(self.origin)
        self.sync(gh, self.new)
        tip = self.remote_tip(self.branch())
        run_time_tip = git(self.harness, "rev-parse", "HEAD").strip()
        outcome = self.sync(gh, run_time_tip)
        self.assertEqual((outcome.state, outcome.pr, outcome.superseded), ("opened", 42, []))
        self.assertEqual(sum(call[:2] == ["pr", "create"] for call in gh.calls), 1)
        self.assertEqual(gh.closes(), [])
        self.assertEqual(self.remote_tip(self.branch()), tip)

    def test_older_commit_never_closes_a_newer_sync(self) -> None:
        # R30, belt and braces: handed the older commit outright, the run refuses rather than superseding #42.
        gh = FakeGh(self.origin)
        self.sync(gh, self.new)
        calls = len(gh.calls)
        with self.assertRaisesRegex(SyncError, "#42 already syncs"):
            self.sync(gh, self.old)
        self.assertEqual([call[:2] for call in gh.calls[calls:]], [["pr", "list"]])
        self.assertEqual(self.remote_branches(), ["chore/harness-sync-" + self.new[:7], "main"])
        self.assert_clean()

    def test_look_alike_heads_are_neither_closed_nor_compared(self) -> None:
        # A person's branch under the prefix is not a sync: never closed, its suffix never read as a revision, even
        # where that suffix names a harness branch ahead of the tip and would otherwise wedge every run.
        self.side_commit("feature")
        gh = FakeGh(self.origin, open_prs=[
            {"number": 10, "headRefName": "chore/harness-sync-notes", "isCrossRepository": False},
            {"number": 11, "headRefName": "chore/harness-sync-feature", "isCrossRepository": False},
            {"number": 12, "headRefName": "chore/harness-sync-origin/feature", "isCrossRepository": False},
            {"number": 13, "headRefName": "chore/harness-sync-abc1234x", "isCrossRepository": False},
        ])
        outcome = self.sync(gh)
        self.assertEqual((outcome.state, outcome.pr, outcome.superseded), ("opened", 42, []))
        self.assertEqual(gh.closes(), [])

    def test_branch_name_suffix_does_not_wedge(self) -> None:
        # Seven hex characters that name a harness branch ahead of the tip, off main: stale, not newer.
        self.side_commit("abcdef0")
        gh = FakeGh(self.origin, open_prs=[
            {"number": 14, "headRefName": "chore/harness-sync-abcdef0", "isCrossRepository": False},
        ])
        outcome = self.sync(gh)
        self.assertEqual((outcome.state, outcome.pr, outcome.superseded), ("opened", 42, [14]))

    def test_off_main_short_sha_ahead_of_the_tip_is_stale(self) -> None:
        ahead = self.side_commit("side")
        gh = FakeGh(self.origin, open_prs=[
            {"number": 15, "headRefName": self.branch(ahead), "isCrossRepository": False},
        ])
        outcome = self.sync(gh)
        self.assertEqual((outcome.state, outcome.pr, outcome.superseded), ("opened", 42, [15]))

    def test_failed_pr_list_hands_the_checkout_back_clean(self) -> None:
        with self.assertRaisesRegex(SyncError, "simulated"):
            self.sync(FakeGh(self.origin, fail_on_list=True))
        self.assert_clean()
        self.assertEqual(git(self.target, "branch", "--show-current").strip(), "main")
        self.assertEqual(self.remote_branches(), ["main"])

    def test_push_replaces_a_leftover_branch_with_no_pr(self) -> None:
        # A run that pushed and died before `gh pr create` leaves the branch behind and no pull request.
        git(self.target, "push", "-q", "origin", f"main:refs/heads/{self.branch()}")
        outcome = self.sync(FakeGh(self.origin))
        self.assertEqual(outcome.pr, 42)
        self.assertEqual(self.trailers(self.remote_tip(self.branch()))[-1], "PR: #42")


class GateAcceptanceTests(SyncTestCase):
    """The sync's title, body and commit pass the target's own gates, as the payload ships them (spec 5.3)."""

    def setUp(self) -> None:
        super().setUp()
        self.seed()
        self.base_sha = git(self.target, "rev-parse", "HEAD").strip()
        self.change_payload()
        self.gh = FakeGh(self.origin)
        self.sync(self.gh)
        self.tip = self.remote_tip(self.branch())

    def test_body_passes_the_closure_gate(self) -> None:
        gate = _load("closure_gate_under_test", "closure-gate/closure_gate.py")
        headline, _, rest = self.message(self.tip).partition("\n")
        payload = {
            "number": 42,
            "url": "https://github.com/o/r/pull/42",
            "body": self.gh.created["--body"],
            "commits": [{"oid": self.tip, "messageHeadline": headline, "messageBody": rest.strip("\n")}],
            "closingIssuesReferences": [],
            "headRefOid": self.tip,
        }
        self.assertEqual(gate.check(payload), [])

    def test_commit_passes_the_commit_gate(self) -> None:
        gate = _load("commit_gate_under_test", "commit-gate/commit_gate.py")
        git(self.target, "fetch", "-q", "origin", self.branch())
        # The gate's own reader runs git in the working directory, as its workflow runs it.
        with contextlib.chdir(self.target):
            commits = gate.collect(self.base_sha, self.tip)
        self.assertEqual(len(commits), 1)
        self.assertEqual(gate.check(42, commits), [])


class CliTests(SyncTestCase):
    def run_main(self, *args: str, gh: FakeGh | None = None) -> tuple[int, str, str]:
        # The real GhCli would reach GitHub; the CLI is tested for what it passes and prints.
        self.gh = gh or FakeGh(self.origin)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("harness_sync.__main__.GhCli", return_value=self.gh) as self.cli:
            with redirect_stdout(out), redirect_stderr(err):
                code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def argv(self, commit: str | None = None) -> list[str]:
        return ["open-pr", "--payload", str(self.payload), "--target", str(self.target), "--commit",
                commit or self.new]

    def test_not_onboarded_prints_one_line_and_exits_0(self) -> None:
        (self.target / ".harness/config.json").unlink()
        self.seed(synced=False)
        code, out, _ = self.run_main(*self.argv())
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 1)
        self.assertIn("not onboarded", out)
        self.assertIn(".harness/config.json", out)

    def test_current_prints_one_line_and_exits_0(self) -> None:
        self.seed()
        code, out, _ = self.run_main(*self.argv())
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 1)
        self.assertIn("current", out)
        self.assertIn(self.old[:7], out)
        self.assert_clean()

    def test_opened_prints_one_line(self) -> None:
        self.seed()
        self.change_payload()
        gh = FakeGh(self.origin, open_prs=[
            {"number": 5, "headRefName": "chore/harness-sync-fedcba9", "isCrossRepository": False},
        ])
        code, out, _ = self.run_main(*self.argv(), "--repo", "o/r", "--run-url", RUN_URL, gh=gh)
        self.assertEqual(code, 0)
        self.cli.assert_called_once_with(self.target, "o/r")
        self.assertEqual(len(out.splitlines()), 1)
        self.assertIn("#42", out)
        self.assertIn("#5", out)
        self.assertIn(f"in run {RUN_URL}.", gh.created["--body"])

    def test_current_reports_the_stale_syncs_it_closed(self) -> None:
        self.seed()
        gh = FakeGh(self.origin, open_prs=[
            {"number": 5, "headRefName": "chore/harness-sync-fedcba9", "isCrossRepository": False},
        ])
        code, out, _ = self.run_main(*self.argv(), gh=gh)
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 1)
        self.assertIn("closed stale #5", out)

    def test_downgrade_exits_non_zero(self) -> None:
        self.seed(at=self.new)
        self.change_payload()
        code, _, err = self.run_main(*self.argv(self.old), "--harness", str(self.harness))
        self.assertNotEqual(code, 0)
        self.assertIn("only moves forward", err)
        self.assertEqual(self.gh.calls, [])

    def test_apply_error_exits_non_zero(self) -> None:
        self.seed()
        self.put(self.payload, ".claude/settings.json", "{}")
        code, _, err = self.run_main(*self.argv())
        self.assertNotEqual(code, 0)
        self.assertIn(".claude/settings.json", err)

    def test_config_error_exits_non_zero(self) -> None:
        self.put(self.target, ".harness/config.json", "{")
        self.seed(synced=False)
        code, _, err = self.run_main(*self.argv())
        self.assertNotEqual(code, 0)
        self.assertIn("config.json", err)


if __name__ == "__main__":
    unittest.main()
