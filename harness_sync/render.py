"""Render a target's .claude/settings.json from the harness base plus its config.

Stdlib only and no package-relative import, by design: Task 5 vendors this file
byte-identical into each target as .harness/render.py, where no harness_sync
package exists and the drift gate imports it (owner: shared-harness spec 5.2).
"""

import copy
import json


class RenderError(Exception):
    """The config asks for something the base forbids."""


def _write_rules(where: str, entries: list) -> None:
    # A Write(path) rule stops Claude Code starting (spec section 6); a file rule is Edit(...).
    for entry in entries:
        if isinstance(entry, str) and entry.startswith("Write("):
            raise RenderError(f"{where} carries {entry!r}: a Write( rule stops Claude Code starting; use Edit(...)")


def _merge(base_list: list, extra: list) -> list:
    out = list(base_list)
    for entry in extra:
        if entry not in out:
            out.append(entry)
    return out


def render_settings(base: dict, cfg: object) -> dict:
    """Return base plus cfg.settings; config can only add, never remove or override."""
    extra = cfg.settings  # type: ignore[attr-defined]  # duck-typed so a target can pass a SimpleNamespace
    perms = base.get("permissions", {})
    base_allow, base_deny = perms.get("allow", []), perms.get("deny", [])
    cfg_allow, cfg_deny = extra.get("allow", []), extra.get("deny", [])

    _write_rules("base permissions", base_allow + base_deny)
    _write_rules("config allow", cfg_allow)
    _write_rules("config deny", cfg_deny)
    # Denies win in Claude Code, so an allow the base denies would be dead text that hides intent.
    for entry in cfg_allow:
        if entry in base_deny:
            raise RenderError(f"config allow {entry!r} is denied by the base")

    env = dict(base.get("env", {}))
    for key, value in extra.get("env", {}).items():
        if key in env:
            raise RenderError(f"config env {key!r} is already set by the base")
        env[key] = value

    hooks = copy.deepcopy(base.get("hooks", {}))
    for event, groups in extra.get("hooks", {}).items():
        hooks[event] = hooks.get(event, []) + copy.deepcopy(groups)

    out = {key: copy.deepcopy(value) for key, value in base.items() if key not in ("env", "permissions", "hooks")}
    out["env"] = env
    out["permissions"] = {**copy.deepcopy(perms), "allow": _merge(base_allow, cfg_allow),
                          "deny": _merge(base_deny, cfg_deny)}
    out["hooks"] = hooks
    return out


def dump_settings(settings: dict) -> str:
    """Serialise in the form backend's file has: two-space indent, key order kept, trailing newline."""
    return json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
