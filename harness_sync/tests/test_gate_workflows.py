"""The payload's gate workflow: one job per pull-request event, nothing the pull request wrote running before every
verdict is posted, and each verdict posted under the check name a ruleset requires."""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / "payload" / ".github" / "workflows"
GATES_YML = WORKFLOWS / "gates.yml"
# The check names the rulesets require, each its gate's directory under .github/.
CHECKS = {"closure-gate", "comment-gate", "commit-gate", "harness-drift"}
# A judge sits outside the checkout; the comment gate holds its path in `$judge`.
JUDGE = re.compile(r'(?<![-\w])python(?: -I)? "\$(?:RUNNER_TEMP/[\w./-]+\.py|judge)"')
# Reads no module from the checkout: how the drift gate reads its manifest ahead of the judge.
ISOLATED = re.compile(r"(?<![-\w])python -I -c\b")
# A list of spellings, so an interpreter it does not name reads as nothing: a command whose first word is a path, a
# shell handed a file, Python, a local action, or any step set to run inside the checkout.
HEAD_CODE = re.compile(
    r"(?<![-\w])python3?(?:\.\d+)?(?=\s)|\bpytest\b|\bunittest\b"
    r"|(?<![-\w])(?:bash|sh|source)[ \t]+\S|^\s*(?:- )?(?:run: )?[\w./-]*/[\w./-]+"
    r"|^\s*(?:- )?uses: \./|^\s*working-directory:", re.M)
REPORT = re.compile(r"(?m)^ +(?:- )?id: report$")


def steps_of(text: str) -> list[str]:
    """The one job's steps, comments dropped; a second job has to be argued here rather than read past."""
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    jobs = code.split("\n    steps:\n")
    if len(jobs) != 2:
        raise ValueError(f"expected one job's steps, found {len(jobs) - 1}")
    return re.split(r"\n(?=      - )", jobs[1])


def report_at(steps: list[str]) -> int:
    at = [i for i, step in enumerate(steps) if REPORT.search(step)]
    if len(at) != 1:
        raise ValueError(f"expected one step posting the verdicts, found {len(at)}")
    if not any(JUDGE.search(step) for step in steps[:at[0]]):
        raise ValueError("expected a judge ahead of the report")
    return at[0]


def runs_head_code(step: str) -> bool:
    return bool(HEAD_CODE.search(JUDGE.sub("", ISOLATED.sub("", step))))


def name_of(step: str) -> str:
    found = re.search(r"name: (.+)", step)
    return found.group(1) if found else step.splitlines()[0].strip()


def head_code_before_the_report(text: str) -> list[str]:
    steps = steps_of(text)
    return [name_of(step) for step in steps[:report_at(steps) + 1] if runs_head_code(step)]


def workflow(*steps: str) -> str:
    body = "\n".join(f"      - name: step {i}\n{step}" for i, step in enumerate(steps))
    return f"name: Gate\njobs:\n  gate:\n    runs-on: ubuntu-latest\n    steps:\n{body}\n"


def run_block(step: str) -> str:
    lines = step.split("\n")
    at = next(i for i, line in enumerate(lines) if line.strip() == "run: |")
    return "\n".join(line[10:] for line in lines[at + 1:]) + "\n"


JUDGES = '        run: python "$RUNNER_TEMP/gate/gate.py"'
REPORTS = "        id: report\n        run: true"


class TheJobs(unittest.TestCase):
    def test_each_pull_request_event_starts_one_job(self) -> None:
        # The account's concurrency cap is the queue: a gate a job each was a runner slot and a queue wait each.
        started: dict[str, list[str]] = {}
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            types = re.search(r"(?m)^  pull_request:\n    types: \[([^\]]+)\]$", text)
            if types is None:
                continue
            jobs = re.findall(r"(?m)^  ([\w-]+):$", text.split("\njobs:\n", 1)[1])
            for event in (t.strip() for t in types.group(1).split(",")):
                started.setdefault(event, []).extend(f"{path.name}:{job}" for job in jobs)
        self.assertEqual({"opened", "synchronize", "reopened", "edited", "labeled", "unlabeled"}, set(started))
        for event, jobs in started.items():
            with self.subTest(event=event):
                self.assertEqual(["gates.yml:gates"], jobs)

    def test_one_gate_failing_does_not_skip_the_next(self) -> None:
        # A step's default condition is success(), so one red gate would leave every later verdict unposted.
        steps = steps_of(GATES_YML.read_text(encoding="utf-8"))
        event = next(i for i, step in enumerate(steps) if "id: event" in step)
        for step in steps[event + 1:]:
            with self.subTest(step=name_of(step)):
                self.assertRegex(step, r"(?m)^        if: \$\{\{ !cancelled\(\) ")

    def test_the_checkout_leaves_no_token_for_head_code(self) -> None:
        first = steps_of(GATES_YML.read_text(encoding="utf-8"))[0]
        self.assertIn("actions/checkout", first)
        self.assertIn("persist-credentials: false", first)


