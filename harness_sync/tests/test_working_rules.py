"""working-rules.md's and task-list.md's rules held against the code, settings and sibling rules they depend on.

No gate reads prose for meaning, so the board, base-deny and gate-trigger cases tie a rule to what makes it true; the
others pin that a rule stays stated.
"""

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ROOT / "payload"
RULES = PAYLOAD / "docs" / "harness" / "working-rules.md"
TASK_LIST = PAYLOAD / "docs" / "harness" / "task-list.md"
BOARD = PAYLOAD / ".claude" / "scripts" / "dispatch_board.py"
BASE = PAYLOAD / ".harness" / "settings.base.json"
LISTER = PAYLOAD / ".claude" / "scripts" / "gh-issue-list.sh"


def _board():
    """The payload's `dispatch_board.py`, which sits outside any package this suite can import."""
    spec = importlib.util.spec_from_file_location("working_rules_dispatch_board", BOARD)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _bullet(rules: str, lead: str) -> str:
    """The top-level bullet of `rules` opening with `lead`, its wrapped lines joined with single spaces."""
    match = re.search(rf"^- \*\*{re.escape(lead)}.*?(?=^- |^## |\Z)", rules, re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError(f"no bullet opens with {lead!r}")
    return re.sub(r"\s+", " ", match.group(0))


class WorkingRulesTests(unittest.TestCase):
    def setUp(self):
        self.rules = RULES.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.list_rules = TASK_LIST.read_text(encoding="utf-8").replace("\r\n", "\n")

    def placement(self):
        """The table under task-list.md's *Where a row sits*, as (state, section) rows."""
        body = self.list_rules.split("\n## Where a row sits\n", 1)[1].split("\n## ", 1)[0]
        return re.findall(r"^\| (.+?) \| (.+?) \|$", body, re.MULTILINE)

    def test_the_state_table_places_rows_only_in_the_sections_the_board_parses(self):
        rows = self.placement()
        self.assertEqual(rows[0], ("State", "Section"), "*Where a row sits* should open on its table")
        placed = {name for _, where in rows for name in re.findall(r"\*([A-Z][a-z]+(?: [a-z]+)?)\*", where)}
        self.assertEqual(placed, set(_board().SECTIONS))

    def test_the_task_list_rule_says_no_session_edits_it_by_hand_and_names_its_owner(self):
        task_list = _bullet(self.rules, "The task list")
        self.assertIn("**No session edits it by hand**", task_list)
        self.assertIn("`docs/harness/task-list.md`", task_list)

    def test_a_pull_request_row_names_one_issue_as_the_board_refuses_two(self):
        rows = " ".join(" | ".join(row) for row in self.placement())
        self.assertIn("a row for each open, unpaused issue it closes", rows)
        board = _board()
        self.assertEqual(1690, board._row("In progress", "| — | #1690 | x | `b` | open |").number)
        with self.assertRaisesRegex(board.Refusal, "names no issue number"):
            board._row("In progress", "| — | #1690, #1691 | x | `b` | open |")

    def test_the_row_with_no_issue_is_spelt_as_the_board_parses_it(self):
        shape = re.sub(r"\s+", " ", self.list_rules)
        spelling = re.search(r"is an issue number, or `([^`]+)` for work with no issue", shape).group(1)
        board = _board()
        row = board._row("In progress", f"| — | {spelling} | x | `b` | started |")
        self.assertIsNone(row.number)
        self.assertEqual("b", board.row_branch(row))
        with self.assertRaisesRegex(board.Refusal, "names no issue number"):
            board._row("In progress", "| — | — | x | `b` | started |")

    def test_stopped_work_and_the_dispatcher_each_say_where_their_row_goes(self):
        task_list = _bullet(self.rules, "The task list")
        self.assertIn("Work that ends with its issue still open", task_list)
        self.assertIn("`/dispatch` is the list's one writer", task_list)

    def test_a_reconcile_reads_a_list_that_refuses_its_own_cut(self):
        # The rebuild once named `--limit 1000` because gh's default of 30 cuts silently; the helper now reads
        # through the lister, which refuses a list as long as its limit rather than reading it as whole.
        reconcile = _bullet(self.list_rules, "`tasks reconcile`")
        self.assertIn("`gh-issue-list.sh`", reconcile)
        lister = LISTER.read_text(encoding="utf-8")
        self.assertIn("--state all --limit", lister)
        self.assertIn("so the list may be cut", lister)

    def test_auto_merge_is_turned_off_by_the_owner_because_the_base_denies_the_raw_merge(self):
        rule = _bullet(self.rules, "Auto-merge waits on")
        self.assertIn("`gh pr merge <n> --disable-auto`", rule)
        self.assertIn("is the owner's", rule)
        deny = json.loads(BASE.read_text(encoding="utf-8"))["permissions"]["deny"]
        self.assertIn("Bash(gh pr merge:*)", deny)

    def test_a_check_the_pull_request_touched_none_of_is_an_update_the_conflict_rule_admits(self):
        rule = _bullet(self.rules, "A check red on a pull request that touched none of it")
        self.assertIn("whether or not `main` ran red", rule)
        self.assertIn("a gate's refusal of its own commits, body or added lines is its own to fix", rule)
        self.assertIn("A rerun comes first, and one that turns green is a flake", rule)
        self.assertIn("is not changed to make it pass", rule)
        self.assertIn("`git-rebase-onto-main.sh`", rule)
        update = _bullet(self.rules, "A branch is updated for a conflict")
        self.assertIn("once the revert or fix for a check that belongs to `main` has landed", update)
        self.assertNotIn("a red `main` it waited on", update)
        fix = _bullet(self.rules, "A red check is fixed at once")
        self.assertIn("A check the pull request touched none of is `main`'s", fix)

    def test_the_gates_that_rule_names_have_no_run_on_main_to_go_red(self):
        rule = _bullet(self.rules, "A check red on a pull request that touched none of it")
        named = re.search(r"((?:`[\w-]+`(?:, | and ))+`[\w-]+`) run on `pull_request` alone", rule)
        gates = re.findall(r"`([\w-]+)`", named.group(1))
        self.assertTrue(gates, "the rule should name the gates that run on pull_request alone")
        # Each is a check the gates workflow posts, so the triggers that matter are that workflow's.
        workflow = (PAYLOAD / ".github" / "workflows" / "gates.yml").read_text(encoding="utf-8").replace("\r\n", "\n")
        block = re.search(r"^on:\n(.*?)(?=^\S)", workflow, re.MULTILINE | re.DOTALL)
        self.assertEqual(re.findall(r"^  (\w+):", block.group(1), re.MULTILINE), ["pull_request"])
        for gate in gates:
            self.assertRegex(workflow, rf"(?m)^ +verdict {re.escape(gate)} ", gate)

    def test_one_owner_per_fact_leaves_an_untouched_restatement_to_the_finding_bar(self):
        rule = _bullet(self.rules, "One owner per fact")
        self.assertIn("never by value", rule)
        self.assertIn("*What counts as a finding*", rule)
        self.assertIn("a stale restatement this branch left untouched", re.sub(r"\s+", " ", self.rules))


if __name__ == "__main__":
    unittest.main()
