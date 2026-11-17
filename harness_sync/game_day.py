"""The harness's game day: break each guard and gate for real, in a throwaway target, and check it refuses.

Guards fire through the rendered hook commands; `FINDING:` marks a call let through, refused for another reason, or
wired with no scenario (README.md, *Tests*). Run as `py -3.12 -m harness_sync.game_day`.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD = ROOT / "payload"
GUARD_COMMAND = re.compile(r'^sh "\$\{CLAUDE_PROJECT_DIR\}/\.claude/hooks/run-guard\.sh" (?P<guard>[\w.-]+\.py)$')

# (tool, guard) -> [(the command or edit that must be refused, a fragment the refusal must carry)]. The fragment
# is the guard's documented reason, so a refusal for some other cause, a crash's included, is a finding too. Nothing
# here runs: the guard judges the event and the tool never starts. `{home}` is the home directory, whose keys the
# edit guard refuses by name.
LOGIN = "a key, a shell profile or git's or npm's own configuration below the home"
GUARD_SCENARIOS = {
    ("Bash", "guard-git-argv.py"): [
        ({"command": "git filter-branch --tree-filter 'touch x' HEAD"},
         "runs the shell commands its --*-filter options carry"),
        ({"command": "git push --force origin HEAD"}, "is not one of the options this guard recognises"),
    ],
    ("PowerShell", "guard-git-argv.py"): [
        ({"command": "git filter-branch --tree-filter 'touch x' HEAD"},
         "a PowerShell command is admitted only as one read-only cmdlet"),
    ],
    ("Bash", "guard-index-argv.py"): [
        ({"command": "bash .claude/skills/codebase-index/scripts/cbx search x; touch y"},
         "may not share the line with another command"),
    ],
    ("Bash", "guard-helper-argv.py"): [
        ({"command": 'py -3.12 .claude/scripts/dispatch_board.py tasks start "$(whoami)"'},
         "a command substitution in a command that runs a helper is refused"),
    ],
    ("Bash", "guard-sed-crlf.py"): [
        ({"command": "sed -i 's/a/b/' crlf.txt"}, "CRLF"),
    ],
    ("Edit", "guard-edit-target.py"): [
        ({"file_path": "{home}/.ssh/authorized_keys", "old_string": "a", "new_string": "b"}, LOGIN),
    ],
    ("Write", "guard-edit-target.py"): [
        ({"file_path": "{home}/.claude/settings.json", "content": "{}"}, "inside the harness's own control surface"),
    ],
    ("NotebookEdit", "guard-edit-target.py"): [
        ({"notebook_path": "{home}/.ssh/game-day.ipynb", "new_source": "x"}, LOGIN),
    ],
    ("MultiEdit", "guard-edit-target.py"): [
        ({"file_path": "{home}/.ssh/config", "edits": []}, LOGIN),
    ],
}

# A guard whose refusal is one platform's, as `os.name` names it: elsewhere it documents admitting the call, and a
# refusal there is the finding. Only Git Bash's sed drops the CR (*The sed line-ending guard*).
REFUSED_ON = {("Bash", "guard-sed-crlf.py"): "nt"}

# The conditions a game day is asked for that this run does not cause, and the suite that does.
REASONS = {
    "sync pull request whose proof does not match its head": "`sync_pr.py verify` reads the pull request from "
    "GitHub; `test_ship_sync.py` and `test_dispatch_sync.py` hold it with `gh` stubbed",
    "red main while /dispatch would launch": "`main-red-open.sh` reads open issues from GitHub; "
    "`test_main_red_open.py` and `test_dispatch_run.py` hold it with `gh` stubbed",
    "stop file mid-night": "it is read from a dispatch run's own directory and state; `test_dispatch_run.py` holds it",
    "a permission deny (Edit or Bash) firing": "Claude Code's permission engine cannot run outside a session; "
    "`test_harness_denies.py` holds the rendered deny list",
}


def run(args, cwd, env=None, stdin=None):
    return subprocess.run(args, cwd=cwd, env=env, input=stdin, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120)


def apply_payload(base):
    """A scratch target with this repository's config and the payload applied, as a sync applies it."""
    target = base / "target"
    (target / ".harness").mkdir(parents=True)
    shutil.copy(ROOT / ".harness" / "config.json", target / ".harness" / "config.json")
    run(["git", "init", "-q", "."], target)
    commit = run(["git", "rev-parse", "HEAD"], ROOT).stdout.strip() or "0" * 40
    done = run([sys.executable, "-m", "harness_sync", "apply", "--payload", str(PAYLOAD), "--target", str(target),
                "--commit", commit], ROOT)
    if done.returncode != 0:
        raise RuntimeError(f"the payload did not apply: {done.stderr.strip() or done.stdout.strip()}")
    return target


def guard_hooks(target):
    """(tool, guard) for each PreToolUse hook the rendered settings wire to the guard launcher."""
    settings = json.loads((target / ".claude" / "settings.json").read_text(encoding="utf-8"))
    wired = set()
    for entry in settings.get("hooks", {}).get("PreToolUse", []):
        for hook in entry.get("hooks", []):
            match = GUARD_COMMAND.match(hook.get("command", ""))
            if match:
                for tool in entry.get("matcher", "").split("|"):
                    wired.add((tool, match["guard"], hook["command"]))
    return wired


def launcher_guards(target):
    """The guards the launcher's closed set admits."""
    text = (target / ".claude" / "hooks" / "run-guard.sh").read_text(encoding="utf-8")
    return set(re.findall(r"guard-[\w-]+\.py", text))


