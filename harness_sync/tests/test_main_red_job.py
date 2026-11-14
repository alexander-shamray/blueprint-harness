"""The harness's own `main-red` job, read as `ci.yml` writes it and fed to the helper that reads what it files."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
HELPER = ROOT / "payload" / ".claude" / "scripts" / "main-red-open.sh"


def _jobs(workflow: Path = CI) -> dict[str, str]:
    """Each job's text by id, with its comment lines left out."""
    text = workflow.read_text(encoding="utf-8").split("\njobs:\n", 1)[1]
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    parts = re.split(r"^  ([\w-]+):$", code, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2]))


class TheJobHearsEveryOtherJob(unittest.TestCase):
    def setUp(self) -> None:
        self.jobs = _jobs()
        self.job = self.jobs["main-red"]

    def test_needs_names_every_other_job(self) -> None:
        # A job added to ci.yml and left out of this list could go red on `main` with nobody told.
        needs = re.search(r"^    needs: \[(.+)\]$", self.job, re.MULTILINE)
        self.assertIsNotNone(needs, "main-red spells no one-line needs")
        self.assertEqual(sorted(set(self.jobs) - {"main-red"}), sorted(n.strip() for n in needs.group(1).split(",")))

    def test_a_cancelled_need_files_as_a_failed_one_does(self) -> None:
        # GitHub reports a job past its timeout, or that no runner picked up, as `cancelled`, and `failure()` is false
        # for that, so the condition must read the needs' results and start past one that did not succeed.
        condition = " ".join(re.search(r"^    if: >-\n((?:      .+\n)+)", self.job, re.MULTILINE).group(1).split())
        self.assertIn("always()", condition)
        self.assertIn("github.event_name == 'push'", condition)
        self.assertIn("contains(needs.*.result, 'failure')", condition)
        self.assertIn("contains(needs.*.result, 'cancelled')", condition)
        self.assertNotIn("failure()", condition)

    def test_every_job_in_every_workflow_is_bounded(self) -> None:
        # An unbounded job runs to GitHub's 360-minute default: a hung suite holds a required check that long, and
        # main-red, which waits on its needs, files nothing until it ends. Read from the directory, so a job or a
        # workflow added later is held too.
        workflows = sorted(p for p in (ROOT / ".github" / "workflows").iterdir() if p.suffix in {".yml", ".yaml"})
        self.assertIn(CI, workflows)
        for workflow in workflows:
            for job, text in _jobs(workflow).items():
                with self.subTest(workflow=workflow.name, job=job):
                    self.assertRegex(text, r"(?m)^    timeout-minutes: [1-9]\d*$")

    def test_main_runs_cancel_nothing_so_cancelled_is_never_a_superseded_push(self) -> None:
        # What lets `cancelled` read as red: a run on `main` has a group of its own and no newer run replaces it.
        code = "\n".join(line for line in CI.read_text(encoding="utf-8").splitlines()
                         if not line.lstrip().startswith("#"))
        self.assertIn("github.ref == 'refs/heads/main' && github.sha", code)
        self.assertIn("cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}", code)


RERUN = ROOT / ".github" / "workflows" / "main-red-rerun.yml"


def _code(workflow: Path) -> str:
    """The workflow's text with its comment lines left out, so a comment cannot stand in for a key."""
    return "\n".join(line for line in workflow.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("#"))


def _condition(job: str) -> str:
    """A job's `if:`, folded to one line, whether written as a block or on the key's own line."""
    block = re.search(r"^    if: >-\n((?:      .+\n)+)", job, re.MULTILINE)
    return " ".join((block.group(1) if block else re.search(r"^    if: (.+)$", job, re.MULTILINE).group(1)).split())


def _grants(job: str) -> list[str]:
    return re.search(r"^    permissions:\n((?:      .+\n)+)", job, re.MULTILINE).group(1).split()


def _group(job: str) -> str | None:
    found = re.search(r"^    concurrency:\n      group: (.+)$", job, re.MULTILINE)
    return found.group(1) if found else None


def _script(job: str) -> str:
    """The job's one `run: |` block, dedented as the runner hands it to bash."""
    # `_jobs` drops the newline that ends a job, and with it the block's last line.
    found = re.search(r"^        run: \|\n((?:          .*\n|\s*\n)+)", job + "\n", re.MULTILINE)
    return "\n".join(line[10:] for line in found.group(1).splitlines()) + "\n"


