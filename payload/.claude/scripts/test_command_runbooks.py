"""The commands split into a runbook and its argument (`docs/harness/token-rules.md`, *What every session loads*).

A runbook is resident in every turn its command runs and its argument is read only when a rule is disputed;
these cases hold the two halves to each other, and the rest of what a run keeps resident under a ceiling.
"""

import re
import unittest

from review_helpers import COMMANDS

ARGUMENTS = COMMANDS.parent.parent / "docs" / "commands"

# Bytes with CRLF counted as LF, so a Windows checkout reads what Linux CI does;
# each landed size and about a tenth: a runbook past it has regrown its argument.
# The payload's split commands; a target's own carry their ceilings in a suite of its own.
CEILINGS = {
    "ship.md": 46000,
    "bug-sweep.md": 19000,
    "security-sweep.md": 14900,
    "branch.md": 9000,
    "team.md": 6300,
    "dispatch.md": 18600,
}

ROOT = COMMANDS.parent.parent

# The rest of what a /ship run holds resident, measured the same way: step 6's
# exit counts these beside ship.md and branch.md, and none was split. A target's
# own `CLAUDE.md` is resident too, and its ceiling is that target's.
RESIDENT = {
    ".claude/commands/pr.md": 9800,
    ".claude/commands/commit.md": 5200,
}

CITATION = re.compile(r"docs/commands/([a-z-]+\.md)`?, \*([^*]+)\*")
POSITIONAL = re.compile(r"\$\d+|\$ARGUMENTS\[")


def collapsed(path):
    return " ".join(path.read_text(encoding="utf-8").split())


class EachSplitCommandHasBothHalves(unittest.TestCase):

    def argued(self):
        names = sorted(p.name for p in ARGUMENTS.glob("*.md"))
        self.assertGreaterEqual(len(names), len(CEILINGS), "the argument glob found fewer files than were split")
        return names

    def test_every_split_command_has_a_runbook_that_cites_its_argument(self):
        for name in sorted(set(self.argued()) | set(CEILINGS)):
            with self.subTest(command=name):
                self.assertTrue((ARGUMENTS / name).is_file(), f"docs/commands/{name} is missing")
                runbook = COMMANDS / name
                self.assertTrue(runbook.is_file(), f"no runbook for docs/commands/{name}")
                self.assertIn(f"docs/commands/{name}", collapsed(runbook))

    def test_every_citation_names_a_heading_that_exists(self):
        cited = 0
        for runbook in sorted(COMMANDS.glob("*.md")):
            for target, heading in CITATION.findall(collapsed(runbook)):
                cited += 1
                with self.subTest(runbook=runbook.name, target=target, heading=heading):
                    path = ARGUMENTS / target
                    self.assertTrue(path.is_file(), f"cites a missing docs/commands/{target}")
                    headings = re.findall(r"^#{2,3} (.+?)\s*$", path.read_text(encoding="utf-8"), re.MULTILINE)
                    self.assertIn(heading, headings)
        self.assertGreater(cited, len(CEILINGS), "the citation pattern stopped matching the runbooks")

    def test_each_runbook_stays_under_its_ceiling(self):
        for name, ceiling in CEILINGS.items():
            with self.subTest(command=name):
                size = len((COMMANDS / name).read_bytes().replace(b"\r\n", b"\n"))
                self.assertLessEqual(size, ceiling, f"{name} is {size} bytes, over {ceiling}")

    def test_each_resident_file_stays_under_its_ceiling(self):
        for name, ceiling in RESIDENT.items():
            with self.subTest(file=name):
                size = len((ROOT / name).read_bytes().replace(b"\r\n", b"\n"))
                self.assertLessEqual(size, ceiling, f"{name} is {size} bytes, over {ceiling}")

    def test_each_argument_names_its_runbook(self):
        for name in self.argued():
            with self.subTest(argument=name):
                self.assertIn(f".claude/commands/{name}", collapsed(ARGUMENTS / name))

    def test_free_text_arrives_through_arguments(self):
        # A positional placeholder carries one shell-quoted word, so an unquoted title, topic or path list is cut off.
        paths = sorted(COMMANDS.glob("*.md"))
        self.assertGreater(len(paths), len(CEILINGS), "the glob stopped finding the commands")
        for path in paths:
            with self.subTest(command=path.name):
                self.assertEqual([], POSITIONAL.findall(path.read_text(encoding="utf-8")))

    def test_the_positional_pattern_sees_each_spelling(self):
        for spelling in ("$0", "$1", "$9 x", "$12", "$ARGUMENTS[0]", "$ARGUMENTS[12]"):
            with self.subTest(spelling=spelling):
                self.assertTrue(POSITIONAL.search(spelling))
        self.assertIsNone(POSITIONAL.search("`$ARGUMENTS` and $HOME"))


