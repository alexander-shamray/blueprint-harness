"""Tests for apply, over throwaway payload and target trees."""

import json
import tempfile
import unittest
from pathlib import Path

from harness_sync.apply import ApplyError, apply, glob_match
from harness_sync.manifest import Manifest, file_hash

COMMIT = "a" * 40
BASE = {"env": {}, "permissions": {"allow": [], "deny": []}, "hooks": {}}
CONFIG = {"repo": "o/r", "task_list": ".todo/r.md"}


class GlobTests(unittest.TestCase):
    def test_star_stays_in_one_segment(self) -> None:
        self.assertTrue(glob_match("a/*.md", "a/x.md"))
        self.assertFalse(glob_match("a/*.md", "a/b/x.md"))

    def test_double_star_crosses_segments(self) -> None:
        self.assertTrue(glob_match("a/**", "a/b/c.md"))
        self.assertTrue(glob_match("a/**/x.md", "a/x.md"))
        self.assertTrue(glob_match("a/**/x.md", "a/b/c/x.md"))
        self.assertFalse(glob_match("a/**/x.md", "b/x.md"))

    def test_question_mark_is_one_non_slash_char(self) -> None:
        self.assertTrue(glob_match("a?.md", "ab.md"))
        self.assertFalse(glob_match("a?.md", "a/.md"))

    def test_regex_metacharacters_are_literal(self) -> None:
        self.assertTrue(glob_match("a.md", "a.md"))
        self.assertFalse(glob_match("a.md", "axmd"))
        self.assertTrue(glob_match("a(1)+.md", "a(1)+.md"))


class ApplyTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.payload = Path(tmp.name) / "payload"
        self.target = Path(tmp.name) / "target"
        self.put(self.payload, ".harness/settings.base.json", json.dumps(BASE).encode())
        self.config(CONFIG)

    def put(self, root: Path, rel: str, data: bytes) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def config(self, cfg: dict) -> None:
        self.put(self.target, ".harness/config.json", json.dumps(cfg).encode())

    def manifest(self) -> Manifest:
        manifest = Manifest.read(self.target / ".harness" / "manifest.json")
        assert manifest is not None
        return manifest

    def test_apply_copies_managed_and_writes_manifest(self) -> None:
        self.put(self.payload, ".claude/commands/x.md", b"x\r\n")
        result = apply(self.payload, self.target, COMMIT)
        self.assertEqual((self.target / ".claude/commands/x.md").read_bytes(), b"x\r\n")
        self.assertIn(".claude/commands/x.md", result.written)
        self.assertIn(".claude/settings.json", result.written)
        manifest = self.manifest()
        self.assertEqual(manifest.harness_commit, COMMIT)
        self.assertEqual(manifest.files[".claude/commands/x.md"], file_hash(b"x\n"))
        rendered = (self.target / ".claude/settings.json").read_bytes()
        self.assertEqual(manifest.files[".claude/settings.json"], file_hash(rendered))
        self.assertIn(".harness/settings.base.json", manifest.files)
        self.assertNotIn(".harness/manifest.json", manifest.files)

    def test_apply_deletes_file_dropped_from_payload(self) -> None:
        self.put(self.payload, "docs/old.md", b"old\n")
        self.put(self.payload, "docs/keep.md", b"keep\n")
        apply(self.payload, self.target, COMMIT)
        (self.payload / "docs/old.md").unlink()
        result = apply(self.payload, self.target, "b" * 40)
        self.assertEqual(result.deleted, ["docs/old.md"])
        self.assertFalse((self.target / "docs/old.md").exists())
        self.assertNotIn("docs/old.md", self.manifest().files)

    def test_delete_removes_emptied_directories_only(self) -> None:
        self.put(self.payload, "a/b/old.md", b"old\n")
        self.put(self.payload, "a/keep.md", b"k\n")
        apply(self.payload, self.target, COMMIT)
        (self.payload / "a/b/old.md").unlink()
        apply(self.payload, self.target, COMMIT)
        self.assertFalse((self.target / "a/b").exists())
        self.assertTrue((self.target / "a/keep.md").exists())
        self.assertTrue(self.target.exists())

    def test_apply_never_touches_local_path(self) -> None:
        self.config({**CONFIG, "local": ["notes/**"]})
        self.put(self.payload, "notes/a.md", b"payload\n")
        self.put(self.target, "notes/a.md", b"payload\n")
        self.put(self.target, "notes/mine.md", b"mine\n")
        apply(self.payload, self.target, COMMIT)
        self.assertNotIn("notes/a.md", self.manifest().files)
        # an old manifest that lists a local path must not get it deleted
        Manifest(COMMIT, {"notes/mine.md": file_hash(b"mine\n")}).write(self.target / ".harness/manifest.json")
        result = apply(self.payload, self.target, COMMIT)
        self.assertEqual(result.deleted, [])
        self.assertEqual((self.target / "notes/mine.md").read_bytes(), b"mine\n")

    def test_identical_local_path_absent_in_target_is_not_created(self) -> None:
        self.config({**CONFIG, "local": ["notes/**"]})
        self.put(self.payload, "notes/a.md", b"p\n")
        apply(self.payload, self.target, COMMIT)
        self.assertFalse((self.target / "notes/a.md").exists())

    def test_local_shadowing_managed_path_refused(self) -> None:
        self.config({**CONFIG, "local": ["notes/*.md"]})
        self.put(self.payload, "notes/a.md", b"payload\n")
        self.put(self.target, "notes/a.md", b"forked\n")
        with self.assertRaises(ApplyError) as ctx:
            apply(self.payload, self.target, COMMIT)
        self.assertIn("notes/a.md", str(ctx.exception))
        self.assertIn("notes/*.md", str(ctx.exception))
        self.assertFalse((self.target / ".harness/manifest.json").exists())

    def test_excluded_payload_path_not_copied(self) -> None:
        self.config({**CONFIG, "exclude": ["skip/**"]})
        self.put(self.payload, "skip/a.md", b"a\n")
        apply(self.payload, self.target, COMMIT)
        self.assertFalse((self.target / "skip/a.md").exists())
        self.assertNotIn("skip/a.md", self.manifest().files)

    def test_pycache_is_not_walked(self) -> None:
        self.put(self.payload, ".harness/__pycache__/render.cpython-312.pyc", b"\x00")
        self.put(self.payload, ".harness/stray.pyc", b"\x00")
        apply(self.payload, self.target, COMMIT)
        self.assertFalse((self.target / ".harness/__pycache__").exists())
        self.assertFalse((self.target / ".harness/stray.pyc").exists())

    def test_settings_written_last(self) -> None:
        self.put(self.payload, "a.md", b"a\n")
        order: list[str] = []

        def record(path: Path, data: bytes) -> None:
            order.append(path.relative_to(self.target).as_posix())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        apply(self.payload, self.target, COMMIT, write=record)
        self.assertEqual(order[-1], ".claude/settings.json")
        self.assertEqual(order[-2], ".harness/manifest.json")
        self.assertEqual(order.count(".claude/settings.json"), 1)

    def test_second_apply_is_unchanged(self) -> None:
        self.put(self.payload, "a.md", b"a\n")
        apply(self.payload, self.target, COMMIT)
        result = apply(self.payload, self.target, COMMIT)
        self.assertEqual((result.written, result.deleted), ([], []))
        self.assertIn("a.md", result.unchanged)
        self.assertIn(".claude/settings.json", result.unchanged)

    def test_crlf_target_is_unchanged_and_not_rewritten(self) -> None:
        self.put(self.payload, "a.cs", b"x\ny\n")
        self.put(self.target, "a.cs", b"x\r\ny\r\n")
        result = apply(self.payload, self.target, COMMIT)
        self.assertIn("a.cs", result.unchanged)
        self.assertEqual((self.target / "a.cs").read_bytes(), b"x\r\ny\r\n")

    def test_crlf_settings_not_rewritten(self) -> None:
        apply(self.payload, self.target, COMMIT)
        path = self.target / ".claude/settings.json"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        crlf = path.read_bytes()
        result = apply(self.payload, self.target, COMMIT)
        self.assertEqual(result.written, [])
        self.assertEqual(path.read_bytes(), crlf)

    def test_changed_file_is_written(self) -> None:
        self.put(self.payload, "a.md", b"1\n")
        apply(self.payload, self.target, COMMIT)
        self.put(self.payload, "a.md", b"2\n")
        result = apply(self.payload, self.target, "b" * 40)
        self.assertEqual(result.written, ["a.md"])
        self.assertEqual(self.manifest().harness_commit, "b" * 40)

    def test_payload_settings_json_refused(self) -> None:
        self.put(self.payload, ".claude/settings.json", b"{}")
        with self.assertRaises(ApplyError) as ctx:
            apply(self.payload, self.target, COMMIT)
        self.assertIn(".claude/settings.json", str(ctx.exception))

    def test_payload_manifest_or_config_refused(self) -> None:
        self.put(self.payload, ".harness/config.json", b"{}")
        with self.assertRaises(ApplyError):
            apply(self.payload, self.target, COMMIT)

    def test_missing_settings_base_refused(self) -> None:
        (self.payload / ".harness/settings.base.json").unlink()
        with self.assertRaises(ApplyError):
            apply(self.payload, self.target, COMMIT)

    def test_bad_commit_refused(self) -> None:
        with self.assertRaises(ApplyError):
            apply(self.payload, self.target, "abc")


if __name__ == "__main__":
    unittest.main()
