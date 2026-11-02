"""Load and validate a target's .harness/config.json (schema: shared-harness spec 5.2)."""

import json
from dataclasses import dataclass
from pathlib import Path

_SETTINGS_KEYS = ("env", "allow", "deny", "hooks")
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


def _settings(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ConfigError("'settings' must be an object")
    for key in raw:
        if key not in _SETTINGS_KEYS:
            raise ConfigError(f"unknown key {key!r} in 'settings'")
    env = raw.get("env", {})
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise ConfigError("'env' must be an object of strings")
    hooks = raw.get("hooks", {})
    if not isinstance(hooks, dict) or not all(isinstance(v, list) for v in hooks.values()):
        raise ConfigError("'hooks' must be an object of lists, one per event")
    return {
        "env": dict(env),
        "allow": list(_strings("allow", raw.get("allow", []))),
        "deny": list(_strings("deny", raw.get("deny", []))),
        "hooks": {event: list(groups) for event, groups in hooks.items()},
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
        local=tuple(_strings("local", raw.get("local", []))),
        exclude=tuple(_strings("exclude", raw.get("exclude", []))),
    )