class AFirstAttemptIsRerunBeforeAnythingIsFiled(unittest.TestCase):
    def setUp(self) -> None:
        self.jobs = _jobs(RERUN)

    def test_main_red_files_from_a_later_attempt_alone(self) -> None:
        # A first attempt that filed would stop every /ship on a flake the rerun is about to turn green.
        self.assertIn("github.run_attempt != '1'", _condition(_jobs()["main-red"]))

    def test_the_rerun_hears_the_first_attempt_of_a_red_push_run_of_ci_on_main(self) -> None:
        ci_name = re.search(r"^name: (.+)$", _code(CI), re.MULTILINE).group(1)
        trigger = re.search(r"^on:\n((?:  .*\n)+)", _code(RERUN) + "\n", re.MULTILINE)
        self.assertIsNotNone(trigger, "the workflow spells no `on:` block")
        # `workflow_run` matches by name, so a renamed ci.yml would leave this workflow hearing nothing.
        self.assertEqual(["  workflow_run:", f"    workflows: [{ci_name}]", "    types: [completed]",
                          "    branches: [main]"], trigger.group(1).splitlines())
        condition = _condition(self.jobs["rerun"])
        self.assertIn("github.event.workflow_run.event == 'push'", condition)
        self.assertIn("github.event.workflow_run.run_attempt == 1", condition)
        for conclusion in ("failure", "cancelled", "timed_out", "startup_failure"):
            self.assertIn(f'"{conclusion}"', condition)

    def test_each_job_holds_the_grants_it_needs_and_no_more(self) -> None:
        self.assertRegex(_code(RERUN), r"(?m)^permissions: \{\}$")
        self.assertEqual(["actions:", "write", "issues:", "write"], _grants(self.jobs["rerun"]))
        self.assertEqual(["issues:", "write"], _grants(self.jobs["file"]))

    def test_the_rerun_sits_in_no_group_a_newer_job_could_cancel_it_from(self) -> None:
        # GitHub cancels a group's pending job when a newer one queues; a cancelled rerun would leave a red first
        # attempt neither rerun nor filed.
        self.assertIsNone(_group(self.jobs["rerun"]))

    def test_a_rerun_not_started_is_filed_under_the_title_label_and_group_main_red_does(self) -> None:
        main_red, file = _jobs()["main-red"], self.jobs["file"]
        self.assertIn("needs: rerun", file)
        self.assertEqual("always() && needs.rerun.result != 'skipped' && needs.rerun.outputs.started != 'true'",
                         _condition(file))
        self.assertEqual(re.search(r"title='([^']+)'", main_red).group(1), re.search(r"title='([^']+)'", file).group(1))
        self.assertEqual(_group(main_red), _group(file))
        create = next(line for line in file.splitlines() if "gh issue create" in line)
        self.assertIn("--label bug", create, "the helper lists bug issues alone")


class Stubbed(unittest.TestCase):
    """A job's own script, run under a `gh` stub that answers what GitHub would."""

    def run_job(self, job: str, env: dict[str, str], rerun_exit: int = 0, tracker: list | None = None,
                bugs: list | None = None) -> tuple[int, str, str, str]:
        bash = shutil.which("bash")
        self.assertIsNotNone(bash, "bash is what the step runs under")
        self.assertIsNotNone(shutil.which("jq"), "jq is what the step reads with")
        with tempfile.TemporaryDirectory() as directory:
            stub = Path(directory) / "gh"
            stub.write_text(
                "#!/usr/bin/env bash\n"
                'printf "gh %s\\n" "$*" >> "$STUB_LOG"\n'
                'case "$1 $2" in\n'
                '  "run view") while [ $# -gt 0 ]; do [ "$1" != --jq ] || { jq -r "$2" <<<"$STUB_JOBS"; exit; }; shift; done ;;\n'
                '  "run rerun") exit "$STUB_RERUN" ;;\n'
                '  "issue list") case "$*" in *flaky*) printf "%s" "$STUB_TRACKER" ;; *) printf "%s" "$STUB_BUGS" ;; esac ;;\n'
                '  "issue comment"|"issue create") cat >> "$STUB_LOG" ;;\n'
                "esac\n", encoding="utf-8", newline="\n")
            stub.chmod(0o755)
            log, output = Path(directory) / "log", Path(directory) / "output"
            log.write_text("", encoding="utf-8")
            output.write_text("", encoding="utf-8")
            env = {**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"], "STUB_LOG": log.as_posix(),
                   "GITHUB_OUTPUT": output.as_posix(), "STUB_RERUN": str(rerun_exit),
                   "STUB_TRACKER": json.dumps(tracker or []), "STUB_BUGS": json.dumps(bugs or []),
                   "RUN_ID": "41", "RUN_URL": "https://run/41", "HEAD_SHA": "abc123", "CONCLUSION": "failure", **env}
            done = subprocess.run([bash, "-c", _script(_jobs(RERUN)[job])], capture_output=True, text=True,
                                  encoding="utf-8", env=env, stdin=subprocess.DEVNULL)
            return (done.returncode, log.read_text(encoding="utf-8"), output.read_text(encoding="utf-8"),
                    done.stdout + done.stderr)


