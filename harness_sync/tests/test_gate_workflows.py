"""The payload's gate workflow: one job judging every gate on every event and one leg per gate named after its check,
so each check run sits in the run's own suite, and no job holding a write grant. That nothing the pull request wrote
runs before every verdict is fixed is the commit gate's suite's case, which every target runs."""

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
# Each check's key among the judging job's outputs.
KEY_OF = {"closure-gate": "closure", "commit-gate": "commit", "harness-drift": "drift", "comment-gate": "comment",
          "locality-gate": "locality"}
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


def jobs_of(text: str) -> list[str]:
    return re.findall(r"(?m)^  ([\w-]+):$", text.split("\njobs:\n", 1)[1])


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


def step_of(step_id: str, job: str = "gates") -> str:
    steps = steps_of(GATES_YML.read_text(encoding="utf-8"), job)
    return next(step for step in steps if re.search(rf"(?m)^        id: {step_id}$", step))


def step_script(step_id: str, job: str = "gates") -> str:
    return run_block(step_of(step_id, job))


def legs(text: str) -> dict[str, str]:
    """The report job's legs: each gate's check name and the output key it reads."""
    pairs = re.findall(r"(?m)^          - gate: ([\w-]+)\n            key: (\w+)$", job_of(text, "report"))
    return dict(pairs)


def find_bash() -> str | None:
    # Git for Windows' bash first: a bare `bash` on a Windows PATH can be WSL's, which reads none of these paths.
    if sys.platform == "win32" and shutil.which("git"):
        top = Path(shutil.which("git")).resolve().parent.parent
        for candidate in (top / "bin" / "bash.exe", top.parent / "bin" / "bash.exe"):
            if candidate.is_file():
                return str(candidate)
    return shutil.which("bash")


def run_step(script: str, env: dict[str, str], cwd: Path | None = None) -> tuple[int, str, str]:
    """A step's script under bash: its exit, its output and what it wrote to $GITHUB_OUTPUT."""
    bash = find_bash()
    if bash is None:
        raise RuntimeError("bash is what the steps run under")  # not a skip: a skip passes unrun
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "output"
        output.write_text("", encoding="utf-8")
        env = {**os.environ, "GITHUB_OUTPUT": output.as_posix(), **env}
        done = subprocess.run([bash, "-c", script], capture_output=True, text=True, encoding="utf-8", env=env,
                              cwd=cwd)
        return done.returncode, done.stdout + done.stderr, output.read_text(encoding="utf-8")


class TheJobs(unittest.TestCase):
    def test_each_pull_request_event_starts_one_judging_job_and_the_legs(self) -> None:
        # The account's concurrency cap is the queue: a gate a job each was a runner slot and a queue wait each.
        started: dict[str, list[str]] = {}
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            for event in pull_request_types(text):
                started.setdefault(event, []).extend(f"{path.name}:{job}" for job in jobs_of(text))
        self.assertEqual({"opened", "synchronize", "reopened", "edited", "labeled", "unlabeled"}, set(started))
        for event, jobs in started.items():
            with self.subTest(event=event):
                self.assertEqual(["gates.yml:gates", "gates.yml:report"], jobs)

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

    def test_the_legs_run_after_the_gates_and_whatever_they_concluded(self) -> None:
        # Their default condition is success(), which would leave a failed gate's check skipped, which a ruleset
        # reads as a pass, and !cancelled() would leave every check cancelled when a run is cancelled during the head
        # suites. A leg that failed fast would cancel the others, hiding which gate held.
        text = GATES_YML.read_text(encoding="utf-8")
        report = job_of(text, "report")
        self.assertRegex(report, r"(?m)^    needs: gates$")
        self.assertRegex(report, r"(?m)^    if: \$\{\{ always\(\) \}\}$")
        self.assertRegex(report, r"(?m)^      fail-fast: false$")
        # A hung head suite would otherwise hold the legs to the six-hour default.
        self.assertRegex(job_of(text, "gates"), r"(?m)^    timeout-minutes: \d+$")

    def test_the_checkout_leaves_no_token_for_head_code(self) -> None:
        first = steps_of(GATES_YML.read_text(encoding="utf-8"))[0]
        self.assertIn("actions/checkout", first)
        self.assertIn("persist-credentials: false", first)


