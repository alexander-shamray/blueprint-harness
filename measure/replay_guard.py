"""Replay the Bash commands of Claude Code transcripts through a guard hook.

Each distinct (command, cwd) runs through the hook's stdin contract, and every use counts.
A crash (exit 1) and a refusal only a cwd now gone earns are not refusals; an unreadable guard is exit 2.
Usage: py -3.12 measure/replay_guard.py --project <glob> --since <date> --guard <hook>"""

import argparse
import concurrent.futures
import datetime
import json
import os
import pathlib
import subprocess
import sys

# Run as the script the usage names, `measure/` is on the path and its parent is not.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from measure.stops import _lines, _parts, _transcripts  # noqa: E402

GUARD_TIMEOUT = 120
PROGRESS_EVERY = 5000

# The guard's own fail-closed branch: a deny, but no judgement of the command.
_CRASHED_DENY = "crashed the guard"
_UNJUDGED_STDERR = ("Traceback (most recent call last)", "not judging")


def touched(project, since, root):
    # The commands run since a day, so a session started earlier holds some of them.
    for path in _transcripts(project, root):
        if datetime.datetime.fromtimestamp(path.stat().st_mtime) >= since:
            yield path


def transcripts(project, since, root):
    # Subagents write their own files, under a directory touched() stops above.
    yield from touched(project, since, root)
    yield from touched(f"{project}/*/subagents", since, root)


def bash_uses(transcript):
    for entry in _lines(transcript):
        if entry.get("type") != "assistant":
            continue
        for part in _parts(entry):
            if part.get("type") != "tool_use" or part.get("name") != "Bash":
                continue
            command = (part.get("input") or {}).get("command")
            if isinstance(command, str):
                yield command, entry.get("cwd") or "", entry.get("sessionId") or transcript.stem


def event_for(command, cwd, session):
    return {
        "session_id": session,
        "cwd": cwd,
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def read_verdict(returncode, stdout, stderr):
    """Read the hook's contract: `("refused"|"admitted"|"crashed", detail)`."""
    if any(mark in stderr for mark in _UNJUDGED_STDERR):
        return "crashed", stderr.strip()[-500:]
    if returncode == 2:
        return "refused", stderr.strip()
    if returncode != 0:
        return "crashed", f"exit {returncode}: {stderr.strip()[-500:]}"
    if not stdout.strip():
        return "admitted", None
    try:
        decision = json.loads(stdout)["hookSpecificOutput"]
    except (ValueError, KeyError, TypeError):
        return "crashed", f"no verdict in stdout: {stdout[:500]}"
    if not isinstance(decision, dict):
        return "crashed", f"no verdict in stdout: {stdout[:500]}"
    if decision.get("permissionDecision") != "deny":
        return "admitted", None
    reason = decision.get("permissionDecisionReason", "")
    return ("crashed" if _CRASHED_DENY in reason else "refused"), reason


def run_guard(guard, command, cwd, session):
    # The caller's CLAUDE_PROJECT_DIR is this run's, not the recorded session's.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    try:
        done = subprocess.run(
            [sys.executable, str(guard)],
            input=json.dumps(event_for(command, cwd, session)).encode("utf-8"),
            capture_output=True,
            timeout=GUARD_TIMEOUT,
            cwd=cwd if cwd and os.path.isdir(cwd) else None,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "crashed", f"no verdict in {GUARD_TIMEOUT}s"
    return read_verdict(
        done.returncode,
        done.stdout.decode("utf-8", "replace"),
        done.stderr.decode("utf-8", "replace"),
    )


def standing(path):
    """The nearest directory at or above `path` that exists, or `""`."""
    while path and not os.path.isdir(path):
        parent = os.path.dirname(path)
        if parent == path:
            return ""
        path = parent
    return path


def judge(guard, command, cwd, session):
    """`read_verdict`'s pair, but `"gone"` for a refusal only a gone cwd earns.

    A guard may refuse for the missing directory alone, as guard-git-argv refuses
    git from a removed worktree, so one judged gone is judged again from above it.
    """
    kind, detail = run_guard(guard, command, cwd, session)
    if kind != "refused" or not cwd or os.path.isdir(cwd):
        return kind, detail
    again = run_guard(guard, command, standing(cwd), session)
    return ("gone", detail) if again[0] == "admitted" else again


def replay(guard, uses, workers):
    """`(commands, rows)`: every use counted, one row per distinct (command, cwd)."""
    total = 0
    distinct = {}
    for command, cwd, session in uses:
        total += 1
        row = distinct.setdefault((command, cwd), {"session": session, "count": 0})
        row["count"] += 1
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        verdicts = pool.map(
            lambda item: judge(guard, item[0][0], item[0][1], item[1]["session"]),
            distinct.items(),
        )
        for index, (item, verdict) in enumerate(zip(distinct.items(), verdicts), 1):
            (command, cwd), row = item
            rows.append({**row, "command": command, "cwd": cwd, "verdict": verdict})
            if index % PROGRESS_EVERY == 0:
                print(f"{index}/{len(distinct)} distinct", file=sys.stderr, flush=True)
    return total, rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", required=True, help="project directory name or glob under --root")
    parser.add_argument("--since", required=True, type=datetime.date.fromisoformat)
    parser.add_argument("--guard", required=True, type=pathlib.Path, help="the hook to run")
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path.home() / ".claude" / "projects")
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    args = parser.parse_args(argv)
    guard = args.guard.resolve()
    try:
        guard.read_bytes()
    except OSError as error:
        print(f"replay_guard: cannot read the guard: {error}", file=sys.stderr)
        return 2
    since = datetime.datetime.combine(args.since, datetime.time.min)
    uses = (use for path in transcripts(args.project, since, args.root) for use in bash_uses(path))
    commands, rows = replay(guard, uses, args.workers)
    refused = crashed = gone = 0
    for row in rows:
        kind, detail = row.pop("verdict")
        if kind == "admitted":
            continue
        if kind == "refused":
            refused += row["count"]
            print(json.dumps({**row, "reason": detail}))
        elif kind == "gone":
            gone += row["count"]
            print(json.dumps({**row, "gone": detail}))
        else:
            crashed += row["count"]
            print(json.dumps({**row, "crash": detail}))
    if gone:
        print(json.dumps({"gone": gone}))
    if crashed:
        print(json.dumps({"crashed": crashed}))
    print(json.dumps({"commands": commands, "refused": refused}))
    return 1 if crashed else 0


if __name__ == "__main__":
    sys.exit(main())
