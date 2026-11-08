"""The skip on `payload-suites`' windows and macos legs: real merge commits, and the workflow as it is written."""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from harness_sync.legs import REACH, changed_paths, reaches, should_test

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
RENDERED = {"settings.json": "payload/.harness/settings.base.json"}
# On a leg for their fixtures, so what they read is not why they run there: `TheShippedTree` in the comment gate's suite
# reads the whole tree off its `ROOT`, which `REACH` deliberately does not hold: Linux runs it on every pull request.
FIXTURE_SUITES = {"payload/.claude/scripts/test_git_branch_drop.py",
                  "payload/.claude/scripts/test_git_pr_trailer_helpers.py",
                  "payload/.github/comment-gate/test_comment_gate.py"}
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _code_lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#")]


def _leg_suites() -> list[str]:
    """Each leg suite's payload path, from the `-s` and `-p` of the step that runs it."""
    steps = re.findall(r'-s (\S+) -p "(test_\w+\.py)"', "\n".join(_code_lines(CI)))
    return [f"payload/{directory}/{suite}" for directory, suite in steps]


class PullRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.git("init", "-q", "-b", "main")
        self.write("README.md", "base\n")
        self.write("payload/.claude/hooks/guard.py", "base\n")
        self.commit("base")

    def git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, env={**os.environ, **IDENTITY})

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def commit(self, subject: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", subject)

    def merge_branch_holding(self, change) -> None:
        """HEAD becomes what GitHub's merge ref is: a merge whose first parent is the base."""
        self.git("switch", "-q", "-c", "work")
        change()
        self.commit("work")
        self.git("switch", "-q", "main")
        self.write("base-moved.md", "other\n")
        self.commit("base moved")
        self.git("merge", "-q", "--no-ff", "-m", "merge", "work")

    def test_a_docs_pull_request_skips(self) -> None:
        self.merge_branch_holding(lambda: self.write("README.md", "docs\n"))
        self.assertEqual(changed_paths(self.root), ["README.md"])
        self.assertFalse(should_test("pull_request", self.root))

    def test_a_hook_pull_request_tests(self) -> None:
        self.merge_branch_holding(lambda: self.write("payload/.claude/hooks/guard.py", "changed\n"))
        self.assertTrue(should_test("pull_request", self.root))

    def test_a_move_out_of_a_reached_tree_tests(self) -> None:
        self.merge_branch_holding(lambda: self.git("mv", "payload/.claude/hooks/guard.py", "docs-guard.py"))
        self.assertTrue(should_test("pull_request", self.root))

    def test_a_path_git_would_quote_still_reaches(self) -> None:
        self.merge_branch_holding(lambda: self.write("payload/.claude/scripts/тест.py", "new\n"))
        self.assertEqual(changed_paths(self.root), ["payload/.claude/scripts/тест.py"])
        self.assertTrue(should_test("pull_request", self.root))

    def test_a_push_tests_whatever_it_touches(self) -> None:
        self.merge_branch_holding(lambda: self.write("README.md", "docs\n"))
        self.assertTrue(should_test("push", self.root))

    def test_a_head_that_is_not_a_merge_tests(self) -> None:
        self.write("README.md", "docs\n")
        self.commit("not a merge")
        self.assertIsNone(changed_paths(self.root))
        self.assertTrue(should_test("pull_request", self.root))

    def test_a_merge_with_an_empty_diff_tests(self) -> None:
        self.git("switch", "-q", "-c", "work")
        self.git("commit", "-q", "--allow-empty", "-m", "empty")
        self.git("switch", "-q", "main")
        self.git("merge", "-q", "--no-ff", "-m", "merge", "work")
        self.assertEqual(changed_paths(self.root), [])
        self.assertTrue(should_test("pull_request", self.root))


class WhatTheFilterLooksAtTests(unittest.TestCase):
    def test_every_entry_names_a_path_this_tree_has(self) -> None:
        self.assertEqual([entry for entry in REACH if not (ROOT / entry).exists()], [])

    def test_every_suite_the_legs_run_is_reached(self) -> None:
        suites = _leg_suites()
        self.assertTrue(suites, "ci.yml names no suite for the legs")
        self.assertEqual(len(suites), len(re.findall(r'-p "test_', "\n".join(_code_lines(CI)))))
        for rel in suites:
            with self.subTest(suite=rel):
                self.assertTrue((ROOT / rel).is_file())
                self.assertTrue(reaches([rel]))

    def test_every_file_a_leg_suite_reads_beside_it_is_reached(self) -> None:
        for suite in _leg_suites():
            text = (ROOT / suite).read_text(encoding="utf-8")
            chains = re.findall(r'SCRIPTS\.parent((?:\s*/\s*"[^"]+")+)', text)
            self.assertEqual(bool(chains), suite not in FIXTURE_SUITES,
                             f"{suite}: what it spells off SCRIPTS.parent disagrees with FIXTURE_SUITES")
            for chain in chains:
                rel = "/".join(re.findall(r'"([^"]+)"', chain))
                with self.subTest(suite=suite, rel=rel):
                    path = RENDERED.get(rel, f"payload/.claude/{rel}")
                    self.assertTrue((ROOT / path).is_file())
                    self.assertTrue(reaches([path]))

    def test_every_exempt_suite_is_on_a_leg(self) -> None:
        self.assertLessEqual(FIXTURE_SUITES, set(_leg_suites()))

    def test_every_leg_step_obeys_the_decision(self) -> None:
        conditions = [line.strip() for line in _code_lines(CI)
                      if re.search(r"matrix\.os (?:!= 'ubuntu-latest'|== '(?:windows|macos)-latest')", line)]
        gated = [line for line in conditions if "steps.reach.outputs.test != 'false'" in line]
        self.assertEqual(len(gated), len(re.findall(r'-p "test_', "\n".join(_code_lines(CI)))))
        self.assertEqual(len(conditions), len(gated) + 1, "only the decision itself is ungated")

    def test_the_decision_runs_with_the_parent_it_reads(self) -> None:
        code = "\n".join(_code_lines(CI))
        self.assertIn("id: reach", code)
        self.assertIn('python -m harness_sync legs --event "$GITHUB_EVENT_NAME" >> "$GITHUB_OUTPUT"', code)
        self.assertIn("fetch-depth: 2", code.split("  payload-suites:", 1)[1])


if __name__ == "__main__":
    unittest.main()
