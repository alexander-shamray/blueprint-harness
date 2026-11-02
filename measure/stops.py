"""Count the stops in Claude Code session transcripts.

Owner: spec 2026-11-02-shared-harness-design.md section 4 ("Agents stop more
often"). A stop is an AskUserQuestion tool use, a handover whose last line
starts "ACTION REQUIRED", or a tool error that is a permission refusal. The
transcript field shapes are recorded in test_stops.py.

Usage:
    py -3.12 measure/stops.py --project 'C--dev-ashamray-blueprint-backend*' \
        --since 2026-10-19 --command ship
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
_NOT_A_TURN = ("<local-command", "<bash-input>", "<bash-stdout>", "<bash-stderr>", "<task-notification>",
               "<system-reminder>")


def _lines(transcript):
    with open(transcript, encoding="utf-8") as handle:
        for raw in handle:
            try:
                yield json.loads(raw)
            except ValueError:
                continue  # a torn final line from a live session


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
    if (entry.get("origin") or {}).get("kind", "human") != "human":
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return not content.lstrip().startswith(_NOT_A_TURN)
    if isinstance(content, list):
        kinds = {p.get("type") for p in content if isinstance(p, dict)}
        return "tool_result" not in kinds and bool(kinds & {"text", "image"})
    return False


def count_stops(transcript):
    counts = dict.fromkeys(KEYS, 0)
    genuine = 0
    for entry in _lines(transcript):
        kind = entry.get("type")
        if kind == "assistant":
            for part in _parts(entry):
                if part.get("type") == "tool_use" and part.get("name") == "AskUserQuestion":
                    counts["ask_user"] += 1
                elif part.get("type") == "text":
                    last = [line for line in part.get("text", "").splitlines() if line.strip()][-1:]
                    if last and last[0].startswith(_ACTION_REQUIRED) and not last[0].rstrip().endswith("none"):
                        counts["action_required"] += 1
        elif kind == "user":
            for part in _parts(entry):
                if part.get("type") == "tool_result" and part.get("is_error"):
                    if _PERMISSION_REFUSAL.match(_flatten(part.get("content") or "")):
                        counts["permission_refused"] += 1
            if _is_genuine_user(entry):
                genuine += 1
    counts["user_turns"] = max(genuine - 1, 0)
    return counts


def is_command_session(transcript, command):
    pattern = re.compile(r"<command-name>/" + re.escape(command) + r"(?![\w-])")
    for entry in _lines(transcript):
        if _is_genuine_user(entry):
            content = (entry.get("message") or {}).get("content")
            return bool(pattern.search(_flatten(content)))
    return False


def summarise(rows):
    if not rows:
        return {"sessions": 0, "median": None}
    return {"sessions": len(rows), "median": {k: statistics.median(r[k] for r in rows) for k in KEYS}}


def sessions(project, since, root):
    pattern = project if pathlib.Path(project).is_absolute() else str(root / project)
    for directory in sorted(glob.glob(pattern)):
        for path in sorted(pathlib.Path(directory).glob("*.jsonl")):
            if datetime.datetime.fromtimestamp(path.stat().st_mtime) >= since:
                yield path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", required=True, help="project directory name or glob under --root")
    parser.add_argument("--since", required=True, type=datetime.date.fromisoformat)
    parser.add_argument("--command", help="only sessions whose first user message is /<command>")
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path.home() / ".claude" / "projects")
    args = parser.parse_args(argv)
    since = datetime.datetime.combine(args.since, datetime.time.min)
    rows = []
    for path in sessions(args.project, since, args.root):
        if args.command and not is_command_session(path, args.command):
            continue
        row = count_stops(path)
        rows.append(row)
        print(json.dumps({"session": path.stem, **row}))
    print(json.dumps(summarise(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
