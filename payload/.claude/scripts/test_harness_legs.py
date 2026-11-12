"""The skip on a target's off-Linux harness legs: real merge commits, and what the suite beside it reads.

The decision's subject is what the `.claude/scripts` suite reads, so the last class holds the reach to the paths the
suites spell off this root rather than to a list written here.
"""

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from review_helpers import GIT, temp_root

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent.parent
HELPER = SCRIPTS / "harness-legs.py"
# What the helper imports, which a fixture target needs beside it to run it as a workflow does.
SHIPPED_WITH = ("harness-legs.py", "sync_pr.py", "dispatch_board.py")
WORKFLOW = ".github/workflows/ci.yml"
WORKFLOW_REF = f"octo/target/{WORKFLOW}@refs/pull/7/merge"
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
MANIFEST = '{"harness_commit": "0", "files": {"docs/harness/working-rules.md": "0", ".github/x-gate/gate.py": "0"}}\n'
CONFIG = '{"local": ["docs/commands/review-branch.md", ".github/x-gate/test_*_target.py"]}\n'
# A path spelt off the rendered root, or off `.claude/` by `SCRIPTS.parent`, each `/ "part"` after it.
SPELT = re.compile(r'\b(SCRIPTS\.parent\.parent|SCRIPTS\.parents\[1\]|SCRIPTS\.parent|ROOT|REPO|COMMANDS\.parent\.parent)'
                   r'((?:\s*/\s*"[^"]+")+)')


