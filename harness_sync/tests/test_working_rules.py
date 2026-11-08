"""`docs/harness/working-rules.md`'s rules held against the code, settings and sibling rules they depend on.

No gate reads prose for meaning, so the board and base-deny cases tie a rule to what makes it true; the others pin
that a rule stays stated.
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
BOARD = PAYLOAD / ".claude" / "scripts" / "dispatch_board.py"
BASE = PAYLOAD / ".harness" / "settings.base.json"


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

    def test_the_state_table_places_rows_only_in_the_sections_the_board_parses(self):
        rows = re.findall(r"^  \| (.+?) \| (.+?) \|$", self.rules, re.MULTILINE)
        self.assertEqual(rows[0], ("State", "Where"), "the table under *The task list* should lead the indented rows")
        placed = {name for _, where in rows for name in re.findall(r"\*([A-Z][a-z]+(?: [a-z]+)?)\*", where)}
        self.assertEqual(placed, set(_board().SECTIONS))

    def test_a_pull_request_row_names_one_issue_as_the_board_refuses_two(self):
        task_list = _bullet(self.rules, "The task list")
        self.assertIn("a row for each open, unpaused issue it closes", task_list)
        board = _board()
        self.assertEqual(1690, board._row("In progress", "| — | #1690 | x | `b` | open |").number)
        with self.assertRaisesRegex(board.Refusal, "names no issue number"):
            board._row("In progress", "| — | #1690, #1691 | x | `b` | open |")

    def test_the_row_with_no_issue_is_spelt_as_the_board_parses_it(self):
        task_list = _bullet(self.rules, "The task list")
        spelling = re.search(r"A row with no issue reads `([^`]+)` in its `#` cell", task_list).group(1)
        board = _board()
        row = board._row("In progress", f"| — | {spelling} | x | `b` | started |")
        self.assertIsNone(row.number)
        self.assertEqual("b", board.row_branch(row))
        with self.assertRaisesRegex(board.Refusal, "names no issue number"):
            board._row("In progress", "| — | — | x | `b` | started |")

    def test_stopped_work_and_the_dispatcher_each_say_where_their_row_goes(self):
        task_list = _bullet(self.rules, "The task list")
        self.assertIn("leaves the issue open and ends its claim", task_list)
        self.assertIn("`/dispatch` is the list's one writer", task_list)

    def test_a_rebuild_asks_past_the_default_cut_of_both_lists(self):
        task_list = _bullet(self.rules, "The task list")
        self.assertIn("`gh pr list --limit 1000`", task_list)
        self.assertIn("`gh issue list --limit 1000`", task_list)

    def test_auto_merge_is_turned_off_by_the_owner_because_the_base_denies_the_raw_merge(self):
        rule = _bullet(self.rules, "Auto-merge waits on")
        self.assertIn("`gh pr merge <n> --disable-auto`", rule)
        self.assertIn("is the owner's", rule)
        deny = json.loads(BASE.read_text(encoding="utf-8"))["permissions"]["deny"]
        self.assertIn("Bash(gh pr merge:*)", deny)

    def test_a_check_red_on_main_is_the_one_update_the_conflict_rule_admits(self):
        rule = _bullet(self.rules, "A check red on a pull request and on `main`")
        self.assertIn("is not changed to make it pass", rule)
        self.assertIn("`git-rebase-onto-main.sh`", rule)
        update = _bullet(self.rules, "A branch is updated for a conflict")
        self.assertIn("a red `main` it waited on", update)
        fix = _bullet(self.rules, "A red check is fixed at once")
        self.assertIn("A check red on `main` as well", fix)

    def test_one_owner_per_fact_leaves_an_untouched_restatement_to_the_finding_bar(self):
        rule = _bullet(self.rules, "One owner per fact")
        self.assertIn("never by value", rule)
        self.assertIn("*What counts as a finding*", rule)
        self.assertIn("a stale restatement this branch left untouched", re.sub(r"\s+", " ", self.rules))


if __name__ == "__main__":
    unittest.main()
