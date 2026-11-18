#!/usr/bin/env python3
"""Negative cases for the commit gate, each beside a positive control."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from commit_gate import check, collect, main, subject_problem


def commit(
    subject: str = "chore(ci): build each commit",
    *,
    parents: int = 1,
    trailers: tuple[tuple[str, str], ...] = (("PR", "#7"),),
    sha: str = "a" * 40,
) -> dict:
    return {
        "sha": sha,
        "parents": ["b" * 40] * parents,
        "subject": subject,
        "trailers": list(trailers),
    }


class Judgement(unittest.TestCase):
    def test_a_well_formed_range_passes(self) -> None:
        self.assertEqual(check(7, [commit(), commit("docs: the form")]), [])

    def test_an_empty_range_is_refused_not_passed(self) -> None:
        self.assertEqual(len(check(7, [])), 1)

    def test_a_merge_commit_fails(self) -> None:
        problems = check(7, [commit(parents=2)])
        self.assertEqual(len(problems), 1)
        self.assertIn("merge commit", problems[0])

    def test_a_missing_trailer_fails(self) -> None:
        problems = check(7, [commit(trailers=())])
        self.assertIn("carries no `PR: #7` trailer", problems[0])

    def test_another_pull_requests_trailer_fails(self) -> None:
        problems = check(7, [commit(trailers=(("PR", "#8"),))])
        self.assertIn("not `PR: #7`", problems[0])

    def test_a_wrong_trailer_beside_the_right_one_fails(self) -> None:
        self.assertEqual(len(check(7, [commit(trailers=(("PR", "#7"), ("PR", "#8")))])), 1)

    def test_the_right_trailer_twice_fails(self) -> None:
        # git-revert-pr.sh and git-trailer-pr.sh compare every parsed PR: line, joined, with one, so a doubled
        # trailer is left out of a revert of this pull request; git appends one on its own when another
        # trailer sits between the two.
        problems = check(7, [commit(trailers=(("PR", "#7"), ("Co-Authored-By", "Claude"), ("PR", "#7")))])
        self.assertEqual(len(problems), 1)
        self.assertIn("twice", problems[0])

    def test_a_trailer_of_another_key_is_not_the_trailer(self) -> None:
        self.assertEqual(len(check(7, [commit(trailers=(("Reverts", "#7"),))])), 1)

    def test_a_trailer_prefix_is_not_the_number(self) -> None:
        self.assertEqual(len(check(7, [commit(trailers=(("PR", "#70"),))])), 1)

    def test_the_other_trailers_beside_it_are_welcome(self) -> None:
        trailers = (("Co-Authored-By", "Claude"), ("Claude-Session", "https://x"), ("PR", "#7"))
        self.assertEqual(check(7, [commit(trailers=trailers)]), [])

    def test_every_commit_is_judged_not_the_first(self) -> None:
        problems = check(7, [commit(), commit(trailers=(), sha="c" * 40)])
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("c" * 12))


class Subjects(unittest.TestCase):
    def test_the_types_the_command_lists_pass(self) -> None:
        for subject in (
            "docs: a",
            "docs(harness): a",
            "feat(catalog): a",
            "fix: a",
            "chore: a",
            "refactor: a",
            "test: a",
        ):
            with self.subTest(subject=subject):
                self.assertIsNone(subject_problem(subject))

    def test_feat_without_a_scope_fails(self) -> None:
        self.assertIsNotNone(subject_problem("feat: a"))

    def test_an_unknown_type_fails(self) -> None:
        self.assertIsNotNone(subject_problem("update: a"))

    def test_an_unknown_type_is_told_the_closed_set_and_the_ci_type(self) -> None:
        problem = subject_problem("ci(observability): a") or ""
        self.assertIn("docs, feat(<scope>), fix, chore, refactor or test", problem)
        self.assertIn("chore(ci) or fix(ci), never ci(...)", problem)

    def test_a_subject_with_no_colon_space_fails(self) -> None:
        for subject in ("docs a", "docs:a", "docs: ", ""):
            with self.subTest(subject=subject):
                self.assertIsNotNone(subject_problem(subject))

    def test_each_leftover_is_named(self) -> None:
        for subject in ("fixup! docs: a", "squash! docs: a", "amend! docs: a", "wip", "WIP: a", "wip docs: a"):
            with self.subTest(subject=subject):
                self.assertIn("leftover", subject_problem(subject) or "")

    def test_a_word_that_merely_starts_with_wip_is_not_a_leftover(self) -> None:
        self.assertNotIn("leftover", subject_problem("wipe: a") or "")

    def test_a_git_written_revert_is_judged_by_its_inner_subject(self) -> None:
        self.assertIsNone(subject_problem('Revert "docs: a"'))
        self.assertIsNotNone(subject_problem('Revert "update: a"'))
        self.assertIn("leftover", subject_problem('Revert "wip: a"') or "")

    def test_a_revert_of_a_revert_is_judged_by_its_innermost_subject(self) -> None:
        # git titles a revert of a revert `Reapply "<subject>"`, an older git `Revert "Revert "<subject>""`; either is
        # what git-revert-pr.sh writes when a reverted pull request is landed again.
        for subject in ('Reapply "docs: a"', 'Revert "Revert "docs: a""', 'Revert "Reapply "fix(x): a""',
                        'Reapply "Revert "docs: a""'):
            with self.subTest(subject=subject):
                self.assertIsNone(subject_problem(subject))
        self.assertIsNotNone(subject_problem('Reapply "update: a"'))
        self.assertIsNotNone(subject_problem('Revert "Revert "update: a""'))
        self.assertIn("leftover", subject_problem('Reapply "Revert "wip: a""') or "")


def git(root: Path, *args: str, stdin: str | None = None) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        input=stdin, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return done.stdout.strip()


class Reading(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "commit", "-q", "--allow-empty", "-m", "chore: base")
        self.base = git(self.root, "rev-parse", "HEAD")
        self.addCleanup(self._dir.cleanup)

    def land(self, message: str) -> None:
        git(self.root, "commit", "-q", "--allow-empty", "-F", "-", stdin=message)

    def read(self) -> list[dict]:
        import os

        previous = os.getcwd()
        os.chdir(self.root)
        try:
            return collect(self.base, "HEAD")
        finally:
            os.chdir(previous)

    def test_a_trailer_in_the_last_paragraph_is_read(self) -> None:
        self.land("docs: a\n\nThe body.\n\nCo-Authored-By: C <c@example.com>\nPR: #7\n")
        commits = self.read()
        self.assertEqual(check(7, commits), [])
        self.assertEqual(len(commits[0]["parents"]), 1)

    def test_the_same_line_in_the_body_is_not_a_trailer(self) -> None:
        self.land("docs: a\n\nThe line below is quoted, not a trailer:\n\nPR: #7\n\nMore prose after it.\n")
        self.assertEqual(len(check(7, self.read())), 1)

    def test_a_real_merge_commit_is_seen_as_one(self) -> None:
        git(self.root, "switch", "-q", "-c", "side")
        self.land("docs: side\n\nPR: #7\n")
        git(self.root, "switch", "-q", "main")
        self.land("docs: main\n\nPR: #7\n")
        git(self.root, "merge", "-q", "--no-ff", "-m", "docs: merge\n\nPR: #7", "side")
        problems = check(7, self.read())
        self.assertTrue(any("merge commit" in p for p in problems))

    def test_main_reports_the_failure_as_an_exit_code(self) -> None:
        self.land("docs: a\n\nPR: #7\n")
        self.land("docs: b\n")
        import os

        previous = os.getcwd()
        os.chdir(self.root)
        try:
            self.assertEqual(main(["--pr", "7", self.base, "HEAD"]), 1)
            self.assertEqual(main(["--pr", "7", self.base, "no-such-ref"]), 2)
        finally:
            os.chdir(previous)


WORKFLOW = Path(__file__).resolve().parent.parent / "workflows" / "gates.yml"
DEPENDABOT_LOGIN = "dependabot[bot]"
DEPENDABOT_MAKER = ("49699333+dependabot[bot]@users.noreply.github.com", "noreply@github.com")
HUMAN = "someone@example.com"
STANDS_DOWN = "steps.dependabot.outputs.own != 'true'"
# The take, the judge and the suite: a step of this gate by its id or the directory it runs in.
OWN_STEP = re.compile(r"(?m)^        (?:id: commit(?:_take)?|working-directory: \.github/commit-gate)$")


def find_bash() -> str | None:
    # Git for Windows' bash first: a bare `bash` on a Windows PATH can be WSL's.
    if sys.platform == "win32" and shutil.which("git"):
        top = Path(shutil.which("git")).resolve().parent.parent
        for candidate in (top / "bin" / "bash.exe", top.parent / "bin" / "bash.exe"):
            if candidate.is_file():
                return str(candidate)
    return shutil.which("bash")


BASH = find_bash()


def setUpModule() -> None:
    # Not a skip: a skip reports a pass for a gate nothing has run.
    if BASH is None:
        raise RuntimeError("bash is needed to run the workflow's deciding step")


def job_of(text: str, job: str) -> str:
    """One job's lines under `jobs:`, from its key to the next job's."""
    found = re.search(rf"(?ms)^  {re.escape(job)}:\n(.*?)(?=^  [\w-]+:\n|^\S|\Z)", text.split("\njobs:\n", 1)[-1])
    if found is None:
        raise ValueError(f"no job {job}")
    return found.group(1)


def gates_job(text: str) -> str:
    """The judging job's lines: the legs concluding each gate's check run no step of this gate."""
    return job_of(text, "gates")


def steps_of(text: str, job: str = "gates") -> list[str]:
    """One job's steps, comments dropped, or the one ahead of the next step reads as the end of this one's script."""
    code = "\n".join(line for line in job_of(text, job).splitlines() if not line.lstrip().startswith("#"))
    parts = code.split("\n    steps:\n") if not code.startswith("    steps:\n") else ["", code[len("    steps:\n"):]]
    if len(parts) != 2:
        raise ValueError(f"expected one steps list in {job}, found {len(parts) - 1}")
    return re.split(r"\n(?=      - )", parts[1])


def workflow_steps() -> list[str]:
    return steps_of(WORKFLOW.read_text(encoding="utf-8"))


def deciding_step() -> str:
    return next(s for s in workflow_steps() if "id: dependabot" in s)


def run_block(step: str) -> str:
    lines = step.split("\n")
    at = next(i for i, line in enumerate(lines) if line.strip() == "run: |")
    return "\n".join(line[10:] for line in lines[at + 1:]) + "\n"


# Each gate directory gates.yml runs a suite in, after the verdicts.
SUITES = {"closure-gate", "comment-gate", "commit-gate", "harness-drift", "locality-gate"}
# A judge sits outside the checkout; the comment gate holds its path in `$judge`.
JUDGE = re.compile(r'(?<![-\w])python(?: -I)? "\$(?:RUNNER_TEMP/[\w./-]+\.py|judge)"')
# Reads no module from the checkout: how the drift gate reads its manifest ahead of the judge.
ISOLATED = re.compile(r"(?<![-\w])python -I -c\b")
# Deny by default: a command reads as head code unless its first word is one of these, the shell's own words or a
# tool that takes the checkout only as data. An interpreter, a build tool or a path is never named here.
SAFE_COMMANDS = frozenset({":", "[", "[[", "cp", "echo", "exit", "false", "gh", "git", "grep", "jq", "mkdir", "printf",
                           "rm", "set", "test", "true"})
# Words after which the shell expects a command, words that close a compound, and words whose header runs nothing.
OPENERS = frozenset({"!", "{", "if", "then", "elif", "else", "while", "until", "do"})
CLOSERS = frozenset({"}", "fi", "done"})
HEADERS = frozenset({"for", "select"})
# Outside the script: a local action, a step run inside the checkout, or a shell other than these.
STEP_HEAD_CODE = re.compile(r"^\s*(?:- )?uses: \./|^\s*working-directory:", re.M)
SHELL = re.compile(r"^\s*(?:- )?shell: *(.*)$", re.M)
SAFE_SHELLS = frozenset({"bash", "sh"})
RUN = re.compile(r"^( *)(- )?run:(.*)$", re.M)


def run_script(step: str) -> str | None:
    """The step's `run`, a block scalar's lines dedented or the one line as written."""
    found = RUN.search(step)
    if not found:
        return None
    value = found.group(3).strip()
    if not value or value[0] not in "|>":
        return value + "\n"
    indent = len(found.group(1)) + len(found.group(2) or "")
    lines = []
    for line in step[found.end() + 1:].split("\n"):
        if line.strip() and len(line) - len(line.lstrip(" ")) <= indent:
            break
        lines.append(line)
    width = min((len(line) - len(line.lstrip(" ")) for line in lines if line.strip()), default=0)
    return "\n".join(line[width:] for line in lines) + "\n"


def command_words(script: str) -> list[str]:
    """The first word of every command in a shell script, `$(...)` and backticks included.

    Quotes and escapes are followed, and what it cannot place, a heredoc or an unclosed quote, it refuses."""
    words: list[str] = []
    frames: list[dict] = [{"kind": "code", "closer": "", "word": "", "head": True, "depth": 0, "target": False}]

    def end_word(frame: dict) -> None:
        word, frame["word"] = frame["word"], ""
        if not word:
            return
        if frame["target"]:
            frame["target"] = False
        elif frame["head"]:
            if re.match(r"[A-Za-z_]\w*=", word) or word in OPENERS:
                return
            frame["head"] = False
            if word not in CLOSERS and word not in HEADERS:
                words.append(word)

    def skip_braces(at: int) -> int:
        depth = 0
        while at < len(script):
            depth += {"{": 1, "}": -1}.get(script[at], 0)
            if depth == 0:
                return at
            at += 1
        raise ValueError("an unclosed ${ in a run script")

    at = 0
    while at < len(script):
        frame, char, ahead = frames[-1], script[at], script[at + 1:at + 2]
        # Inside double quotes a character joins the word the quote stands in.
        word = frame if frame["kind"] == "code" else frame["parent"]
        if char == "\\":
            if ahead != "\n":
                word["word"] += ahead
            elif frame["kind"] == "code":
                end_word(frame)
            at += 2
            continue
        if char == "$" and ahead == "{":
            end = skip_braces(at + 1)
            word["word"] += script[at:end + 1]
            at = end + 1
            continue
        if char == "$" and ahead == "(":
            if script[at + 2:at + 3] == "(":
                raise ValueError("arithmetic $(( in a run script")
            word["word"] += "$"
            frames.append({"kind": "code", "closer": ")", "word": "", "head": True, "depth": 0, "target": False})
            at += 2
            continue
        if char == "`":
            if frame["kind"] == "code" and frame["closer"] == "`":
                end_word(frame)
                frames.pop()
            else:
                word["word"] += "$"
                frames.append({"kind": "code", "closer": "`", "word": "", "head": True, "depth": 0, "target": False})
            at += 1
            continue
        if frame["kind"] == "quote":
            if char == '"':
                frames.pop()
            else:
                word["word"] += char
            at += 1
            continue
        if char == '"':
            frames.append({"kind": "quote", "parent": frame})
        elif char == "'":
            end = script.find("'", at + 1)
            if end < 0:
                raise ValueError("an unclosed ' in a run script")
            frame["word"] += script[at + 1:end]
            at = end
        elif char == "#" and not frame["word"]:
            end = script.find("\n", at)
            at = (end if end >= 0 else len(script)) - 1
        elif char in " \t":
            end_word(frame)
        elif char in "\n;&|":
            end_word(frame)
            frame["head"] = True
        elif char in "<>":
            if script[at:at + 3] == "<<<":
                at += 2
            elif script[at:at + 2] == "<<":
                raise ValueError("a heredoc in a run script")
            if frame["word"].isdigit():
                frame["word"] = ""
            end_word(frame)
            while script[at + 1:at + 2] in (">", "&") and script[at + 1:at + 2]:
                at += 1
            frame["target"] = True
        elif char == "(":
            end_word(frame)
            frame["depth"] += 1
            frame["head"] = True
        elif char == ")":
            end_word(frame)
            if frame["depth"]:
                frame["depth"] -= 1
                frame["head"] = True
            elif frame["closer"] == ")":
                frames.pop()
            else:
                raise ValueError("an unmatched ) in a run script")
        else:
            frame["word"] += char
        at += 1
    if len(frames) != 1 or frames[0]["depth"]:
        raise ValueError("an unclosed quote, substitution or group in a run script")
    end_word(frames[0])
    return words


VERDICTS = re.compile(r"(?m)^ +(?:- )?id: verdicts$")


def verdicts_at(steps: list[str]) -> int:
    """Where the judging job fixes its verdicts; nothing the head wrote may run at or before it."""
    at = [i for i, step in enumerate(steps) if VERDICTS.search(step)]
    if len(at) != 1:
        raise ValueError(f"expected one step fixing the verdicts, found {len(at)}")
    if not any(JUDGE.search(step) for step in steps[:at[0]]):
        raise ValueError("expected a judge ahead of the verdicts")
    return at[0]


def runs_head_code(step: str) -> bool:
    shell = SHELL.search(step)
    if STEP_HEAD_CODE.search(step) or (shell and shell.group(1).strip() not in SAFE_SHELLS):
        return True
    script = run_script(step)
    if script is None:
        return False
    # A judge and an isolated read stand in as `:`, so their arguments are read as arguments.
    script = JUDGE.sub(":", ISOLATED.sub(":", script))
    defined = set(re.findall(r"(?m)^\s*(\w+)\(\)", script))
    return any(word not in SAFE_COMMANDS and word not in defined for word in command_words(script))


def name_of(step: str) -> str:
    found = re.search(r"name: (.+)", step)
    return found.group(1) if found else step.splitlines()[0].strip()


def head_code_before_the_verdicts(text: str, job: str = "gates") -> list[str]:
    steps = steps_of(text, job)
    return [name_of(step) for step in steps[:verdicts_at(steps) + 1] if runs_head_code(step)]


def workflow(*steps: str) -> str:
    body = "\n".join(f"      - name: step {i}\n{step}" for i, step in enumerate(steps))
    return f"name: Gate\njobs:\n  gates:\n    runs-on: ubuntu-latest\n    steps:\n{body}\n"


JUDGES = '        run: python "$RUNNER_TEMP/gate/gate.py"'
REPORTS = "        id: verdicts\n        run: true"


class Standing(unittest.TestCase):
    """The deciding step of gates.yml, run as written against real commits."""

    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.root = Path(self._dir.name) / "repo"
        self.root.mkdir()
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "commit", "-q", "--allow-empty", "-m", "chore: base")
        self.base = git(self.root, "rev-parse", "HEAD")

    def commit(self, author: str, committer: str) -> None:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "a", "GIT_AUTHOR_EMAIL": author,
            "GIT_COMMITTER_NAME": "c", "GIT_COMMITTER_EMAIL": committer,
        }
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "-q", "--allow-empty", "-m", "chore: x"],
            env=env, check=True, capture_output=True,
        )

    def own(self, opener: str) -> str:
        step = deciding_step()
        declared = re.search(r"^ +DEPENDABOT: (.+)$", step, re.M)
        out = Path(self._dir.name) / "output"
        out.write_text("", encoding="utf-8")
        env = {
            **os.environ,
            "PR_AUTHOR": opener,
            "BASE_SHA": self.base,
            "HEAD_SHA": git(self.root, "rev-parse", "HEAD"),
            "DEPENDABOT": declared.group(1).strip(),
            "GITHUB_OUTPUT": out.as_posix(),
        }
        subprocess.run(
            [BASH, "-c", run_block(step)],
            cwd=self.root, env=env, check=True, capture_output=True,
            text=True, encoding="utf-8",
        )
        return re.search(r"^own=(\w+)$", out.read_text(encoding="utf-8"), re.M).group(1)

    def test_dependabots_own_commits_on_its_own_pull_request_stand_down(self) -> None:
        self.commit(*DEPENDABOT_MAKER)
        self.commit(*DEPENDABOT_MAKER)
        self.assertEqual(self.own(DEPENDABOT_LOGIN), "true")

    def test_a_human_committer_on_dependabots_pull_request_is_judged(self) -> None:
        self.commit(*DEPENDABOT_MAKER)
        self.commit(DEPENDABOT_MAKER[0], HUMAN)
        self.assertEqual(self.own(DEPENDABOT_LOGIN), "false")

    def test_a_wholly_human_commit_on_dependabots_pull_request_is_judged(self) -> None:
        self.commit(*DEPENDABOT_MAKER)
        self.commit(HUMAN, HUMAN)
        self.assertEqual(self.own(DEPENDABOT_LOGIN), "false")

    def test_a_human_author_with_githubs_committer_is_judged(self) -> None:
        self.commit(HUMAN, DEPENDABOT_MAKER[1])
        self.assertEqual(self.own(DEPENDABOT_LOGIN), "false")

    def test_dependabots_commits_on_a_pull_request_a_human_opened_are_judged(self) -> None:
        self.commit(*DEPENDABOT_MAKER)
        self.assertEqual(self.own("someone"), "false")

    def test_an_empty_range_is_judged(self) -> None:
        self.assertEqual(self.own(DEPENDABOT_LOGIN), "false")


class WorkflowShape(unittest.TestCase):
    def test_the_job_runs_on_every_event_so_a_human_push_is_judged(self) -> None:
        job = gates_job(WORKFLOW.read_text(encoding="utf-8")).split("\n    steps:\n", 1)[0]
        self.assertEqual([], re.findall(r"(?m)^    (?:if|needs): (.*)$", job))

    def test_the_checkout_runs_first_with_full_history_and_no_condition(self) -> None:
        first = workflow_steps()[0]
        self.assertIn("actions/checkout", first)
        self.assertIn("fetch-depth: 0", first)
        self.assertNotIn("if:", first)

    def test_every_step_of_the_gate_after_the_decision_stands_down_with_it(self) -> None:
        steps = workflow_steps()
        at = steps.index(deciding_step())
        own = [step for step in steps if OWN_STEP.search(step)]
        self.assertEqual(3, len(own))
        for step in own:
            self.assertGreater(steps.index(step), at)
            # On the `if:` line, or on the lines a folded `>-` condition continues on.
            condition = re.search(r"(?m)^        if: (?:>-\n((?:          .+\n?)+)|(.+)$)", step)
            self.assertIsNotNone(condition)
            self.assertIn(STANDS_DOWN, condition.group(1) or condition.group(2))

    def test_the_stand_down_is_posted_as_a_pass(self) -> None:
        # The steps skip, so the check a ruleset requires has to be posted as passing or it never reports.
        verdicts = next(step for step in workflow_steps() if "id: verdicts" in step)
        commit_gate = re.search(r"(?m)^          COMMIT_GATE: >-\n((?:            .+\n)+)", verdicts)
        self.assertIsNotNone(commit_gate)
        self.assertEqual(2, commit_gate.group(1).count("steps.dependabot.outputs.own == 'true' && 'success' ||"))


class TheOrder(unittest.TestCase):
    """Test code can rewrite `$GITHUB_ENV`, `$GITHUB_PATH` or a tool, so no suite may run before a verdict is fixed."""

    def test_nothing_the_head_wrote_runs_before_the_verdicts(self) -> None:
        self.assertEqual([], head_code_before_the_verdicts(WORKFLOW.read_text(encoding="utf-8")))

    def test_each_gate_still_runs_its_suite_after_the_verdicts(self) -> None:
        # Moving a suite past the verdicts is the fix; deleting it would pass the case above.
        steps = workflow_steps()
        suites = [step for step in steps[verdicts_at(steps) + 1:] if "python -m unittest" in step]
        found = [re.search(r"working-directory: \.github/(\S+)", step) for step in suites]
        self.assertNotIn(None, found)
        self.assertEqual(sorted(SUITES), sorted(match.group(1) for match in found))


class TheReader(unittest.TestCase):
    """What the order cases lean on, against workflows that are wrong on purpose."""

    def test_a_suite_moved_ahead_of_the_verdicts_is_named(self) -> None:
        suite = "        working-directory: .github/commit-gate\n        run: python -m unittest"
        self.assertEqual(["step 1"], head_code_before_the_verdicts(workflow(JUDGES, suite, REPORTS)))
        self.assertEqual(["step 0"], head_code_before_the_verdicts(workflow(suite, JUDGES, REPORTS)))

    def test_each_spelling_of_head_code_before_the_verdicts_is_named(self) -> None:
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
                         "        working-directory: .github/gate\n        run: make",
                         # Deny by default: a tool no list spelled is named for not being one of the safe words.
                         "        run: npm test",
                         "        run: node .github/gate/check.mjs",
                         "        run: dotnet test",
                         "        run: pwsh .github/gate/suite.ps1",
                         "        run: make check",
                         "        run: env CI=1 npm test",
                         "        run: git log -1 && npm test",
                         "        run: git log -1 | node",
                         "        run: out=$(npm test)",
                         '        run: echo "$(./tool)"',
                         "        run: echo `make`",
                         "        run: |\n          if true; then\n            npm ci\n          fi",
                         "        run: |\n          for gate in a b; do\n            make \"$gate\"\n          done",
                         "        run: |\n          check() { npm test; }\n          check",
                         "        shell: python {0}\n        run: print(1)",
                         "        shell: pwsh\n        run: true"):
            with self.subTest(spelling=spelling):
                self.assertEqual(["step 1"], head_code_before_the_verdicts(workflow(JUDGES, spelling, REPORTS)))

    def test_a_path_run_by_a_nameless_step_is_named(self) -> None:
        text = ("jobs:\n  gates:\n    steps:\n"
                '      - run: python "$RUNNER_TEMP/gate/gate.py"\n      - run: ./.github/gate/suite.sh\n'
                "      - id: verdicts\n        run: true\n")
        self.assertEqual(["- run: ./.github/gate/suite.sh"], head_code_before_the_verdicts(text))

    def test_the_same_code_after_the_verdicts_are_not_named(self) -> None:
        self.assertEqual([], head_code_before_the_verdicts(workflow(JUDGES, REPORTS, "        run: python -m unittest")))

    def test_head_code_beside_a_judge_is_named_on_either_side(self) -> None:
        above = '        run: |\n          python .github/gate/check.py\n          python "$RUNNER_TEMP/gate/gate.py"'
        below = '        run: |\n          python "$RUNNER_TEMP/gate/gate.py"\n          python .github/gate/check.py'
        for step in (above, below):
            with self.subTest(step=step):
                self.assertEqual(["step 0"], head_code_before_the_verdicts(workflow(step, REPORTS)))

    def test_what_runs_nothing_from_the_checkout_is_not_named(self) -> None:
        for spelling in ("        uses: actions/setup-python@v7\n        with:\n          python-version: '3.12'",
                         "        run: python -I -c 'import json'",
                         "        shell: bash\n        env:\n          GATE: .github/gate/gate.py\n        run: true",
                         "        run: git show \"$BASE_SHA:$GATE\" > \"$RUNNER_TEMP/gate/gate.py\"",
                         "        # python -m unittest\n        run: true",
                         "        run: echo 'npm test; make' \"a;b | node\"",
                         '        run: git log -1 > "$RUNNER_TEMP/log" 2>&1',
                         "        run: |\n          take() { git show \"$1\"; }\n          take HEAD"):
            with self.subTest(spelling=spelling):
                self.assertEqual([], head_code_before_the_verdicts(workflow(spelling, JUDGES, REPORTS)))

    def test_a_script_the_reader_cannot_place_is_refused(self) -> None:
        for spelling in ("        run: |\n          cat <<EOF\n          npm test\n          EOF",
                         "        run: echo 'unclosed",
                         '        run: echo "$(git log"',
                         "        run: echo $((1 + 2))"):
            with self.subTest(spelling=spelling), self.assertRaises(ValueError):
                head_code_before_the_verdicts(workflow(spelling, JUDGES, REPORTS))

    def test_the_reader_finds_the_commands_the_workflow_runs(self) -> None:
        # The order case above passes on a reader that finds nothing, so its subject is checked here.
        steps = workflow_steps()
        found = {word for step in steps[:verdicts_at(steps) + 1] if (script := run_script(step))
                 for word in command_words(script)}
        self.assertLessEqual({"git", "gh", "jq", "mkdir", "python"}, found)

    def test_a_workflow_with_no_verdicts_two_or_no_judge_ahead_is_refused(self) -> None:
        for steps in ((JUDGES,), (JUDGES, REPORTS, REPORTS), (REPORTS, JUDGES)):
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                head_code_before_the_verdicts(workflow(*steps))

    def test_a_second_jobs_steps_are_not_read_as_the_first_jobs(self) -> None:
        second = "  other:\n    runs-on: ubuntu-latest\n    steps:\n      - run: python -m unittest\n"
        self.assertEqual([], head_code_before_the_verdicts(workflow(JUDGES, REPORTS) + second))
        self.assertEqual(["- run: python -m unittest"], [name_of(step) for step in steps_of(
            workflow(JUDGES, REPORTS) + second, "other") if runs_head_code(step)])

    def test_a_job_that_is_not_there_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            head_code_before_the_verdicts(workflow(JUDGES, REPORTS), "other")


if __name__ == "__main__":
    unittest.main()
