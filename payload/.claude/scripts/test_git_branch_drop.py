"""git-branch-drop.sh: a local branch deleted only once it has landed.

The helper deletes a branch when `pr-for-branch.sh` reports a pull request
for it MERGED into `main` at the branch's own tip, and the branch is checked
out nowhere. The repositories are real; GitHub is a `gh` shim on PATH that
answers the two reads `pr-for-branch.sh` makes, so the rows go through that
helper's own `jq` filter as they would in a session. Each refusal is paired
with the drop succeeding on the same fixture, so a refusal is not the helper
failing for another reason.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from review_helpers import SCRIPTS, setUpModule, run_bash as _run_bash  # noqa: F401

HELPER = SCRIPTS / "git-branch-drop.sh"
OWNER = "acme/widgets"

SPELLINGS = ("main", "Main", "MAIN", "heads/main", "refs/heads/main",
             "origin/main", "refs/remotes/origin/main")


def run_bash(script, **env):
    """`review_helpers.run_bash` with the caller's git configuration shut out."""
    return _run_bash("set -eu\n" + script,
                     GIT_CONFIG_GLOBAL="/dev/null",
                     GIT_CONFIG_SYSTEM="/dev/null",
                     GIT_CONFIG_NOSYSTEM="1",
                     **env)


# A remote, a checkout of it on `main`, and a branch with one commit, published.
BUILD = '''
root=$(mktemp -d)
git init -q --bare --initial-branch=main "$root/remote.git"
git init -q --initial-branch=main "$root/work"
cd "$root/work"
git config user.email test@example.invalid
git config user.name Test
git remote add origin "$root/remote.git"
echo base > a.txt && git add -A && git commit -qm "the base"
git push -q -u origin main
git checkout -qb feat/x
echo work > b.txt && git add -A && git commit -qm "the branch work"
git push -q -u origin feat/x
git checkout -q main
printf %s "$root"
'''


class Fixture(unittest.TestCase):

    def setUp(self):
        built = run_bash(BUILD)
        self.assertEqual(0, built.returncode, built.stderr)
        self.root = built.stdout.strip()
        self.assertTrue(self.root, "the fixture produced no path")
        self.addCleanup(lambda: run_bash('rm -rf "$R"', R=self.root))
        self.work = self.root + "/work"
        self.bin = tempfile.mkdtemp(prefix="ghstub-")
        self.addCleanup(shutil.rmtree, self.bin, ignore_errors=True)
        stub = Path(self.bin, "gh")
        stub.write_text(
            "#!/usr/bin/env bash\n"
            'if [ "$1 $2" = "repo view" ]; then printf "%s" "$STUB_OWNER"; exit 0; fi\n'
            'if [ "$1 $2" = "pr list" ]; then printf "%s" "$STUB_ROWS"; exit "${STUB_EXIT:-0}"; fi\n'
            'echo "unexpected gh call: $*" >&2; exit 9\n',
            encoding="utf-8", newline="\n")
        stub.chmod(0o755)

    def at(self, script):
        result = run_bash('cd "$W"\n' + script, W=self.work, R=self.root)
        self.assertEqual(0, result.returncode, f"{script}: {result.stderr}")
        return result.stdout.strip()

    def tip(self, branch="feat/x"):
        return self.at(f"git rev-parse refs/heads/{branch}")

    def exists(self, branch="feat/x"):
        return run_bash(f'cd "$W"\ngit show-ref --verify --quiet "refs/heads/{branch}"',
                        W=self.work).returncode == 0

    @staticmethod
    def row(state="MERGED", oid="", base="main", number=7, owner=OWNER):
        return {"number": number, "state": state, "url": f"u{number}", "headRefOid": oid,
                "baseRefName": base, "headRepository": {"nameWithOwner": owner}}

    def helper(self, branch="feat/x", rows=None, exit_code="0"):
        if rows is None:
            rows = [self.row(oid=self.tip())]
        return run_bash(
            f'cd "$W"\nbash "$H" "$B"',
            W=self.work, H=str(HELPER), B=branch,
            STUB_OWNER=OWNER, STUB_ROWS=json.dumps(rows), STUB_EXIT=exit_code,
            PATH=self.bin + os.pathsep + os.environ["PATH"])


