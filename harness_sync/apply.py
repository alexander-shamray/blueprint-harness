"""Apply the harness payload to a target tree and record its manifest (spec 5.3, 5.4, 6)."""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from harness_sync.config import Config, load_config
from harness_sync.manifest import Manifest, ManifestError, file_hash
from harness_sync.render import dump_settings, render_settings

SETTINGS = ".claude/settings.json"
BASE = ".harness/settings.base.json"
RENDER = ".harness/render.py"
MANIFEST = ".harness/manifest.json"
CONFIG = ".harness/config.json"
# The target owns its config and apply owns the manifest; a payload copy of either would fork them silently.
_RESERVED = (MANIFEST, CONFIG)
# What the drift gate needs delivered to judge a target. Excluded or local, the target stays green and is never checked
# again, so apply refuses either (spec 5.4); drift_gate.py keeps a copy, and the parity test holds it to the payload.
GATE_FILES = (
    BASE,
    RENDER,
    ".github/harness-drift/README.md",
    ".github/harness-drift/drift_gate.py",
    ".github/harness-drift/test_drift_gate.py",
    ".github/workflows/harness-drift.yml",
)
# A relative path in a hook's command, never starting inside a variable's name: `$D/.claude/x.py` and
# `${CLAUDE_PROJECT_DIR}/.claude/x.py` both yield `.claude/x.py`.
_HOOK_TOKEN = re.compile(
    r"(?<![\w$.-])(?P<path>[\w.-]+(?:/[\w.-]+)+)"
    r"|(?<![\w$./-])(?P<bare>[\w-][\w.-]*\.(?:py|sh))(?![\w/.-])"
)


class ApplyError(Exception):
    """The payload and target cannot be reconciled; nothing has been written."""


@dataclass(frozen=True)
class ApplyResult:
    written: list[str]
    deleted: list[str]
    unchanged: list[str]


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
    """POSIX relative path match: `**` crosses `/`, `*` and `?` do not (3.12 has no PurePath.full_match)."""
    return _glob_regex(glob).fullmatch(path) is not None


def _first_match(globs: tuple[str, ...], path: str, *, ignore_case: bool = False) -> str | None:
    if ignore_case:
        return next((g for g in globs if glob_match(g.lower(), path.lower())), None)
    return next((g for g in globs if glob_match(g, path)), None)


def _command_paths(command: str) -> set[str]:
    """Paths one hook command names. A leading `./` is dropped. A bare `x.py` or `x.sh` is a path only after the
    first script path of its simple command (split at `&`, `|`, `;` and a newline, but not at a redirection's `&`), and is then that script's sibling:
    `hint-bound.sh <event> index-search-hint.py` loads it from `hint-bound.sh`'s own directory. A module a hook
    loads by path itself, or a hook a target adds through its config, is not derived."""
    found: set[str] = set()
    for part in re.split(r"[;|\n]|(?<![>&])&(?!>)", command):
        receiver: str | None = None
        for match in _HOOK_TOKEN.finditer(part):
            if (path := match.group("path")) is not None:
                while path.startswith("./"):
                    path = path[2:]
                found.add(path)
                if receiver is None and path.endswith((".py", ".sh")):
                    receiver = path.rpartition("/")[0]
            elif receiver is not None:
                found.add(f"{receiver}/{match.group('bare')}" if receiver else match.group("bare"))
    return found


def hook_paths(base: object) -> list[str]:
    """The paths the settings base's hook commands name; a target without one runs a hook that fails, unseen."""
    found: set[str] = set()
    hooks = base.get("hooks") if isinstance(base, dict) else None
    for groups in hooks.values() if isinstance(hooks, dict) else ():
        for group in groups if isinstance(groups, list) else ():
            inner = group.get("hooks") if isinstance(group, dict) else None
            for hook in inner if isinstance(inner, list) else ():
                command = hook.get("command") if isinstance(hook, dict) else None
                if isinstance(command, str):
                    found.update(_command_paths(command))
    return sorted(found)


def _refuse_protected(cfg: Config, paths: list[str] | tuple[str, ...], why: str) -> None:
    for rel in paths:
        for kind, globs in (("exclude", cfg.exclude), ("local", cfg.local)):
            glob = _first_match(globs, rel)
            if glob is not None:
                raise ApplyError(f"{kind} glob {glob!r} matches {rel}, which {why}")


