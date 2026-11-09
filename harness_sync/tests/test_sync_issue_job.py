"""`sync.yml`'s `sync-issue` job, read as the workflow writes it and its script run against a stub `gh`."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from harness_sync.tests.test_main_red_job import HELPER, ROOT, _jobs

SYNC = ROOT / ".github" / "workflows" / "sync.yml"
STUB = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$STUB_LOG"
case "$1 $2" in
  "issue list") printf '%s' "$STUB_ROWS" ;;
  "issue create") cat >> "$STUB_LOG" ;;
  "api "*) printf '%s' "$STUB_JOBS"; exit "${STUB_API_EXIT:-0}" ;;
esac
"""
# The shapes run 42575459566 of a scratch workflow read from the API: a job past its limit ran steps and a waiting job
# a newer one superseded ran none, and both conclude `cancelled`.
RAN = [{"conclusion": "success"}, {"conclusion": "cancelled"}, {"conclusion": "success"}]
PAST_ITS_LIMIT = {"name": "sync (a/b)", "conclusion": "cancelled", "steps": RAN}
SUPERSEDED = {"name": "sync (a/c)", "conclusion": "cancelled", "steps": []}
FAILED = {"name": "sync (a/d)", "conclusion": "failure", "steps": RAN}
PASSED = {"name": "sync (a/e)", "conclusion": "success", "steps": RAN}


def _job() -> str:
    return _jobs(SYNC)["sync-issue"]


def _title() -> str:
    return re.search(r"title='([^']+)'", _job()).group(1)


def _stub_dir(directory: str) -> Path:
    stub = Path(directory) / "gh"
    stub.write_text(STUB, encoding="utf-8", newline="\n")
    stub.chmod(0o755)
    return Path(directory)


class TheJobHearsARedRun(unittest.TestCase):
    def test_needs_names_every_other_job(self) -> None:
        # A job added to sync.yml and left out of this list could go red with nobody told.
        jobs = _jobs(SYNC)
        needs = re.search(r"^    needs: \[(.+)\]$", jobs["sync-issue"], re.MULTILINE)
        self.assertIsNotNone(needs, "sync-issue spells no one-line needs")
        self.assertEqual(sorted(set(jobs) - {"sync-issue"}), sorted(n.strip() for n in needs.group(1).split(",")))

    def test_the_condition_reaches_the_step_for_a_cancelled_job_but_not_a_cancelled_run(self) -> None:
        # Measured on run 42575459566: at a job's limit `failure()` and `cancelled()` are both false, so neither hears
        # it, and `!cancelled()` is true there and false only for a run somebody cancels whole.
        self.assertIn(
            "if: ${{ !cancelled() && (contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled')) }}",
            _job())
        self.assertNotIn("always()", _job())

    def test_every_step_times_out_inside_its_job(self) -> None:
        # A step past its timeout fails, which is the plain red. The job's clock runs through every step, so each has a
        # limit and all of them together end before the job's does, which leaves that limit to a hang outside a step.
        jobs = _jobs(SYNC)
        for name in sorted(set(jobs) - {"sync-issue"}):
            with self.subTest(job=name):
                job_limit = re.search(r"(?m)^    timeout-minutes: (\d+)$", jobs[name])
                self.assertIsNotNone(job_limit, "the job has no limit of its own, so GitHub's six hours is its limit")
                steps = re.split(r"(?m)^      - ", jobs[name].split("\n    steps:\n", 1)[1])[1:]
                self.assertTrue(steps, "no steps read, so nothing below is checked")
                limits = [re.search(r"(?m)^        timeout-minutes: (\d+)$", step) for step in steps]
                unbounded = [step.splitlines()[0] for step, limit in zip(steps, limits) if limit is None]
                self.assertEqual([], unbounded)
                self.assertLess(sum(int(limit.group(1)) for limit in limits), int(job_limit.group(1)))

    def test_it_holds_no_token_but_the_workflows_own(self) -> None:
        # The sync token is the harness-sync environment's, and a job that names neither cannot reach it.
        job = _job()
        self.assertNotIn("environment:", job)
        self.assertNotIn("secrets.", job)
        self.assertRegex(job, r"(?m)^    permissions:\n      actions: read\n      issues: write\n    steps:$")


