"""The payload's gate workflows: nothing the pull request wrote runs on the runner before the base copy has judged."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / "payload" / ".github" / "workflows"
GATES = {"closure-gate.yml", "comment-gate.yml", "commit-gate.yml", "harness-drift.yml"}
# The judge sits outside the checkout; comment-gate.yml holds its path in `$judge`.
JUDGE = re.compile(r'(?<![-\w])python(?: -I)? "\$(?:RUNNER_TEMP/[\w./-]+\.py|judge)"')
# Reads no module from the checkout: how harness-drift.yml reads its manifest ahead of the gate.
ISOLATED = re.compile(r"(?<![-\w])python -I -c\b")
# A list of spellings, so an interpreter it does not name reads as nothing: a command whose first word is a path, a
# shell handed a file, Python, a local action, or any step set to run inside the checkout.
HEAD_CODE = re.compile(
    r"(?<![-\w])python3?(?:\.\d+)?(?=\s)|\bpytest\b|\bunittest\b"
    r"|(?<![-\w])(?:bash|sh|source)[ \t]+\S|^\s*(?:run: )?[\w./-]*/[\w./-]+"
    r"|^\s*(?:- )?uses: \./|^\s*working-directory:", re.M)


def steps_of(text: str) -> list[str]:
    """The one job's steps, comments dropped; a second job has to be argued here rather than read past."""
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    jobs = code.split("\n    steps:\n")
    if len(jobs) != 2:
        raise ValueError(f"expected one job's steps, found {len(jobs) - 1}")
    return re.split(r"\n(?=      - )", jobs[1])


def judge_at(steps: list[str]) -> int:
    at = [i for i, step in enumerate(steps) if JUDGE.search(step)]
    if len(at) != 1:
        raise ValueError(f"expected one step running the base copy, found {len(at)}")
    return at[0]


def runs_head_code(step: str) -> bool:
    return bool(HEAD_CODE.search(ISOLATED.sub("", step)))


def name_of(step: str) -> str:
    found = re.search(r"name: (.+)", step)
    return found.group(1) if found else step.splitlines()[0].strip()


def head_code_before_the_judge(text: str) -> list[str]:
    steps = steps_of(text)
    at = judge_at(steps)
    above = steps[at][:JUDGE.search(steps[at]).start()]
    return [name_of(step) for step in [*steps[:at], above] if runs_head_code(step)]


def workflow(*steps: str) -> str:
    body = "\n".join(f"      - name: step {i}\n{step}" for i, step in enumerate(steps))
    return f"name: Gate\njobs:\n  gate:\n    runs-on: ubuntu-latest\n    steps:\n{body}\n"


JUDGES = '        run: python "$RUNNER_TEMP/gate/gate.py"'


class TheOrder(unittest.TestCase):
    def test_every_gate_workflow_is_read(self) -> None:
        self.assertLessEqual(GATES, {path.name for path in WORKFLOWS.glob("*.yml")})

    def test_nothing_the_head_wrote_runs_before_the_judge(self) -> None:
        for path in sorted(WORKFLOWS.glob("*.yml")):
            with self.subTest(workflow=path.name):
                self.assertEqual([], head_code_before_the_judge(path.read_text(encoding="utf-8")))

    def test_each_gate_still_runs_its_suite_after_the_judge(self) -> None:
        # Moving the suite past the judge is the fix; deleting it would pass the case above.
        for path in sorted(WORKFLOWS.glob("*.yml")):
            with self.subTest(workflow=path.name):
                steps = steps_of(path.read_text(encoding="utf-8"))
                suites = [step for step in steps[judge_at(steps) + 1:] if "python -m unittest" in step]
                self.assertEqual(1, len(suites))
                directory = re.search(r"working-directory: (\S+)", suites[0])
                self.assertIsNotNone(directory)
                self.assertEqual(f".github/{path.stem}", directory.group(1))


class TheReader(unittest.TestCase):
    """What the cases above lean on, against workflows that are wrong on purpose."""

    def test_each_spelling_of_head_code_before_the_judge_is_named(self) -> None:
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
                self.assertEqual(["step 0"], head_code_before_the_judge(workflow(spelling, JUDGES)))

    def test_the_same_code_after_the_judge_is_not_named(self) -> None:
        self.assertEqual([], head_code_before_the_judge(workflow(JUDGES, "        run: python -m unittest")))

    def test_head_code_above_the_judge_in_its_own_step_is_named(self) -> None:
        above = '        run: |\n          python .github/gate/check.py\n          python "$RUNNER_TEMP/gate/gate.py"'
        below = '        run: |\n          python "$RUNNER_TEMP/gate/gate.py"\n          python .github/gate/check.py'
        self.assertEqual(["step 0"], head_code_before_the_judge(workflow(above)))
        self.assertEqual([], head_code_before_the_judge(workflow(below)))

    def test_what_runs_nothing_from_the_checkout_is_not_named(self) -> None:
        for spelling in ("        uses: actions/setup-python@v7\n        with:\n          python-version: '3.12'",
                         "        run: python -I -c 'import json'",
                         "        shell: bash\n        env:\n          GATE: .github/gate/gate.py\n        run: true",
                         "        run: git show \"$BASE_SHA:$GATE\" > \"$RUNNER_TEMP/gate/gate.py\"",
                         "        # python -m unittest\n        run: true"):
            with self.subTest(spelling=spelling):
                self.assertEqual([], head_code_before_the_judge(workflow(spelling, JUDGES)))

    def test_a_workflow_with_no_judge_or_two_is_refused(self) -> None:
        for steps in (("        run: true",), (JUDGES, JUDGES)):
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                head_code_before_the_judge(workflow(*steps))

    def test_a_second_job_is_refused(self) -> None:
        second = "  other:\n    runs-on: ubuntu-latest\n    steps:\n      - run: true\n"
        with self.assertRaises(ValueError):
            head_code_before_the_judge(workflow(JUDGES) + second)


if __name__ == "__main__":
    unittest.main()
