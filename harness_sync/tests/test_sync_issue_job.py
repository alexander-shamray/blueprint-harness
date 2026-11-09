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


def _red() -> str:
    return _jobs(SYNC)["sync-red"]


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
        needs = re.search(r"^    needs: \[(.+)\]$", jobs["sync-red"], re.MULTILINE)
        self.assertIsNotNone(needs, "sync-red spells no one-line needs")
        self.assertEqual(sorted(set(jobs) - {"sync-red", "sync-issue"}),
                         sorted(n.strip() for n in needs.group(1).split(",")))
        self.assertRegex(jobs["sync-issue"], r"(?m)^    needs: \[sync-red\]$")

    def test_the_condition_reaches_the_step_for_a_cancelled_job_but_not_a_cancelled_run(self) -> None:
        # Measured on run 42575459566: at a job's limit `failure()` and `cancelled()` are both false, so neither hears
        # it, and `!cancelled()` is true there and false only for a run somebody cancels whole.
        self.assertIn(
            "if: ${{ !cancelled() && (contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled')) }}",
            _red())
        self.assertNotIn("always()", _red())

    def test_a_run_read_as_not_red_cannot_take_a_waiting_issue_job_s_place(self) -> None:
        # A group keeps one waiting job, so a run that found nothing red and entered it could cancel a red run's.
        self.assertRegex(_job(), r"(?m)^      group: sync-issue$")
        self.assertNotIn("concurrency:", _red())
        self.assertIn(
            "if: ${{ !cancelled() && (needs.sync-red.result == 'failure' || needs.sync-red.result == 'cancelled'"
            " || needs.sync-red.outputs.red == 'true') }}",
            _job())
        self.assertRegex(_red(), r"(?m)^      red: \$\{\{ steps\.read\.outputs\.red \}\}$")
        self.assertRegex(_red(), r"(?m)^        id: read$")

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
        for job in (_job(), _red()):
            self.assertNotIn("environment:", job)
            self.assertNotIn("secrets.", job)
        self.assertRegex(_job(), r"(?m)^    permissions:\n      issues: write\n    steps:$")
        self.assertRegex(_red(), r"(?m)^    permissions:\n      actions: read\n    outputs:$")


class _StepCase(unittest.TestCase):
    def run_step(self, job: str, rows: list[dict[str, object]] | None = None, jobs: str = "",
                 api_exit: int = 0) -> tuple[subprocess.CompletedProcess[str], str, str]:
        """The job's step's result, each `gh` line it ran and what it wrote for its outputs, its stub given `rows` for
        the listing and `jobs` for the run."""
        bash = shutil.which("bash")
        self.assertIsNotNone(bash, "bash is what the job's step runs under")
        # `_jobs` leaves a job's text with no final newline, so the step's last line may end at the end of the text.
        script = textwrap.dedent(re.search(r"run: \|\n((?: {10}.*(?:\n|$)|\n)+)", job).group(1))
        with tempfile.TemporaryDirectory() as directory:
            root = _stub_dir(directory)
            log = root / "log"
            log.touch()
            output = root / "output"
            output.touch()
            path = root / "step.sh"
            path.write_text(script, encoding="utf-8", newline="\n")
            env = {**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"],
                   "STUB_LOG": log.as_posix(), "STUB_ROWS": json.dumps(rows or []), "STUB_JOBS": jobs,
                   "STUB_API_EXIT": str(api_exit), "GH_REPO": "a/h", "GITHUB_RUN_ID": "9",
                   "GITHUB_OUTPUT": output.as_posix(), "GITHUB_SHA": "abc123", "RUN_URL": "https://run"}
            result = subprocess.run([bash, path.as_posix()], capture_output=True, text=True, encoding="utf-8", env=env)
            return result, log.read_text(encoding="utf-8"), output.read_text(encoding="utf-8")


class TheRedJobTellsThemApart(_StepCase):
    def read(self, *pages: dict[str, object], api_exit: int = 0) -> tuple[subprocess.CompletedProcess[str], str, str]:
        return self.run_step(_red(), jobs="".join(json.dumps(page) for page in pages), api_exit=api_exit)

    def test_it_reads_this_run_s_jobs(self) -> None:
        _, log, _ = self.read({"jobs": [FAILED]})
        self.assertIn("api --paginate repos/a/h/actions/runs/9/jobs", log)

    def test_a_job_past_its_limit_is_red(self) -> None:
        result, _, output = self.read({"jobs": [PAST_ITS_LIMIT, PASSED]})
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("red=true\n", output)

    def test_a_superseded_job_alone_is_not_red_and_says_so(self) -> None:
        result, _, output = self.read({"jobs": [SUPERSEDED, PASSED]})
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("::notice::", result.stdout)
        self.assertEqual("", output)

    def test_a_superseded_job_does_not_hide_a_failed_one(self) -> None:
        _, _, output = self.read({"jobs": [SUPERSEDED, FAILED]})
        self.assertEqual("red=true\n", output)

    def test_a_red_job_on_a_later_page_is_heard(self) -> None:
        # `--paginate` writes one object per page, so the filter has to read a stream of them.
        _, _, output = self.read({"jobs": [SUPERSEDED]}, {"jobs": [FAILED]})
        self.assertEqual("red=true\n", output)

    def test_an_unread_job_list_fails_the_step_and_gives_no_all_clear(self) -> None:
        # The issue job hears this failure, because no answer is not the all-clear a run of superseded jobs gets.
        result, _, output = self.read(api_exit=1)
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("::notice::", result.stdout)
        self.assertEqual("", output)


class TheScriptFilesOneIssue(_StepCase):
    def run_script(self, rows: list[dict[str, object]]) -> tuple[subprocess.CompletedProcess[str], str]:
        """The issue job's step's result and each `gh` line it ran."""
        result, log, _ = self.run_step(_job(), rows)
        return result, log

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
