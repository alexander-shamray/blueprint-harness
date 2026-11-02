"""Tests for the command line."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from harness_sync.__main__ import main

COMMIT = "c" * 40


class MainTests(unittest.TestCase):
    def tree(self, tmp: str) -> tuple[Path, Path]:
        payload, target = Path(tmp) / "p", Path(tmp) / "t"
        (payload / ".harness").mkdir(parents=True)
        (payload / ".harness/settings.base.json").write_text(json.dumps({"hooks": {}}), encoding="utf-8")
        (payload / "a.md").write_text("a\n", encoding="utf-8")
        (target / ".harness").mkdir(parents=True)
        (target / ".harness/config.json").write_text(json.dumps({"repo": "o/r", "task_list": "t"}), encoding="utf-8")
        return payload, target

    def run_main(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def argv(self, payload: Path, target: Path, commit: str) -> list[str]:
        return ["apply", "--payload", str(payload), "--target", str(target), "--commit", commit]

    def test_apply_prints_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload, target = self.tree(tmp)
            code, out, _ = self.run_main(*self.argv(payload, target, COMMIT))
            self.assertEqual(code, 0)
            self.assertIn("a.md", out)

    def test_bad_commit_exits_non_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload, target = self.tree(tmp)
            code, _, err = self.run_main(*self.argv(payload, target, "zz"))
            self.assertNotEqual(code, 0)
            self.assertIn("40", err)

    def test_refusal_goes_to_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload, target = self.tree(tmp)
            (payload / ".claude").mkdir()
            (payload / ".claude/settings.json").write_text("{}", encoding="utf-8")
            code, _, err = self.run_main(*self.argv(payload, target, COMMIT))
            self.assertNotEqual(code, 0)
            self.assertIn(".claude/settings.json", err)

    def test_missing_config_exits_non_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload, target = self.tree(tmp)
            (target / ".harness/config.json").unlink()
            code, _, err = self.run_main(*self.argv(payload, target, COMMIT))
            self.assertNotEqual(code, 0)
            self.assertIn("config.json", err)

    def test_check_reports_each_problem_and_exits_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload, target = self.tree(tmp)
            self.run_main(*self.argv(payload, target, COMMIT))
            (target / ".claude/hooks").mkdir(parents=True)
            (target / ".claude/hooks/stray.sh").write_text("x\n", encoding="utf-8")
            code, out, _ = self.run_main("check", "--target", str(target))
            self.assertEqual(code, 1)
            self.assertIn(".claude/hooks/stray.sh", out)

    def test_check_is_clean_on_a_target_the_real_payload_was_applied_to(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "t"
            (target / ".harness").mkdir(parents=True)
            config = (repo / "targets/blueprint-backend.config.json").read_text(encoding="utf-8")
            (target / ".harness/config.json").write_text(config, encoding="utf-8")
            code, _, err = self.run_main(*self.argv(repo / "payload", target, COMMIT))
            self.assertEqual(code, 0, err)
            code, out, _ = self.run_main("check", "--target", str(target))
            self.assertEqual(code, 0, out)
            self.assertIn("clean", out)


if __name__ == "__main__":
    unittest.main()
