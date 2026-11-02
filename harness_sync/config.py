"""Load and validate a target's .harness/config.json (schema: shared-harness spec 5.2)."""

import json
from dataclasses import dataclass
from pathlib import Path

from harness_sync.render import RenderError, validate_settings

_TOP_KEYS = ("repo", "task_list", "settings", "local", "exclude")


class ConfigError(Exception):
    """The config file is unreadable or does not match the schema."""


@dataclass(frozen=True)
class Config:
    repo: str
    task_list: str
    settings: dict
    local: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


def _strings(key: str, value: object) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"{key!r} must be a list of strings")
    return value


def _globs(key: str, value: object) -> list[str]:
    # Globs are POSIX relative paths; a backslash or leading slash would silently match nothing.
    globs = _strings(key, value)
    for glob in globs:
        if "\\" in glob or glob.startswith("/"):
            raise ConfigError(f"{key!r} glob {glob!r} must be relative POSIX: no backslash, no leading slash")
    return globs


def _settings(raw: object) -> dict:
    try:
        validate_settings(raw)
    except RenderError as exc:
        raise ConfigError(str(exc)) from exc
    return {
        "env": dict(raw.get("env", {})),
        "allow": list(raw.get("allow", [])),
        "deny": list(raw.get("deny", [])),
        "hooks": {event: list(groups) for event, groups in raw.get("hooks", {}).items()},
    }


def load_config(path: Path) -> Config:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("config must be a JSON object")
    for key in raw:
        if key not in _TOP_KEYS:
            raise ConfigError(f"unknown key {key!r}")
    for key in ("repo", "task_list"):
        if key not in raw:
            raise ConfigError(f"missing required key {key!r}")
        if not isinstance(raw[key], str):
            raise ConfigError(f"{key!r} must be a string")
    return Config(
        repo=raw["repo"],
        task_list=raw["task_list"],
        settings=_settings(raw.get("settings", {})),
        local=tuple(_globs("local", raw.get("local", []))),
        exclude=tuple(_globs("exclude", raw.get("exclude", []))),
    )
