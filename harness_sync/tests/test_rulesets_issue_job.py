"""`rulesets.yml`'s `rulesets-issue` job, read as the workflow writes it and its script run against a stub `gh`."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest

from harness_sync.tests.test_main_red_job import ROOT, _jobs
from harness_sync.tests.test_sync_issue_job import _stub_dir

RULESETS = ROOT / ".github" / "workflows" / "rulesets.yml"


def _job() -> str:
    return _jobs(RULESETS)["rulesets-issue"]


class TheJobHearsARedScheduledRun(unittest.TestCase):
    def test_needs_names_the_read_back(self) -> None:
        self.assertEqual({"rulesets", "rulesets-issue"}, set(_jobs(RULESETS)))
        self.assertRegex(_job(), r"(?m)^    needs: rulesets$")

    def test_the_condition_reaches_the_step_for_a_job_past_its_limit_but_not_a_cancelled_run(self) -> None:
        # Measured on run 42575459566 (README, sync.yml's sync-red): at a job's limit `failure()` and `cancelled()` are
        # both false, so `failure()` alone misses a read-back that hung, and `!cancelled()` is false only for a run
        # somebody cancels whole.
        self.assertIn(
            "if: ${{ !cancelled() && github.event_name == 'schedule' && "
            "(needs.rulesets.result == 'failure' || needs.rulesets.result == 'cancelled') }}",
            _job())
        self.assertNotIn("always()", _job())
        self.assertNotRegex(_job(), r"(?m)^    if: failure\(\)")

    def test_every_step_times_out_inside_its_job(self) -> None:
        # A step past its timeout fails, which is the plain red. The job's clock runs through every step, so each has a
        # limit and all of them together end before the job's does, which leaves that limit to a hang outside a step.
        jobs = _jobs(RULESETS)
        for name in sorted(jobs):
            with self.subTest(job=name):
                job_limit = re.search(r"(?m)^    timeout-minutes: (\d+)$", jobs[name])
                self.assertIsNotNone(job_limit, "the job has no limit of its own, so GitHub's six hours is its limit")
                steps = re.split(r"(?m)^      - ", jobs[name].split("\n    steps:\n", 1)[1])[1:]
                self.assertTrue(steps, "no steps read, so nothing below is checked")
                limits = [re.search(r"(?m)^        timeout-minutes: (\d+)$", step) for step in steps]
                unbounded = [step.splitlines()[0] for step, limit in zip(steps, limits) if limit is None]
                self.assertEqual([], unbounded)
                self.assertLess(sum(int(limit.group(1)) for limit in limits), int(job_limit.group(1)))


class TheScriptFilesOneIssue(unittest.TestCase):
    def run_script(self, rows: list[dict[str, object]], status: str = "",
                   differences: str = "") -> tuple[subprocess.CompletedProcess[str], str]:
        """The issue job's step's result and each `gh` line it ran, `status` and `differences` being the read-back's
        outputs, both empty for a job that ended before its check step wrote them."""
        bash = shutil.which("bash")
        self.assertIsNotNone(bash, "bash is what the job's step runs under")
        script = textwrap.dedent(re.search(r"run: \|\n((?: {10}.*(?:\n|$)|\n)+)", _job()).group(1))
        with tempfile.TemporaryDirectory() as directory:
            root = _stub_dir(directory)
            log = root / "log"
            log.touch()
            path = root / "step.sh"
            path.write_text(script, encoding="utf-8", newline="\n")
            env = {**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"],
                   "STUB_LOG": log.as_posix(), "STUB_ROWS": json.dumps(rows), "GH_REPO": "a/h",
                   "STATUS": status, "DIFFERENCES": differences, "RUN_URL": "https://run"}
            result = subprocess.run([bash, path.as_posix()], capture_output=True, text=True, encoding="utf-8", env=env,
                                    stdin=subprocess.DEVNULL)
            return result, log.read_text(encoding="utf-8")

    def test_a_read_back_cut_off_at_its_limit_files_a_failed_read_back(self) -> None:
        # A job cut off before its check step wrote its outputs, at set-up or in the step, hands both on empty.
        result, log = self.run_script([{"number": 3, "title": "another"}])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("issue create --title", log)
        self.assertIn("--label bug --label harness --label high", log)
        self.assertIn("The scheduled read-back (https://run) failed (exit status unknown):", log)
        self.assertIn("no output reached this job; see the run", log)
        self.assertNotIn("issue comment", log)

    def test_a_difference_says_so(self) -> None:
        result, log = self.run_script([], status="1", differences="a/b: required checks differ")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("The scheduled read-back (https://run) found differences:", log)
        self.assertIn("a/b: required checks differ", log)

    def test_an_open_issue_takes_a_comment_and_no_second_one(self) -> None:
        title = re.search(r'TITLE="([^"]+)"', _job()).group(1)
        result, log = self.run_script([{"number": 7, "title": title}])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("issue comment 7 --body", log)
        self.assertNotIn("issue create", log)


if __name__ == "__main__":
    unittest.main()
