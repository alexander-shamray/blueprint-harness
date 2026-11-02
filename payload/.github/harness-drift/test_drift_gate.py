#!/usr/bin/env python3
"""Negative cases for the drift gate, each beside a positive control."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from drift_gate import check, main

HERE = Path(__file__).resolve().parent
BASE = {"env": {"A": "1"}, "permissions": {"allow": ["Bash(ls)"], "deny": []}, "hooks": {}}


def sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


class Tree:
    """A throwaway target: the real renderer, a small base, and files recorded in a manifest."""

    def __init__(self, tmp: str, local: tuple[str, ...] = ()) -> None:
        self.root = Path(tmp)
        self.files: dict[str, str] = {}
        (self.root / ".harness").mkdir()
        shutil.copy(HERE.parents[1] / ".harness/render.py", self.root / ".harness/render.py")
        self.write_json(".harness/config.json", {"repo": "o/r", "task_list": "t", "local": list(local)})
        self.write_json(".harness/settings.base.json", BASE)
        spec = importlib.util.spec_from_file_location("_r", self.root / ".harness/render.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rendered = mod.dump_settings(mod.render_settings(BASE, SimpleNamespace(settings={})))
        self.add(".claude/settings.json", rendered.encode("utf-8"))
        self.add(".claude/skills/a/SKILL.md", b"one\ntwo\n")
        self.save_manifest()

    def write_json(self, rel: str, body: object) -> None:
        self.put(rel, json.dumps(body).encode("utf-8"))

    def put(self, rel: str, data: bytes) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def add(self, rel: str, data: bytes) -> None:
        self.put(rel, data)
        self.files[rel] = sha(data)

    def save_manifest(self) -> None:
        self.write_json(".harness/manifest.json", {"harness_commit": "c" * 40, "files": self.files})


class DriftGate(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name

    def test_clean_tree_passes(self) -> None:
        self.assertEqual(check(Tree(self.tmp).root), [])

    def test_crlf_copy_passes(self) -> None:
        tree = Tree(self.tmp)
        tree.put(".claude/skills/a/SKILL.md", b"one\r\ntwo\r\n")
        self.assertEqual(check(tree.root), [])

    def test_one_char_change_fails(self) -> None:
        tree = Tree(self.tmp)
        tree.put(".claude/skills/a/SKILL.md", b"one\ntwp\n")
        problems = check(tree.root)
        self.assertEqual(len(problems), 1)
        self.assertIn(".claude/skills/a/SKILL.md", problems[0])
        self.assertIn("differs", problems[0])

    def test_missing_managed_file_fails(self) -> None:
        tree = Tree(self.tmp)
        (tree.root / ".claude/skills/a/SKILL.md").unlink()
        problems = check(tree.root)
        self.assertEqual(len(problems), 1)
        self.assertIn("missing", problems[0])

    def test_unlisted_file_in_managed_dir_fails(self) -> None:
        tree = Tree(self.tmp)
        tree.put(".claude/hooks/extra.sh", b"x\n")
        problems = check(tree.root)
        self.assertEqual(len(problems), 1)
        self.assertIn(".claude/hooks/extra.sh", problems[0])

    def test_unlisted_file_in_every_managed_dir_fails(self) -> None:
        tree = Tree(self.tmp)
        dirs = (".claude/agents", ".claude/commands", ".claude/hooks", ".claude/scripts", ".claude/skills",
                "docs/commands", ".github/harness-drift")
        for d in dirs:
            tree.put(f"{d}/new/stray.txt", b"x\n")
        self.assertEqual(len(check(tree.root)), len(dirs))

    def test_local_file_in_managed_dir_passes(self) -> None:
        tree = Tree(self.tmp, local=(".claude/commands/*.md",))
        tree.put(".claude/commands/mine.md", b"x\n")
        self.assertEqual(check(tree.root), [])

    def test_local_match_ignores_case(self) -> None:
        tree = Tree(self.tmp, local=(".claude/commands/mine.md",))
        tree.put(".claude/commands/Mine.md", b"x\n")
        self.assertEqual(check(tree.root), [])

    def test_bytecode_is_not_an_unlisted_file(self) -> None:
        tree = Tree(self.tmp)
        tree.put(".claude/scripts/__pycache__/x.cpython-312.pyc", b"\0")
        tree.put(".claude/scripts/y.pyc", b"\0")
        self.assertEqual(check(tree.root), [])

    def test_file_outside_managed_dirs_is_not_judged(self) -> None:
        tree = Tree(self.tmp)
        tree.put("src/app.py", b"x\n")
        self.assertEqual(check(tree.root), [])

    def test_settings_edited_by_hand_fails(self) -> None:
        tree = Tree(self.tmp)
        tree.add(".claude/settings.json", b'{"env": {}}\n')  # manifest agrees, so only the render check can object
        tree.save_manifest()
        problems = check(tree.root)
        self.assertEqual(len(problems), 1)
        self.assertIn(".claude/settings.json", problems[0])
        self.assertIn("render", problems[0])

    def test_settings_follow_the_config(self) -> None:
        tree = Tree(self.tmp)
        tree.write_json(".harness/config.json", {"settings": {"allow": ["Bash(pwd)"]}})
        problems = check(tree.root)
        self.assertEqual(len(problems), 1)
        self.assertIn("render", problems[0])

    def test_render_error_is_a_problem_not_a_traceback(self) -> None:
        tree = Tree(self.tmp)
        tree.write_json(".harness/config.json", {"settings": {"env": {"a": "2"}}})
        problems = check(tree.root)
        self.assertTrue(any("already set" in p for p in problems), problems)

    def test_unreadable_inputs_are_problems(self) -> None:
        for rel in (".harness/config.json", ".harness/settings.base.json", ".harness/manifest.json",
                    ".harness/render.py"):
            with self.subTest(rel=rel), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(tmp)
                (tree.root / rel).unlink()
                self.assertTrue(check(tree.root))
                tree.put(rel, b"{ not valid python or json")
                self.assertTrue(check(tree.root))

    def test_non_object_inputs_are_problems(self) -> None:
        for rel in (".harness/config.json", ".harness/settings.base.json", ".harness/manifest.json"):
            for body in (b"[]", b'{"harness_commit": "x", "files": []}', b'{"settings": 3, "local": "a"}'):
                with self.subTest(rel=rel, body=body), tempfile.TemporaryDirectory() as tmp:
                    tree = Tree(tmp)
                    tree.put(rel, body)
                    check(tree.root)  # must not raise

    def test_bad_manifest_paths_are_problems_and_never_read(self) -> None:
        outside = Path(self.tmp).parent / "outside-secret.txt"
        outside.write_bytes(b"s\n")
        self.addCleanup(outside.unlink)
        for bad in ("../outside-secret.txt", "/etc/passwd", "a\\b", "C:/x", "a//b", "./a"):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                tree = Tree(tmp)
                tree.files[bad] = sha(b"s\n")
                tree.save_manifest()
                problems = check(tree.root)
                self.assertEqual(len(problems), 1)
                self.assertIn("canonical", problems[0])

    def test_an_alternative_renderer_judges_the_settings(self) -> None:
        tree = Tree(self.tmp)
        other = Path(self.tmp).parent / "other_render.py"
        source = "def render_settings(base, cfg): return {}\ndef dump_settings(s): return '{}'\n"
        other.write_text(source, encoding="utf-8")
        self.addCleanup(other.unlink)
        self.assertEqual(len(check(tree.root, other)), 1)
        self.assertEqual(check(tree.root), [])

    def test_gate_reads_the_shipped_manifest(self) -> None:
        """The gate looks at the tree CI hands it: this file's own rendered root.

        It runs where it sits in a rendered tree (payload-suites' worktree, then each target), where
        `.harness/manifest.json` exists. It is never run from raw `payload/`, which has no manifest.
        """
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(check(root), [])

    def test_cli_exits_1_with_one_line_per_problem(self) -> None:
        tree = Tree(self.tmp)
        tree.put(".claude/skills/a/SKILL.md", b"changed\n")
        tree.put(".claude/hooks/extra.sh", b"x\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--root", str(tree.root)])
        self.assertEqual(code, 1)
        self.assertEqual(len(out.getvalue().strip().splitlines()), 2)

    def test_cli_exits_0_when_clean(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--root", str(Tree(self.tmp).root)])
        self.assertEqual(code, 0)
        self.assertIn("clean", out.getvalue())


if __name__ == "__main__":
    unittest.main()
