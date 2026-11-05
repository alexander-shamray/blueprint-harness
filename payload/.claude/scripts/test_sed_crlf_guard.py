"""What `.claude/hooks/guard-sed-crlf.py` refuses, and what it must not.

The verdict cases call the hook's `offence` with `strips_cr=True`, because only Git Bash's sed drops the CR and the
cases have to run on the Linux and macOS jobs too; the process cases run the hook as the harness does and assert the
host's own answer. The last class has the registration as its subject, since every case above passes against a hook
the harness never calls.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
HOOK = SCRIPTS.parent / "hooks" / "guard-sed-crlf.py"
SETTINGS = SCRIPTS.parent / "settings.json"
GIT = shutil.which("git")


def setUpModule():
    # Not a skip: a skip on a missing tool reports a pass, and without git no case can make a tracked file.
    if GIT is None:
        raise AssertionError("git is not on PATH, so no tracked file can be made and nothing here is judged")
    if not HOOK.exists():
        raise AssertionError(f"the hook is missing: {HOOK}")


def guard_module():
    spec = importlib.util.spec_from_file_location("guard_sed_crlf", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GUARD = guard_module()


class ACheckout(unittest.TestCase):
    """A checkout holding tracked CRLF and LF files, an untracked CRLF file, and a tracked CRLF file one level down."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.git("init", "-q")
        self.put("crlf.txt", b"one\r\ntwo\r\n")
        self.put("lf.txt", b"one\ntwo\n")
        self.put(os.path.join("sub", "inner.txt"), b"one\r\ntwo\r\n")
        self.git("-c", "core.autocrlf=false", "add", "crlf.txt", "lf.txt", "sub/inner.txt")
        self.put("loose.txt", b"one\r\ntwo\r\n")

    def git(self, *arguments):
        subprocess.run([GIT, "-C", self.root, *arguments], check=True, capture_output=True)

    def put(self, name, data):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)

    def verdict(self, command, strips_cr=True, tool="Bash"):
        event = {"hook_event_name": "PreToolUse", "cwd": self.root, "tool_name": tool,
                 "tool_input": {"command": command}}
        return GUARD.offence(event, strips_cr=strips_cr)

    def assertRefused(self, command, names):
        reason = self.verdict(command)
        self.assertIsNotNone(reason, f"admitted: {command}")
        self.assertIn(names, reason)
        return reason

    def assertAdmitted(self, command, **kwargs):
        self.assertIsNone(self.verdict(command, **kwargs), f"refused: {command}")


