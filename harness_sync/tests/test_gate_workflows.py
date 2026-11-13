"""The payload's gate workflow: one job opening each gate's check run, one judging and one completing them, each
verdict posted under its gate's check name, and the write grant held only by the jobs with no checkout. That nothing
the pull request wrote runs before every verdict is fixed is the commit gate's suite's case, which every target runs."""

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


def job_of(text: str, job: str) -> str:
    """One job's lines under `jobs:`, from its key to the next job's."""
    found = re.search(rf"(?ms)^  {re.escape(job)}:\n(.*?)(?=^  [\w-]+:\n|^\S|\Z)", text.split("\njobs:\n", 1)[-1])
    if found is None:
        raise ValueError(f"no job {job}")
    return found.group(1)


def steps_of(text: str, job: str = "gates") -> list[str]:
    """One job's steps, comments dropped."""
    code = "\n".join(line for line in job_of(text, job).splitlines() if not line.lstrip().startswith("#"))
    parts = code.split("\n    steps:\n") if not code.startswith("    steps:\n") else ["", code[len("    steps:\n"):]]
    if len(parts) != 2:
        raise ValueError(f"expected one steps list in {job}, found {len(parts) - 1}")
    return re.split(r"\n(?=      - )", parts[1])


def name_of(step: str) -> str:
    found = re.search(r"name: (.+)", step)
    return found.group(1) if found else step.splitlines()[0].strip()


def run_block(step: str) -> str:
    lines = step.split("\n")
    at = next(i for i, line in enumerate(lines) if line.strip() == "run: |")
    return "\n".join(line[10:] for line in lines[at + 1:]) + "\n"


class TheJobs(unittest.TestCase):
    def test_each_pull_request_event_starts_one_judging_job_beside_the_two_posting_ones(self) -> None:
        # The account's concurrency cap is the queue: a gate a job each was a runner slot and a queue wait each. The
        # posting jobs are the write grant's, which may not sit beside the checkout (ADR-197 in blueprint-backend).
        started: dict[str, list[str]] = {}
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            jobs = re.findall(r"(?m)^  ([\w-]+):$", text.split("\njobs:\n", 1)[1])
            for event in pull_request_types(text):
                started.setdefault(event, []).extend(f"{path.name}:{job}" for job in jobs)
        self.assertEqual({"opened", "synchronize", "reopened", "edited", "labeled", "unlabeled"}, set(started))
        for event, jobs in started.items():
            with self.subTest(event=event):
                self.assertEqual(["gates.yml:open", "gates.yml:gates", "gates.yml:report"], jobs)

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
        setup = next(i for i, step in enumerate(steps) if "id: setup" in step)
        for step in steps[setup + 1:]:
            with self.subTest(step=name_of(step)):
                self.assertRegex(step, r"(?m)^        if: (?:>-\n          )?\$\{\{ !cancelled\(\) ")

    def test_the_report_runs_after_the_gates_and_whatever_they_concluded(self) -> None:
        # Its default condition is success(), which would leave a failed gate's check in progress, and !cancelled()
        # would leave every check in progress when a run is cancelled during the head suites.
        text = GATES_YML.read_text(encoding="utf-8")
        report = job_of(text, "report")
        self.assertRegex(report, r"(?m)^    needs: \[open, gates\]$")
        self.assertRegex(report, r"(?m)^    if: \$\{\{ always\(\) \}\}$")
        # A hung head suite would otherwise hold the report to the six-hour default.
        self.assertRegex(job_of(text, "gates"), r"(?m)^    timeout-minutes: \d+$")

    def test_the_judging_job_reads_the_open_jobs_one_decision(self) -> None:
        text = GATES_YML.read_text(encoding="utf-8")
        gates = job_of(text, "gates")
        self.assertRegex(gates, r"(?m)^    needs: open$")
        self.assertNotIn("steps.event.", gates)
        decisions = set(re.findall(r'(?m)^ +echo "(\w+)=', step_of("event", "open")))
        self.assertEqual({"closure", "commit", "drift", "comment", "locality"}, decisions)
        self.assertEqual(decisions, set(re.findall(r"needs\.open\.outputs\.(\w+)", gates)))

    def test_each_output_a_later_job_reads_is_one_a_step_writes(self) -> None:
        text = GATES_YML.read_text(encoding="utf-8")
        report = step_of("report", "report")
        for job, step, read in (("gates", "verdicts", re.findall(r"needs\.gates\.outputs\.(\w+)", report)),
                                ("open", "event", re.findall(r"needs\.open\.outputs\.(\w+)", job_of(text, "gates"))),
                                ("open", "open", re.findall(r"needs\.open\.outputs\.(\w+)_id", report))):
            with self.subTest(job=job, step=step):
                outputs = dict(re.findall(rf"(?m)^      (\w+): \$\{{\{{ steps\.{step}\.outputs\.(\w+) \}}\}}$",
                                          job_of(text, job)))
                keys = {key.removesuffix("_id"): value for key, value in outputs.items()}
                self.assertEqual({key: key for key in keys}, keys)
                self.assertEqual(sorted(set(read)), sorted(keys))
        written = set(re.findall(r'(?m)^ +echo "(\w+)=\$', step_of("verdicts")))
        self.assertEqual({"closure", "commit", "drift", "comment", "locality"}, written)
        # The open step writes `$1=$id` for the key it is handed.
        self.assertEqual({"closure", "commit", "drift", "comment", "locality"},
                         set(re.findall(r"(?m)^          open (\w+) [\w-]+ ", step_of("open", "open"))))

    def test_the_checkout_leaves_no_token_for_head_code(self) -> None:
        first = steps_of(GATES_YML.read_text(encoding="utf-8"))[0]
        self.assertIn("actions/checkout", first)
        self.assertIn("persist-credentials: false", first)


