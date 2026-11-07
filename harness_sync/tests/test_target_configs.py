"""The draft target configs under `targets/` render against the real base (plan 5, Task 5)."""

import json
import unittest
from pathlib import Path

from harness_sync.apply import glob_match
from harness_sync.config import load_config
from harness_sync.render import render_settings

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "payload" / ".harness" / "settings.base.json"
FRONTEND = ROOT / "targets" / "blueprint-frontend.config.json"
OTHERS = (ROOT / "targets" / "blueprint-backend.config.json", ROOT / ".harness" / "config.json")

# Frontend's settings.json at 41a3f45 denies these and the base does not; plan 5 *Decisions* keeps them as additions.
FRONTEND_DENIES = (
    "Edit(AGENTS.md)",
    "Edit(./AGENTS.md)",
    "Edit(.github/**)",
    "Edit(./.github/**)",
    "Edit(package.json)",
    "Edit(./package.json)",
    "Edit(**/package.json)",
    "Edit(.npmrc)",
    "Edit(./.npmrc)",
    "Edit(**/.npmrc)",
    "Edit(angular.json)",
    "Edit(./angular.json)",
    "Edit(tsconfig.json)",
    "Edit(./tsconfig.json)",
    "Edit(tsconfig.app.json)",
    "Edit(./tsconfig.app.json)",
    "Edit(tsconfig.spec.json)",
    "Edit(./tsconfig.spec.json)",
    "Edit(**/tsconfig*.json)",
    "Edit(**/*.config.cjs)",
    "Edit(**/*.config.mjs)",
    "Edit(**/vitest.config.ts)",
    "Edit(**/vite.config.ts)",
    "Edit(**/playwright.config.ts)",
    "Edit(**/capacitor.config.ts)",
    "Edit(**/*.config.mts)",
    "Edit(node_modules/**)",
    "Edit(./node_modules/**)",
    "Bash(git *--no-index*)",
)
# Frontend denies these too, and *Decisions* sends them to the base; the config holds them until the base does,
# and the renderer drops the copy from then on.
RAW_FORMS = ("Bash(gh pr merge:*)", "Bash(git worktree remove:*)")


def real_base() -> dict:
    return json.loads(BASE.read_text(encoding="utf-8"))


class FrontendConfigTests(unittest.TestCase):
    def test_frontend_config_renders(self) -> None:
        base = real_base()
        cfg = load_config(FRONTEND)
        self.assertEqual(cfg.repo, "alexander-shamray/blueprint-frontend")
        self.assertEqual(len(FRONTEND_DENIES), 29)
        self.assertEqual(tuple(cfg.settings["deny"]), FRONTEND_DENIES + RAW_FORMS)

        rendered = render_settings(base, cfg)
        deny = rendered["permissions"]["deny"]
        self.assertEqual(len(deny), len(set(deny)))
        for entry in base["permissions"]["deny"] + list(FRONTEND_DENIES + RAW_FORMS):
            with self.subTest(deny=entry):
                self.assertIn(entry, deny)
        self.assertEqual(deny[: len(base["permissions"]["deny"])], base["permissions"]["deny"])
        self.assertIn("Bash(bash .claude/scripts/npm-checks.sh:*)", rendered["permissions"]["allow"])
        self.assertEqual(rendered["hooks"], base["hooks"])
        self.assertEqual(rendered["env"], base["env"])

    def test_frontends_local_globs_take_no_payload_file(self) -> None:
        """A glob that matched a payload file would leave that file unmanaged in frontend, and stale after a sync."""
        payload = ROOT / "payload"
        files = [p.relative_to(payload).as_posix() for p in payload.rglob("*") if p.is_file()]
        self.assertGreater(len(files), 100)
        self.assertTrue(glob_match(".claude/scripts/test_*_frontend.py", ".claude/scripts/test_x_frontend.py"))
        for glob in load_config(FRONTEND).local:
            with self.subTest(glob=glob):
                self.assertEqual([], [rel for rel in files if glob_match(glob, rel)])

    def test_the_other_configs_render_none_of_frontends_denies(self) -> None:
        """Frontend's additions live in its config alone: backend's and the harness's own settings are unchanged."""
        base = real_base()
        for path in OTHERS:
            rendered = render_settings(base, load_config(path))
            with self.subTest(config=path.name):
                self.assertFalse(set(FRONTEND_DENIES) & set(rendered["permissions"]["deny"]))
                self.assertNotIn("Bash(bash .claude/scripts/npm-checks.sh:*)", rendered["permissions"]["allow"])


if __name__ == "__main__":
    unittest.main()