class TheRerunStep(Stubbed):
    JOBS = json.dumps({"jobs": [
        {"name": "sync-tool", "conclusion": "success", "steps": [{"name": "Test", "conclusion": "success"}]},
        {"name": "payload-suites (macos-latest)", "conclusion": "failure",
         "steps": [{"name": "Checkout", "conclusion": "success"}, {"name": "Run the suites", "conclusion": "failure"}]},
        {"name": "payload-suites (windows-latest)", "conclusion": "cancelled", "steps": []},
        {"name": "main-red", "conclusion": "skipped", "steps": []}]})

    def run_step(self, rerun_exit: int, tracker: list | None = None) -> tuple[int, str, str, str]:
        return self.run_job("rerun", {"STUB_JOBS": self.JOBS}, rerun_exit, tracker)

    def test_a_rerun_files_nothing_and_writes_each_failed_job_and_step_on_the_tracker(self) -> None:
        code, log, output, out = self.run_step(0, [{"number": 156, "title": "Flaky tests tracker"}])
        self.assertEqual(0, code, out)
        self.assertIn("gh run rerun 41 --failed", log)
        self.assertIn("started=true", output.splitlines())
        self.assertNotIn("issue create", log)
        self.assertIn("gh issue comment 156 --body-file -", log)
        self.assertIn("- `payload-suites (macos-latest)` (failure): `Run the suites`", log)
        self.assertIn("- `payload-suites (windows-latest)` (cancelled): no step failed", log)
        self.assertNotIn("`sync-tool`", log)
        self.assertNotIn("`main-red`", log)
        self.assertIn("https://run/41", log)

    def test_no_tracker_is_a_warning_and_the_rerun_still_stands(self) -> None:
        code, log, output, out = self.run_step(0)
        self.assertEqual(0, code, out)
        self.assertIn("gh run rerun 41 --failed", log)
        self.assertIn("started=true", output.splitlines())
        self.assertNotIn("issue comment", log)
        self.assertIn("::warning::", out)

    def test_a_refused_rerun_says_it_did_not_start_and_hands_file_the_failed_jobs(self) -> None:
        code, log, output, out = self.run_step(1, [{"number": 156, "title": "Flaky tests tracker"}])
        self.assertEqual(0, code, out)
        self.assertNotIn("started=true", output)
        self.assertIn("- `payload-suites (macos-latest)` (failure): `Run the suites`", output)
        self.assertNotIn("issue comment", log)
        self.assertNotIn("issue create", log)


class TheFileStep(Stubbed):
    def test_it_files_main_is_red_with_the_failed_jobs_the_rerun_read(self) -> None:
        code, log, _, out = self.run_job("file", {"FAILED": "- `payload-suites (macos-latest)` (failure): `Run`"})
        self.assertEqual(0, code, out)
        self.assertIn("gh issue create --title main is red: ci --label bug", log)
        self.assertIn("were not rerun: https://run/41", log)
        self.assertIn("- `payload-suites (macos-latest)` (failure): `Run`", log)

    def test_it_comments_on_an_open_main_is_red_rather_than_filing_a_second(self) -> None:
        code, log, _, out = self.run_job("file", {"FAILED": ""}, bugs=[{"number": 7, "title": "main is red: ci"}])
        self.assertEqual(0, code, out)
        self.assertIn("gh issue comment 7 --body Red again at abc123", log)
        self.assertNotIn("issue create", log)


class TheHelperReadsWhatTheJobFiles(unittest.TestCase):
    def test_the_title_and_the_label_are_ones_the_helper_stops_on(self) -> None:
        job = _jobs()["main-red"]
        title = re.search(r"title='([^']+)'", job).group(1)
        create = next(line for line in job.splitlines() if "gh issue create" in line)
        self.assertIn("--label bug", create, "the helper lists bug issues alone")
        self.assertIn('--title "$title"', create)
        bash = shutil.which("bash")
        self.assertIsNotNone(bash, "bash is what the helper runs under")
        with tempfile.TemporaryDirectory() as directory:
            stub = Path(directory) / "gh"
            # The helper confirms each listed number's own state, which `issue view` answers and the listing does not.
            stub.write_text('#!/usr/bin/env bash\n[ "$2" != view ] || { echo OPEN; exit 0; }\nprintf "%s" "$STUB_ROWS"\n',
                            encoding="utf-8", newline="\n")
            stub.chmod(0o755)
            env = {**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"],
                   "STUB_ROWS": json.dumps([{"number": 7, "title": title, "url": "u"}])}
            result = subprocess.run([bash, str(HELPER)], capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(3, result.returncode, result.stderr)
        self.assertEqual("main is red: #7 u\n", result.stdout)


if __name__ == "__main__":
    unittest.main()