WRITE = re.compile(r"([a-z-]+):\s*['\"]?write\b|\bwrite-all\b")


def permissions_of(lines: str, indent: int) -> str | None:
    """The `permissions:` block at one indentation, inline value and nested lines, comments dropped; None for none."""
    pad = " " * indent
    found = re.search(rf"(?m)^{pad}permissions:(.*)\n((?:{pad}  .*\n|\s*\n)*)", lines + "\n")
    if found is None:
        return None
    return "\n".join(line for line in (found.group(1) + "\n" + found.group(2)).splitlines()
                     if not line.lstrip().startswith("#"))


class TheGrants(unittest.TestCase):
    """No job a pull request reaches holds a write grant beside a checkout of its branch."""

    def test_no_shipped_workflow_holds_a_write_grant_beside_a_checkout(self) -> None:
        held = 0
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            # With no block at either level a job holds the repository's default token, which may write.
            inherited = permissions_of(text, 0)
            for job in re.findall(r"(?m)^  ([\w-]+):$", text.split("\njobs:\n", 1)[1]):
                lines = job_of(text, job)
                own = permissions_of(lines, 4)
                grants = WRITE.findall(own if own is not None else inherited if inherited is not None else "write-all")
                held += bool(grants)
                with self.subTest(job=f"{path.name}:{job}"):
                    if grants:
                        self.assertNotRegex(lines, r"(?m)^\s*(?:- )?uses:\s*['\"]?actions/checkout@")
        # A reader that found no grant at all would pass the case above vacuously.
        self.assertEqual(2, held)

    def test_the_workflow_grants_nothing_a_job_could_inherit(self) -> None:
        self.assertEqual("{}", (permissions_of(GATES_YML.read_text(encoding="utf-8"), 0) or "").strip())

    def test_the_judging_job_reads_and_the_posting_jobs_write_checks_alone(self) -> None:
        text = GATES_YML.read_text(encoding="utf-8")
        for job, want in (("gates", [("contents", "read"), ("pull-requests", "read")]),
                          ("open", [("contents", "read"), ("checks", "write")]),
                          ("report", [("checks", "write")])):
            with self.subTest(job=job):
                self.assertEqual(want, re.findall(r"(?m)^\s+([a-z-]+): (\w+)$",
                                                  permissions_of(job_of(text, job), 4) or ""))

    def test_the_posting_jobs_run_no_action_at_all(self) -> None:
        # Not only no checkout: an action is code this file does not hold, run beside the checks token.
        for job in ("open", "report"):
            with self.subTest(job=job):
                self.assertNotRegex(job_of(GATES_YML.read_text(encoding="utf-8"), job), r"(?m)^\s*(?:- )?uses:")

    def test_the_reader_finds_a_grant_beside_a_checkout(self) -> None:
        inherited = "permissions:\n  checks: write\njobs:\n  gate:\n    steps:\n      - uses: actions/checkout@v7\n"
        self.assertEqual(["checks"], WRITE.findall(permissions_of(inherited, 0) or ""))
        own = "    permissions:\n      # checks: write\n      contents: read\n    steps:\n"
        self.assertEqual([], WRITE.findall(permissions_of(own, 4) or ""))
        self.assertEqual(["checks"], WRITE.findall(permissions_of("    permissions: { checks: write }\n", 4) or ""))