class ARewriteOfATrackedCrlfFileIsRefused(ACheckout):

    def test_the_plain_form_is_refused_with_the_safe_forms_named(self):
        reason = self.assertRefused("sed -i 's/one/uno/' crlf.txt", "crlf.txt")
        self.assertIn("guard-sed-crlf", reason)
        self.assertIn("Edit tool", reason)
        self.assertIn('newline=""', reason)
        self.assertIn("--binary", reason)

    def test_every_spelling_of_in_place_is_refused(self):
        for command in (
            "sed -i.bak 's/one/uno/' crlf.txt",
            "sed --in-place 's/one/uno/' crlf.txt",
            "sed --in-place=.orig 's/one/uno/' crlf.txt",
            "sed --in-pl 's/one/uno/' crlf.txt",
            "sed -ni 's/one/uno/p' crlf.txt",
            "sed -E -i 's/(o)ne/\\1/' crlf.txt",
            "sed -e 's/one/uno/' -i crlf.txt",
            "sed -i -e 's/one/uno/' -e 's/two/dos/' crlf.txt",
            "sed -i -- 's/one/uno/' crlf.txt",
            # `-ie` is `-i` with the suffix `e`, so the script is the next word and the file is still rewritten.
            "sed -ie 's/one/uno/' crlf.txt",
        ):
            with self.subTest(command=command):
                self.assertRefused(command, "crlf.txt")

    def test_a_file_among_others_is_found(self):
        self.assertRefused("sed -i 's/one/uno/' lf.txt loose.txt crlf.txt", "crlf.txt")

    def test_a_sed_after_a_separator_or_a_prefix_is_judged(self):
        for command in (
            "git status && sed -i 's/one/uno/' crlf.txt",
            "true; sed -i 's/one/uno/' crlf.txt",
            "true\nsed -i 's/one/uno/' crlf.txt",
            "LC_ALL=C sed -i 's/one/uno/' crlf.txt",
            "command sed -i 's/one/uno/' crlf.txt",
            "/usr/bin/sed -i 's/one/uno/' crlf.txt",
            "sed -i 's/one/uno/' crlf.txt 2>/dev/null",
        ):
            with self.subTest(command=command):
                self.assertRefused(command, "crlf.txt")

    def test_a_continued_line_and_a_comment_are_read_as_bash_reads_them(self):
        # Review R1: an indented continuation reached `shlex` as a newline token, read as a separator, and an
        # apostrophe in a comment as an unbalanced quote, so both admitted the whole command.
        for command in (
            "sed -i \\\n  -e 's/one/uno/' \\\n  crlf.txt",
            "# don't touch the build\nsed -i 's/one/uno/' crlf.txt",
            "true # it's fine\nsed -i 's/one/uno/' crlf.txt",
        ):
            with self.subTest(command=command):
                self.assertRefused(command, "crlf.txt")

    def test_what_only_looks_like_a_heredoc_leaves_the_lines_after_it_judged(self):
        # Review R2: a here-string and an arithmetic shift matched the heredoc opener, and every later line went
        # unjudged.
        for command in (
            "cat <<< 'one'\nsed -i 's/one/uno/' crlf.txt",
            "echo $((1<<2))\nsed -i 's/one/uno/' crlf.txt",
            "echo '<<EOF'\nsed -i 's/one/uno/' crlf.txt",
        ):
            with self.subTest(command=command):
                self.assertRefused(command, "crlf.txt")

    def test_a_cd_moves_the_files_after_it(self):
        self.assertRefused("cd sub && sed -i 's/one/uno/' inner.txt", "inner.txt")
        self.assertRefused("(cd sub && sed -i 's/one/uno/' inner.txt)", "inner.txt")

    def test_a_cd_in_a_subshell_or_a_pipeline_stays_there(self):
        # Review R4: bash runs a `( … )` group and each pipeline stage in a subshell, so the `cd` is gone after it.
        for command in (
            "(cd sub && true); sed -i 's/one/uno/' crlf.txt",
            "(cd sub; (cd ..)); sed -i 's/one/uno/' crlf.txt",
            "cd sub | true; sed -i 's/one/uno/' crlf.txt",
        ):
            with self.subTest(command=command):
                self.assertRefused(command, "crlf.txt")

    def test_a_sed_inside_a_clause_or_a_group_is_judged(self):
        for command in (
            "if true; then sed -i 's/one/uno/' crlf.txt; fi",
            "{ sed -i 's/one/uno/' crlf.txt; }",
            "! sed -i 's/one/uno/' crlf.txt",
        ):
            with self.subTest(command=command):
                self.assertRefused(command, "crlf.txt")

    def test_a_path_spelled_from_elsewhere_is_judged(self):
        self.assertRefused("sed -i 's/one/uno/' sub/inner.txt", "sub/inner.txt")
        absolute = os.path.join(self.root, "crlf.txt")
        self.assertRefused(f"sed -i 's/one/uno/' '{absolute}'", absolute)

    def test_a_glob_is_expanded_as_bash_would(self):
        self.assertRefused("sed -i 's/one/uno/' *.txt", "*.txt")


class WhatSedLeavesAloneIsAdmitted(ACheckout):

    def test_a_tracked_lf_file(self):
        self.assertAdmitted("sed -i 's/one/uno/' lf.txt")

    def test_an_untracked_crlf_file(self):
        self.assertAdmitted("sed -i 's/one/uno/' loose.txt")

    def test_the_binary_forms_that_keep_the_cr(self):
        for command in (
            "sed --binary -i 's/one/uno/' crlf.txt",
            "sed -b -i 's/one/uno/' crlf.txt",
            "sed -bi 's/one/uno/' crlf.txt",
            "sed -i --bin 's/one/uno/' crlf.txt",
        ):
            with self.subTest(command=command):
                self.assertAdmitted(command)

    def test_a_sed_that_writes_nothing_in_place(self):
        for command in (
            "sed 's/one/uno/' crlf.txt",
            "sed -n '1p' crlf.txt > out.txt",
            # With no -e the first operand is the script, so this names no file at all.
            "sed -i crlf.txt",
            "sed --help",
        ):
            with self.subTest(command=command):
                self.assertAdmitted(command)

    def test_a_command_that_only_mentions_sed(self):
        for command in (
            "grep -i one crlf.txt",
            "echo sed -i 's/one/uno/' crlf.txt",
            "git log --grep='sed -i' -- crlf.txt",
        ):
            with self.subTest(command=command):
                self.assertAdmitted(command)

    def test_a_heredoc_body_is_data(self):
        for opener in ("<<'EOF'", "<<EOF", '<<"EOF"', "<<\\EOF", "<< EOF"):
            with self.subTest(opener=opener):
                self.assertAdmitted(f"cat > fix.sh {opener}\nsed -i 's/one/uno/' crlf.txt\nEOF\n")
        self.assertAdmitted("cat > fix.sh <<-EOF\n\tsed -i 's/one/uno/' crlf.txt\n\tEOF\n")

    def test_a_platform_whose_sed_keeps_the_cr(self):
        # GNU sed on Linux and macOS treats the CR as an ordinary character, so a refusal there would block a
        # harmless edit: the guard's criterion 3.
        self.assertAdmitted("sed -i 's/one/uno/' crlf.txt", strips_cr=False)

    def test_another_tool(self):
        self.assertAdmitted("sed -i 's/one/uno/' crlf.txt", tool="PowerShell")


