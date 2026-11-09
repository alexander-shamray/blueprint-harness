"""Tests for the guard replay, against synthetic transcripts and stub guards.

transcript-shapes.md records the field shapes. A ``tool_use`` line also carries
``cwd`` and ``sessionId``, and a subagent's lines are in ``<session>/subagents/``.
"""

import contextlib
import datetime
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import textwrap
import unittest

from measure import replay_guard

# Refuses a command holding "refuse-me", crashes the two ways a guard can on
# one holding "crash-me", and records what it was handed for "show-me".
STUB = textwrap.dedent("""\
    import json, sys
    event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    command = event["tool_input"]["command"]
    if "raise-me" in command:
        raise RuntimeError("boom")
    if "crash-me" in command:
        reason = "this command crashed the guard that judges it"
    elif "refuse-me" in command:
        reason = "refused in " + event["cwd"]
    else:
        sys.exit(0)
    json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "permissionDecision": "deny",
                                      "permissionDecisionReason": reason}},
              sys.stdout)
""")


def bash(command, cwd="/repo", session="s1", **extra):
    return {
        "type": "assistant",
        "cwd": cwd,
        "sessionId": session,
        "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": command}},
        ]},
        **extra,
    }


class Replay(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name) / "projects"
        self.project = self.root / "project"
        self.project.mkdir(parents=True)
        self.guard = pathlib.Path(temporary.name) / "guard.py"
        self.guard.write_text(STUB, encoding="utf-8")

    def transcript(self, name, *entries):
        path = self.project / f"{name}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")

    def replay(self, guard=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = replay_guard.main([
                "--project", "project", "--since", "2000-01-01",
                "--guard", str(guard or self.guard), "--root", str(self.root),
            ])
        return code, [json.loads(line) for line in out.getvalue().splitlines()]

    def test_the_window_reads_the_files_last_use_and_not_the_sessions_start(self):
        started = {"timestamp": "1999-01-01T00:00:00.000Z"}
        self.transcript("used_since", bash("refuse-me", **started))
        self.transcript("not_since", bash("refuse-me too", session="not_since", **started))
        stamp = datetime.datetime(1999, 6, 1).timestamp()
        os.utime(self.project / "not_since.jsonl", (stamp, stamp))
        _, lines = self.replay()
        self.assertEqual(lines[-1], {"commands": 1, "refused": 1})
        self.assertEqual(lines[0]["command"], "refuse-me")

    def test_a_refused_command_is_printed_with_its_session(self):
        self.transcript("s1", bash("git status"), bash("refuse-me", cwd="/worktree"))
        code, lines = self.replay()
        self.assertEqual(code, 0)
        self.assertEqual(lines[-1], {"commands": 2, "refused": 1})
        self.assertEqual(lines[0]["session"], "s1")
        self.assertEqual(lines[0]["command"], "refuse-me")
        self.assertEqual(lines[0]["cwd"], "/worktree")
        self.assertEqual(lines[0]["count"], 1)
        self.assertIn("refused in /worktree", lines[0]["reason"])

    def test_it_runs_as_the_script_its_usage_names(self):
        self.transcript("s1", bash("refuse-me"))
        done = subprocess.run(
            [sys.executable, replay_guard.__file__, "--project", "project", "--since", "2000-01-01",
             "--guard", str(self.guard), "--root", str(self.root)],
            capture_output=True, encoding="utf-8", check=False, cwd=self.root,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout.splitlines()[-1]), {"commands": 1, "refused": 1})

    def test_a_transcript_with_no_bash_prints_zero_commands(self):
        self.transcript("s1", {"type": "user", "message": {"content": "hello"}})
        code, lines = self.replay()
        self.assertEqual(code, 0)
        self.assertEqual(lines, [{"commands": 0, "refused": 0}])

    def test_an_unreadable_guard_exits_nonzero(self):
        self.transcript("s1", bash("refuse-me"))
        for guard in (self.guard.with_name("absent.py"), self.guard.parent):
            with self.subTest(guard=guard):
                code, lines = self.replay(guard)
                self.assertNotEqual(code, 0)
                self.assertEqual(lines, [])

    def test_a_repeated_command_is_judged_once_and_every_use_counted(self):
        self.guard.write_text(
            'import pathlib, sys\n'
            f'with open({str(self.guard) + ".log"!r}, "a", encoding="utf-8") as log:\n'
            '    log.write(sys.stdin.buffer.read().decode("utf-8") + "\\n")\n',
            encoding="utf-8")
        self.transcript("s1", bash("git status"), bash("git status"))
        self.transcript("s2", bash("git status", session="s2"), bash("git status", cwd="/other"))
        code, lines = self.replay()
        self.assertEqual(code, 0)
        self.assertEqual(lines, [{"commands": 4, "refused": 0}])
        log = pathlib.Path(str(self.guard) + ".log").read_text(encoding="utf-8")
        self.assertEqual(len(log.splitlines()), 2)

    def test_a_refusal_repeated_across_sessions_counts_each_use(self):
        self.transcript("s1", bash("refuse-me"), bash("refuse-me"))
        self.transcript("s2", bash("refuse-me", session="s2"))
        _, lines = self.replay()
        self.assertEqual(lines[-1], {"commands": 3, "refused": 3})
        self.assertEqual([(line["session"], line["count"]) for line in lines[:-1]], [("s1", 3)])

    def test_the_guard_is_handed_the_events_recorded_cwd_on_stdin(self):
        self.transcript("s1", bash("refuse-me", cwd="C:\\gone\\worktree"))
        _, lines = self.replay()
        self.assertIn("C:\\gone\\worktree", lines[0]["reason"])

    def test_a_sidechain_entry_is_bash_too(self):
        self.transcript("s1", bash("refuse-me", isSidechain=True))
        subagent = self.project / "s2" / "subagents"
        subagent.mkdir(parents=True)
        (subagent / "agent-a.jsonl").write_text(
            json.dumps(bash("refuse-me too", session="s2", isSidechain=True)) + "\n",
            encoding="utf-8")
        _, lines = self.replay()
        self.assertEqual(lines[-1], {"commands": 2, "refused": 2})
        self.assertEqual({line["session"] for line in lines[:-1]}, {"s1", "s2"})

    def test_a_crashing_guard_is_neither_a_refusal_nor_an_admission(self):
        for command in ("raise-me", "crash-me"):
            with self.subTest(command=command):
                self.transcript("s1", bash(command))
                code, lines = self.replay()
                self.assertEqual(code, 1)
                self.assertEqual(lines[-1], {"commands": 1, "refused": 0})
                self.assertEqual(lines[0]["session"], "s1")
                self.assertEqual(lines[0]["command"], command)
                self.assertEqual(lines[-2], {"crashed": 1})

    def test_a_crash_is_counted_in_uses_as_a_refusal_is(self):
        # Both final numbers count uses, so a command run twice crashes twice.
        self.transcript("s1", bash("crash-me"), bash("crash-me"))
        code, lines = self.replay()
        self.assertEqual(code, 1)
        self.assertEqual(lines[-2], {"crashed": 2})

    def test_output_that_is_no_verdict_is_a_crash(self):
        self.guard.write_text('print("not json")\n', encoding="utf-8")
        self.transcript("s1", bash("git status"))
        code, lines = self.replay()
        self.assertEqual(code, 1)
        self.assertEqual(lines[-2], {"crashed": 1})


if __name__ == "__main__":
    unittest.main()
