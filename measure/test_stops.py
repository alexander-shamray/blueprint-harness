"""Tests for the stop counter, against synthetic transcripts.

transcript-shapes.md records the field shapes they copy.
"""

import contextlib
import datetime
import io
import json
import os
import pathlib
import tempfile
import unittest
import unittest.mock

from measure import stops


def user(content, **extra):
    return {"type": "user", "message": {"role": "user", "content": content}, **extra}


def assistant(*parts):
    return {"type": "assistant", "message": {"role": "assistant", "content": list(parts)}}


def text(value):
    return {"type": "text", "text": value}


def tool_result(value, is_error=True, **extra):
    part = {"type": "tool_result", "tool_use_id": "t1", "is_error": is_error, "content": value}
    return user([part], **extra)


def local(name):
    """A command Claude Code runs itself, in the shape transcript-shapes.md records."""
    command = f"<command-name>/{name}</command-name>\n<command-message>{name}</command-message>"
    shown = {"type": "system", "subtype": "local_command"} if name in ("clear", "reload-plugins") else user(
        "<local-command-stdout></local-command-stdout>")
    return [user("<local-command-caveat>x</local-command-caveat>", isMeta=True), user(command), shown]


class StopsTest(unittest.TestCase):
    def transcript(self, *lines):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = pathlib.Path(directory.name) / "s.jsonl"
        with open(path, "w", encoding="utf-8") as handle:
            for line in lines:
                handle.write(json.dumps(line, ensure_ascii=False) + "\n")
        return path

    def test_ask_user_counted(self):
        path = self.transcript(
            user("go", origin={"kind": "human"}),
            assistant({"type": "tool_use", "name": "AskUserQuestion", "input": {"questions": []}}),
            assistant({"type": "tool_use", "name": "Bash", "input": {}}),
        )
        self.assertEqual(stops.count_stops(path)["ask_user"], 1)

    def test_a_line_torn_inside_a_character_is_skipped_like_any_torn_line(self):
        # A live session's last line can end mid-way through a multi-byte character, which no text read decodes.
        path = self.transcript(
            user("go", origin={"kind": "human"}),
            assistant({"type": "tool_use", "name": "AskUserQuestion", "input": {"questions": []}}),
        )
        with open(path, "ab") as handle:
            handle.write('{"type": "user", "message": {"content": "я'.encode("utf-8")[:-1])
        self.assertEqual(stops.count_stops(path)["ask_user"], 1)

    def test_a_sidechain_entry_counts_toward_nothing(self):
        # A subagent's lines are its own; were one in this file, its questions and refusals are not this session's.
        path = self.transcript(
            user("go", origin={"kind": "human"}),
            {**assistant({"type": "tool_use", "name": "AskUserQuestion", "input": {"questions": []}},
                         text("done\n⚠️ ACTION REQUIRED — run: x")), "isSidechain": True},
            tool_result("Permission for this action was denied.", isSidechain=True),
        )
        counts = stops.count_stops(path)
        self.assertEqual((0, 0, 0), (counts["ask_user"], counts["action_required"], counts["permission_refused"]))

    def test_action_required_counted(self):
        path = self.transcript(
            user("go"),
            assistant(text("Done.\n\n⚠️ ACTION REQUIRED — run: !script.sh")),
            assistant(text("⚠️ ACTION REQUIRED — mentioned mid-text\nand then more")),
            assistant(text("Nothing owed.\n⚠️ ACTION REQUIRED — none")),
            assistant(text("⚠️ ACTION REQUIRED — run: !fix-none")),
        )
        self.assertEqual(stops.count_stops(path)["action_required"], 2)

    def test_permission_refusal_counted(self):
        path = self.transcript(
            user("go"),
            tool_result("Permission for this action was denied by the Claude Code auto mode classifier."),
            tool_result("The user doesn't want to proceed with this tool use."),
            tool_result("The server-side auto mode classifier gave no verdict (error)."),
            tool_result([{"type": "text", "text": "The user doesn't want to proceed with this tool use."}]),
            tool_result("Permission for this action was denied", is_error=False),
        )
        self.assertEqual(stops.count_stops(path)["permission_refused"], 4)

    def test_hook_refusal_not_a_permission_stop(self):
        path = self.transcript(
            user("go"),
            tool_result("PreToolUse:Bash hook error: a script handed to a shell", toolDenialKind="permission-rule"),
            tool_result("Exit code 1\nTraceback"),
        )
        self.assertEqual(stops.count_stops(path)["permission_refused"], 0)

    def test_tool_result_is_not_a_user_turn(self):
        path = self.transcript(
            user("first", origin={"kind": "human"}),
            tool_result("ok", is_error=False),
            user("<local-command-stdout>x</local-command-stdout>"),
            user("<bash-input>ls</bash-input>"),
            user("<task-notification>x</task-notification>", origin={"kind": "task-notification"}),
            user([text("reminder")], isMeta=True),
            user("<system-reminder>x</system-reminder>"),
            user([text("[Request interrupted by user for tool use]")]),
            user("[Request interrupted by user]"),
            user("second"),
            user([text("third"), {"type": "image", "source": {}}], origin={"kind": "human"}),
        )
        self.assertEqual(stops.count_stops(path)["user_turns"], 2)

    def test_command_filter_matches_first_user_message(self):
        ship = self.transcript(
            user("<system-reminder>x</system-reminder>", isMeta=True),
            user("<command-message>ship</command-message>\n<command-name>/ship</command-name>"),
        )
        later = self.transcript(user("hello"), user("<command-name>/ship</command-name>"))
        other = self.transcript(user("<command-name>/ship-it</command-name>"))
        self.assertTrue(stops.is_command_session(ship, "ship"))
        self.assertFalse(stops.is_command_session(later, "ship"))
        self.assertFalse(stops.is_command_session(other, "ship"))

    def test_command_filter_reads_past_the_local_commands_that_open_a_session(self):
        ship = user("<command-message>ship</command-message>\n<command-name>/ship</command-name>\n<command-args>x</command-args>")
        after_clear = self.transcript(*local("clear"), ship)
        after_all = self.transcript(*local("clear"), *local("model"), *local("reload-plugins"), ship)
        after_any = self.transcript(*local("clear"), *local("mcp"), ship)
        prose = self.transcript(*local("clear"), user("hello"), ship)
        alone = self.transcript(*local("clear"))
        self.assertTrue(stops.is_command_session(after_clear, "ship"))
        self.assertTrue(stops.is_command_session(after_all, "ship"))
        self.assertTrue(stops.is_command_session(after_any, "ship"))
        self.assertFalse(stops.is_command_session(prose, "ship"))
        self.assertFalse(stops.is_command_session(alone, "ship"))

    def test_only_a_caveat_right_ahead_makes_a_command_local(self):
        ship = user("<command-name>/ship</command-name>")
        caveat = user("<local-command-caveat>x</local-command-caveat>", isMeta=True)
        shell = self.transcript(caveat, user("<bash-input>ls</bash-input>"), ship, user("more"))
        quoted = self.transcript(user("<local-command-caveat>x</local-command-caveat>"), ship, user("more"))
        answer = self.transcript(assistant(text("<local-command-caveat>x")), ship, user("more"))
        for path in (shell, quoted, answer):
            self.assertTrue(stops.is_command_session(path, "ship"))
            self.assertEqual(stops.count_stops(path)["user_turns"], 1)

    def test_command_filter_refuses_a_message_that_only_quotes_the_tag(self):
        quoted = self.transcript(user("Review this change:\n+ <command-name>/ship</command-name>"))
        listed = self.transcript(user([text("Review this:"), text("<command-name>/ship</command-name>")]))
        unclosed = self.transcript(user("<command-name>/ship is the tag to look for"))
        self.assertFalse(stops.is_command_session(quoted, "ship"))
        self.assertFalse(stops.is_command_session(listed, "ship"))
        self.assertFalse(stops.is_command_session(unclosed, "ship"))

    def test_user_turns_start_after_the_command_a_clear_opens(self):
        ship = user("<command-name>/ship</command-name>")
        more = user("more")
        cases = (
            (0, [*local("clear")]),
            (0, [*local("clear"), ship]),
            (1, [*local("clear"), ship, more]),
            (1, [*local("clear"), *local("model"), ship, more]),
            (1, [ship, more]),
        )
        for expected, lines in cases:
            self.assertEqual(stops.count_stops(self.transcript(*lines))["user_turns"], expected, lines)

    def test_a_local_command_later_in_a_session_is_not_a_turn(self):
        ship = user("<command-name>/ship</command-name>")
        more = user("more")
        for name in ("model", "compact", "mcp", "reload-plugins", "exit"):
            lines = [ship, *local(name), more]
            self.assertEqual(stops.count_stops(self.transcript(*lines))["user_turns"], 1, name)
        skill = user("<command-name>/commit</command-name>")
        self.assertEqual(stops.count_stops(self.transcript(ship, skill, more))["user_turns"], 2)

    def test_a_compact_summary_is_not_a_user_turn(self):
        summary = user("This session is being continued from a previous conversation.", isCompactSummary=True,
                       isVisibleInTranscriptOnly=True)
        path = self.transcript(user("<command-name>/ship</command-name>"), summary, user("more"))
        self.assertEqual(stops.count_stops(path)["user_turns"], 1)
        self.assertTrue(stops.is_command_session(self.transcript(summary, user("<command-name>/ship</command-name>")),
                                                 "ship"))

    def window(self, sessions, *args):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        project = pathlib.Path(directory.name) / "project"
        project.mkdir()
        for name, lines in sessions.items():
            (project / f"{name}.jsonl").write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = stops.main(["--project", "project", "--root", directory.name, *args])
        self.assertEqual(code, 0)
        rows = [json.loads(line) for line in out.getvalue().splitlines()]
        return [row["session"] for row in rows[:-1]]

    def test_until_bounds_the_window_and_holds_its_own_day(self):
        sessions = {
            "before": [user("go", timestamp="2026-10-18T23:59:59.999Z")],
            "first": [user("go", timestamp="2026-10-19T00:00:00.000Z")],
            "last": [user("go", timestamp="2026-11-02T23:59:59.999Z")],
            "after": [user("go", timestamp="2026-11-03T00:00:00.000Z")],
        }
        self.assertEqual(self.window(sessions, "--since", "2026-10-19", "--until", "2026-11-02"), ["first", "last"])
        self.assertEqual(self.window(sessions, "--since", "2026-10-19"), ["after", "first", "last"])

    def test_the_window_reads_a_sessions_start_and_not_its_later_use(self):
        sessions = {
            "resumed_inside": [user("go", timestamp="2026-10-18T02:25:20.788Z"),
                               user("more", timestamp="2026-10-19T04:01:06.901Z")],
            "resumed_after": [user("go", timestamp="2026-11-02T10:00:00.000Z"),
                              user("more", timestamp="2026-11-03T10:00:00.000Z")],
        }
        self.assertEqual(self.window(sessions, "--since", "2026-10-19", "--until", "2026-11-02"), ["resumed_after"])

    def test_the_window_ignores_the_files_modification_time(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        project = pathlib.Path(directory.name) / "project"
        project.mkdir()
        path = project / "session.jsonl"
        path.write_text(json.dumps(user("go", timestamp="2026-10-20T00:00:00.000Z")) + "\n", encoding="utf-8")
        stamp = datetime.datetime(2026, 12, 1).timestamp()
        os.utime(path, (stamp, stamp))
        since = datetime.datetime(2026, 10, 19, tzinfo=datetime.UTC)
        before = datetime.datetime(2026, 11, 3, tzinfo=datetime.UTC)
        self.assertEqual(list(stops.sessions("project", since, pathlib.Path(directory.name), before)), [path])

    def test_a_sessions_start_is_its_first_stamped_line_in_utc(self):
        ahead = [{"type": "mode", "mode": "auto"}, {"type": "ai-title", "aiTitle": "x"}]
        sessions = {
            "bookkeeping": [*ahead, {"type": "queue-operation", "timestamp": "2026-10-19T01:00:00.000Z"}, user("go")],
            "offset": [user("go", timestamp="2026-10-19T06:00:00+07:00")],
            "unreadable": [user("go", timestamp="not a date"), user("go", timestamp=1),
                           user("more", timestamp="2026-10-19T02:00:00.000Z")],
            "unstamped": [*ahead, user("go")],
        }
        self.assertEqual(self.window(sessions, "--since", "2026-10-19"), ["bookkeeping", "unreadable"])

    def test_a_transcript_deleted_after_the_listing_is_skipped_and_the_totals_print(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        project = pathlib.Path(directory.name) / "project"
        project.mkdir()
        kept = project / "kept.jsonl"
        kept.write_text(json.dumps(user("<command-name>/ship</command-name>", timestamp="2026-10-20T00:00:00Z")) + "\n",
                        encoding="utf-8")
        gone = project / "gone.jsonl"
        started = datetime.datetime(2026, 10, 20, tzinfo=datetime.UTC)
        # Gone before its start is read, and gone between that read and the count.
        for name, patches in (("before the start", {}), ("after the start", {"_started": lambda path: started})):
            for command in ([], ["--command", "ship"]):
                with self.subTest(name, command=command):
                    out = io.StringIO()
                    with contextlib.ExitStack() as stack:
                        stack.enter_context(unittest.mock.patch.object(
                            stops, "_transcripts", lambda project, root: iter([gone, kept])))
                        for attribute, value in patches.items():
                            stack.enter_context(unittest.mock.patch.object(stops, attribute, value))
                        stack.enter_context(contextlib.redirect_stdout(out))
                        code = stops.main(["--project", "project", "--root", directory.name,
                                           "--since", "2026-10-19", *command])
                    self.assertEqual(code, 0)
                    rows = [json.loads(line) for line in out.getvalue().splitlines()]
                    self.assertEqual([row["session"] for row in rows[:-1]], ["kept"])
                    self.assertEqual(rows[-1]["sessions"], 1)

    def test_a_root_holding_glob_characters_names_itself(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        # Windows refuses ? and * in a name, so the brackets stand for every glob character.
        for name in ("home[1]", "[ab]home"):
            with self.subTest(name):
                root = pathlib.Path(directory.name) / name / "projects"
                (root / "project").mkdir(parents=True)
                (root / "project" / "s.jsonl").write_text(
                    json.dumps(user("go", timestamp="2026-10-20T00:00:00Z")) + "\n", encoding="utf-8")
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = stops.main(["--project", "proj*", "--root", str(root), "--since", "2026-10-19"])
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(out.getvalue().splitlines()[-1])["sessions"], 1)

    def refused(self, *args):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        (pathlib.Path(directory.name) / "project").mkdir()
        (pathlib.Path(directory.name) / "project" / "s.jsonl").write_text("", encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as caught:
                stops.main(["--root", directory.name, *args])
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(out.getvalue(), "")
        return err.getvalue()

    def test_a_project_that_matches_no_directory_is_refused_and_not_an_empty_window(self):
        for project in ("absent", "absent*", "project/s.jsonl"):
            with self.subTest(project):
                self.assertIn("matches no directory", self.refused("--project", project, "--since", "2026-10-19"))

    def test_an_until_before_the_since_is_refused(self):
        self.assertIn("before --since", self.refused("--project", "project", "--since", "2026-10-19",
                                                     "--until", "2026-10-18"))

    def test_the_command_filter_takes_the_slash_form_and_refuses_an_empty_name(self):
        sessions = {
            "shipped": [user("<command-name>/ship</command-name>", timestamp="2026-10-20T00:00:00Z")],
            "other": [user("go", timestamp="2026-10-20T00:00:00Z")],
        }
        for command in ("ship", "/ship"):
            with self.subTest(command):
                self.assertEqual(self.window(sessions, "--since", "2026-10-19", "--command", command), ["shipped"])
        for command in ("", "/"):
            with self.subTest(command):
                self.assertIn("names no command", self.refused("--project", "project", "--since", "2026-10-19",
                                                               "--command", command))

    def test_median_line_reports_zero_sessions(self):
        self.assertEqual(stops.summarise([]), {"sessions": 0, "median": None})
        rows = [{"ask_user": 1, "action_required": 0, "permission_refused": 2, "user_turns": 3},
                {"ask_user": 2, "action_required": 0, "permission_refused": 4, "user_turns": 5}]
        self.assertEqual(stops.summarise(rows)["median"]["permission_refused"], 3)
        self.assertEqual(stops.summarise(rows)["total"]["user_turns"], 8)
        self.assertEqual(stops.summarise(rows)["max"]["user_turns"], 5)


if __name__ == "__main__":
    unittest.main()
