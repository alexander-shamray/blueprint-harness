"""The payload's sync_pr.py cannot import harness_sync, so what it reads of pr.py's output is held equal here."""

import importlib.util
import re
import sys
import unittest
from pathlib import Path

from harness_sync import apply as apply_mod
from harness_sync import pr

SCRIPTS = Path(__file__).resolve().parents[2] / "payload/.claude/scripts"
RUN_URL = "https://github.com/alexander-shamray/blueprint-harness/actions/runs/123"
COMMIT = "1234567890abcdef1234567890abcdef12345678"


def _load():
    # The script imports its sibling dispatch_board, so its directory is on the path while it loads.
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location("sync_pr_under_test", SCRIPTS / "sync_pr.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS))
    return module


class SyncPrConstants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = _load()

    def test_the_payload_reads_the_sync_shape_pr_py_writes(self):
        self.assertEqual(pr.HARNESS, self.script.HARNESS_REPO)
        self.assertEqual(pr.FOOTER, self.script.FOOTER)
        self.assertEqual(pr.SYNC_HEAD.pattern, self.script.SYNC_HEAD.pattern)
        self.assertTrue(self.script.SYNC_HEAD.fullmatch(f"{pr.PREFIX}{COMMIT[:7]}"))
        for run_url in (None, RUN_URL):
            body = pr.pr_body(COMMIT, ["docs/a.md"], ["docs/c.md"], run_url)
            self.assertTrue(self.script.is_sync_body(body), run_url)
            self.assertFalse(self.script.is_sync_body(body.replace(pr.FOOTER, "Opened by someone else")), run_url)
            self.assertFalse(self.script.is_sync_body(body + "trailing line\n"), run_url)

    def test_the_worktree_helper_takes_the_sync_head_and_no_other(self):
        # The helper is bash, so its pattern is read out of its text and held to pr.py's, not re-spelled.
        text = (SCRIPTS / "git-worktree-sync.sh").read_text(encoding="utf-8")
        found = re.findall(r'^\[\[ "\$branch" =~ \^(\S+)\$ \]\]', text, re.MULTILINE)
        self.assertEqual([pr.SYNC_HEAD.pattern], found)
        self.assertFalse(pr.SYNC_HEAD.pattern.startswith("^") or pr.SYNC_HEAD.pattern.endswith("$"))

    def test_the_branch_drop_takes_a_closed_pull_requests_branch_only_for_the_sync_head(self):
        text = (SCRIPTS / "git-branch-drop.sh").read_text(encoding="utf-8")
        self.assertEqual([pr.SYNC_HEAD.pattern], re.findall(r'\[\[ "\$branch" =~ \^(chore/\S+)\$ \]\]', text))

    def test_the_glob_matcher_is_apply_s(self):
        cases = [("a.md", "a.md"), ("*.md", "d/a.md"), ("**/*.md", "a.md"), ("d/**", "d/e/f"), ("d/**", "d"),
                 ("d/?.md", "d/ab.md"), ("(x)+", "(x)+"), ("a.b", "aXb")]
        for glob, path in cases:
            with self.subTest(glob=glob, path=path):
                self.assertEqual(apply_mod.glob_match(glob, path), self.script.glob_match(glob, path))

    def test_the_pr_body_names_the_diff_the_review_reads(self):
        body = pr.pr_body(COMMIT, [], [], None)
        flat = re.sub(r"\s+", " ", body)
        self.assertIn("`sync_pr.py review-diff` writes what a round should be given, leaving out managed content "
                      "but for the settings diff", flat)
        self.assertIn("A sync is taken by `/dispatch`, or by `/ship sync #<n>`.", flat)


if __name__ == "__main__":
    unittest.main()