class TheOrder(unittest.TestCase):
    def test_nothing_the_head_wrote_runs_before_the_report(self) -> None:
        self.assertEqual([], head_code_before_the_report(GATES_YML.read_text(encoding="utf-8")))

    def test_each_gate_still_runs_its_suite_after_the_report(self) -> None:
        # Moving a suite past the report is the fix; deleting it would pass the case above.
        steps = steps_of(GATES_YML.read_text(encoding="utf-8"))
        suites = [step for step in steps[report_at(steps) + 1:] if "python -m unittest" in step]
        found = [re.search(r"working-directory: \.github/(\S+)", step) for step in suites]
        self.assertNotIn(None, found)
        self.assertEqual(sorted(CHECKS), sorted(match.group(1) for match in found))

    def test_the_report_posts_every_check_a_ruleset_requires(self) -> None:
        report = steps_of(GATES_YML.read_text(encoding="utf-8"))
        report = report[report_at(report)]
        self.assertEqual(sorted(CHECKS), sorted(re.findall(r"(?m)^          verdict ([\w-]+) \$", report)))


class TheReport(unittest.TestCase):
    """The report step's script, run as written with `gh` stubbed, for the verdicts it posts."""

    @classmethod
    def setUpClass(cls) -> None:
        steps = steps_of(GATES_YML.read_text(encoding="utf-8"))
        cls.script = run_block(steps[report_at(steps)])
        cls.bash = shutil.which("bash")
        if cls.bash is None:
            raise RuntimeError("bash is what the report step runs under")  # not a skip: a skip passes unrun

    def post(self, *, gh_rc: int = 0, **gates: str) -> tuple[int, list[dict[str, str]], str]:
        env_of = {"closure-gate": "CLOSURE_GATE", "commit-gate": "COMMIT_GATE",
                  "harness-drift": "HARNESS_DRIFT", "comment-gate": "COMMENT_GATE"}
        values = {name: "true success" for name in env_of}
        values.update({name.replace("_", "-"): value for name, value in gates.items()})
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "posts"
            stub = Path(directory) / "gh"
            # Each post's -f fields a line each, then a line of its own ending the post.
            stub.write_text(
                '#!/usr/bin/env bash\nwhile [ "$#" -gt 0 ]; do\n'
                '  if [ "$1" = -f ]; then printf "%s\\n" "$2" >> "$POSTS"; shift; fi; shift\ndone\n'
                'echo -- >> "$POSTS"\nexit "$STUB_RC"\n', encoding="utf-8", newline="\n")
            stub.chmod(0o755)
            env = {**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"], "POSTS": str(log),
                   "STUB_RC": str(gh_rc), "GH_TOKEN": "t", "REPO": "o/r", "HEAD_SHA": "f" * 40, "RUN_URL": "u",
                   **{env_of[name]: value for name, value in values.items()}}
            done = subprocess.run([self.bash, "-c", self.script], capture_output=True, text=True, encoding="utf-8",
                                  env=env)
            text = log.read_text(encoding="utf-8") if log.exists() else ""
            posts = [dict(line.split("=", 1) for line in post.splitlines() if line) for post in text.split("--\n")[:-1]]
        return done.returncode, posts, done.stdout + done.stderr

    def test_every_gate_that_passed_is_posted_as_a_success(self) -> None:
        rc, posts, out = self.post()
        self.assertEqual(0, rc, out)
        self.assertEqual(sorted(CHECKS), sorted(post["name"] for post in posts))
        for post in posts:
            self.assertEqual(("completed", "success", "f" * 40), (post["status"], post["conclusion"], post["head_sha"]))

    def test_one_failed_step_posts_its_gate_as_a_failure_and_fails_the_step(self) -> None:
        rc, posts, out = self.post(harness_drift="true success failure skipped")
        self.assertEqual(1, rc, out)
        conclusions = {post["name"]: post["conclusion"] for post in posts}
        self.assertEqual("failure", conclusions.pop("harness-drift"))
        self.assertEqual({"success"}, set(conclusions.values()))

    def test_a_gate_this_event_does_not_run_posts_nothing(self) -> None:
        # An `edited` run must not overwrite the commit gate's verdict from the push.
        rc, posts, out = self.post(commit_gate="false skipped skipped skipped", harness_drift="false skipped",
                                   comment_gate="false skipped")
        self.assertEqual(0, rc, out)
        self.assertEqual(["closure-gate"], [post["name"] for post in posts])

    def test_a_missing_decision_posts_nothing_and_fails(self) -> None:
        # The event step failed: no output, so the outcomes come first and are no decision.
        rc, posts, out = self.post(closure_gate=" skipped skipped")
        self.assertEqual(1, rc, out)
        self.assertNotIn("closure-gate", [post["name"] for post in posts])

    def test_a_gate_with_no_outcomes_is_a_failure(self) -> None:
        rc, posts, out = self.post(comment_gate="true")
        self.assertEqual(1, rc, out)
        self.assertIn({"name": "comment-gate", "conclusion": "failure"},
                      [{"name": p["name"], "conclusion": p["conclusion"]} for p in posts])

    def test_a_post_that_fails_fails_the_step(self) -> None:
        rc, _, out = self.post(gh_rc=1)
        self.assertEqual(1, rc, out)
        self.assertIn("could not post", out)


