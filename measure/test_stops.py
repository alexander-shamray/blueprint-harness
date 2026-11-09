"""Tests for the stop counter, against synthetic transcripts.

Field shapes, read from real session transcripts under
~/.claude/projects/<project>/<session>.jsonl (one JSON object per line; the
shapes only, no content):

* A session is one ``.jsonl`` file. Lines of interest have ``type`` of
  ``user`` or ``assistant``; the rest (``attachment``, ``ai-title``,
  ``api-request`` ...) are bookkeeping and ignored.
* AskUserQuestion: an ``assistant`` line whose ``message.content`` is a list
  holding ``{"type": "tool_use", "name": "AskUserQuestion", "input": {...}}``.
* Handover: an ``assistant`` line holding ``{"type": "text", "text": ...}``
  whose last non-empty line starts ``⚠️ ACTION REQUIRED``. The convention
  also writes ``⚠️ ACTION REQUIRED — none`` when nothing is owed; that is not
  a stop and is not counted.
* Tool result: a ``user`` line whose ``message.content`` is a list holding
  ``{"type": "tool_result", "is_error": true, "content": <str or list>}``.
  The line also carries ``toolDenialKind`` (``user-rejected``,
  ``automode-blocked``, ``automode-unavailable``, or ``permission-rule``) and
  ``permissionDecision``. A hook refusal is ``is_error: true`` and
  ``toolDenialKind: "permission-rule"`` too, so the flags cannot tell it from
  a permission refusal; only the text can. Permission refusals start
  "Permission for this action was denied", "The user doesn't want to proceed"
  or "The server-side auto mode classifier gave no verdict". Hook refusals
  start "PreToolUse:<Tool> hook error:".
* Genuine user message: a ``user`` line with ``isMeta`` absent, no
  ``isSidechain``, no ``isCompactSummary``, ``origin`` absent or
  ``{"kind": "human"}``, and ``message.content`` either a string or a list of
  ``text``/``image`` parts with no ``tool_result``. Not genuine: tool results;
  ``isMeta: true`` lines (skill and system-reminder expansions); a ``/compact``
  summary, a string line carrying ``isCompactSummary`` and
  ``isVisibleInTranscriptOnly``; ``origin.kind`` other than human
  (``task-notification``, ``plugin``); strings opening ``<local-command``,
  ``<bash-input>``, ``<bash-stdout>``, ``<task-notification>`` or
  ``<system-reminder>``.
* Interruption marker: a ``user`` line whose content is a list holding one
  ``text`` part opening ``[Request interrupted``; no ``origin`` or ``isMeta``.
* Slash command: a genuine string message opening
  ``<command-name>/<name></command-name>``, or ``<command-message>`` and then
  that tag. A diff or fixture quoting the tag holds it later in the message.
* A session a ``/clear`` opens: the new transcript's first genuine message is
  the ``/clear``, an ordinary slash command message, and no later message in
  the file is one. ``/model`` or ``/reload-plugins`` can follow it before the
  task's own command.
"""

