#!/usr/bin/env python3
"""The harness drift gate: a target's managed files are what its manifest says (shared-harness spec 5.4).

Stdlib only and standalone: a target has no harness_sync package, so the hash and the glob matcher below are
copies, and harness_sync/tests/test_drift_gate_parity.py (in the harness repository) keeps them equal to apply's.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import types
from pathlib import Path

SETTINGS = ".claude/settings.json"
BASE = ".harness/settings.base.json"
RENDER = ".harness/render.py"
MANIFEST = ".harness/manifest.json"
CONFIG = ".harness/config.json"
# The directories whose every file is the harness's; a file there that no manifest line names is drift.
MANAGED_DIRS = (
    ".claude/agents",
    ".claude/commands",
    ".claude/hooks",
    ".claude/scripts",
    ".claude/skills",
    "docs/commands",
    ".github/harness-drift",
)


def file_hash(data: bytes) -> str:
    """SHA-256 with CRLF folded, so a Windows checkout hashes like the payload (copy of harness_sync.manifest)."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _glob_regex(glob: str) -> re.Pattern[str]:
    out, i = [], 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("".join(out))


def glob_match(glob: str, path: str) -> bool:
    """POSIX relative path match: `**` crosses `/`, `*` and `?` do not (copy of harness_sync.apply)."""
    return _glob_regex(glob).fullmatch(path) is not None


def is_local(globs: list[str] | tuple[str, ...], path: str) -> bool:
    # Case-insensitive on every OS, as apply's deletion protection is: any filesystem may fold case.
    return any(glob_match(g.lower(), path.lower()) for g in globs)


def walk_files(directory: Path) -> list[str]:
    """Files under `directory` as POSIX paths relative to it, skipping what test runs leave behind."""
    paths = []
    for item in directory.rglob("*"):
        rel = item.relative_to(directory)
        if not item.is_file() or "__pycache__" in rel.parts or item.suffix == ".pyc":
            continue
        paths.append(rel.as_posix())
    return sorted(paths)


def _canonical_problem(rel: str) -> str | None:
    """Same rule as apply: a manifest is editable by any target PR, so no entry may reach outside the root."""
    parts = rel.split("/")
    if "\\" in rel or ":" in rel or any(part in ("", ".", "..") for part in parts):
        return f"{MANIFEST} lists {rel!r}, which is not a canonical relative POSIX path"
    if any(part.lower() == ".git" for part in parts):
        return f"{MANIFEST} lists {rel!r}, which has a .git segment"
    return None


def _link_problem(root: Path, rel: str) -> str | None:
    current = root
    for part in rel.split("/"):
        current = current / part
        if current.is_symlink() or current.is_junction():
            return f"{rel} passes through a link at {current.relative_to(root).as_posix()}"
    if not (root / rel).resolve().is_relative_to(root.resolve()):
        return f"{rel} resolves outside the root"
    return None


def _load_json(root: Path, rel: str, problems: list[str]) -> object | None:
    try:
        return json.loads((root / rel).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # UnicodeDecodeError is a ValueError
        problems.append(f"cannot read {rel}: {exc}")
        return None


def _manifest_files(root: Path, problems: list[str]) -> dict[str, str] | None:
    raw = _load_json(root, MANIFEST, problems)
    if raw is None:
        return None
    files = raw.get("files") if isinstance(raw, dict) else None
    if not isinstance(files, dict) or not all(
        isinstance(k, str) and isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v) for k, v in files.items()
    ):
        problems.append(f"{MANIFEST} must be an object whose files map paths to 64-character lowercase hex hashes")
        return None
    return files


def _local_globs(root: Path, problems: list[str]) -> list[str]:
    raw = _load_json(root, CONFIG, problems)
    if raw is None:
        return []
    local = raw.get("local", []) if isinstance(raw, dict) else None
    if not isinstance(local, list) or not all(isinstance(g, str) for g in local):
        problems.append(f"{CONFIG} must be an object whose local is a list of strings")
        return []
    return local


def _check_listed(root: Path, files: dict[str, str], problems: list[str]) -> None:
    for rel, expected in sorted(files.items()):
        problem = _canonical_problem(rel) or _link_problem(root, rel)
        if problem:
            problems.append(problem)
            continue
        path = root / rel
        if not path.is_file():
            problems.append(f"{rel} is in the manifest but missing")
            continue
        try:
            actual = file_hash(path.read_bytes())
        except OSError as exc:
            problems.append(f"cannot read {rel}: {exc}")
            continue
        if actual != expected:
            problems.append(f"{rel} differs from the manifest")


def _check_unlisted(root: Path, files: dict[str, str], local: list[str], problems: list[str]) -> None:
    for directory in MANAGED_DIRS:
        base = root / directory
        if not base.is_dir():
            continue
        for sub in walk_files(base):
            rel = f"{directory}/{sub}"
            if rel not in files and not is_local(local, rel):
                problems.append(f"{rel} is under a managed directory but neither in the manifest nor local")


def _check_settings(root: Path, local_problems: list[str], render_path: Path) -> None:
    base = _load_json(root, BASE, local_problems)
    config = _load_json(root, CONFIG, [])  # an unreadable config was already reported by _local_globs
    if base is None or config is None:
        return
    if not isinstance(base, dict) or not isinstance(config, dict):
        local_problems.append(f"{BASE} and {CONFIG} must be JSON objects")
        return
    try:
        spec = importlib.util.spec_from_file_location("_harness_render", render_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"no loader for {RENDER}")
        render = importlib.util.module_from_spec(spec)
        keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # no __pycache__ in the checked tree
        try:
            spec.loader.exec_module(render)
        finally:
            sys.dont_write_bytecode = keep
    except Exception as exc:  # the renderer is target-supplied code; any failure to load it is a finding
        local_problems.append(f"cannot load {RENDER}: {exc!r}")
        return
    try:
        cfg = types.SimpleNamespace(settings=config.get("settings", {}))
        want = render.dump_settings(render.render_settings(base, cfg))
    except Exception as exc:  # RenderError, or a config shape the renderer did not expect
        local_problems.append(f"cannot render {SETTINGS}: {exc}")
        return
    try:
        have = (root / SETTINGS).read_bytes().decode("utf-8")
    except (OSError, ValueError) as exc:
        local_problems.append(f"cannot read {SETTINGS}: {exc}")
        return
    if have.replace("\r\n", "\n") != want.replace("\r\n", "\n"):
        local_problems.append(f"{SETTINGS} is not what {RENDER} renders from {BASE} and {CONFIG}")


def check(root: Path, render: Path | None = None) -> list[str]:
    """Problems with the tree at `root`, empty when it is exactly what its manifest records.

    `render` names the renderer to judge settings with; the workflow passes the base commit's copy so a pull request
    cannot bring its own. The tree's own `.harness/render.py` is still hash-checked against the manifest.
    """
    root = Path(root)
    problems: list[str] = []
    local = _local_globs(root, problems)
    files = _manifest_files(root, problems)
    if files is not None:
        _check_listed(root, files, problems)
        _check_unlisted(root, files, local, problems)
    _check_settings(root, problems, Path(render) if render else root / RENDER)
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail when a managed harness file differs from the manifest.")
    parser.add_argument("--root", type=Path, default=Path("."), help="the tree to check (default: current directory)")
    parser.add_argument("--render", type=Path, help="the renderer to use instead of <root>/.harness/render.py")
    args = parser.parse_args(argv)
    problems = check(args.root, args.render)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print("harness-drift: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
