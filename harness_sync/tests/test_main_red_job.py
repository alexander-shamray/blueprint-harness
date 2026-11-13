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

    def test_main_runs_cancel_nothing_so_cancelled_is_never_a_superseded_push(self) -> None:
        # What lets `cancelled` read as red: a run on `main` has a group of its own and no newer run replaces it.
        code = "\n".join(line for line in CI.read_text(encoding="utf-8").splitlines()
                         if not line.lstrip().startswith("#"))
        self.assertIn("github.ref == 'refs/heads/main' && github.sha", code)
        self.assertIn("cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}", code)


RERUN = ROOT / ".github" / "workflows" / "main-red-rerun.yml"


def _condition(job: str) -> str:
    return " ".join(re.search(r"^    if: >-\n((?:      .+\n)+)", job, re.MULTILINE).group(1).split())


def _script(job: str) -> str:
    """The job's one `run: |` block, dedented as the runner hands it to bash."""
    # `_jobs` drops the newline that ends a job, and with it the block's last line.
    found = re.search(r"^        run: \|\n((?:          .*\n|\s*\n)+)", job + "\n", re.MULTILINE)
    return "\n".join(line[10:] for line in found.group(1).splitlines()) + "\n"


class AFirstAttemptIsRerunBeforeAnythingIsFiled(unittest.TestCase):
    def setUp(self) -> None:
        self.text = RERUN.read_text(encoding="utf-8")
        self.job = _jobs(RERUN)["rerun"]

    def test_main_red_files_from_a_second_attempt_alone(self) -> None:
        # A first attempt that filed would stop every /ship on a flake the rerun is about to turn green.
        self.assertIn("github.run_attempt != '1'", _condition(_jobs()["main-red"]))

    def test_the_rerun_hears_the_first_attempt_of_a_red_push_run_of_ci_on_main(self) -> None:
        ci_name = re.search(r"^name: (.+)$", CI.read_text(encoding="utf-8"), re.MULTILINE).group(1)
        # `workflow_run` matches by name, so a renamed ci.yml would leave this workflow hearing nothing.
        self.assertIn(f"workflows: [{ci_name}]", self.text)
        self.assertIn("types: [completed]", self.text)
        self.assertIn("branches: [main]", self.text)
        condition = _condition(self.job)
        self.assertIn("github.event.workflow_run.event == 'push'", condition)
        self.assertIn("github.event.workflow_run.run_attempt == 1", condition)
        for conclusion in ("failure", "cancelled", "timed_out", "startup_failure"):
            self.assertIn(f'"{conclusion}"', condition)

    def test_it_holds_the_grants_a_rerun_and_a_comment_need_and_no_more(self) -> None:
        self.assertRegex(self.text, r"(?m)^permissions: \{\}$")
        grants = re.search(r"^    permissions:\n((?:      .+\n)+)", self.job, re.MULTILINE).group(1).split()
        self.assertEqual(["actions:", "write", "issues:", "write"], grants)

    def test_it_files_under_the_title_label_and_group_main_red_does(self) -> None:
        main_red = _jobs()["main-red"]
        self.assertEqual(re.search(r"title='([^']+)'", main_red).group(1), re.search(r"title='([^']+)'", self.job).group(1))
        group = re.compile(r"^      group: (.+)$", re.MULTILINE)
        self.assertEqual(group.search(main_red).group(1), group.search(self.job).group(1))
        create = next(line for line in self.job.splitlines() if "gh issue create" in line)
        self.assertIn("--label bug", create, "the helper lists bug issues alone")


class TheRerunStep(unittest.TestCase):
    """The step's own script, run under a `gh` stub that answers what GitHub would."""

    JOBS = json.dumps({"jobs": [
        {"name": "sync-tool", "conclusion": "success", "steps": [{"name": "Test", "conclusion": "success"}]},
        {"name": "payload-suites (macos-latest)", "conclusion": "failure",
         "steps": [{"name": "Checkout", "conclusion": "success"}, {"name": "Run the suites", "conclusion": "failure"}]},
        {"name": "payload-suites (windows-latest)", "conclusion": "cancelled", "steps": []},
        {"name": "main-red", "conclusion": "skipped", "steps": []}]})

    def run_step(self, rerun_exit: int, tracker: list, bugs: list) -> tuple[int, str, str]:
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
            log = Path(directory) / "log"
            log.write_text("", encoding="utf-8")
            env = {**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"], "STUB_LOG": log.as_posix(),
                   "STUB_JOBS": self.JOBS, "STUB_RERUN": str(rerun_exit), "STUB_TRACKER": json.dumps(tracker),
                   "STUB_BUGS": json.dumps(bugs), "RUN_ID": "41", "RUN_URL": "https://run/41",
                   "HEAD_SHA": "abc123", "CONCLUSION": "failure"}
            done = subprocess.run([bash, "-c", _script(_jobs(RERUN)["rerun"])], capture_output=True, text=True,
                                  encoding="utf-8", env=env, stdin=subprocess.DEVNULL)
            return done.returncode, log.read_text(encoding="utf-8"), done.stdout + done.stderr

    def test_a_rerun_files_nothing_and_writes_each_failed_job_and_step_on_the_tracker(self) -> None:
        code, log, output = self.run_step(0, [{"number": 156, "title": "Flaky tests tracker"}], [])
        self.assertEqual(0, code, output)
        self.assertIn("gh run rerun 41 --failed", log)
        self.assertNotIn("issue create", log)
        self.assertIn("gh issue comment 156 --body-file -", log)
        self.assertIn("- `payload-suites (macos-latest)` (failure): `Run the suites`", log)
        self.assertIn("- `payload-suites (windows-latest)` (cancelled): no step failed", log)
        self.assertNotIn("`sync-tool`", log)
        self.assertNotIn("`main-red`", log)
        self.assertIn("https://run/41", log)

    def test_no_tracker_is_a_warning_and_the_rerun_still_stands(self) -> None:
        code, log, output = self.run_step(0, [], [])
        self.assertEqual(0, code, output)
        self.assertIn("gh run rerun 41 --failed", log)
        self.assertNotIn("issue comment", log)
        self.assertIn("::warning::", output)

    def test_a_refused_rerun_files_main_is_red_rather_than_staying_silent(self) -> None:
        code, log, _ = self.run_step(1, [{"number": 156, "title": "Flaky tests tracker"}], [])
        self.assertEqual(1, code)
        self.assertIn("gh issue create --title main is red: ci --label bug", log)
        self.assertIn("could not be rerun: https://run/41", log)
        self.assertNotIn("issue comment", log)

    def test_a_refused_rerun_comments_on_an_open_main_is_red_rather_than_filing_a_second(self) -> None:
        code, log, _ = self.run_step(1, [], [{"number": 7, "title": "main is red: ci"}])
        self.assertEqual(1, code)
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
