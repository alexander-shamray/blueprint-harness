"""The game day run on every pull request: each guard and gate refuses the condition it claims to catch."""

import io
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from harness_sync import game_day


class GameDayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="game-day-test-"))
        cls.target = game_day.apply_payload(cls.base)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)

    def test_a_clean_run_has_no_finding(self):
        out = io.StringIO()
        with redirect_stdout(out):
            status = game_day.main()
        self.assertNotIn("FINDING:", out.getvalue())
        self.assertEqual(status, 0, out.getvalue())

    def test_every_wired_guard_is_the_payloads(self):
        # The subject is the rendered settings, not this file's table: a guard the payload wires is read from them.
        wired = {(tool, guard) for tool, guard, _ in game_day.guard_hooks(self.target)}
        self.assertIn(("Bash", "guard-git-argv.py"), wired)
        self.assertEqual(game_day.launcher_guards(self.target), {guard for _, guard in wired})

    def test_a_guard_with_no_scenario_is_a_finding(self):
        scenarios = dict(game_day.GUARD_SCENARIOS)
        del scenarios[("Bash", "guard-sed-crlf.py")]
        with mock.patch.object(game_day, "GUARD_SCENARIOS", scenarios):
            findings, _ = game_day.guard_scenarios(self.target)
        self.assertIn("guard-sed-crlf.py is wired for Bash with no game-day scenario", findings)

    def test_a_command_let_through_is_a_finding(self):
        scenarios = dict(game_day.GUARD_SCENARIOS)
        scenarios[("Bash", "guard-sed-crlf.py")] = [({"command": "git status"}, "CRLF")]
        with mock.patch.object(game_day, "GUARD_SCENARIOS", scenarios):
            findings, _ = game_day.guard_scenarios(self.target)
        self.assertTrue(any("guard-sed-crlf.py on Bash" in f and "let through" in f for f in findings), findings)

    def _stubbed(self, marker, answer):
        """`game_day.run` with each call whose argv holds `marker` answered by `answer`, the rest run for real."""
        real = game_day.run

        def run(args, cwd, env=None, stdin=None):
            if marker in args:
                return subprocess.CompletedProcess(args, answer[0], answer[1], answer[2])
            return real(args, cwd, env=env, stdin=stdin)
        return mock.patch.object(game_day, "run", run)

    def test_a_drift_gate_passing_an_edited_file_is_a_finding(self):
        base = Path(tempfile.mkdtemp(prefix="game-day-test-"))
        self.addCleanup(shutil.rmtree, base, True)
        target = game_day.apply_payload(base)
        with self._stubbed("check", (0, "harness-drift: clean\n", "")):
            findings, oks = game_day.drift_scenario(target)
        self.assertEqual(oks, [])
        self.assertEqual(len(findings), 1)
        self.assertIn("the drift gate passed a managed file edited in the target", findings[0])

    def test_a_task_list_written_over_is_a_finding(self):
        with self._stubbed(".claude/scripts/dispatch_board.py", (0, "", "")):
            findings, _ = game_day.task_list_scenario(self.target)
        self.assertEqual(len(findings), 1)
        self.assertIn("dispatch_board.py wrote over a task list in a shape `board` refuses", findings[0])

    def test_a_task_list_refused_for_another_reason_is_a_finding(self):
        other = "refused: a /dispatch executor writes no task list\n"
        with self._stubbed(".claude/scripts/dispatch_board.py", (2, "", other)):
            findings, _ = game_day.task_list_scenario(self.target)
        self.assertEqual(len(findings), 1)
        self.assertIn("but not with its documented reason", findings[0])

    def test_a_refusal_for_another_reason_is_a_finding(self):
        scenarios = dict(game_day.GUARD_SCENARIOS)
        scenarios[("Bash", "guard-index-argv.py")] = [
            (scenarios[("Bash", "guard-index-argv.py")][0][0], "a reason no guard gives")]
        with mock.patch.object(game_day, "GUARD_SCENARIOS", scenarios):
            findings, _ = game_day.guard_scenarios(self.target)
        self.assertTrue(any("not with its documented reason" in f for f in findings), findings)


if __name__ == "__main__":
    unittest.main()