class TheHelperKeepsWhatHasNotLanded(Fixture):

    def test_main_is_refused_however_it_is_spelled(self):
        # The fake answers a MERGED row at main's own tip, so the name is the
        # only thing that stops the drop.
        landed = [self.row(oid=self.tip("main"))]
        self.at("git checkout -q feat/x")
        for spelling in SPELLINGS:
            with self.subTest(spelling=spelling):
                result = self.helper(spelling, rows=landed)
                self.assertEqual(3, result.returncode, f"{spelling!r}: {result.stderr}")
                self.assertIn("refusing to delete main", result.stderr)
        self.assertTrue(self.exists("main"), "main was deleted")

    def test_an_unmerged_branch_is_kept(self):
        result = self.helper(rows=[self.row(state="OPEN", oid=self.tip())])
        self.assertEqual(7, result.returncode, result.stderr)
        self.assertIn("has not landed", result.stderr)
        self.assertTrue(self.exists())

    def test_a_branch_with_no_pull_request_is_kept(self):
        result = self.helper(rows=[])
        self.assertEqual(7, result.returncode, result.stderr)
        self.assertTrue(self.exists())

    def test_a_tip_after_the_merge_is_kept(self):
        # The pull request merged at the commit before this one, so the tip
        # carries work no merge holds.
        merged_at = self.tip()
        self.at("git checkout -q feat/x && echo more > c.txt && git add -A "
                "&& git commit -qm 'after the merge' && git checkout -q main")
        result = self.helper(rows=[self.row(oid=merged_at)])
        self.assertEqual(7, result.returncode, result.stderr)
        self.assertIn("has not landed", result.stderr)
        self.assertTrue(self.exists())

    def test_a_merge_into_another_base_is_kept(self):
        result = self.helper(rows=[self.row(oid=self.tip(), base="release")])
        self.assertEqual(7, result.returncode, result.stderr)
        self.assertTrue(self.exists())

    def test_a_forks_merged_row_is_not_this_branchs(self):
        # pr-for-branch.sh drops a row from another repository, so a
        # stranger's same-named pull request cannot land this branch.
        result = self.helper(rows=[self.row(oid=self.tip(), owner="mallory/widgets")])
        self.assertEqual(7, result.returncode, result.stderr)
        self.assertTrue(self.exists())

    def test_a_branch_checked_out_elsewhere_is_kept(self):
        self.at('git worktree add -q "$R/elsewhere" feat/x')
        result = self.helper()
        self.assertEqual(4, result.returncode, result.stderr)
        self.assertIn("checked out", result.stderr)
        self.assertTrue(self.exists())

    def test_a_branch_checked_out_here_is_kept(self):
        self.at("git checkout -q feat/x")
        result = self.helper()
        self.assertEqual(4, result.returncode, result.stderr)
        self.assertTrue(self.exists())

    def test_an_unanswered_read_keeps_it(self):
        result = self.helper(exit_code="1")
        self.assertEqual(12, result.returncode, result.stderr)
        self.assertTrue(self.exists())

    def test_a_branch_that_is_not_there_is_refused_by_its_own_message(self):
        result = self.helper("feat/gone", rows=[])
        self.assertEqual(6, result.returncode, result.stderr)
        self.assertIn("no local branch feat/gone", result.stderr)

    def test_a_name_that_could_be_a_flag_is_refused(self):
        for name in ("-D", "--force", "-rfoo"):
            with self.subTest(name=name):
                result = self.helper(name, rows=[])
                self.assertEqual(2, result.returncode, result.stderr)

    def test_it_takes_exactly_one_argument(self):
        result = run_bash('cd "$W"\nbash "$H"', W=self.work, H=str(HELPER))
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertIn("usage: git-branch-drop.sh", result.stderr)


class TheHelperDropsWhatLanded(Fixture):

    def test_a_landed_branch_is_dropped(self):
        # The positive control for every refusal above.
        result = self.helper()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("dropped feat/x", result.stdout)
        self.assertFalse(self.exists())
        self.assertTrue(self.exists("main"))

    def test_one_landed_row_among_others_is_enough(self):
        # A branch reopened after a closed attempt has several rows.
        rows = [self.row(state="CLOSED", oid="0" * 40, number=5), self.row(oid=self.tip())]
        result = self.helper(rows=rows)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(self.exists())


if __name__ == "__main__":
    unittest.main()