def loaded():
    """The helper, whose filename is not an importable module name."""
    spec = importlib.util.spec_from_file_location("harness_legs", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LEGS = loaded()


class PullRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(GIT, "git is not on PATH, so no merge commit can be built")
        self.root = Path(temp_root(self))
        self.git("init", "-q", "-b", "main")
        self.write("README.md", "base\n")
        self.write(".claude/hooks/guard.py", "base\n")
        self.write(".harness/manifest.json", MANIFEST)
        self.write(".harness/config.json", CONFIG)
        self.commit("base")
        self.base = subprocess.run([GIT, "rev-parse", "HEAD"], cwd=self.root, check=True, capture_output=True,
                                   text=True, encoding="utf-8").stdout.strip()

    def git(self, *args: str) -> None:
        subprocess.run([GIT, *args], cwd=self.root, check=True, capture_output=True, env={**os.environ, **IDENTITY})

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def commit(self, subject: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", subject)

    def merge_branch_holding(self, change) -> None:
        """HEAD becomes what GitHub's merge ref is: a merge whose first parent is the base."""
        self.git("switch", "-q", "-C", "work")
        change()
        self.commit("work")
        self.git("switch", "-q", "main")
        self.write("base-moved.md", "other\n")
        self.commit("base moved")
        self.git("merge", "-q", "--no-ff", "-m", "merge", "work")

    def decides(self, event: str = "pull_request", ref: str | None = WORKFLOW_REF) -> bool:
        return LEGS.should_test(event, self.root, ref)

    def test_a_product_pull_request_skips(self) -> None:
        self.merge_branch_holding(lambda: self.write("src/app.ts", "product\n"))
        self.assertEqual(LEGS.changed_paths(self.root), ["src/app.ts"])
        self.assertFalse(self.decides())

    def test_each_path_the_suite_reads_tests(self) -> None:
        for rel in (".claude/hooks/guard.py", ".claude/scripts/test_x_target.py", ".harness/config.json",
                    "docs/harness-local.md", "docs/harness/working-rules.md", ".github/x-gate/gate.py",
                    "docs/commands/review-branch.md", ".github/x-gate/test_y_target.py", WORKFLOW,
                    ".gitignore", "src/scratch/.gitignore", "src/.gitattributes"):
            with self.subTest(rel=rel):
                self.git("switch", "-q", "main")
                self.git("reset", "-q", "--hard", self.base)
                self.merge_branch_holding(lambda: self.write(rel, "changed\n"))
                self.assertTrue(self.decides())

    def test_the_reach_folds_case_as_a_checkout_may(self) -> None:
        read = LEGS.reach(self.root, WORKFLOW)
        for rel in ("Docs/Harness-Local.md", ".CLAUDE/x.py", "DOCS/HARNESS/WORKING-RULES.MD",
                    "Docs/Commands/Review-Branch.md", ".github/workflows/CI.yml", "src/.GitIgnore"):
            with self.subTest(rel=rel):
                self.assertTrue(LEGS.reaches(rel, *read))

    def test_another_workflow_skips(self) -> None:
        self.merge_branch_holding(lambda: self.write(".github/workflows/e2e.yml", "on: push\n"))
        self.assertFalse(self.decides())

    def test_a_move_out_of_a_reached_tree_tests(self) -> None:
        self.merge_branch_holding(lambda: self.git("mv", ".claude/hooks/guard.py", "guard.py"))
        self.assertTrue(self.decides())

    def test_a_path_git_would_quote_still_reaches(self) -> None:
        self.merge_branch_holding(lambda: self.write(".claude/scripts/тест.py", "new\n"))
        self.assertEqual(LEGS.changed_paths(self.root), [".claude/scripts/тест.py"])
        self.assertTrue(self.decides())

    def test_a_push_tests_whatever_it_touches(self) -> None:
        self.merge_branch_holding(lambda: self.write("src/app.ts", "product\n"))
        self.assertTrue(self.decides("push"))
        self.assertTrue(self.decides(None))

    def test_a_head_that_is_not_a_merge_tests(self) -> None:
        self.write("src/app.ts", "product\n")
        self.commit("not a merge")
        self.assertIsNone(LEGS.changed_paths(self.root))
        self.assertTrue(self.decides())

    def test_a_merge_with_an_empty_diff_tests(self) -> None:
        self.git("switch", "-q", "-c", "work")
        self.git("commit", "-q", "--allow-empty", "-m", "empty")
        self.git("switch", "-q", "main")
        self.git("merge", "-q", "--no-ff", "-m", "merge", "work")
        self.assertEqual(LEGS.changed_paths(self.root), [])
        self.assertTrue(self.decides())

    def test_a_workflow_it_cannot_name_tests(self) -> None:
        self.merge_branch_holding(lambda: self.write("src/app.ts", "product\n"))
        for ref in (None, "", "octo/target/ci.yml@refs/pull/7/merge", f"{WORKFLOW}@refs/pull/7/merge"):
            with self.subTest(ref=ref):
                self.assertTrue(self.decides(ref=ref))

    def test_a_manifest_or_config_it_cannot_read_tests(self) -> None:
        self.merge_branch_holding(lambda: self.write("src/app.ts", "product\n"))
        for rel, text in ((".harness/manifest.json", "not json"), (".harness/manifest.json", '{"files": []}'),
                          (".harness/config.json", '{"local": "docs/**"}'), (".harness/config.json", '{"local": [1]}'),
                          (".harness/config.json", "[]")):
            with self.subTest(rel=rel, text=text):
                original = (self.root / rel).read_text(encoding="utf-8")
                self.write(rel, text)
                self.assertTrue(self.decides())
                self.write(rel, original)
        (self.root / ".harness" / "manifest.json").unlink()
        self.assertTrue(self.decides())

    def test_the_helper_runs_as_a_target_workflow_runs_it(self) -> None:
        # From the target's own `.claude/scripts`, with only GitHub's environment: its imports resolve beside it.
        for name in SHIPPED_WITH:
            self.write(f".claude/scripts/{name}", (SCRIPTS / name).read_text(encoding="utf-8"))
        self.commit("the helper")
        self.merge_branch_holding(lambda: self.write("src/app.ts", "product\n"))
        helper = self.root / ".claude" / "scripts" / "harness-legs.py"
        for event, expected in (("pull_request", "test=false\n"), ("push", "test=true\n")):
            with self.subTest(event=event):
                env = {**os.environ, "GITHUB_EVENT_NAME": event, "GITHUB_WORKFLOW_REF": WORKFLOW_REF}
                done = subprocess.run([sys.executable, str(helper)], cwd=self.root, capture_output=True, text=True,
                                      encoding="utf-8", env=env, check=False)
                self.assertEqual((0, expected), (done.returncode, done.stdout), done.stderr)
        done = subprocess.run([sys.executable, str(helper), "--event", "push"], capture_output=True, text=True,
                              encoding="utf-8", check=False)
        self.assertEqual(2, done.returncode)
        self.assertEqual("", done.stdout)


class WorkflowRefTests(unittest.TestCase):
    def test_the_path_is_read_out_of_the_ref(self) -> None:
        for ref, path in ((WORKFLOW_REF, WORKFLOW),
                          ("o/r/.github/workflows/harness.yaml@refs/heads/main", ".github/workflows/harness.yaml"),
                          ("o/r/.github/workflows/sub/ci.yml@refs/pull/1/merge", ".github/workflows/sub/ci.yml"),
                          ("o/r/.github/workflows/ci.yml", None), ("o/r/ci.yml@refs/pull/1/merge", None),
                          ("o/r/docs/ci.yml@refs/pull/1/merge", None), (None, None)):
            with self.subTest(ref=ref):
                self.assertEqual(path, LEGS.workflow_path(ref))


def _spelt(text: str) -> list[str]:
    """The root-relative paths a suite's source spells, `.claude/`-relative ones made root-relative."""
    found = []
    for base, chain in SPELT.findall(text):
        rel = "/".join(re.findall(r'"([^"]+)"', chain))
        found.append(f".claude/{rel}" if base == "SCRIPTS.parent" else rel)
    return found


def _files(rel: str) -> list[str]:
    """`rel` if it is a file here, every file under it if it is a directory, and nothing if it is neither."""
    path = ROOT / rel
    if path.is_file():
        return [rel]
    return [p.relative_to(ROOT).as_posix() for p in sorted(path.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts] if path.is_dir() else []


class WhatTheDecisionLooksAtTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reach = LEGS.reach(ROOT, WORKFLOW)
        self.assertIsNotNone(self.reach, "this root's manifest or config does not read, so nothing here is judged")

    def test_every_suite_beside_it_is_reached(self) -> None:
        suites = sorted(p.relative_to(ROOT).as_posix() for p in SCRIPTS.glob("test_*.py"))
        self.assertGreater(len(suites), 40, "the helpers directory went empty, so this checks nothing")
        for rel in suites:
            with self.subTest(suite=rel):
                self.assertTrue(LEGS.reaches(rel, *self.reach))

    def test_every_file_a_suite_reads_off_the_root_is_reached(self) -> None:
        # The subject is what the suites spell, so a suite that starts reading a file the reach misses fails here
        # rather than passing on a pull request whose legs skipped. `review_helpers` is read for its suites.
        sources = [*SCRIPTS.glob("test_*.py"), SCRIPTS / "review_helpers.py"]
        spelt = {rel for source in sources for rel in _spelt(source.read_text(encoding="utf-8"))}
        self.assertLessEqual({".claude/settings.json", ".harness/config.json", "docs/harness-boundaries.md"}, spelt,
                             "the pattern stopped finding what the suites read")
        files = sorted({rel for spelling in spelt for rel in _files(spelling)})
        self.assertIn("docs/harness-local.md", files)
        for rel in files:
            with self.subTest(rel=rel):
                self.assertTrue(LEGS.reaches(rel, *self.reach))

    def test_the_pattern_reads_each_base_a_suite_spells(self) -> None:
        # The positive control for the case above: each spelling of the root, and `.claude/` off SCRIPTS. Built from
        # parts, so `harness_sync/tests/test_legs.py`, which scans this file the same way, reads no path in it.
        spellings = [("SCRIPTS.parent", "settings.json"), ("ROOT", "docs", "x.md"), ("self.ROOT", ".harness", "c.json"),
                     ("SCRIPTS.parent.parent", ".github", "w.yml"), ("SCRIPTS.parents[1]", "a"), ("REPO", "b")]
        text = "\n".join(" / ".join([base, *(f'"{part}"' for part in parts)]) for base, *parts in spellings)
        self.assertEqual([".claude/settings.json", "docs/x.md", ".harness/c.json", ".github/w.yml", "a", "b"],
                         _spelt(text))

    def test_a_product_path_is_not_reached(self) -> None:
        # The negative control: a reach that took everything would pass both cases above and skip nothing.
        for rel in ("src/app.ts", "package.json", ".github/workflows/e2e-never-a-harness-leg.yml"):
            with self.subTest(rel=rel):
                self.assertFalse(LEGS.reaches(rel, *self.reach))


if __name__ == "__main__":
    unittest.main()