class TheChecks(unittest.TestCase):
    """Each gate's check is a leg of the run, so the newest run of a head carries every gate a ruleset requires."""

    def test_each_leg_is_named_after_its_gates_check(self) -> None:
        # A check run a step POSTs is filed in whichever suite GitHub picks, and dropped when that suite's workflow
        # runs again on the head; a job's check run is its own run's, and its name is the job's name.
        text = GATES_YML.read_text(encoding="utf-8")
        self.assertEqual(KEY_OF, legs(text))
        self.assertRegex(job_of(text, "report"), r"(?m)^    name: \$\{\{ matrix\.gate \}\}$")
        self.assertNotIn("check-runs", text)

    def test_an_edited_run_posts_every_gate(self) -> None:
        # The gates job and the legs carry no condition an event can turn off: no job condition but the legs'
        # `always()`, and no step of the judging job reading the event's action or another job's decision. The one
        # gate that may judge nothing is the locality gate, on a base that carries none, read from the base commit.
        text = GATES_YML.read_text(encoding="utf-8")
        self.assertIn("edited", pull_request_types(text))
        gates = job_of(text, "gates")
        self.assertEqual([], re.findall(r"(?m)^    (?:if|needs): (.*)$", gates.split("\n    steps:\n", 1)[0]))
        self.assertEqual(["${{ always() }}"], re.findall(r"(?m)^    if: (.*)$", job_of(text, "report")))
        self.assertNotIn("github.event.action", text)
        self.assertNotIn("needs.", gates)
        conditions = re.findall(r"steps\.decide\.outputs\.(\w+)", gates)
        self.assertEqual({"locality"}, set(conditions))
        self.assertEqual(set(CHECKS), set(legs(text)))

    def test_each_output_a_leg_reads_is_one_the_verdicts_step_writes(self) -> None:
        text = GATES_YML.read_text(encoding="utf-8")
        outputs = dict(re.findall(r"(?m)^      (\w+): \$\{\{ steps\.verdicts\.outputs\.(\w+) \}\}$",
                                  job_of(text, "gates")))
        self.assertEqual({key: key for key in KEY_OF.values()}, outputs)
        written = set(re.findall(r'(?m)^ +echo "(\w+)=\$', step_of("verdicts")))
        self.assertEqual(set(KEY_OF.values()), written)
        self.assertIn("LINE: ${{ needs.gates.outputs[matrix.key] }}", step_of("verdict", "report"))


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
    """No job a pull request reaches holds a write grant: a job's own check run needs none."""

    def test_no_shipped_workflow_holds_a_write_grant(self) -> None:
        jobs = 0
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            # With no block at either level a job holds the repository's default token, which may write.
            inherited = permissions_of(text, 0)
            for job in jobs_of(text):
                own = permissions_of(job_of(text, job), 4)
                jobs += 1
                with self.subTest(job=f"{path.name}:{job}"):
                    self.assertEqual([], WRITE.findall(own if own is not None else inherited
                                                       if inherited is not None else "write-all"))
        # A reader that found no job would pass the case above vacuously.
        self.assertEqual(2, jobs)

    def test_the_workflow_grants_nothing_a_job_could_inherit(self) -> None:
        self.assertEqual("{}", (permissions_of(GATES_YML.read_text(encoding="utf-8"), 0) or "").strip())

    def test_the_judging_job_reads_and_the_legs_hold_nothing(self) -> None:
        text = GATES_YML.read_text(encoding="utf-8")
        self.assertEqual([("contents", "read"), ("pull-requests", "read")],
                         re.findall(r"(?m)^\s+([a-z-]+): (\w+)$", permissions_of(job_of(text, "gates"), 4) or ""))
        self.assertEqual("{}", (permissions_of(job_of(text, "report"), 4) or "").strip())

    def test_the_legs_run_no_action_at_all(self) -> None:
        # Not only no checkout: an action is code this file does not hold.
        self.assertNotRegex(job_of(GATES_YML.read_text(encoding="utf-8"), "report"), r"(?m)^\s*(?:- )?uses:")

    def test_the_reader_finds_a_grant(self) -> None:
        inherited = "permissions:\n  checks: write\njobs:\n  gate:\n    steps:\n      - uses: actions/checkout@v7\n"
        self.assertEqual(["checks"], WRITE.findall(permissions_of(inherited, 0) or ""))
        own = "    permissions:\n      # checks: write\n      contents: read\n    steps:\n"
        self.assertEqual([], WRITE.findall(permissions_of(own, 4) or ""))
        self.assertEqual(["checks"], WRITE.findall(permissions_of("    permissions: { checks: write }\n", 4) or ""))


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True)
    return done.stdout.strip()