import contextlib
import datetime
import io
import json
import os
import pathlib
import tempfile
import unittest

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
            user("<local-command-caveat>x</local-command-caveat>", isMeta=True),
            user("<command-message>ship</command-message>\n<command-name>/ship</command-name>"),
        )
        later = self.transcript(user("hello"), user("<command-name>/ship</command-name>"))
        other = self.transcript(user("<command-name>/ship-it</command-name>"))
        self.assertTrue(stops.is_command_session(ship, "ship"))
        self.assertFalse(stops.is_command_session(later, "ship"))
        self.assertFalse(stops.is_command_session(other, "ship"))

    def test_command_filter_reads_past_the_local_commands_that_open_a_session(self):
        clear = "<command-name>/clear</command-name>\n<command-message>clear</command-message>"
        model = "<command-name>/model</command-name>\n<command-message>model</command-message>"
        plugins = "<command-name>/reload-plugins</command-name>"
        ship = "<command-message>ship</command-message>\n<command-name>/ship</command-name>\n<command-args>x</command-args>"
        after_clear = self.transcript(
            user("<local-command-caveat>x</local-command-caveat>", isMeta=True),
            user(clear),
            user("<local-command-stdout></local-command-stdout>"),
            user(ship),
        )
        after_all = self.transcript(user(clear), user(model), user(plugins), user(ship))
        prose = self.transcript(user(clear), user("hello"), user(ship))
        alone = self.transcript(user(clear))
        self.assertTrue(stops.is_command_session(after_clear, "ship"))
        self.assertTrue(stops.is_command_session(after_all, "ship"))
        self.assertFalse(stops.is_command_session(prose, "ship"))
        self.assertFalse(stops.is_command_session(alone, "ship"))

    def test_command_filter_refuses_a_message_that_only_quotes_the_tag(self):
        quoted = self.transcript(user("Review this change:\n+ <command-name>/ship</command-name>"))
        listed = self.transcript(user([text("Review this:"), text("<command-name>/ship</command-name>")]))
        unclosed = self.transcript(user("<command-name>/ship is the tag to look for"))
        self.assertFalse(stops.is_command_session(quoted, "ship"))
        self.assertFalse(stops.is_command_session(listed, "ship"))
        self.assertFalse(stops.is_command_session(unclosed, "ship"))

    def test_user_turns_start_after_the_command_a_clear_opens(self):
        clear = "<command-name>/clear</command-name>"
        ship = "<command-name>/ship</command-name>"
        cases = (
            (0, [user(clear)]),
            (0, [user(clear), user(ship)]),
            (1, [user(clear), user(ship), user("more")]),
            (1, [user(clear), user("<command-name>/model</command-name>"), user(ship), user("more")]),
            (1, [user(ship), user("more")]),
            (2, [user(ship), user("<command-name>/model</command-name>"), user("more")]),
        )
        for expected, lines in cases:
            self.assertEqual(stops.count_stops(self.transcript(*lines))["user_turns"], expected, lines)

    def test_a_compact_summary_is_not_a_user_turn(self):
        summary = user("This session is being continued from a previous conversation.", isCompactSummary=True,
                       isVisibleInTranscriptOnly=True)
        path = self.transcript(user("<command-name>/ship</command-name>"), summary, user("more"))
        self.assertEqual(stops.count_stops(path)["user_turns"], 1)
        self.assertTrue(stops.is_command_session(self.transcript(summary, user("<command-name>/ship</command-name>")),
                                                 "ship"))

    def test_until_bounds_the_window_and_holds_its_own_day(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        project = pathlib.Path(directory.name) / "project"
        project.mkdir()
        modified = {"before": (2026, 10, 18, 23, 59), "first": (2026, 10, 19, 0, 0), "last": (2026, 11, 2, 23, 59),
                    "after": (2026, 11, 3, 0, 0)}
        for name, when in modified.items():
            path = project / f"{name}.jsonl"
            path.write_text(json.dumps(user("go")) + "\n", encoding="utf-8")
            stamp = datetime.datetime(*when).timestamp()
            os.utime(path, (stamp, stamp))

        def run(*window):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = stops.main(["--project", "project", "--root", directory.name, *window])
            self.assertEqual(code, 0)
            rows = [json.loads(line) for line in out.getvalue().splitlines()]
            return [row["session"] for row in rows[:-1]]

        self.assertEqual(run("--since", "2026-10-19", "--until", "2026-11-02"), ["first", "last"])
        self.assertEqual(run("--since", "2026-10-19"), ["after", "first", "last"])

    def test_median_line_reports_zero_sessions(self):
        self.assertEqual(stops.summarise([]), {"sessions": 0, "median": None})
        rows = [{"ask_user": 1, "action_required": 0, "permission_refused": 2, "user_turns": 3},
                {"ask_user": 2, "action_required": 0, "permission_refused": 4, "user_turns": 5}]
        self.assertEqual(stops.summarise(rows)["median"]["permission_refused"], 3)
        self.assertEqual(stops.summarise(rows)["total"]["user_turns"], 8)
        self.assertEqual(stops.summarise(rows)["max"]["user_turns"], 5)


if __name__ == "__main__":
    unittest.main()
