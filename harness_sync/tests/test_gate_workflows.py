"""The payload's gate workflow: one job per pull-request event, nothing the pull request wrote running before every
verdict is posted, and each verdict posted under its gate's check name."""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / "payload" / ".github" / "workflows"
GATES_YML = WORKFLOWS / "gates.yml"
# The check name each gate posts, its directory under .github/; rulesets/main.json requires all but comment-gate,
# and locality-gate only of the targets with a change contract, whose own the gate directory is.
CHECKS = {"closure-gate", "comment-gate", "commit-gate", "harness-drift", "locality-gate"}
# What `pull_request` with no `types` starts on, GitHub's default.
DEFAULT_TYPES = ("opened", "synchronize", "reopened")


def pull_request_types(text: str) -> tuple[str, ...]:
    """The pull-request events a workflow starts on, or none; a spelling this reader cannot parse is refused."""
    # A comment at column 0 would end the block early, and the key may be quoted, as yamllint's truthy rule asks.
    code = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
    found = re.search(r"(?ms)^([\"']?)on\1:(.*?)(?=^\S)", code + "\nend")
    if found is None:
        if "pull_request" in code:
            raise ValueError("a workflow naming pull_request with no `on:` block this reader finds")
        return ()
    triggers = found.group(2)
    if "pull_request" not in triggers:
        return ()
    if "pull_request_target" in triggers:
        raise ValueError("pull_request_target is not read here")
    types = re.search(r"(?m)^  pull_request:\n    types: \[([^\]]+)\]$", triggers)
    if types:
        return tuple(t.strip() for t in types.group(1).split(","))
    if "types" in triggers:
        raise ValueError("a pull_request types list this reader cannot parse")
    return DEFAULT_TYPES


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
            jobs = re.findall(r"(?m)^  ([\w-]+):$", text.split("\njobs:\n", 1)[1])
            for event in pull_request_types(text):
                started.setdefault(event, []).extend(f"{path.name}:{job}" for job in jobs)
        self.assertEqual({"opened", "synchronize", "reopened", "edited", "labeled", "unlabeled"}, set(started))
        for event, jobs in started.items():
            with self.subTest(event=event):
                self.assertEqual(["gates.yml:gates"], jobs)

    def test_the_reader_takes_every_spelling_of_the_trigger(self) -> None:
        listed = "on:\n  pull_request:\n    types: [opened, edited]\njobs:\n"
        self.assertEqual(("opened", "edited"), pull_request_types(listed))
        for bare in ("on: [push, pull_request]\njobs:\n", "on: pull_request\njobs:\n",
                     "on:\n  pull_request:\n    branches: [main]\njobs:\n", "on:\n  pull_request:\njobs:\n",
                     '"on":\n  pull_request:\njobs:\n', "on:\n# a note\n  pull_request:\njobs:\n"):
            with self.subTest(bare=bare):
                self.assertEqual(DEFAULT_TYPES, pull_request_types(bare))
        for unread in ("on:\n  pull_request:\n    types:\n      - opened\njobs:\n",
                       "on:\n  pull_request_target:\njobs:\n", "true:\n  pull_request:\njobs:\n"):
            with self.subTest(unread=unread), self.assertRaises(ValueError):
                pull_request_types(unread)
        self.assertEqual((), pull_request_types("on:\n  push:\njobs:\n"))

    def test_one_gate_failing_does_not_skip_the_next(self) -> None:
        # A step's default condition is success(), so one red gate would leave every later verdict unposted.
        steps = steps_of(GATES_YML.read_text(encoding="utf-8"))
        event = next(i for i, step in enumerate(steps) if "id: event" in step)
        for step in steps[event + 1:]:
            with self.subTest(step=name_of(step)):
                self.assertRegex(step, r"(?m)^        if: (?:>-\n          )?\$\{\{ !cancelled\(\) ")

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

    def test_the_report_posts_each_gates_check_name(self) -> None:
        report = steps_of(GATES_YML.read_text(encoding="utf-8"))
        report = report[report_at(report)]
        self.assertEqual(sorted(CHECKS), sorted(re.findall(r'(?m)^          verdict ([\w-]+) "\$', report)))

    def test_the_report_completes_the_runs_opened_at_the_start_and_opens_none(self) -> None:
        # A run that posted only at its end could finish after a later run and stand over its verdict.
        steps = steps_of(GATES_YML.read_text(encoding="utf-8"))
        opened = next(i for i, step in enumerate(steps) if re.search(r"(?m)^        id: open$", step))
        self.assertLess(opened, min(i for i, step in enumerate(steps) if JUDGE.search(step)))
        self.assertNotIn("--method POST", steps[report_at(steps)])
        self.assertIn("--method PATCH", steps[report_at(steps)])