def fire(target, tool, command, tool_input):
    """The hook command run as Claude Code runs it: `sh -c`, the project directory in the environment."""
    event = {"session_id": "game-day", "hook_event_name": "PreToolUse", "tool_name": tool, "cwd": str(target),
             "tool_input": tool_input}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(target))
    return run(["sh", "-c", command], target, env=env, stdin=json.dumps(event))


def refusal(done):
    """The refusal's reason, or None where the hook let the call through."""
    if done.returncode == 2:
        return done.stderr.strip() or "(exit 2)"
    if done.returncode != 0:
        return None
    try:
        output = json.loads(done.stdout) if done.stdout.strip() else {}
    except json.JSONDecodeError:
        return None
    specific = output.get("hookSpecificOutput", {}) if isinstance(output, dict) else {}
    if specific.get("permissionDecision") == "deny":
        return specific.get("permissionDecisionReason", "")
    return None


def guard_scenarios(target):
    findings, oks = [], []
    wired = guard_hooks(target)
    covered = {(tool, guard) for tool, guard, _ in wired}
    for guard in sorted(launcher_guards(target) - {guard for _, guard in covered}):
        findings.append(f"{guard} is in the launcher's closed set but no PreToolUse hook runs it")
    for key in sorted(covered - set(GUARD_SCENARIOS)):
        findings.append(f"{key[1]} is wired for {key[0]} with no game-day scenario")
    for key in sorted(set(GUARD_SCENARIOS) - covered):
        findings.append(f"the scenario for {key[1]} on {key[0]} names a hook the settings no longer wire")
    (target / "crlf.txt").write_bytes(b"a\r\nb\r\n")
    run(["git", "add", "crlf.txt"], target)
    home = Path.home().as_posix()
    for tool, guard, command in sorted(wired):
        for tool_input, fragment in GUARD_SCENARIOS.get((tool, guard), []):
            tool_input = {k: v.replace("{home}", home) if isinstance(v, str) else v for k, v in tool_input.items()}
            reason = refusal(fire(target, tool, command, tool_input))
            name = f"{guard} on {tool} for {tool_input}"
            if (tool, guard) in REFUSED_ON and os.name != REFUSED_ON[(tool, guard)]:
                if reason is None:
                    oks.append(f"{name} let through, as it documents off {REFUSED_ON[(tool, guard)]}")
                else:
                    findings.append(f"{name} refused off {REFUSED_ON[(tool, guard)]}, where it documents admitting it: "
                                    f"{reason[:300]}")
            elif reason is None:
                findings.append(f"{name} let through what it documents refusing")
            elif fragment not in reason:
                findings.append(f"{name} refused, but not with its documented reason ({fragment!r}): {reason[:300]}")
            else:
                oks.append(f"{name} refused")
    return findings, oks


def drift_scenario(target):
    gate = [sys.executable, "-m", "harness_sync", "check", "--target", str(target)]
    clean = run(gate, ROOT)
    if clean.returncode != 0:
        return [f"the drift gate refuses a freshly applied target: {clean.stdout.strip()} {clean.stderr.strip()}"], []
    managed = ".claude/hooks/run-guard.py"
    with open(target / managed, "a", encoding="utf-8") as handle:
        handle.write("# edited in the target\n")
    edited = run(gate, ROOT)
    if edited.returncode == 0 or f"{managed} differs from the manifest" not in edited.stdout + edited.stderr:
        return [f"the drift gate passed a managed file edited in the target: {edited.stdout.strip()}"], []
    return [], ["the drift gate refused a managed file edited in the target"]


# What `dispatch_board.py`'s section scan refuses a list missing a section with.
SHAPE = r"section '[^']+' is missing"


def task_list_scenario(target):
    config = json.loads((target / ".harness" / "config.json").read_text(encoding="utf-8"))
    listed = target.parent / config["task_list"]
    listed.parent.mkdir(parents=True, exist_ok=True)
    listed.write_text("# Tasks\n\n- [ ] something written by hand\n", encoding="utf-8")
    before = listed.read_bytes()
    # An executor's environment would refuse every write for another cause, so the scenario runs outside one.
    env = {k: v for k, v in os.environ.items() if k != "HARNESS_DISPATCHED"}
    done = run([sys.executable, ".claude/scripts/dispatch_board.py", "tasks", "start", "owed", "--branch",
                "feat/game-day", "--worktree", ".", "--what", "game day"], target, env=env)
    if done.returncode == 0:
        return [f"dispatch_board.py wrote over a task list in a shape `board` refuses ({SHAPE})"], []
    if listed.read_bytes() != before:
        return ["dispatch_board.py refused a task list in a shape `board` refuses but changed it anyway"], []
    if not re.search(rf"refused: .*{SHAPE}", done.stderr):
        return [f"dispatch_board.py refused a task list in a shape `board` refuses, but not with its documented reason "
                f"({SHAPE!r}): {done.stderr.strip()[:300]}"], []
    return [], ["dispatch_board.py refused a task list in a shape `board` refuses"]


def main():
    base = Path(tempfile.mkdtemp(prefix="game-day-"))
    try:
        target = apply_payload(base)
        findings, oks = [], []
        for scenario in (guard_scenarios, drift_scenario, task_list_scenario):
            found, passed = scenario(target)
            findings += found
            oks += passed
    finally:
        shutil.rmtree(base, ignore_errors=True)
    for line in oks:
        print(f"ok: {line}")
    for condition, reason in REASONS.items():
        print(f"not caused: {condition}: {reason}")
    for line in findings:
        print(f"FINDING: {line}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
