#!/usr/bin/env python3
"""Whether a target's off-Linux harness legs test: prints `test=true` or `test=false` for `$GITHUB_OUTPUT`.

`docs/harness-boundaries.md`, *The harness legs decision*: only a clean merge reaching nothing the suite reads skips.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from sync_pr import folded

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ".harness/manifest.json"
CONFIG = ".harness/config.json"

# Trees and files every target's suite reads whatever its manifest lists: the harness's own trees, which hold the
# target's `local` helpers and the settings, and the one document a target writes for the payload's commands.
TREES = (".claude/", ".harness/")
FILES = ("docs/harness-local.md",)
# At any depth: a nested ignore file is what `test_root_ignore_covers_nested.py` reads, and an attributes file sets
# the line endings a Windows checkout gets.
NAMES = (".gitignore", ".gitattributes")
# `owner/repo/<path>@<ref>`, which GitHub sets for the run; the path is the workflow that calls this helper.
WORKFLOW_REF = re.compile(r"[^/]+/[^/]+/(\.github/workflows/[^@]+\.ya?ml)@.+")


def _git(root, *args):
    try:
        done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8",
                              check=False)
    except OSError:
        return None
    return done.stdout if done.returncode == 0 else None


def changed_paths(root):
    """What HEAD changes against its first parent, both sides of a move, or None unless HEAD is a merge read whole."""
    if _git(root, "rev-parse", "--verify", "--quiet", "HEAD^2") is None:
        return None
    out = _git(root, "diff", "--name-only", "--no-renames", "-z", "HEAD^1", "HEAD")
    return None if out is None else [path for path in out.split("\0") if path]


def workflow_path(ref):
    """The calling workflow's path out of `GITHUB_WORKFLOW_REF`, or None when it does not read as one."""
    match = WORKFLOW_REF.fullmatch(ref or "")
    return match.group(1) if match else None


def _json(root, rel):
    try:
        return json.loads((root / rel).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def reach(root, workflow):
    """(managed paths, `local` globs, the workflow), each read from the target, or None if any read failed."""
    manifest, config = _json(root, MANIFEST), _json(root, CONFIG)
    files = manifest.get("files") if isinstance(manifest, dict) else None
    local = config.get("local", []) if isinstance(config, dict) else None
    if (not isinstance(files, dict) or not isinstance(local, list) or not all(isinstance(g, str) for g in local)
            or workflow is None):
        return None
    return {path.lower() for path in files}, local, workflow.lower()


def reaches(path, managed, local, workflow):
    """Whether the suite reads `path`, case folded as `apply` folds a local path, since a wrong skip loses a run."""
    lower = path.lower()
    return (lower.startswith(TREES) or lower in FILES or lower.rsplit("/", 1)[-1] in NAMES
            or lower in managed or lower == workflow or folded(local, path))


def should_test(event, root, workflow_ref):
    if event != "pull_request":
        return True
    paths = changed_paths(root)
    if not paths:
        return True
    read = reach(root, workflow_path(workflow_ref))
    return read is None or any(reaches(path, *read) for path in paths)


def main(argv):
    if len(argv) != 1:
        print("usage: harness-legs.py        (it takes no arguments: GitHub's environment says what it reads)",
              file=sys.stderr)
        return 2
    test = should_test(os.environ.get("GITHUB_EVENT_NAME"), ROOT, os.environ.get("GITHUB_WORKFLOW_REF"))
    print(f"test={'true' if test else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