class WhatTheHookCannotPlaceFailsOpen(ACheckout):
    """The issue's own rule: a path the hook cannot resolve is let through rather than blocking work."""

    def test_unplaceable_operands_and_commands(self):
        for command in (
            "sed -i 's/one/uno/' missing.txt",
            "sed -i 's/one/uno/' \"$FILE\"",
            "sed -i 's/one/uno/' $(git ls-files)",
            "sed -i 's/one/uno/' sub",
            "cd \"$DIR\" && sed -i 's/one/uno/' crlf.txt",
            "sed -i 's/one/uno/ crlf.txt",
        ):
            with self.subTest(command=command):
                self.assertAdmitted(command)

    def test_no_git_admits(self):
        original = GUARD.shutil.which
        GUARD.shutil.which = lambda name: None
        self.addCleanup(setattr, GUARD.shutil, "which", original)
        self.assertAdmitted("sed -i 's/one/uno/' crlf.txt")


class TheHookAsTheHarnessRunsIt(ACheckout):

    def run_hook(self, payload):
        return subprocess.run([sys.executable, str(HOOK)], input=payload.encode("utf-8"), capture_output=True)

    def test_the_host_gives_its_own_answer(self):
        event = {"hook_event_name": "PreToolUse", "cwd": self.root, "tool_name": "Bash",
                 "tool_input": {"command": "sed -i 's/one/uno/' crlf.txt"}}
        result = self.run_hook(json.dumps(event))
        self.assertEqual(0, result.returncode)
        if os.name == "nt":
            verdict = json.loads(result.stdout)["hookSpecificOutput"]
            self.assertEqual("deny", verdict["permissionDecision"])
            self.assertIn("crlf.txt", verdict["permissionDecisionReason"])
        else:
            self.assertEqual(b"", result.stdout.strip())

    def test_a_malformed_event_does_not_take_the_session_down(self):
        for payload in ("not json at all", "[1, 2, 3]", ""):
            with self.subTest(payload=payload):
                result = self.run_hook(payload)
                self.assertEqual(0, result.returncode)
                self.assertEqual(b"", result.stdout.strip())
                self.assertIn(b"guard-sed-crlf", result.stderr)


class TheWiringWithoutWhichNoneOfTheAboveRuns(unittest.TestCase):

    def commands_for(self, tool):
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        return [
            hook.get("command") or ""
            for entry in settings.get("hooks", {}).get("PreToolUse", [])
            if entry.get("matcher") == tool
            for hook in entry.get("hooks") or []
        ]

    def test_the_hook_is_registered_on_bash_on_the_312_floor(self):
        mine = [command for command in self.commands_for("Bash") if HOOK.name in command]
        self.assertEqual(1, len(mine), f"{HOOK.name} is not registered once on Bash: {self.commands_for('Bash')}")
        self.assertIn("py -3.12", mine[0])
        self.assertIn("CLAUDE_PROJECT_DIR", mine[0])

    def test_the_guards_beside_it_are_still_registered(self):
        # An entry added to a list is the shape most likely to be written as a replacement.
        commands = self.commands_for("Bash")
        for guard in ("guard-git-argv.py", "guard-index-argv.py"):
            with self.subTest(guard=guard):
                self.assertTrue(any(guard in command for command in commands), commands)


if __name__ == "__main__":
    unittest.main()
