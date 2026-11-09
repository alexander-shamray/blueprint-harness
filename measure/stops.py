"""Count the stops in Claude Code session transcripts.

Owner: spec 2026-11-02-shared-harness-design.md section 4. What counts and the
command lines: docs/baseline-2026-11.md. Field shapes: transcript-shapes.md.
"""

import argparse
import datetime
import glob
import json
import pathlib
import re
import statistics
import sys

KEYS = ("ask_user", "action_required", "permission_refused", "user_turns")

# Only the text tells a permission refusal from a hook refusal: both are
# is_error with toolDenialKind "permission-rule".
_PERMISSION_REFUSAL = re.compile(
    r"\s*(Permission for this action was denied"
    r"|The user doesn't want to (proceed|take this action)"
    r"|The server-side auto mode classifier gave no verdict)"
)
_ACTION_REQUIRED = "⚠️ ACTION REQUIRED"
_NO_HANDOVER = _ACTION_REQUIRED + " — none"
_NOT_A_TURN = ("<local-command", "<bash-input>", "<bash-stdout>", "<bash-stderr>", "<task-notification>",
               "<system-reminder>", "[Request interrupted")
_COMMAND_TAG = re.compile(r"\s*(?:<command-message>[^<]*</command-message>\s*)?<command-name>/([^<]*)</command-name>")
_LOCAL_CAVEAT = "<local-command-caveat"


def _lines(transcript):
    with open(transcript, encoding="utf-8") as handle:
        for raw in handle:
            try:
                yield json.loads(raw)
            except ValueError:
                # A live session can leave a torn final line. A corrupt line
                # mid-file would lose only its own event, so skipping it
                # undercounts by at most that event; the measure is a floor.
                continue


def _parts(entry):
    content = (entry.get("message") or {}).get("content")
    return content if isinstance(content, list) else []


def _flatten(content):
    if isinstance(content, str):
        return content
    return "\n".join(p.get("text", "") for p in content if isinstance(p, dict))


def _is_genuine_user(entry):
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isSidechain"):
        return False
    if entry.get("isCompactSummary"):
        return False
    if (entry.get("origin") or {}).get("kind", "human") != "human":
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return not content.lstrip().startswith(_NOT_A_TURN)
    if isinstance(content, list):
        kinds = {p.get("type") for p in content if isinstance(p, dict)}
        if "tool_result" in kinds:
            return False
        # Interruption markers arrive as a list holding one text part.
        texts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
        if "image" not in kinds and all(t.lstrip().startswith(_NOT_A_TURN) for t in texts):
            return False
        return bool(kinds & {"text", "image"})
    return False


def _command_opening(entry):
    match = _COMMAND_TAG.match(_flatten((entry.get("message") or {}).get("content")))
    return match.group(1) if match else None


def _is_local_command(entry, previous):
    # A command Claude Code runs itself asks the session for nothing, so it opens
    # no task and is no turn. Only such a command has this line right ahead of it.
    if _command_opening(entry) is None or previous.get("type") != "user" or not previous.get("isMeta"):
        return False
    return _flatten((previous.get("message") or {}).get("content") or "").lstrip().startswith(_LOCAL_CAVEAT)


def count_stops(transcript):
    counts = dict.fromkeys(KEYS, 0)
    opened = False
    previous = {}
    for entry in _lines(transcript):
        kind = entry.get("type")
        if kind == "assistant":
            for part in _parts(entry):
                if part.get("type") == "tool_use" and part.get("name") == "AskUserQuestion":
                    counts["ask_user"] += 1
                elif part.get("type") == "text":
                    last = [line for line in part.get("text", "").splitlines() if line.strip()][-1:]
                    if last and last[0].startswith(_ACTION_REQUIRED) and last[0].strip() != _NO_HANDOVER:
                        counts["action_required"] += 1
        elif kind == "user":
            for part in _parts(entry):
                if part.get("type") == "tool_result" and part.get("is_error"):
                    if _PERMISSION_REFUSAL.match(_flatten(part.get("content") or "")):
                        counts["permission_refused"] += 1
            if _is_genuine_user(entry) and not _is_local_command(entry, previous):
                if opened:
                    counts["user_turns"] += 1
                opened = True
        previous = entry
    return counts


def is_command_session(transcript, command):
    previous = {}
    for entry in _lines(transcript):
        if _is_genuine_user(entry) and not _is_local_command(entry, previous):
            return _command_opening(entry) == command
        previous = entry
    return False


def summarise(rows):
    if not rows:
        return {"sessions": 0, "median": None}
    return {
        "sessions": len(rows),
        "median": {k: statistics.median(r[k] for r in rows) for k in KEYS},
        "total": {k: sum(r[k] for r in rows) for k in KEYS},
        "max": {k: max(r[k] for r in rows) for k in KEYS},
    }


def _transcripts(project, root):
    pattern = project if pathlib.Path(project).is_absolute() else str(root / project)
    for directory in sorted(glob.glob(pattern)):
        yield from sorted(pathlib.Path(directory).glob("*.jsonl"))


def _started(transcript):
    # Bookkeeping lines carry no timestamp, so the first one that does is the start.
    for entry in _lines(transcript):
        stamp = entry.get("timestamp")
        if isinstance(stamp, str):
            try:
                return datetime.datetime.fromisoformat(stamp).astimezone(datetime.UTC)
            except ValueError:
                continue
    return None


def sessions(project, since, root, before=None):
    for path in _transcripts(project, root):
        started = _started(path)
        if started is not None and started >= since and (before is None or started < before):
            yield path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", required=True, help="project directory name or glob under --root")
    parser.add_argument("--since", required=True, type=datetime.date.fromisoformat,
                        help="the window's first day, in UTC: a session counts by the day it started")
    parser.add_argument("--until", type=datetime.date.fromisoformat, help="the window's last day, itself included")
    parser.add_argument("--command", help="only sessions whose first user message, past any local command such as "
                                          "/clear or /model, opens with /<command>")
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path.home() / ".claude" / "projects")
    args = parser.parse_args(argv)
    since = datetime.datetime.combine(args.since, datetime.time.min, datetime.UTC)
    before = None
    if args.until:
        before = datetime.datetime.combine(args.until + datetime.timedelta(days=1), datetime.time.min, datetime.UTC)
    rows = []
    for path in sessions(args.project, since, args.root, before):
        if args.command and not is_command_session(path, args.command):
            continue
        row = count_stops(path)
        rows.append(row)
        print(json.dumps({"session": path.stem, **row}))
    print(json.dumps(summarise(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