class TheDecision(unittest.TestCase):
    """The one decision the judging job takes, run as written against a real base commit."""

    def decide(self, files: dict[str, str] | None, base: str | None = None) -> tuple[dict[str, str], str]:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            git(repo, "init", "-q", "-b", "main")
            for name, content in (files or {}).items():
                (repo / name).parent.mkdir(parents=True, exist_ok=True)
                (repo / name).write_text(content, encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m",
                "base")
            sha = base or git(repo, "rev-parse", "HEAD")
            rc, out, output = run_step(step_script("decide"), {"BASE_SHA": sha,
                                                               "GATE": ".github/locality-gate/locality_gate.py"},
                                       cwd=repo)
        self.assertEqual(0, rc, out)
        return dict(line.split("=", 1) for line in output.splitlines()), out

    def test_a_base_carrying_the_gate_runs_it(self) -> None:
        decided, _ = self.decide({".github/locality-gate/locality_gate.py": "print()\n"})
        self.assertEqual({"locality": "true"}, decided)

    def test_a_base_with_no_locality_gate_judges_nothing(self) -> None:
        # A target with no change contract, this repository among them, has no class map to judge by; one that keeps
        # only the class map, as blueprint-frontend does for its local `pr-locality.sh`, has no gate script either.
        for files in (None, {".github/locality-gate/classes.yml": "classes: {}\n"},
                      {".github/locality-gate/locality_gate.py/inner.py": "print()\n"}):
            with self.subTest(files=files):
                decided, out = self.decide(files)
                self.assertEqual({"locality": "false"}, decided)
                self.assertIn("nothing to judge", out)

    def test_a_base_missing_from_the_checkout_runs_the_gate(self) -> None:
        # Skipped on an unreadable base is a silent pass; run, the gate fails where the base carries no script.
        decided, out = self.decide(None, base="b" * 40)
        self.assertEqual({"locality": "true"}, decided)
        self.assertIn("::warning::", out)

    def test_the_locality_gate_judges_only_on_the_decision(self) -> None:
        self.assertIn("steps.decide.outputs.locality == 'true'", step_of("locality_take"))
        self.assertIn("${{ steps.decide.outputs.locality }}", step_of("verdicts"))


class TheVerdicts(unittest.TestCase):
    """The step fixing each gate's line as the judging job's outputs, run as written."""

    def test_each_gates_line_is_written_as_it_was_handed(self) -> None:
        env = {name: f"true {name.lower()}" for name in
               ("CLOSURE_GATE", "COMMIT_GATE", "HARNESS_DRIFT", "COMMENT_GATE", "LOCALITY_GATE")}
        rc, out, output = run_step(step_script("verdicts"), env)
        self.assertEqual(0, rc, out)
        self.assertEqual({"closure": "true closure_gate", "commit": "true commit_gate", "drift": "true harness_drift",
                          "comment": "true comment_gate", "locality": "true locality_gate"},
                         dict(line.split("=", 1) for line in output.splitlines()))

    def test_every_gate_but_the_locality_gate_always_judges(self) -> None:
        verdicts = step_of("verdicts")
        for env in ("CLOSURE_GATE", "COMMIT_GATE", "HARNESS_DRIFT", "COMMENT_GATE"):
            with self.subTest(gate=env):
                self.assertRegex(verdicts, rf"(?m)^          {env}: (?:>-\n            )?true ")

    def test_dependabots_own_pull_request_fixes_the_locality_gate_as_a_pass(self) -> None:
        # The env turns the skipped steps of a stand-down into successes, as the commit gate's.
        block = re.search(r"(?m)^          LOCALITY_GATE: >-\n((?:            .+\n)+)", step_of("verdicts"))
        self.assertIsNotNone(block)
        for step in ("locality_take", "locality"):
            with self.subTest(step=step):
                self.assertIn(f"own == 'true' && 'success' || steps.{step}.outcome", block.group(1))


class TheLeg(unittest.TestCase):
    """A leg's script, run as written, for the conclusion it gives its gate's check."""

    def conclude(self, line: str, gate: str = "harness-drift", head: str = "o/r") -> tuple[int, str]:
        rc, out, _ = run_step(step_script("verdict", "report"),
                              {"GATE": gate, "LINE": line, "HEAD_REPO": head, "REPO": "o/r"})
        return rc, out

    def test_a_forks_pull_request_fails_every_gate_however_it_was_judged(self) -> None:
        # A leg needs no token, so the fork barrier the read-only token gave is kept by name.
        for line in ("true success", "false"):
            with self.subTest(line=line):
                rc, out = self.conclude(line, "closure-gate", head="someone/r")
                self.assertEqual(1, rc, out)
                self.assertIn("a fork", out)
        self.assertIn("HEAD_REPO: ${{ github.event.pull_request.head.repo.full_name }}", step_of("verdict", "report"))

    def test_a_gate_whose_every_step_passed_passes(self) -> None:
        for line in ("true success", "true success success success"):
            with self.subTest(line=line):
                rc, out = self.conclude(line)
                self.assertEqual(0, rc, out)
                self.assertIn("harness-drift: success", out)

    def test_any_step_that_did_not_pass_fails_the_gate(self) -> None:
        for line in ("true success failure skipped", "true skipped", "true cancelled success"):
            with self.subTest(line=line):
                rc, out = self.conclude(line)
                self.assertEqual(1, rc, out)
                self.assertIn("::error::", out)

    def test_a_judging_job_that_published_nothing_fails_every_gate(self) -> None:
        # The gates job died before its verdicts step, so the line is empty; a decision with no outcome is malformed.
        for line in ("", " ", "true"):
            with self.subTest(line=line):
                rc, out = self.conclude(line)
                self.assertEqual(1, rc, out)

    def test_a_gate_the_base_does_not_carry_passes_with_nothing_judged(self) -> None:
        rc, out = self.conclude("false", "locality-gate")
        self.assertEqual(0, rc, out)
        self.assertIn("nothing to judge", out)


if __name__ == "__main__":
    unittest.main()