class TheOrder(unittest.TestCase):
    def test_the_report_posts_each_gates_check_name(self) -> None:
        report = step_of("report", "report")
        self.assertEqual(sorted(CHECKS), sorted(re.findall(r'(?m)^          verdict ([\w-]+) "\$', report)))

    def test_the_report_completes_the_runs_opened_before_any_judge_and_opens_none(self) -> None:
        # A run that posted only at its end could finish after a later run and stand over its verdict, and an
        # `edited` run would leave the push's verdict standing while it judged.
        text = GATES_YML.read_text(encoding="utf-8")
        self.assertRegex(job_of(text, "gates"), r"(?m)^    needs: open$")
        self.assertIn("status=in_progress", step_of("open", "open"))
        self.assertNotIn("--method POST", step_of("report", "report"))
        self.assertIn("--method PATCH", step_of("report", "report"))


ENV_OF = {"closure-gate": "CLOSURE_GATE", "commit-gate": "COMMIT_GATE", "harness-drift": "HARNESS_DRIFT",
          "comment-gate": "COMMENT_GATE", "locality-gate": "LOCALITY_GATE"}
ID_OF = {"closure-gate": "11", "commit-gate": "12", "harness-drift": "13", "comment-gate": "14", "locality-gate": "15"}
# Each call a line per argument it was handed, then a line of its own ending the call; it answers with $STUB_ID, and
# a read of a head's check runs by name with $STUB_NEWEST, failing with $STUB_READ_RC.
GH_STUB = """#!/usr/bin/env bash
while [ "$#" -gt 0 ]; do
  case "$1" in
    api) ;;
    --method) echo "method=$2" >> "$CALLS"; shift ;;
    -f) echo "$2" >> "$CALLS"; shift ;;
    --jq) shift ;;
    *) echo "path=$1" >> "$CALLS"; last=$1 ;;
  esac
  shift
done
echo -- >> "$CALLS"
if [[ "$last" == *check_name=* ]]; then
  echo "$STUB_NEWEST"
  exit "$STUB_READ_RC"
fi
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


def run_with_gh(script: str, env: dict[str, str], *, gh_rc: int = 0, gh_id: str = "42", newest: str = "0",
                read_rc: int = 0) -> tuple[int, list[dict], str, str]:
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
               "STUB_RC": str(gh_rc), "STUB_ID": gh_id, "STUB_NEWEST": newest, "STUB_READ_RC": str(read_rc),
               "GITHUB_OUTPUT": output.as_posix(), "GH_TOKEN": "t",
               "REPO": "o/r", "HEAD_SHA": "f" * 40, "RUN_URL": "u", "RUN_ID": "7", **env}
        done = subprocess.run([bash, "-c", script], capture_output=True, text=True, encoding="utf-8", env=env)
        text = log.read_text(encoding="utf-8") if log.exists() else ""
        calls = [dict(line.split("=", 1) for line in call.splitlines() if line) for call in text.split("--\n")[:-1]]
        return done.returncode, calls, done.stdout + done.stderr, output.read_text(encoding="utf-8")


def step_of(step_id: str, job: str = "gates") -> str:
    steps = steps_of(GATES_YML.read_text(encoding="utf-8"), job)
    return next(step for step in steps if re.search(rf"(?m)^        id: {step_id}$", step))


def step_script(step_id: str, job: str = "gates") -> str:
    return run_block(step_of(step_id, job))


BASE = "b" * 40
GATE_AT_BASE = f"repos/o/r/contents/.github/locality-gate/locality_gate.py?ref={BASE}"


class TheEvent(unittest.TestCase):
    """The decision step, run as written with `gh` answering whether the base commit carries the locality gate."""

    def decide(self, action: str, *, answer: str = "file", rc: int = 0) -> dict[str, str]:
        rc_seen, calls, out, output = run_with_gh(step_script("event", "open"), {"ACTION": action, "BASE_SHA": BASE},
                                                  gh_rc=rc, gh_id=answer)
        self.assertEqual(0, rc_seen, out)
        # The one read it makes, of the gate script at the base, and only when the event runs the gate.
        self.assertIn(calls, ([], [{"path": GATE_AT_BASE}]))
        self.calls = calls
        return dict(line.split("=", 1) for line in output.splitlines())

    def test_the_locality_gate_runs_on_the_closure_gates_events_where_the_base_carries_it(self) -> None:
        for action in ("opened", "synchronize", "reopened", "edited", "labeled", "unlabeled"):
            with self.subTest(action=action):
                decided = self.decide(action)
                self.assertEqual(decided["closure"], decided["locality"])
                self.assertEqual(decided["closure"] == "true", bool(self.calls))

    def test_a_base_with_no_locality_gate_runs_and_posts_none(self) -> None:
        # A target with no change contract, this repository among them, has no class map to judge by; one that keeps
        # only the class map, as blueprint-frontend does for its local `pr-locality.sh`, has no gate script either.
        for action in ("opened", "edited"):
            with self.subTest(action=action):
                decided = self.decide(action, answer="gh: Not Found (HTTP 404)", rc=1)
                self.assertEqual(("true", "false"), (decided["closure"], decided["locality"]))

    def test_a_base_whose_gate_path_is_no_file_runs_and_posts_none(self) -> None:
        decided = self.decide("opened", answer="dir")
        self.assertEqual(("true", "false"), (decided["closure"], decided["locality"]))

    def test_the_filter_reads_a_directorys_array_as_no_file(self) -> None:
        # The contents API answers a directory with an array, on which `.type` alone errors and fails the step.
        jq = shutil.which("jq")
        if jq is None:
            raise RuntimeError("jq is what `gh --jq` evaluates")  # not a skip: a skip passes unrun
        expression = re.search(r"--jq '([^']+)'", step_of("event", "open")).group(1)
        for answer, want in (('[{"type": "file"}]', "dir"), ('{"type": "file"}', "file"),
                             ('{"type": "symlink"}', "symlink")):
            with self.subTest(answer=answer):
                done = subprocess.run([jq, "-r", expression], input=answer, capture_output=True, text=True,
                                      encoding="utf-8")
                self.assertEqual((0, want), (done.returncode, done.stdout.strip()), done.stderr)

    def test_a_read_that_fails_otherwise_runs_the_gate_and_decides_every_other(self) -> None:
        # Skipped on a 500 is a silent pass, and a failed step would leave an `edited` run's closure gate unopened, so
        # the push's verdict stood over the new description. Run, the gate fails where the base has no script.
        for action in ("opened", "edited"):
            with self.subTest(action=action):
                decided = self.decide(action, answer="gh: Server Error (HTTP 500)", rc=1)
                self.assertEqual(("true", "true"), (decided["closure"], decided["locality"]))
                self.assertEqual({"closure", "commit", "drift", "comment", "locality"}, set(decided))

    def test_each_gate_judges_only_on_its_own_events(self) -> None:
        # The Dependabot decision runs for either gate, so a gate behind it has to name its own event too: an
        # `edited` run would otherwise post a commit gate the event never opened.
        for take, event in (("commit_take", "commit"), ("locality_take", "locality")):
            with self.subTest(step=take):
                self.assertIn(f"needs.open.outputs.{event} == 'true'", step_of(take))


class TheOpening(unittest.TestCase):
    """The step opening a check run per gate, run as written with `gh` stubbed."""

    def test_each_gate_the_event_runs_is_opened_in_progress_and_its_id_kept(self) -> None:
        env = {"CLOSURE": "true", "COMMIT": "false", "DRIFT": "false", "COMMENT": "true", "LOCALITY": "true"}
        rc, calls, out, output = run_with_gh(step_script("open", "open"), env)
        self.assertEqual(0, rc, out)
        self.assertEqual(["closure-gate", "comment-gate", "locality-gate"], [call["name"] for call in calls])
        for call in calls:
            self.assertEqual(("POST", "repos/o/r/check-runs", "in_progress", "f" * 40, "7"),
                             (call["method"], call["path"], call["status"], call["head_sha"], call["external_id"]))
        self.assertEqual("closure=42\ncomment=42\nlocality=42\n", output)

    def test_an_answer_with_no_id_fails_the_step(self) -> None:
        env = {"CLOSURE": "true", "COMMIT": "false", "DRIFT": "false", "COMMENT": "false", "LOCALITY": "false"}
        rc, _, out, _ = run_with_gh(step_script("open", "open"), env, gh_id="null")
        self.assertEqual(1, rc, out)


class TheVerdicts(unittest.TestCase):
    """The step fixing each gate's line as the judging job's outputs, run as written."""

    def test_each_gates_line_is_written_as_it_was_handed(self) -> None:
        env = {name: f"true {name.lower()}" for name in ENV_OF.values()}
        rc, calls, out, output = run_with_gh(step_script("verdicts"), env)
        self.assertEqual(0, rc, out)
        self.assertEqual([], calls)
        self.assertEqual({"closure": "true closure_gate", "commit": "true commit_gate", "drift": "true harness_drift",
                          "comment": "true comment_gate", "locality": "true locality_gate"},
                         dict(line.split("=", 1) for line in output.splitlines()))

    def test_dependabots_own_pull_request_fixes_the_locality_gate_as_a_pass(self) -> None:
        # The env turns the skipped steps of a stand-down into successes, as the commit gate's.
        block = re.search(r"(?m)^          LOCALITY_GATE: >-\n((?:            .+\n)+)", step_of("verdicts"))
        self.assertIsNotNone(block)
        for step in ("locality_take", "locality"):
            with self.subTest(step=step):
                self.assertIn(f"own == 'true' && 'success' || steps.{step}.outcome", block.group(1))


class TheReport(unittest.TestCase):
    """The report job's script, run as written with `gh` stubbed, for the verdicts it posts."""

    def post(self, *, gh_rc: int = 0, ids: dict[str, str] | None = None, newest: str = "0", read_rc: int = 0,
             **gates: str) -> tuple[int, list[dict], str]:
        values = {name: "true success" for name in ENV_OF}
        values.update({name.replace("_", "-"): value for name, value in gates.items()})
        env = {ENV_OF[name]: value for name, value in values.items()}
        env.update({f"{ENV_OF[name]}_ID": value for name, value in {**ID_OF, **(ids or {})}.items()})
        rc, calls, out, _ = run_with_gh(step_script("report", "report"), env, gh_rc=gh_rc, newest=newest,
                                     read_rc=read_rc)
        name_of_id = {f"repos/o/r/check-runs/{value}": name for name, value in ID_OF.items()}
        reads = [call for call in calls if "method" not in call]
        self.assertTrue(all(call["path"].startswith("repos/o/r/commits/" + "f" * 40 + "/check-runs?check_name=")
                            for call in reads), reads)
        calls = [call for call in calls if "method" in call]
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

    def test_a_check_run_a_later_run_of_the_head_opened_over_is_completed_neutral(self) -> None:
        # The older run's `open` job ran after the newer's, so its ids are the lower: it yields rather than standing.
        rc, posts, out = self.post(newest="99")
        self.assertEqual(0, rc, out)
        self.assertEqual(sorted(CHECKS), sorted(post["name"] for post in posts))
        for post in posts:
            self.assertEqual(("completed", "neutral"), (post["status"], post["conclusion"]))
            self.assertIn("check run 99", post["output[summary]"])

    def test_a_failure_is_posted_as_it_is_even_under_a_later_run(self) -> None:
        # A red is posted as it is: a red turned neutral would be a way past a failing gate.
        rc, posts, out = self.post(newest="99", harness_drift="true failure")
        self.assertEqual(1, rc, out)
        conclusions = {post["name"]: post["conclusion"] for post in posts}
        self.assertEqual("failure", conclusions.pop("harness-drift"))
        self.assertEqual({"neutral"}, set(conclusions.values()))

    def test_the_read_is_scoped_to_the_actions_apps_stamped_runs(self) -> None:
        # The stub cannot run the filter, so the step's text is held: no other app's check run may withdraw a verdict.
        report = step_of("report", "report")
        self.assertIn('select(.app.slug == "github-actions"', report)
        self.assertIn('.external_id // "")', report)

    def test_the_newest_check_run_posts_its_own_verdict(self) -> None:
        for newest in ("0", "11"):
            with self.subTest(newest=newest):
                rc, posts, out = self.post(newest=newest, harness_drift="true failure")
                self.assertEqual(1, rc, out)
                self.assertEqual({"success", "failure"}, {post["conclusion"] for post in posts})

    def test_a_read_that_fails_posts_the_runs_own_verdict(self) -> None:
        # A missing post leaves the check in progress, which is the worse of the two.
        rc, posts, out = self.post(newest="99", read_rc=1)
        self.assertEqual(0, rc, out)
        self.assertEqual({"success"}, {post["conclusion"] for post in posts})

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

    def test_a_missing_decision_posts_nothing_and_fails(self) -> None:
        # The open job's event step failed, so the gates job never ran: the line is the two empty outputs.
        rc, posts, out = self.post(closure_gate=" ")
        self.assertEqual(1, rc, out)
        self.assertNotIn("closure-gate", [post["name"] for post in posts])

    def test_a_judging_job_that_published_nothing_completes_each_opened_run_as_a_failure(self) -> None:
        # The gates job was skipped or died before its verdicts step: each line is the open job's decision alone, and
        # a run left in progress would stand until somebody reran the workflow.
        rc, posts, out = self.post(**{name.replace("-", "_"): "true" for name in ENV_OF})
        self.assertEqual(1, rc, out)
        self.assertEqual(sorted(CHECKS), sorted(post["name"] for post in posts))
        self.assertEqual({"failure"}, {post["conclusion"] for post in posts})

    def test_each_gates_decision_comes_from_the_open_job_ahead_of_its_outcomes(self) -> None:
        report = step_of("report", "report")
        for key, env in (("closure", "CLOSURE_GATE"), ("commit", "COMMIT_GATE"), ("drift", "HARNESS_DRIFT"),
                         ("comment", "COMMENT_GATE"), ("locality", "LOCALITY_GATE")):
            with self.subTest(gate=key):
                self.assertIn(f"          {env}: ${{{{ needs.open.outputs.{key} }}}} "
                              f"${{{{ needs.gates.outputs.{key} }}}}\n", report)
                self.assertNotIn("needs.open.outputs.", step_of("verdicts").split(f"{env}:", 1)[1].split(":", 1)[0])

    def test_a_gate_with_no_outcomes_is_a_failure(self) -> None:
        rc, posts, out = self.post(comment_gate="true")
        self.assertEqual(1, rc, out)
        self.assertIn({"name": "comment-gate", "conclusion": "failure"},
                      [{"name": p["name"], "conclusion": p["conclusion"]} for p in posts])

    def test_a_post_that_fails_fails_the_step(self) -> None:
        rc, _, out = self.post(gh_rc=1)
        self.assertEqual(1, rc, out)
        self.assertIn("could not post", out)


if __name__ == "__main__":
    unittest.main()