ENV_OF = {"closure-gate": "CLOSURE_GATE", "commit-gate": "COMMIT_GATE", "harness-drift": "HARNESS_DRIFT",
          "comment-gate": "COMMENT_GATE", "locality-gate": "LOCALITY_GATE"}
ID_OF = {"closure-gate": "11", "commit-gate": "12", "harness-drift": "13", "comment-gate": "14", "locality-gate": "15"}
# Each call a line per argument it was handed, then a line of its own ending the call; it answers with $STUB_ID.
GH_STUB = """#!/usr/bin/env bash
while [ "$#" -gt 0 ]; do
  case "$1" in
    api) ;;
    --method) echo "method=$2" >> "$CALLS"; shift ;;
    -f) echo "$2" >> "$CALLS"; shift ;;
    --jq) shift ;;
    *) echo "path=$1" >> "$CALLS" ;;
  esac
  shift
done
echo -- >> "$CALLS"
echo "$STUB_ID"
exit "$STUB_RC"
"""


def find_bash() -> str | None:
    # Git for Windows' bash first: a bare `bash` on a Windows PATH can be WSL's, which reads none of these paths.
    if sys.platform == "win32" and shutil.which("git"):
        top = Path(shutil.which("git")).resolve().parent.parent
        for candidate in (top / "bin" / "bash.exe", top.parent / "bin" / "bash.exe"):
            if candidate.is_file():
                return str(candidate)
    return shutil.which("bash")


def run_with_gh(script: str, env: dict[str, str], *, gh_rc: int = 0, gh_id: str = "42") -> tuple[int, list[dict], str, str]:
    """A step's script under bash with `gh` stubbed: its exit, each call's fields, its output and $GITHUB_OUTPUT."""
    bash = find_bash()
    if bash is None:
        raise RuntimeError("bash is what the steps run under")  # not a skip: a skip passes unrun
    with tempfile.TemporaryDirectory() as directory:
        log, output, stub = Path(directory) / "calls", Path(directory) / "output", Path(directory) / "gh"
        output.write_text("", encoding="utf-8")
        stub.write_text(GH_STUB, encoding="utf-8", newline="\n")
        stub.chmod(0o755)
        env = {**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"], "CALLS": str(log),
               "STUB_RC": str(gh_rc), "STUB_ID": gh_id, "GITHUB_OUTPUT": output.as_posix(), "GH_TOKEN": "t",
               "REPO": "o/r", "HEAD_SHA": "f" * 40, "RUN_URL": "u", **env}
        done = subprocess.run([bash, "-c", script], capture_output=True, text=True, encoding="utf-8", env=env)
        text = log.read_text(encoding="utf-8") if log.exists() else ""
        calls = [dict(line.split("=", 1) for line in call.splitlines() if line) for call in text.split("--\n")[:-1]]
        return done.returncode, calls, done.stdout + done.stderr, output.read_text(encoding="utf-8")


def step_of(step_id: str) -> str:
    steps = steps_of(GATES_YML.read_text(encoding="utf-8"))
    return next(step for step in steps if re.search(rf"(?m)^        id: {step_id}$", step))


def step_script(step_id: str) -> str:
    return run_block(step_of(step_id))


def git(directory: str, *args: str) -> str:
    done = subprocess.run(["git", "-C", directory, *args], capture_output=True, text=True, encoding="utf-8",
                          check=True)
    return done.stdout.strip()


