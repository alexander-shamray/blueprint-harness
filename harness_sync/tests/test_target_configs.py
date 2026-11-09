"""The draft target configs under `targets/` render against the real base (plan 5 Task 5, plan 6 Task 4)."""

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

ADMIN = ROOT / "targets" / "blueprint-admin.config.json"
# Admin's settings.json at c5ec185c denies these and the base does not; plan 6 *Decisions* keeps them as additions.
ADMIN_DENIES = (
    "Edit(.claude/rules/**)",
    "Edit(./.claude/rules/**)",
    "Edit(.claude/output-styles/**)",
    "Edit(./.claude/output-styles/**)",
    "Edit(CLAUDE.local.md)",
    "Edit(./CLAUDE.local.md)",
    "Edit(Directory.Packages.props)",
    "Edit(./Directory.Packages.props)",
    "Edit(global.json)",
    "Edit(./global.json)",
    "Edit(BlueprintAdmin.slnx)",
    "Edit(./BlueprintAdmin.slnx)",
    "Edit(Directory.Build.targets)",
    "Edit(./Directory.Build.targets)",
    "Edit(Directory.Build.rsp)",
    "Edit(./Directory.Build.rsp)",
    "Edit(Directory.Solution.props)",
    "Edit(./Directory.Solution.props)",
    "Edit(Directory.Solution.targets)",
    "Edit(./Directory.Solution.targets)",
    "Edit(NuGet.Config)",
    "Edit(./NuGet.Config)",
    "Edit(nuget.config)",
    "Edit(./nuget.config)",
    "Edit(NuGet.config)",
    "Edit(./NuGet.config)",
    "Edit(BlueprintAdmin.slnx.targets)",
    "Edit(./BlueprintAdmin.slnx.targets)",
    "Edit(before.BlueprintAdmin.slnx.targets)",
    "Edit(./before.BlueprintAdmin.slnx.targets)",
    "Edit(after.BlueprintAdmin.slnx.targets)",
    "Edit(./after.BlueprintAdmin.slnx.targets)",
    "Edit(**/Directory.Build.*)",
    "Edit(**/Directory.Solution.*)",
    "Edit(**/NuGet.Config)",
    "Edit(**/nuget.config)",
    "Edit(**/NuGet.config)",
    "Edit(**/*.slnx.targets)",
    "Edit(**/Directory.Packages.*)",
    "Edit(**/*.csproj.user)",
    "Edit(**/obj/**)",
    "Edit(MSBuild.rsp)",
    "Edit(./MSBuild.rsp)",
    "Edit(msbuild.rsp)",
    "Edit(./msbuild.rsp)",
    "Edit(**/MSBuild.rsp)",
    "Edit(**/msbuild.rsp)",
    "Edit(**/global.json)",
    "Edit(AGENTS.md)",
    "Edit(./AGENTS.md)",
    "Bash(git *--no-index*)",
)
# Admin's ship.md denied these and its settings do not, and the payload's /ship denies none. An .npmrc is committed and
# moves the registry `spa-ci.sh` installs from; no edit in admin's transcripts since 2026-10-19 touched one.
ADMIN_NPMRC = ("Edit(.npmrc)", "Edit(./.npmrc)", "Edit(**/.npmrc)")
# The forms admin's ship.md grants at the pin, where host-checks.sh takes a mode; the payload's /ship grants none.
ADMIN_ALLOWS = (
    "Bash(bash .claude/scripts/host-checks.sh:*)",
    "Bash(bash .claude/scripts/spa-ci.sh)",
    "Bash(bash .claude/scripts/harness-checks.sh:*)",
    "Bash(bash .claude/scripts/npm-checks.sh:*)",
)


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


class AdminConfigTests(unittest.TestCase):
    def test_admin_config_renders(self) -> None:
        base = real_base()
        cfg = load_config(ADMIN)
        self.assertEqual(cfg.repo, "alexander-shamray/blueprint-admin")
        self.assertEqual(cfg.task_list, ".todo/blueprint-admin.md")
        self.assertEqual(len(ADMIN_DENIES), 51)
        self.assertEqual(tuple(cfg.settings["deny"]), ADMIN_DENIES + ADMIN_NPMRC)
        self.assertEqual(tuple(cfg.settings["allow"]), ADMIN_ALLOWS)
        self.assertEqual(cfg.settings["env"], {})
        self.assertEqual(cfg.exclude, ())

        rendered = render_settings(base, cfg)
        deny = rendered["permissions"]["deny"]
        self.assertEqual(len(deny), len(set(deny)))
        self.assertEqual(deny, base["permissions"]["deny"] + list(ADMIN_DENIES + ADMIN_NPMRC))
        for entry in ADMIN_ALLOWS:
            with self.subTest(allow=entry):
                self.assertIn(entry, rendered["permissions"]["allow"])
        self.assertEqual(rendered["hooks"], base["hooks"])
        self.assertEqual(rendered["env"], base["env"])

    def test_admins_local_globs_take_no_payload_file(self) -> None:
        """A glob that matched a payload file would leave that file unmanaged in admin, and stale after a sync."""
        payload = ROOT / "payload"
        files = [p.relative_to(payload).as_posix() for p in payload.rglob("*") if p.is_file()]
        self.assertGreater(len(files), 100)
        self.assertTrue(glob_match(".claude/scripts/test_*_admin.py", ".claude/scripts/test_x_admin.py"))
        for glob in load_config(ADMIN).local:
            with self.subTest(glob=glob):
                self.assertEqual([], [rel for rel in files if glob_match(glob, rel)])

    def test_the_other_configs_render_none_of_admins_additions(self) -> None:
        """Admin's additions live in its config alone; the two it shares with frontend are frontend's own there."""
        base = real_base()
        admin_denies = set(ADMIN_DENIES) - set(FRONTEND_DENIES)
        shared = {"Edit(AGENTS.md)", "Edit(./AGENTS.md)", "Bash(git *--no-index*)"}
        self.assertEqual(set(ADMIN_DENIES) - admin_denies, shared)
        admin_allows = set(ADMIN_ALLOWS) - {"Bash(bash .claude/scripts/npm-checks.sh:*)"}
        for path in (*OTHERS, FRONTEND):
            rendered = render_settings(base, load_config(path))
            with self.subTest(config=path.name):
                self.assertFalse(admin_denies & set(rendered["permissions"]["deny"]))
                self.assertFalse(admin_allows & set(rendered["permissions"]["allow"]))


if __name__ == "__main__":
    unittest.main()