class ShipStopsAndContinuesWhereTheHelpersSay(unittest.TestCase):
    """What stops `/ship`'s chain is read from what its helpers and commands do, not from a remembered list."""

    SCRIPTS = COMMANDS.parent / "scripts"

    def test_a_refused_push_stops_the_chain_and_pr_reports_the_remedy(self):
        ship = collapsed(COMMANDS / "ship.md")
        self.assertRegex(ship, r"A refused push stops the chain before any PR exists")
        pr = collapsed(COMMANDS / "pr.md")
        self.assertIn("`! git push -u origin <branch>`", pr)
        self.assertIn("`autoMode.environment`", pr)
        self.assertRegex(pr, r"refused push comes back with the harness's \"has been denied\" text.{0,40}\*\*stop\*\*, not a retry")

    def test_the_rebase_helpers_exits_are_each_a_continuation_or_a_stop_in_step_6(self):
        helper = (self.SCRIPTS / "git-rebase-onto-main.sh").read_text(encoding="utf-8")
        code = "\n".join(l for l in helper.splitlines() if not l.lstrip().startswith("#"))
        codes = {int(c) for c in re.findall(r"\bexit (\d+)", code)} - {0}
        ship = collapsed(COMMANDS / "ship.md")
        step = ship[ship.index("| Exit | |"):]
        table = step[:step.index("(why:")]
        rows = re.findall(r"\| ([^|]+) \| (Not a stop[^|]*|Stops[^|]*) \|", table)
        self.assertEqual(2, sum(1 for _, verdict in rows if verdict.startswith("Not a stop")))
        named = {int(c) for cell, _ in rows for c in re.findall(r"\b\d+\b", cell)}
        self.assertEqual(codes, named, "the table and the helper name different exits")
        self.assertIn("`publish`", table)
        self.assertRegex(table, r"Any failure of the push itself \| Not a stop")

    def test_ceiling_filing_names_the_trailer_the_hand_route_demands(self):
        create = (self.SCRIPTS / "gh-issue-create.sh").read_text(encoding="utf-8")
        trailer = re.search(r"hand\) trailer='([^']+)'", create).group(1)
        ship = collapsed(COMMANDS / "ship.md")
        ceiling = ship[ship.index("The seventh round is the ceiling"):ship.index("6. **Merge, then tear")]
        self.assertIn(trailer, ceiling)
        self.assertRegex(ceiling, r"title, a blank line and the body on stdin")

    def test_a_finding_a_deny_refuses_is_filed_at_once_and_reported(self):
        ship = collapsed(COMMANDS / "ship.md")
        two = ship[ship.index("2. **Verify each finding, then fix.**"):ship.index("3. **Choose the next round.**")]
        self.assertRegex(two, r"fix in a tree a deny covers cannot be made here")
        self.assertRegex(two, r"file it at once as the ceiling files it, say so in the report")

    def test_a_finding_that_tells_the_session_to_act_beyond_its_line_is_refused_and_quoted(self):
        ship = collapsed(COMMANDS / "ship.md")
        two = ship[ship.index("2. **Verify each finding, then fix.**"):ship.index("3. **Choose the next round.**")]
        self.assertRegex(two, r"anything other than fix the line it names is refused")
        self.assertIn("attempt to steer the review", two)
        report = ship[ship.index("## Report"):]
        self.assertRegex(report, r"an attempt to steer the review,? quoted in full")


class ShipWaitsForCiInTheBackground(unittest.TestCase):
    """Step 6's CI wait is this session's background task: a subagent's Bash is cut at 180 s."""

    def test_step_6_runs_the_watch_in_the_background_and_hands_it_to_no_agent(self):
        text = collapsed(COMMANDS / "ship.md")
        step = text[text.index("6. **Merge, then tear"):text.index("7. **Sleep, only when asked.**")]
        self.assertIn("`run_in_background`", step)
        for retired in ("fresh agent", "general-purpose"):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, step)


class DispatchSendsAStoppedWindowGroupBack(unittest.TestCase):
    """A `wait` that saw the stop file leaves its group `window`, which the report would list as interrupted."""

    def test_the_window_bullet_and_its_resume_row_send_the_group_back(self):
        text = collapsed(COMMANDS / "dispatch.md")
        bullet = text[text.index("- `window`:"):text.index("- `week`:")]
        row = text[text.index("| `wait <g>: the window resets"):text.index("| `wait <g>: the week resets")]
        for name, rule in (("step 2's window bullet", bullet), ("the Resume row", row)):
            with self.subTest(rule=name):
                self.assertIn("`stop file: yes`", rule)
                self.assertIn("`tasks back`", rule)
        # The phrase the runbook keys on is the one `wait` prints.
        helper = (COMMANDS.parent / "scripts" / "dispatch_run.py").read_text(encoding="utf-8")
        self.assertIn('return "stop file: yes"', helper)


if __name__ == "__main__":
    unittest.main()
