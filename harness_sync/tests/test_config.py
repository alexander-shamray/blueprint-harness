"""Tests for the target config loader."""

import json
import tempfile
import unittest
from pathlib import Path

from harness_sync.config import Config, ConfigError, load_config

MINIMAL = {"repo": "o/r", "task_list": ".todo/r.md"}


class ConfigTests(unittest.TestCase):
    def load(self, data: object) -> Config:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return load_config(path)

    def test_minimal_config_gets_defaults(self) -> None:
        cfg = self.load(MINIMAL)
        self.assertEqual(cfg.settings, {"env": {}, "allow": [], "deny": [], "hooks": {}})
        self.assertEqual((cfg.local, cfg.exclude), ((), ()))

    def test_full_config(self) -> None:
        cfg = self.load({**MINIMAL, "settings": {"allow": ["a"]}, "local": ["x/*"], "exclude": ["y"]})
        self.assertEqual(cfg.settings["allow"], ["a"])
        self.assertEqual(cfg.local, ("x/*",))
        self.assertEqual(cfg.exclude, ("y",))

    def test_config_rejects_unknown_key(self) -> None:
        with self.assertRaises(ConfigError) as ctx:
            self.load({**MINIMAL, "extra": 1})
        self.assertIn("extra", str(ctx.exception))

    def test_rejects_unknown_settings_key(self) -> None:
        with self.assertRaises(ConfigError) as ctx:
            self.load({**MINIMAL, "settings": {"mcp": {}}})
        self.assertIn("mcp", str(ctx.exception))

    def test_missing_required_key(self) -> None:
        with self.assertRaises(ConfigError) as ctx:
            self.load({"repo": "o/r"})
        self.assertIn("task_list", str(ctx.exception))

    def test_type_errors_name_the_key(self) -> None:
        bad = [
            ({"repo": 1, "task_list": "t"}, "repo"),
            ({**MINIMAL, "local": "x"}, "local"),
            ({**MINIMAL, "exclude": [1]}, "exclude"),
            ({**MINIMAL, "settings": []}, "settings"),
            ({**MINIMAL, "settings": {"allow": "a"}}, "allow"),
            ({**MINIMAL, "settings": {"deny": [1]}}, "deny"),
            ({**MINIMAL, "settings": {"env": {"A": 1}}}, "env"),
            ({**MINIMAL, "settings": {"hooks": {"Stop": {}}}}, "hooks"),
            ({**MINIMAL, "settings": {"hooks": {"Stop": [1]}}}, "hooks"),
            ({**MINIMAL, "settings": {"hooks": {"Stop": [{"matcher": "x"}]}}}, "hooks"),
            ({**MINIMAL, "settings": {"hooks": {"Stop": [{"hooks": [{"type": "command"}]}]}}}, "hooks"),
        ]
        for data, key in bad:
            with self.subTest(key=key):
                with self.assertRaises(ConfigError) as ctx:
                    self.load(data)
                self.assertIn(key, str(ctx.exception))

    def test_non_object_top_level(self) -> None:
        with self.assertRaises(ConfigError):
            self.load([])

    def test_invalid_json_is_config_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