class TheEvent(unittest.TestCase):
    """The decision step, run as written in a repository whose base commit does or does not carry the locality gate."""

    def decide(self, action: str, *, base_has_gate: bool) -> dict[str, str]:
        with tempfile.TemporaryDirectory() as directory:
            git(directory, "init", "-q")
            gate = Path(directory) / (".github/locality-gate/classes.yml" if base_has_gate else "README.md")
            gate.parent.mkdir(parents=True, exist_ok=True)
            gate.write_text("x\n", encoding="utf-8")
            git(directory, "add", "-A")
            git(directory, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
            base = git(directory, "rev-parse", "HEAD")
            script = f"cd '{Path(directory).as_posix()}'\n" + step_script("event")
            rc, _, out, output = run_with_gh(script, {"ACTION": action, "BASE_SHA": base})
        self.assertEqual(0, rc, out)
        return dict(line.split("=", 1) for line in output.splitlines())

    def test_the_locality_gate_runs_on_the_closure_gates_events_where_the_base_carries_it(self) -> None:
        for action in ("opened", "synchronize", "reopened", "edited", "labeled", "unlabeled"):
            with self.subTest(action=action):
                decided = self.decide(action, base_has_gate=True)
                self.assertEqual(decided["closure"], decided["locality"])

    def test_a_base_with_no_locality_gate_runs_and_posts_none(self) -> None:
        # A target with no change contract, this repository among them, has no class map to judge by.
        for action in ("opened", "edited"):
            with self.subTest(action=action):
                decided = self.decide(action, base_has_gate=False)
                self.assertEqual(("true", "false"), (decided["closure"], decided["locality"]))

    def test_each_gate_judges_only_on_its_own_events(self) -> None:
        # The Dependabot decision runs for either gate, so a gate behind it has to name its own event too: an
        # `edited` run would otherwise post a commit gate the event never opened.
        for take, event in (("commit_take", "commit"), ("locality_take", "locality")):
            with self.subTest(step=take):
                self.assertIn(f"steps.event.outputs.{event} == 'true'", step_of(take))


class TheOpening(unittest.TestCase):
    """The step opening a check run per gate, run as written with `gh` stubbed."""

    def test_each_gate_the_event_runs_is_opened_in_progress_and_its_id_kept(self) -> None:
        env = {"CLOSURE": "true", "COMMIT": "false", "DRIFT": "false", "COMMENT": "true", "LOCALITY": "true"}
        rc, calls, out, output = run_with_gh(step_script("open"), env)
        self.assertEqual(0, rc, out)
        self.assertEqual(["closure-gate", "comment-gate", "locality-gate"], [call["name"] for call in calls])
        for call in calls:
            self.assertEqual(("POST", "repos/o/r/check-runs", "in_progress", "f" * 40),
                             (call["method"], call["path"], call["status"], call["head_sha"]))
        self.assertEqual("closure=42\ncomment=42\nlocality=42\n", output)

    def test_an_answer_with_no_id_fails_the_step(self) -> None:
        env = {"CLOSURE": "true", "COMMIT": "false", "DRIFT": "false", "COMMENT": "false", "LOCALITY": "false"}
        rc, _, out, _ = run_with_gh(step_script("open"), env, gh_id="null")
        self.assertEqual(1, rc, out)


class TheReport(unittest.TestCase):
    """The report step's script, run as written with `gh` stubbed, for the verdicts it posts."""

    def post(self, *, gh_rc: int = 0, ids: dict[str, str] | None = None, **gates: str) -> tuple[int, list[dict], str]:
        values = {name: "true success" for name in ENV_OF}
        values.update({name.replace("_", "-"): value for name, value in gates.items()})
        env = {ENV_OF[name]: value for name, value in values.items()}
        env.update({f"{ENV_OF[name]}_ID": value for name, value in {**ID_OF, **(ids or {})}.items()})
        rc, calls, out, _ = run_with_gh(step_script("report"), env, gh_rc=gh_rc)
        name_of_id = {f"repos/o/r/check-runs/{value}": name for name, value in ID_OF.items()}
        for call in calls:
            self.assertEqual("PATCH", call["method"])
            call["name"] = name_of_id[call["path"]]
        return rc, calls, out

    def test_every_gate_that_passed_is_completed_as_a_success(self) -> None:
        rc, posts, out = self.post()
        self.assertEqual(0, rc, out)
        self.assertEqual(sorted(CHECKS), sorted(post["name"] for post in posts))
        for post in posts:
            self.assertEqual(("completed", "success"), (post["status"], post["conclusion"]))

    def test_a_gate_whose_run_was_not_opened_fails(self) -> None:
        rc, posts, out = self.post(ids={"commit-gate": ""})
        self.assertEqual(1, rc, out)
        self.assertNotIn("commit-gate", [post["name"] for post in posts])
        self.assertIn("no check run was opened for commit-gate", out)

    def test_one_failed_step_posts_its_gate_as_a_failure_and_fails_the_step(self) -> None:
        rc, posts, out = self.post(harness_drift="true success failure skipped")
        self.assertEqual(1, rc, out)
        conclusions = {post["name"]: post["conclusion"] for post in posts}
        self.assertEqual("failure", conclusions.pop("harness-drift"))
        self.assertEqual({"success"}, set(conclusions.values()))

    def test_a_gate_this_event_does_not_run_posts_nothing(self) -> None:
        # An `edited` run must not overwrite the commit gate's verdict from the push.
        rc, posts, out = self.post(commit_gate="false skipped skipped skipped", harness_drift="false skipped",
                                   comment_gate="false skipped", locality_gate="false skipped skipped skipped")
        self.assertEqual(0, rc, out)
        self.assertEqual(["closure-gate"], [post["name"] for post in posts])

    def test_dependabots_own_pull_request_posts_the_locality_gate_as_a_pass(self) -> None:
        # The report's env turns the skipped steps of a stand-down into successes, as the commit gate's.
        block = re.search(r"(?m)^          LOCALITY_GATE: >-\n((?:            .+\n)+)", step_of("report"))
        self.assertIsNotNone(block)
        for step in ("locality_take", "locality"):
            with self.subTest(step=step):
                self.assertIn(f"own == 'true' && 'success' || steps.{step}.outcome", block.group(1))

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
