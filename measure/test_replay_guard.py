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
import unittest.mock

from measure import replay_guard

# A recorded cwd that exists, so only the cases about a gone one meet a gone one.
HERE = str(pathlib.Path(__file__).resolve().parent)
GIT_GUARD = pathlib.Path(HERE).parent / "payload" / ".claude" / "hooks" / "guard-git-argv.py"

# Refuses "refuse-me", "gone-me" only where its cwd is missing and "sub-me" only
# from a directory named sub, and crashes the two ways a guard can on "crash-me".
STUB = textwrap.dedent("""\
    import json, os, sys
    event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    command, cwd = event["tool_input"]["command"], event["cwd"]
    if "raise-me" in command:
        raise RuntimeError("boom")
    if "crash-me" in command:
        reason = "this command crashed the guard that judges it"
    elif ("refuse-me" in command or ("gone-me" in command and not os.path.isdir(cwd))
          or ("sub-me" in command and os.path.basename(cwd) == "sub")):
        reason = "refused in " + event["cwd"]
    else:
        sys.exit(0)
    json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "permissionDecision": "deny",
                                      "permissionDecisionReason": reason}},
              sys.stdout)
""")


def bash(command, cwd=HERE, session="s1", **extra):
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
        self.transcript("used_since", bash("refuse-me before", **started),
                        bash("refuse-me", timestamp="2000-06-01T00:00:00.000Z"))
        self.transcript("not_since", bash("refuse-me too", session="not_since", **started))
        stamp = datetime.datetime(1999, 6, 1).timestamp()
        os.utime(self.project / "not_since.jsonl", (stamp, stamp))
        _, lines = self.replay()
        self.assertEqual(lines[-1], {"commands": 1, "refused": 1})
        self.assertEqual(lines[0]["command"], "refuse-me")

    def test_a_refused_command_is_printed_with_its_session(self):
        worktree = str(self.project)
        self.transcript("s1", bash("git status"), bash("refuse-me", cwd=worktree))
        code, lines = self.replay()
        self.assertEqual(code, 0)
        self.assertEqual(lines[-1], {"commands": 2, "refused": 1})
        self.assertEqual(lines[0]["session"], "s1")
        self.assertEqual(lines[0]["command"], "refuse-me")
        self.assertEqual(lines[0]["cwd"], worktree)
        self.assertEqual(lines[0]["count"], 1)
        self.assertIn(f"refused in {worktree}", lines[0]["reason"])

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

    def test_a_transcript_deleted_after_the_listing_is_skipped_and_the_totals_print(self):
        self.transcript("kept", bash("refuse-me"))
        kept, gone = self.project / "kept.jsonl", self.project / "gone.jsonl"
        # Gone before its time is read, and gone between that read and its lines.
        for name, attribute, value in (
            ("before the stat", "_transcripts",
             lambda project, root: iter([gone, kept] if project == "project" else [])),
            ("after the stat", "transcripts", lambda project, since, root: iter([gone, kept])),
        ):
            with self.subTest(name), unittest.mock.patch.object(replay_guard, attribute, value):
                code, lines = self.replay()
                self.assertEqual(code, 0)
                self.assertEqual(lines[-1], {"commands": 1, "refused": 1})

    def test_a_project_that_matches_no_directory_is_refused_and_not_an_empty_window(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as caught:
                replay_guard.main(["--project", "absent*", "--since", "2000-01-01",
                                   "--guard", str(self.guard), "--root", str(self.root)])
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("matches no directory", err.getvalue())

    def test_a_command_naming_the_project_dir_is_counted_unjudged_and_not_admitted(self):
        # The stub admits it, as the real guard admits a write target it cannot expand.
        for command in ('echo x > "$CLAUDE_PROJECT_DIR/.claude/settings.json"',
                        "cd ${CLAUDE_PROJECT_DIR} && git push --force"):
            with self.subTest(command):
                self.transcript("s1", bash(command), bash("refuse-me"))
                code, lines = self.replay()
                self.assertEqual(code, 0)
                self.assertEqual(lines[0]["command"], command)
                self.assertIn("CLAUDE_PROJECT_DIR", lines[0]["unjudged"])
                self.assertEqual(lines[-2:], [{"unjudged": 1}, {"commands": 2, "refused": 1}])

    def test_a_repeated_command_is_judged_once_and_every_use_counted(self):
        self.guard.write_text(
            'import pathlib, sys\n'
            f'with open({str(self.guard) + ".log"!r}, "a", encoding="utf-8") as log:\n'
            '    log.write(sys.stdin.buffer.read().decode("utf-8") + "\\n")\n',
            encoding="utf-8")
        self.transcript("s1", bash("git status"), bash("git status"))
        self.transcript("s2", bash("git status", session="s2"), bash("git status", cwd=str(self.project)))
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
        gone = str(self.root / ".claude" / "worktrees" / "merged")
        self.transcript("s1", bash("gone-me", cwd=gone))
        _, lines = self.replay()
        self.assertIn(f"refused in {gone}", lines[0]["gone"])

    def test_a_refusal_that_stands_in_the_main_checkout_is_refused(self):
        gone = str(self.root / ".claude" / "worktrees" / "merged")
        self.transcript("s1", bash("refuse-me", cwd=gone), bash("gone-me", cwd=gone))
        _, lines = self.replay()
        self.assertEqual(lines[-2:], [{"gone": 1}, {"commands": 2, "refused": 1}])
        self.assertEqual(lines[0]["command"], "refuse-me")
        self.assertEqual(lines[0]["reason"], f"refused in {self.root}")

    def test_a_removed_worktrees_subdirectory_is_judged_from_the_same_one_in_main(self):
        # From the checkout root rather than root/sub, a relative path names another file.
        (self.root / "sub").mkdir()
        gone = str(self.root / ".claude" / "worktrees" / "merged" / "sub")
        self.transcript("s1", bash("sub-me", cwd=gone))
        _, lines = self.replay()
        self.assertEqual(lines[-1], {"commands": 1, "refused": 1})
        self.assertEqual(lines[0]["reason"], f"refused in {self.root / 'sub'}")

    def test_a_removed_worktrees_command_that_climbs_is_judged_as_recorded(self):
        # From the checkout root, ../../.. would climb out of the checkout instead.
        gone = str(self.root / ".claude" / "worktrees" / "merged")
        self.transcript("s1", bash("gone-me > ../../../.claude/settings.json", cwd=gone),
                        bash("cd ..&& gone-me", cwd=gone))
        _, lines = self.replay()
        self.assertEqual(lines[-1], {"commands": 2, "refused": 2})
        self.assertEqual([line["reason"] for line in lines[:-1]], [f"refused in {gone}"] * 2)

    def test_a_gone_cwd_outside_a_worktree_is_judged_as_recorded(self):
        gone = str(self.root / "gone")
        self.transcript("s1", bash("gone-me", cwd=gone))
        _, lines = self.replay()
        self.assertEqual(lines[-1], {"commands": 1, "refused": 1})
        self.assertEqual(lines[0]["reason"], f"refused in {gone}")

    def test_a_refusal_in_a_gone_cwd_is_counted_apart_from_the_refused(self):
        # The real guard refuses every git command from a removed worktree for
        # the missing directory alone, which is no refusal the session met.
        main = self.root.parent / "main"
        (main / ".git").mkdir(parents=True)
        removed = str(main / ".claude" / "worktrees" / "merged")
        self.transcript("s1", bash("git status", cwd=removed), bash("git status", cwd=removed),
                        bash("ls", cwd=removed), bash("git status", cwd=str(main)),
                        bash("git push --force origin x", cwd=removed),
                        bash("git log origin/main..HEAD", cwd=removed))
        code, lines = self.replay(GIT_GUARD)
        self.assertEqual(code, 0)
        self.assertEqual(lines[-2:], [{"gone": 3}, {"commands": 6, "refused": 1}])
        self.assertEqual((lines[0]["cwd"], lines[0]["count"]), (removed, 2))
        self.assertIn("git no longer registers a worktree there", lines[0]["gone"])
        self.assertEqual((lines[1]["command"], lines[1]["cwd"]), ("git push --force origin x", removed))
        self.assertIn("`git push --force` is not", lines[1]["reason"])
        self.assertEqual(lines[2]["command"], "git log origin/main..HEAD")
        self.assertIn("gone", lines[2])
        self.assertEqual(len(lines), 5)

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