def _walk(payload: Path) -> list[str]:
    paths = []
    for item in payload.rglob("*"):
        rel = item.relative_to(payload)
        if not item.is_file() or "__pycache__" in rel.parts or item.suffix == ".pyc":
            continue
        paths.append(rel.as_posix())
    return sorted(paths)


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _is_current(path: Path, data: bytes) -> bool:
    return path.is_file() and file_hash(path.read_bytes()) == file_hash(data)


def _prune_empty_parents(path: Path, root: Path) -> None:
    for parent in path.parents:
        if parent == root or not parent.is_relative_to(root):
            return
        try:
            parent.rmdir()
        except OSError:
            return


def _remove_empty_tree(path: Path) -> None:
    if not path.is_dir():
        return
    for directory, _, _ in os.walk(path, topdown=False):
        Path(directory).rmdir()


def _check_canonical(rel: str, where: str) -> None:
    """Payload and manifest must both name canonical relative POSIX paths, so one apply can read the last."""
    parts = rel.split("/")
    if "\\" in rel or ":" in rel or any(part in ("", ".", "..") for part in parts):
        raise ApplyError(f"{where} lists {rel!r}, which is not a canonical relative POSIX path")
    # A .git segment at any depth is a repository or a submodule gitlink, never a managed file.
    if any(part.lower() == ".git" for part in parts):
        raise ApplyError(f"{where} lists {rel!r}, which has a .git segment")


def _check_manifest_path(target: Path, rel: str) -> None:
    """A manifest is editable by any target PR, so each entry must be a canonical path inside the target."""
    _check_canonical(rel, MANIFEST)
    if rel.lower() in (CONFIG, MANIFEST):
        raise ApplyError(f"{MANIFEST} lists {rel!r}, which apply never manages")
    _check_inside(target, rel)


def _check_inside(target: Path, rel: str) -> None:
    """Refuse a path that is, or sits under, a symlink or junction, or that resolves outside the target."""
    current = target
    for part in rel.split("/"):
        current = current / part
        if current.is_symlink() or current.is_junction():
            raise ApplyError(f"{rel} passes through a link at {current.relative_to(target).as_posix()}")
    if not (target / rel).resolve().is_relative_to(target.resolve()):
        raise ApplyError(f"{rel} resolves outside the target")


def _check_clearable(target: Path, path: Path, rel: str, dropped: set[str]) -> None:
    """Only dropped files and empty directories may sit where a file lands; a link would defeat the removal."""
    for directory, dirnames, filenames in os.walk(path):
        dirnames.sort()  # the first offender named must not depend on filesystem order
        for name in dirnames:
            child = Path(directory) / name
            if child.is_symlink() or child.is_junction():
                raise ApplyError(f"{rel} is a directory in the target holding a link at {name}")
        for name in sorted(filenames):
            if (Path(directory) / name).relative_to(target).as_posix() not in dropped:
                raise ApplyError(f"{rel} is a directory in the target but apply writes a file there")


def _check_no_conflicts(target: Path, writes: list[str], dropped: set[str]) -> None:
    """A directory where a file will land, or a file where a directory is needed, would fail mid-apply."""
    for rel in writes:
        path = target / rel
        if path.is_dir():
            _check_clearable(target, path, rel, dropped)
        parts = rel.split("/")
        for n in range(1, len(parts)):
            prefix = "/".join(parts[:n])
            if (target / prefix).exists() and not (target / prefix).is_dir() and prefix not in dropped:
                raise ApplyError(f"{prefix} is a file in the target but {rel} needs it to be a directory")


