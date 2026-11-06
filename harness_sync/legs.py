"""Whether a run of `payload-suites` tests on its windows and macos legs: prints `test=true` or `test=false`.

Their suites read the rendered tree, so a change reaches them through what renders that tree or the steps that test it.
Only a pull request whose merge commit reads cleanly and reaches none of that skips; a wrong skip loses a run.
"""

import subprocess
from collections.abc import Iterable
from pathlib import Path

REACH = (
    ".github/workflows/ci.yml",
    "harness_sync/",
    "payload/.claude/hooks/",
    "payload/.claude/scripts/",
    "payload/.claude/skills/codebase-index/examples/",
    "payload/.harness/",
    "targets/",
)


def _git(root: Path, *args: str) -> str | None:
    done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", check=False)
    return done.stdout if done.returncode == 0 else None


def changed_paths(root: Path) -> list[str] | None:
    """What HEAD changes against its first parent, both sides of a move, or None unless HEAD is a merge."""
    if _git(root, "rev-parse", "--verify", "--quiet", "HEAD^2") is None:
        return None
    out = _git(root, "diff", "--name-only", "--no-renames", "-z", "HEAD^1", "HEAD")
    return None if out is None else [path for path in out.split("\0") if path]


def reaches(paths: Iterable[str]) -> bool:
    return any(path.startswith(REACH) for path in paths)


def should_test(event: str, root: Path) -> bool:
    if event != "pull_request":
        return True
    paths = changed_paths(root)
    return not paths or reaches(paths)
