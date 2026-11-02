"""The payload's settings base and vendored renderer against their owners (shared-harness plan, Task 5).

Backend's sync must leave its `settings.json` saying what it says today, reordered at most (plan Task 9 step 3),
and the drift gate a target runs imports `.harness/render.py`, so that copy must be the renderer the sync used.
"""

import json
import unittest
from collections import Counter
from pathlib import Path

from harness_sync.config import load_config
from harness_sync.render import render_settings

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "payload" / ".harness" / "settings.base.json"
BACKEND_CONFIG = ROOT / "targets" / "blueprint-backend.config.json"
# Backend's .claude/settings.json; the same blob (aeb89a9) at f61a0932f and at IMPORT.md's pin.
BACKEND_SETTINGS = Path(__file__).parent / "fixtures" / "backend-settings.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _hook_groups(settings: dict) -> dict[str, Counter]:
    # A group is compared whole, as canonical JSON, so a dropped hook or a changed matcher inside it counts.
    return {
        event: Counter(json.dumps(group, sort_keys=True) for group in groups)
        for event, groups in settings.get("hooks", {}).items()
    }


class BackendRenderEquivalentTests(unittest.TestCase):
    def test_backend_render_equivalent(self) -> None:
        rendered = render_settings(_read_json(BASE), load_config(BACKEND_CONFIG))
        current = _read_json(BACKEND_SETTINGS)
        for key in ("allow", "deny"):
            with self.subTest(key=key):
                self.assertEqual(Counter(current["permissions"][key]), Counter(rendered["permissions"][key]))
        self.assertEqual(_hook_groups(current), _hook_groups(rendered))
        self.assertEqual(current["env"], rendered["env"])


class VendoredRenderTests(unittest.TestCase):
    def test_vendored_render_identical(self) -> None:
        vendored = ROOT / "payload" / ".harness" / "render.py"
        self.assertEqual((ROOT / "harness_sync" / "render.py").read_bytes(), vendored.read_bytes())


if __name__ == "__main__":
    unittest.main()