def apply(
    payload: Path,
    target: Path,
    harness_commit: str,
    *,
    write: Callable[[Path, bytes], None] | None = None,
) -> ApplyResult:
    payload, target = Path(payload), Path(target)
    write = write or _write_bytes
    if not re.fullmatch(r"[0-9a-f]{40}", harness_commit):
        raise ApplyError(f"harness commit must be 40 hex characters, got {harness_commit!r}")
    _check_inside(target, CONFIG)  # a linked .harness/ or config would make load_config read outside the target
    cfg = load_config(target / CONFIG)

    _refuse_protected(cfg, GATE_FILES, "the drift gate needs managed")

    contents: dict[str, bytes] = {}
    excluded: list[str] = []
    for rel in _walk(payload):
        if rel == SETTINGS:
            raise ApplyError(f"payload contains {SETTINGS}; it is rendered, never copied")
        if rel in _RESERVED:
            raise ApplyError(f"payload contains {rel}; the target owns it")
        _check_canonical(rel, "payload")
        if _first_match(cfg.exclude, rel) is not None:
            excluded.append(rel)
            continue
        contents[rel] = (payload / rel).read_bytes()
    if BASE not in contents:
        raise ApplyError(f"payload has no {BASE} to render {SETTINGS} from")

    # All refusals come before the first write so a refused apply leaves the target as it was.
    managed: dict[str, bytes] = {}
    for rel, data in contents.items():
        glob = _first_match(cfg.local, rel)
        if glob is None:
            managed[rel] = data
        elif (target / rel).is_file() and not _is_current(target / rel, data):
            raise ApplyError(f"{rel} is local (matches {glob!r}) but the payload manages it and the target differs")

    try:
        base = json.loads(contents[BASE].decode("utf-8"))
    except ValueError as exc:
        raise ApplyError(f"{BASE} is not valid JSON: {exc}") from exc
    _refuse_protected(cfg, hook_paths(base), f"a hook in {BASE} runs")
    rendered = dump_settings(render_settings(base, cfg)).encode("utf-8")

    new_files = {rel: file_hash(data) for rel, data in managed.items()}
    new_files[SETTINGS] = file_hash(rendered)
    manifest = Manifest(harness_commit, new_files)

    _check_inside(target, MANIFEST)
    try:
        old = Manifest.read(target / MANIFEST)
    except ManifestError as exc:
        raise ApplyError(f"{MANIFEST} is malformed: {exc}") from exc
    old_files = old.files if old else {}
    for rel in sorted(old_files):
        _check_manifest_path(target, rel)
    # Always case-insensitive, on every OS: any filesystem may fold case (NTFS, CIFS and casefold mounts on Linux),
    # and failing safe means keeping a file that may be local; a missed deletion is an orphan, a wrong one is loss.
    dropped = sorted(
        rel
        for rel in old_files
        if rel not in new_files and _first_match(cfg.local, rel, ignore_case=True) is None
    )

    # Exclude means "not delivered", never "replaced" (spec 5.2): a target keeping its own copy of a managed file
    # would fork the harness. A file this apply is about to delete as no longer managed is on its way out.
    # Every offender is named, sorted, so the message does not depend on filesystem order.
    forks = []
    for rel in sorted(excluded):
        path = target / rel
        if not (path.exists() or path.is_symlink()):
            continue
        # The deletion loop below unlinks regular files only, so anything else would survive and stay a fork.
        if rel not in dropped or path.is_symlink() or not path.is_file():
            forks.append(rel)
    if forks:
        raise ApplyError(
            f"{', '.join(forks)} excluded but present in the target; remove them. `local` allows only an absent or "
            "identical copy; a target that needs different behaviour adds a new local path, never a replacement"
        )

    writes = [*managed, MANIFEST, SETTINGS]
    for rel in [*writes, *dropped]:
        _check_inside(target, rel)
    _check_no_conflicts(target, writes, set(dropped))

    # Deletions come first: a case-only rename or a file/directory swap needs the old path gone before the new write.
    deleted = []
    for rel in dropped:
        path = target / rel
        if path.is_file():
            path.unlink()
            _prune_empty_parents(path, target)
            deleted.append(rel)

    for rel in writes:  # directories left empty by the deletions (or empty to begin with) make way for a file
        _remove_empty_tree(target / rel)

    written, unchanged = [], []
    for rel, data in sorted(managed.items()):
        if _is_current(target / rel, data):
            unchanged.append(rel)
        else:
            write(target / rel, data)
            written.append(rel)

    manifest_path = target / MANIFEST
    manifest_bytes = manifest.dumps().encode("utf-8")
    if not _is_current(manifest_path, manifest_bytes):
        write(manifest_path, manifest_bytes)

    # Settings self-lock: it lands whole and last, after the manifest that records its hash (spec 6).
    if _is_current(target / SETTINGS, rendered):
        unchanged.append(SETTINGS)
    else:
        write(target / SETTINGS, rendered)
        written.append(SETTINGS)
    return ApplyResult(sorted(written), deleted, sorted(unchanged))
