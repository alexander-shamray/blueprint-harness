"""Tests for the settings renderer (spec section 5.2, second bullet; section 6)."""

import json
import types
import unittest
from pathlib import Path

from harness_sync.render import RenderError, dump_settings, render_settings

FIXTURE = Path(__file__).parent / "fixtures" / "backend-settings.json"


def base() -> dict:
    return {
        "$schema": "https://example.invalid/schema.json",
        "env": {"A": "1"},
        "permissions": {"allow": ["Bash(git status:*)"], "deny": ["Bash(git push --force:*)"]},
        "hooks": {
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "base"}]}],
            "SessionStart": [{"hooks": [{"type": "command", "command": "start"}]}],
        },
    }


def cfg(**settings: object) -> types.SimpleNamespace:
    return types.SimpleNamespace(settings=settings)


class RenderTests(unittest.TestCase):
    def test_empty_config_reproduces_base(self) -> None:
        self.assertEqual(render_settings(base(), cfg()), base())

    def test_key_order_is_schema_env_permissions_hooks(self) -> None:
        self.assertEqual(list(render_settings(base(), cfg())), ["$schema", "env", "permissions", "hooks"])

    def test_base_is_not_mutated(self) -> None:
        b = base()
        render_settings(b, cfg(allow=["X"], env={"B": "2"}, hooks={"PreToolUse": [{"matcher": "Y", "hooks": []}]}))
        self.assertEqual(b, base())

    def test_allow_appended_after_base(self) -> None:
        out = render_settings(base(), cfg(allow=["Bash(npm test:*)"]))
        self.assertEqual(out["permissions"]["allow"], ["Bash(git status:*)", "Bash(npm test:*)"])

    def test_duplicates_of_base_entries_dropped(self) -> None:
        out = render_settings(base(), cfg(allow=["Bash(git status:*)", "N", "N"], deny=["Bash(git push --force:*)"]))
        self.assertEqual(out["permissions"]["allow"], ["Bash(git status:*)", "N"])
        self.assertEqual(out["permissions"]["deny"], ["Bash(git push --force:*)"])

    def test_deny_appended_after_base(self) -> None:
        out = render_settings(base(), cfg(deny=["Edit(package.json)"]))
        self.assertEqual(out["permissions"]["deny"], ["Bash(git push --force:*)", "Edit(package.json)"])

    def test_allow_entry_matching_base_deny_refused(self) -> None:
        with self.assertRaises(RenderError) as ctx:
            render_settings(base(), cfg(allow=["Bash(git push --force:*)"]))
        self.assertIn("Bash(git push --force:*)", str(ctx.exception))

    def test_env_added(self) -> None:
        self.assertEqual(render_settings(base(), cfg(env={"B": "2"}))["env"], {"A": "1", "B": "2"})

    def test_env_override_of_base_key_refused(self) -> None:
        with self.assertRaises(RenderError) as ctx:
            render_settings(base(), cfg(env={"A": "9"}))
        self.assertIn("A", str(ctx.exception))

    def test_write_rule_refused(self) -> None:
        for key in ("allow", "deny"):
            with self.subTest(key=key), self.assertRaises(RenderError) as ctx:
                render_settings(base(), cfg(**{key: ["Write(.claude/**)"]}))
            self.assertIn("Write(.claude/**)", str(ctx.exception))

    def test_env_override_is_case_insensitive(self) -> None:
        with self.assertRaises(RenderError) as ctx:
            render_settings(base(), cfg(env={"a": "9"}))
        self.assertIn("'a'", str(ctx.exception))

    def test_render_validates_settings_shape(self) -> None:
        for bad, key in (({"allow": "Bash(x)"}, "allow"), ({"ask": []}, "ask"), ({"env": {"A": 1}}, "env"),
                         ({"hooks": {"Stop": [1]}}, "hooks"), ({"hooks": {"Stop": [{"hooks": [{}]}]}}, "hooks")):
            with self.subTest(bad=bad):
                with self.assertRaises(RenderError) as ctx:
                    render_settings(base(), cfg(**bad))
                self.assertIn(key, str(ctx.exception))

    def test_output_shape_follows_base(self) -> None:
        for b in ({"permissions": {"allow": ["x"]}}, {"extra": 1, "env": {}, "permissions": {}, "hooks": {}},
                  {"$schema": "s", "hooks": {}, "zzz": [1], "env": {"A": "1"}}):
            with self.subTest(base=b):
                out = render_settings(b, cfg())
                self.assertEqual(out, b)
                self.assertEqual(list(out), list(b))

    def test_section_missing_from_base_added_only_with_content(self) -> None:
        out = render_settings({"$schema": "s"}, cfg(allow=["A"]))
        self.assertEqual(out, {"$schema": "s", "permissions": {"allow": ["A"]}})

    def test_write_rule_spellings_refused(self) -> None:
        for rule in (" Write(x)", "Write (x)", "Write	(x)"):
            with self.subTest(rule=rule), self.assertRaises(RenderError):
                render_settings(base(), cfg(deny=[rule]))

    def test_allow_vs_deny_comparison_strips(self) -> None:
        with self.assertRaises(RenderError):
            render_settings(base(), cfg(allow=["  Bash(git push --force:*) "]))

    def test_write_rule_in_base_refused(self) -> None:
        b = base()
        b["permissions"]["deny"].append("Write(x)")
        with self.assertRaises(RenderError):
            render_settings(b, cfg())

    def test_hooks_config_entries_follow_base_entries(self) -> None:
        extra = {"matcher": "PowerShell", "hooks": [{"type": "command", "command": "cfg"}]}
        out = render_settings(base(), cfg(hooks={"PreToolUse": [extra], "Stop": [extra]}))
        self.assertEqual(out["hooks"]["PreToolUse"], base()["hooks"]["PreToolUse"] + [extra])
        self.assertEqual(out["hooks"]["SessionStart"], base()["hooks"]["SessionStart"])
        self.assertEqual(out["hooks"]["Stop"], [extra])
        self.assertEqual(list(out["hooks"]), ["PreToolUse", "SessionStart", "Stop"])

    def test_dump_matches_backend_form(self) -> None:
        raw = FIXTURE.read_bytes().decode("utf-8").replace("\r\n", "\n")
        self.assertEqual(dump_settings(json.loads(raw)), raw)


if __name__ == "__main__":
    unittest.main()
