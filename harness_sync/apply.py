"""Apply the harness payload to a target tree and record its manifest (spec 5.3, 5.4, 6)."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from harness_sync.config import load_config
from harness_sync.manifest import Manifest, file_hash
from harness_sync.render import dump_settings, render_settings

SETTINGS = ".claude/settings.json"
BASE = ".harness/settings.base.json"
MANIFEST = ".harness/manifest.json"
CONFIG = ".harness/config.json"
# The target owns its config and apply owns the manifest; a payload copy of either would fork them silently.
_RESERVED = (MANIFEST, CONFIG)


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


def _first_match(globs: tuple[str, ...], path: str) -> str | None:
    return next((g for g in globs if glob_match(g, path)), None)


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
        if parent == root:
            return
        try:
            parent.rmdir()
        except OSError:
            return


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
    cfg = load_config(target / CONFIG)

    contents: dict[str, bytes] = {}
    for rel in _walk(payload):
        if rel == SETTINGS:
            raise ApplyError(f"payload contains {SETTINGS}; it is rendered, never copied")
        if rel in _RESERVED:
            raise ApplyError(f"payload contains {rel}; the target owns it")
        if _first_match(cfg.exclude, rel) is not None:
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
    rendered = dump_settings(render_settings(base, cfg)).encode("utf-8")

    new_files = {rel: file_hash(data) for rel, data in managed.items()}
    new_files[SETTINGS] = file_hash(rendered)
    manifest = Manifest(harness_commit, new_files)

    old = Manifest.read(target / MANIFEST)
    dropped = sorted(
        rel for rel in (old.files if old else {}) if rel not in new_files and _first_match(cfg.local, rel) is None
    )

    written, unchanged = [], []
    for rel, data in sorted(managed.items()):
        if _is_current(target / rel, data):
            unchanged.append(rel)
        else:
            write(target / rel, data)
            written.append(rel)
    deleted = []
    for rel in dropped:
        path = target / rel
        if path.is_file():
            path.unlink()
            _prune_empty_parents(path, target)
            deleted.append(rel)

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
