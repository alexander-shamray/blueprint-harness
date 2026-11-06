"""/ship's sync row: a harness sync pull request is reviewed once, for this target.

Nobody reads a dispatched run as it happens, so each case reads the command
text an executor is given, as `test_ship_dispatched.py` does.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHIP = ROOT / ".claude" / "commands" / "ship.md"
ARGUMENT = ROOT / "docs" / "commands" / "ship.md"
BASE = ROOT / ".harness" / "settings.base.json"

HEADING = "A sync pull request is reviewed once, for this target"
HELPER = "bash .claude/scripts/git-worktree-sync.sh"
SYNC_PR = "py -3.12 .claude/scripts/sync_pr.py"


def flat(text):
    # Backticks and line breaks are layout, not wording: a rewrap must not fail a case.
    return " ".join(text.replace("`", "").split())


def ship():
    return SHIP.read_text(encoding="utf-8")


def section():
    text = ship()
    start = text.index(f"## {HEADING}")
    return text[start:text.index("\n## ", start + 4)]


def bullet(name):
    """One bullet of the section, whitespace-collapsed, from its bold lead to the next bullet or the citation."""
    for part in re.split(r"\n(?=- \*\*|\(why:)", section()):
        if flat(part).startswith(f"- **{name}"):
            return flat(part)
    raise AssertionError(f"no bullet opens {name!r}")


def frontmatter(key):
    front = ship().split("---")[1]
    return next(ln for ln in front.splitlines() if ln.startswith(f"{key}:")).split(":", 1)[1].strip()


class TheSyncRow(unittest.TestCase):

    def test_the_section_follows_the_plan_section_and_precedes_the_steps(self):
        text = ship()
        order = [text.index(f"## {h}") for h in ("A plan is reviewed once, for contradiction", HEADING, "Steps")]
        self.assertEqual(order, sorted(order))

    def test_the_resume_table_has_a_sync_row(self):
        table = ship().split("## Resume, don't restart", 1)[1].split("\n## ", 1)[0]
        rows = [ln for ln in table.splitlines() if ln.startswith("| On a branch named `chore/harness-sync-")]
        self.assertEqual(1, len(rows), "one row for a sync branch")
        row = flat(rows[0])
        self.assertIn(HEADING, row)
        self.assertIn("never steps 3 and 4", row)

    def test_a_sync_branch_is_never_committed_to(self):
        steps = bullet("Steps 3 and 4")
        self.assertIn("never committed to or pushed", steps)
        self.assertIn("A dirty tree is reported and ends the run unmerged", steps)
        # Nothing in the section tells a sync run to commit, push or open a PR, in any spelling.
        for word in ("/commit", "/pr", "git commit", "git push", "git add"):
            self.assertNotIn(word, flat(section()).replace("never committed to or pushed", ""), word)

    def test_a_failed_verify_reviews_nothing(self):
        lead = flat(section().split("\n- **", 1)[0])
        self.assertIn(f"{SYNC_PR} verify <n> exits 0", lead)
        failed = bullet("A failed verify reviews nothing")
        self.assertIn("a moved head included", failed)
        self.assertIn("report its lines and end unmerged, or hand it back under --dispatched", failed)
        self.assertIn("none of the seven stops", failed)
        # The verify comes before the worktree is opened, so a head that fails it is never checked out.
        self.assertLess(lead.index("verify <n>"), lead.index(HELPER))

    def test_the_head_in_the_worktree_is_what_every_later_read_is_pinned_to(self):
        lead = flat(section().split("\n- **", 1)[0])
        self.assertIn("There git rev-parse HEAD is the head", lead)
        # The verify in the worktree runs before step 2 reads anything, and the pre-worktree verify has no pin.
        self.assertIn("verify <n> --head <oid> runs before step 2 reads anything", lead)
        self.assertIn("every later verify and review-diff takes the same --head <oid>", lead)
        self.assertIn("sync-<n>-r1.diff --head <oid>", bullet("Step 5"))
        self.assertLess(lead.index(HELPER), lead.index("--head <oid> runs before step 2"))

    def test_step_1_opens_the_worktree_on_the_existing_branch(self):
        lead = flat(section().split("\n- **", 1)[0])
        self.assertIn(f"{HELPER} .claude/worktrees/sync-<sha7> <head> in place of /branch", lead)
        self.assertIn("chore/harness-sync-[0-9a-f]{7}", lead)

    def test_step_2_runs_the_target_local_suites_as_ci_does(self):
        step = bullet("Step 2")
        self.assertIn("each path sync_pr.py local-suites prints", step)
        self.assertIn("py -3.12 -m unittest discover -s <dir> -p <file>", step)
        self.assertIn("nothing else in *Ship checks*", step)

    def test_the_sync_round_reads_review_diff(self):
        step = bullet("Step 5")
        self.assertIn("one round", step)
        self.assertIn("sync_pr.py review-diff <n> artifacts/review/sync-<n>-r1.diff", step)
        self.assertIn("never Write", step)
        self.assertNotIn("git diff", step, "the branch diff holds the managed files a sync review must not read")
        for severity in ("bug", "medium", "low", "nit"):
            self.assertIn(severity, step)
        self.assertIn("Low findings left by <repo>#<n>: <title>", step)
        # A payload finding is filed in the harness, which a target's checkout cannot name: the closed fifth word.
        self.assertIn("gh-issue-create.sh bug <severity> <area> hand harness", step)

    def test_step_6_verifies_again_after_a_rebase(self):
        step = bullet("Step 6")
        self.assertIn("After its rebase helper the new HEAD is the head, and sync_pr.py verify <n> --head <oid> "
                      "runs on it before gh-pr-merge.sh", step)
        self.assertIn("replacing the step 5 recheck", step)
        self.assertIn("a failed verify is handed back", step)
        # Step 6 merges the head that was proved: a differing headRefOid is a moved sync and merges nothing.
        self.assertIn("its <oid> must be that head: a headRefOid that differs is a moved sync, a failed verify, "
                      "and nothing merges", step)
        # And no round follows: the recheck the step otherwise re-enters is named only to be replaced.
        self.assertNotIn("re-enter", step)

    def test_a_dispatched_sync_names_its_group(self):
        step = bullet("Under --dispatched")
        self.assertIn("the group is sync-<n>", step)
        self.assertIn("issues is []", step)
        report = flat(ship()[ship().index("\n## Report"):])
        self.assertIn("or sync-<n> for sync #<n>", report)

    def test_the_argument_is_cited_and_argued(self):
        self.assertIn(f"(why: docs/commands/ship.md, *{HEADING}*)", flat(section()).replace("`", ""))
        self.assertIn(f"\n## {HEADING}\n", ARGUMENT.read_text(encoding="utf-8").replace("\r\n", "\n"))
        self.assertIn("sync #<n>", frontmatter("argument-hint"))

    def test_the_grants_name_every_read_a_dispatched_sync_makes(self):
        grants = [g.strip() for g in frontmatter("allowed-tools").split(",")]
        for grant in (f"Bash({SYNC_PR}:*)", f"Bash({HELPER}:*)"):
            self.assertIn(grant, grants)
        # The same two reach a session that is not /ship through the settings the sync renders.
        allow = json.loads(BASE.read_text(encoding="utf-8"))["permissions"]["allow"]
        self.assertIn(f"Bash({HELPER}:*)", allow)
        self.assertIn(f"Bash({SYNC_PR}:*)", allow)


if __name__ == "__main__":
    unittest.main()