class TheScriptFilesOneIssue(unittest.TestCase):
    def run_script(self, rows: list[dict[str, object]], jobs: str = json.dumps({"jobs": [FAILED]}),
                   api_exit: int = 0) -> tuple[subprocess.CompletedProcess[str], str]:
        """The step's result and each `gh` line it ran, its stub given `rows` for the listing and `jobs` for the run."""
        bash = shutil.which("bash")
        self.assertIsNotNone(bash, "bash is what the job's step runs under")
        # `_jobs` leaves a job's text with no final newline, so the step's last line may end at the end of the text.
        script = textwrap.dedent(re.search(r"run: \|\n((?: {10}.*(?:\n|$)|\n)+)", _job()).group(1))
        with tempfile.TemporaryDirectory() as directory:
            root = _stub_dir(directory)
            log = root / "log"
            log.touch()
            path = root / "step.sh"
            path.write_text(script, encoding="utf-8", newline="\n")
            env = {**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"],
                   "STUB_LOG": log.as_posix(), "STUB_ROWS": json.dumps(rows), "STUB_JOBS": jobs,
                   "STUB_API_EXIT": str(api_exit), "GH_REPO": "a/h", "GITHUB_RUN_ID": "9",
                   "GITHUB_SHA": "abc123", "RUN_URL": "https://run"}
            result = subprocess.run([bash, path.as_posix()], capture_output=True, text=True, encoding="utf-8", env=env)
            return result, log.read_text(encoding="utf-8")

    def test_no_open_issue_files_one_with_its_severity_in_both_places(self) -> None:
        result, log = self.run_script([{"number": 3, "title": "another"}])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(f"issue create --title {_title()} --label bug --label code --label medium", log)
        self.assertIn("## Severity\n\nmedium\n", log)
        self.assertIn("abc123: https://run", log)
        self.assertNotIn("issue comment", log)

    def test_an_open_issue_takes_a_comment_and_no_second_one(self) -> None:
        result, log = self.run_script([{"number": 3, "title": "another"}, {"number": 7, "title": _title()}])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("issue comment 7 --body Red again at abc123: https://run", log)
        self.assertNotIn("issue create", log)

    def test_the_listing_sees_the_label_it_files_under(self) -> None:
        # A listing narrower than what was filed misses the open issue and files a second one every red run.
        job = _job()
        listed = re.search(r"gh issue list [^)]*--label (\w+)", job).group(1)
        created = re.findall(r"--label (\w+)", next(line for line in job.splitlines() if "gh issue create" in line))
        self.assertIn(listed, created)

    def test_a_listing_at_its_limit_files_nothing(self) -> None:
        result, log = self.run_script([{"number": n, "title": "another"} for n in range(1000)])
        self.assertEqual(1, result.returncode)
        self.assertIn("reached its limit", result.stdout)
        self.assertNotIn("issue create", log)

    def test_it_reads_this_run_s_jobs(self) -> None:
        _, log = self.run_script([])
        self.assertIn("api --paginate repos/a/h/actions/runs/9/jobs", log)

    def test_a_job_past_its_limit_files_one(self) -> None:
        result, log = self.run_script([], json.dumps({"jobs": [PAST_ITS_LIMIT, PASSED]}))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("issue create", log)

    def test_a_superseded_job_alone_files_nothing_and_says_so(self) -> None:
        result, log = self.run_script([], json.dumps({"jobs": [SUPERSEDED, PASSED]}))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("::notice::", result.stdout)
        self.assertNotIn("issue ", log)

    def test_a_superseded_job_does_not_hide_a_failed_one(self) -> None:
        _, log = self.run_script([], json.dumps({"jobs": [SUPERSEDED, FAILED]}))
        self.assertIn("issue create", log)

    def test_a_red_job_on_a_later_page_is_heard(self) -> None:
        # `--paginate` writes one object per page, so the filter has to read a stream of them.
        pages = json.dumps({"jobs": [SUPERSEDED]}) + json.dumps({"jobs": [FAILED]})
        _, log = self.run_script([], pages)
        self.assertIn("issue create", log)

    def test_an_unread_job_list_fails_the_step_and_files_nothing(self) -> None:
        # No answer is not the all-clear a run of superseded jobs gets.
        result, log = self.run_script([], "", api_exit=1)
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("::notice::", result.stdout)
        self.assertNotIn("issue ", log)


class TheTitleIsNotMainIsRed(unittest.TestCase):
    def test_the_helper_step_6_reads_does_not_stop_on_it(self) -> None:
        # README decides a red sync stops no landing, and `main-red-open.sh`'s rule on the title is what decides that.
        bash = shutil.which("bash")
        self.assertIsNotNone(bash, "bash is what the helper runs under")
        with tempfile.TemporaryDirectory() as directory:
            _stub_dir(directory)
            env = {**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"],
                   "STUB_LOG": (Path(directory) / "log").as_posix(),
                   "STUB_ROWS": json.dumps([{"number": 7, "title": _title(), "url": "u"}])}
            result = subprocess.run([bash, str(HELPER)], capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout)


if __name__ == "__main__":
    unittest.main()