class TheReader(unittest.TestCase):
    """What the order cases lean on, against workflows that are wrong on purpose."""

    def test_each_spelling_of_head_code_before_the_report_is_named(self) -> None:
        for spelling in ("        run: python -m unittest",
                         "        run: python .github/gate/test_gate.py",
                         "        run: python3 -m pytest",
                         "        run: python3.12 .github/gate/test_gate.py",
                         "        run: bash .github/gate/suite.sh",
                         "        run: sh .github/gate/suite.sh",
                         "        run: source .github/gate/suite.sh",
                         "        run: ./.github/gate/suite.sh",
                         "        run: .github/gate/suite.sh",
                         "        run: |\n          set -e\n          .github/gate/suite.sh",
                         "        uses: ./.github/actions/suite",
                         "        working-directory: .github/gate\n        run: make"):
            with self.subTest(spelling=spelling):
                self.assertEqual(["step 1"], head_code_before_the_report(workflow(JUDGES, spelling, REPORTS)))

    def test_a_path_run_by_a_nameless_step_is_named(self) -> None:
        text = ("jobs:\n  gate:\n    steps:\n"
                '      - run: python "$RUNNER_TEMP/gate/gate.py"\n      - run: ./.github/gate/suite.sh\n'
                "      - id: report\n        run: true\n")
        self.assertEqual(["- run: ./.github/gate/suite.sh"], head_code_before_the_report(text))

    def test_the_same_code_after_the_report_is_not_named(self) -> None:
        self.assertEqual([], head_code_before_the_report(workflow(JUDGES, REPORTS, "        run: python -m unittest")))

    def test_head_code_beside_a_judge_is_named_on_either_side(self) -> None:
        above = '        run: |\n          python .github/gate/check.py\n          python "$RUNNER_TEMP/gate/gate.py"'
        below = '        run: |\n          python "$RUNNER_TEMP/gate/gate.py"\n          python .github/gate/check.py'
        for step in (above, below):
            with self.subTest(step=step):
                self.assertEqual(["step 0"], head_code_before_the_report(workflow(step, REPORTS)))

    def test_what_runs_nothing_from_the_checkout_is_not_named(self) -> None:
        for spelling in ("        uses: actions/setup-python@v7\n        with:\n          python-version: '3.12'",
                         "        run: python -I -c 'import json'",
                         "        shell: bash\n        env:\n          GATE: .github/gate/gate.py\n        run: true",
                         "        run: git show \"$BASE_SHA:$GATE\" > \"$RUNNER_TEMP/gate/gate.py\"",
                         "        # python -m unittest\n        run: true"):
            with self.subTest(spelling=spelling):
                self.assertEqual([], head_code_before_the_report(workflow(spelling, JUDGES, REPORTS)))

    def test_a_workflow_with_no_report_two_or_no_judge_ahead_is_refused(self) -> None:
        for steps in ((JUDGES,), (JUDGES, REPORTS, REPORTS), (REPORTS, JUDGES)):
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                head_code_before_the_report(workflow(*steps))

    def test_a_second_job_is_refused(self) -> None:
        second = "  other:\n    runs-on: ubuntu-latest\n    steps:\n      - run: true\n"
        with self.assertRaises(ValueError):
            head_code_before_the_report(workflow(JUDGES, REPORTS) + second)


if __name__ == "__main__":
    unittest.main()
