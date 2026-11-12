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
# Where a path a leg suite spells off the rendered tree comes from, when it is not the payload's file of the same name:
# the base renders `settings.json`, the workflow copies backend's draft config in, apply writes the manifest, and
# `harness-local.md` is this repository's own, which apply leaves in place.
RENDERED = {".claude/settings.json": "payload/.harness/settings.base.json",
            ".harness/config.json": "targets/blueprint-backend.config.json",
            ".harness/manifest.json": "harness_sync/apply.py",
            "docs/harness-local.md": "docs/harness-local.md"}
HELPERS = "payload/.claude/scripts"
# On a leg for its fixture, so what it reads is not why it runs there: `TheShippedTree` reads the whole tree off its
# `ROOT`, which `REACH` deliberately does not hold: Linux runs it on every pull request.
FIXTURE_SUITES = {"payload/.github/comment-gate/test_comment_gate.py"}
# A path spelt off the rendered root, or off `.claude/` by `SCRIPTS.parent`, each `/ "part"` after it.
SPELT = re.compile(r'\b(SCRIPTS\.parent\.parent|SCRIPTS\.parents\[1\]|SCRIPTS\.parent|ROOT|REPO|COMMANDS\.parent\.parent)'
                   r'((?:\s*/\s*"[^"]+")+)')
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _code_lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#")]


def _leg_suites() -> list[str]:
    """Each suite a leg runs, by payload path: the whole helpers directory, and each suite a step names by `-p`."""
    code = "\n".join(_code_lines(CI))
    named = re.findall(r'-s (\S+) -p "(test_\w+\.py)"', code)
    whole = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / HELPERS).glob("test_*.py"))
    return whole + [f"payload/{directory}/{suite}" for directory, suite in named]


def _spelt(text: str) -> list[str]:
    """The rendered-tree paths a suite's source spells, `.claude/`-relative ones made root-relative."""
    found = []
    for base, chain in SPELT.findall(text):
        rel = "/".join(re.findall(r'"([^"]+)"', chain))
        found.append(f".claude/{rel}" if base == "SCRIPTS.parent" else rel)
    return found


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

    def test_the_legs_run_the_whole_helpers_suite(self) -> None:
        # The legs once ran four named modules, and frontend's first whole run off Linux failed 142 cases. A step
        # that narrowed the run again with `-p` would pass every case below on the modules it kept.
        code = "\n".join(_code_lines(CI))
        self.assertEqual(1, code.count("python .claude/scripts/shard-harness-suite.py"), code)
        self.assertEqual([], re.findall(r"-s \.claude/scripts", code))
        step = code.split("- name: Test the review helpers", 1)[1].split("- name:", 1)[0]
        self.assertIn("if: matrix.os == 'ubuntu-latest' || steps.reach.outputs.test != 'false'", step)

    def test_every_suite_the_legs_run_is_reached(self) -> None:
        suites = _leg_suites()
        self.assertGreater(len(suites), 40, "the helpers directory went empty, so this checks nothing")
        self.assertLessEqual(FIXTURE_SUITES, set(suites))
        for rel in suites:
            with self.subTest(suite=rel):
                self.assertTrue((ROOT / rel).is_file())
                self.assertTrue(reaches([rel]))

    def test_every_file_a_leg_suite_reads_beside_it_is_reached(self) -> None:
        # The subject is what the suites spell, so a suite that starts reading a file `REACH` misses fails here
        # rather than passing on a pull request whose legs skipped. `review_helpers` is read for its suites.
        sources = [s for s in _leg_suites() if s not in FIXTURE_SUITES] + [f"{HELPERS}/review_helpers.py"]
        spelt = {rel for source in sources for rel in _spelt((ROOT / source).read_text(encoding="utf-8"))}
        self.assertLessEqual({".claude/settings.json", ".harness/config.json", "docs/harness-boundaries.md"}, spelt,
                             "the pattern stopped finding what the suites read")
        for rel in sorted(spelt):
            path = RENDERED.get(rel, f"payload/{rel}")
            with self.subTest(rel=rel):
                self.assertTrue((ROOT / path).exists(), path)
                self.assertTrue(reaches([path]))

    def test_the_pattern_reads_each_base_a_suite_spells(self) -> None:
        # The positive control for the case above: each spelling of the rendered root, and `.claude/` off SCRIPTS.
        text = "\n".join(['SCRIPTS.parent / "settings.json"', 'ROOT / "docs" / "x.md"',
                          'self.ROOT / ".harness" / "c.json"', 'SCRIPTS.parent.parent / ".github" / "w.yml"',
                          'SCRIPTS.parents[1] / "a"', 'REPO / "b"'])
        self.assertEqual([".claude/settings.json", "docs/x.md", ".harness/c.json", ".github/w.yml", "a", "b"],
                         _spelt(text))

    def test_every_leg_step_obeys_the_decision(self) -> None:
        conditions = [line.strip() for line in _code_lines(CI)
                      if re.search(r"matrix\.os (?:!= 'ubuntu-latest'|== '(?:windows|macos)-latest')", line)]
        gated = [line for line in conditions if "steps.reach.outputs.test != 'false'" in line]
        self.assertEqual(len(gated), len(re.findall(r'-p "test_', "\n".join(_code_lines(CI)))))
        self.assertEqual(len(conditions), len(gated) + 1, "only the decision itself is ungated")

    def test_every_leg_runs_the_suite_through_the_shard_runner(self) -> None:
        # The windows and macos legs once ran it serially, which made them the slowest job in the workflow (#402).
        # The step's whole script is read, so a branch on the host that sent one leg elsewhere fails here.
        code = "\n".join(_code_lines(CI))
        step = code.split("- name: Test the review helpers", 1)[1].split("- name:", 1)[0]
        script = [line.strip() for line in step.split("run: |", 1)[1].splitlines() if line.strip()]
        self.assertEqual(["bash --version | head -n 1", "python .claude/scripts/shard-harness-suite.py"], script)

    def test_the_decision_runs_with_the_parent_it_reads(self) -> None:
        code = "\n".join(_code_lines(CI))
        self.assertIn("id: reach", code)
        self.assertIn('python -m harness_sync legs --event "$GITHUB_EVENT_NAME" >> "$GITHUB_OUTPUT"', code)
        self.assertIn("fetch-depth: 2", code.split("  payload-suites:", 1)[1])


if __name__ == "__main__":
    unittest.main()
