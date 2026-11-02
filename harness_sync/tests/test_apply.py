"""Tests for apply, over throwaway payload and target trees."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from harness_sync.apply import ApplyError, apply, glob_match
from harness_sync.config import ConfigError
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

    def test_excluded_payload_path_that_exists_in_the_target_is_refused(self) -> None:
        """Exclude means not delivered, never replaced (spec 5.2): a kept copy of a managed file is a fork."""
        self.config({**CONFIG, "exclude": ["skip/**"]})
        self.put(self.payload, "skip/a.md", b"a\n")
        self.put(self.target, "skip/a.md", b"my own\n")
        with self.assertRaises(ApplyError) as ctx:
            apply(self.payload, self.target, COMMIT)
        self.assertIn("skip/a.md", str(ctx.exception))
        self.assertFalse((self.target / ".harness/manifest.json").exists())

    def test_a_file_excluded_after_a_sync_is_removed_not_refused(self) -> None:
        self.put(self.payload, "skip/a.md", b"a\n")
        apply(self.payload, self.target, COMMIT)
        self.config({**CONFIG, "exclude": ["skip/**"]})
        result = apply(self.payload, self.target, COMMIT)
        self.assertIn("skip/a.md", result.deleted)

    def test_a_dropped_path_now_excluded_that_is_a_directory_is_refused(self) -> None:
        self.put(self.payload, "skip/a.md", b"a\n")
        apply(self.payload, self.target, COMMIT)
        (self.target / "skip/a.md").unlink()
        (self.target / "skip/a.md").mkdir()  # a directory now sits where the managed file was
        (self.target / "skip/a.md/inner.txt").write_bytes(b"x")
        self.config({**CONFIG, "exclude": ["skip/**"]})
        with self.assertRaises(ApplyError) as ctx:
            apply(self.payload, self.target, COMMIT)
        self.assertIn("skip/a.md", str(ctx.exception))

    def test_a_local_excluded_path_that_exists_is_still_refused(self) -> None:
        self.config({**CONFIG, "exclude": ["skip/**"], "local": ["skip/**"]})
        self.put(self.payload, "skip/a.md", b"a\n")
        self.put(self.target, "skip/a.md", b"a\n")
        with self.assertRaises(ApplyError):
            apply(self.payload, self.target, COMMIT)

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
        for name in ("config.json", "manifest.json"):
            with self.subTest(name=name):
                self.put(self.payload, f".harness/{name}", b"{}")
                with self.assertRaises(ApplyError) as ctx:
                    apply(self.payload, self.target, COMMIT)
                self.assertIn(f".harness/{name}", str(ctx.exception))
                (self.payload / ".harness" / name).unlink()

    def test_missing_settings_base_refused(self) -> None:
        (self.payload / ".harness/settings.base.json").unlink()
        with self.assertRaises(ApplyError):
            apply(self.payload, self.target, COMMIT)

    def test_bad_commit_refused(self) -> None:
        with self.assertRaises(ApplyError):
            apply(self.payload, self.target, "abc")

    # Fix round 1: the manifest and config are editable by any target PR.
    def old_manifest(self, files: dict[str, str]) -> None:
        self.put(self.target, ".harness/manifest.json", Manifest(COMMIT, files).dumps().encode())

    def test_hostile_manifest_entries_refused(self) -> None:
        outside = self.target.parent / "outside.txt"
        outside.write_bytes(b"keep")
        h = "0" * 64
        entries = ["../outside.txt", str(outside), "..\\outside.txt", "a\\b", "C:/x", "a/./b", "a//b", "",
                   ".harness/config.json", ".HARNESS/Config.json", ".git/config", ".Git/config"]
        for entry in entries:
            with self.subTest(entry=entry):
                self.old_manifest({entry: h})
                with self.assertRaises(ApplyError):
                    apply(self.payload, self.target, COMMIT)
                self.assertTrue(outside.exists())
                self.assertTrue((self.target / ".harness/config.json").exists())

    def test_case_variant_of_local_path_not_deleted(self) -> None:
        self.config({**CONFIG, "local": ["notes/**"]})
        self.put(self.target, "notes/a.md", b"mine\n")
        self.old_manifest({"Notes/A.md": "0" * 64})
        result = apply(self.payload, self.target, COMMIT)
        self.assertEqual(result.deleted, [])
        self.assertEqual((self.target / "notes/a.md").read_bytes(), b"mine\n")

    def test_malformed_manifest_refused(self) -> None:
        good = "0" * 64
        bad = [b"not json", b"[]", b'{"harness_commit": "' + COMMIT.encode() + b'"}',
               json.dumps({"harness_commit": COMMIT, "files": []}).encode(),
               json.dumps({"harness_commit": COMMIT, "files": {"a": 1}}).encode(),
               json.dumps({"harness_commit": COMMIT, "files": {"a": "ABC"}}).encode(),
               json.dumps({"harness_commit": "zz", "files": {"a": good}}).encode(),
               json.dumps({"harness_commit": COMMIT, "files": {}, "extra": 1}).encode()]
        for data in bad:
            with self.subTest(data=data):
                self.put(self.target, ".harness/manifest.json", data)
                with self.assertRaises(ApplyError):
                    apply(self.payload, self.target, COMMIT)

    def test_case_only_rename_ends_with_new_name(self) -> None:
        self.put(self.payload, "docs/A.md", b"x\n")
        apply(self.payload, self.target, COMMIT)
        (self.payload / "docs/A.md").unlink()
        self.put(self.payload, "docs/a.md", b"x\n")
        apply(self.payload, self.target, COMMIT)
        self.assertEqual(sorted(os.listdir(self.target / "docs")), ["a.md"])
        self.assertEqual((self.target / "docs/a.md").read_bytes(), b"x\n")
        self.assertIn("docs/a.md", self.manifest().files)

    def test_file_to_directory_swap(self) -> None:
        self.put(self.payload, "docs/x", b"file\n")
        apply(self.payload, self.target, COMMIT)
        (self.payload / "docs/x").unlink()
        self.put(self.payload, "docs/x/y.md", b"y\n")
        apply(self.payload, self.target, COMMIT)
        self.assertEqual((self.target / "docs/x/y.md").read_bytes(), b"y\n")

    def test_directory_to_file_swap(self) -> None:
        self.put(self.payload, "docs/x/y.md", b"y\n")
        apply(self.payload, self.target, COMMIT)
        (self.payload / "docs/x/y.md").unlink()
        (self.payload / "docs/x").rmdir()
        self.put(self.payload, "docs/x", b"file\n")
        apply(self.payload, self.target, COMMIT)
        self.assertEqual((self.target / "docs/x").read_bytes(), b"file\n")

    def test_directory_at_managed_file_path_refused_before_writes(self) -> None:
        self.put(self.payload, "a.md", b"a\n")
        self.put(self.payload, "z.md", b"z\n")
        self.put(self.target, "z.md/stray.txt", b"s")
        with self.assertRaises(ApplyError):
            apply(self.payload, self.target, COMMIT)
        self.assertFalse((self.target / "a.md").exists())

    def test_symlinked_parent_refused(self) -> None:
        outside = self.target.parent / "outside"
        outside.mkdir()
        (self.target).mkdir(exist_ok=True)
        try:
            os.symlink(outside, self.target / "docs", target_is_directory=True)
        except (OSError, NotImplementedError):
            # Windows without the symlink privilege can still make a junction, which is the same escape.
            if os.name != "nt" or subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(self.target / "docs"), str(outside)], capture_output=True
            ).returncode:
                self.skipTest("this OS refuses to create links")
        self.put(self.payload, "docs/a.md", b"a\n")
        with self.assertRaises(ApplyError) as ctx:
            apply(self.payload, self.target, COMMIT)
        self.assertIn("passes through a link", str(ctx.exception))
        self.assertEqual(os.listdir(outside), [])

    def test_symlinked_file_refused(self) -> None:
        outside = self.target.parent / "outside.txt"
        outside.write_bytes(b"keep")
        try:
            os.symlink(outside, self.target / "a.md")
        except (OSError, NotImplementedError):
            self.skipTest("this OS refuses to create symlinks")
        self.put(self.payload, "a.md", b"a\n")
        with self.assertRaises(ApplyError) as ctx:
            apply(self.payload, self.target, COMMIT)
        self.assertIn("passes through a link", str(ctx.exception))
        self.assertEqual(outside.read_bytes(), b"keep")

    def test_base_and_render_must_stay_managed(self) -> None:
        for key in ("exclude", "local"):
            for rel in (".harness/settings.base.json", ".harness/render.py"):
                with self.subTest(key=key, rel=rel):
                    self.config({**CONFIG, key: [rel]})
                    with self.assertRaises(ApplyError) as ctx:
                        apply(self.payload, self.target, COMMIT)
                    self.assertIn(rel, str(ctx.exception))

    def test_bad_globs_rejected_at_config_load(self) -> None:
        for key in ("local", "exclude"):
            for glob in ("a\\b", "/a"):
                with self.subTest(key=key, glob=glob):
                    self.config({**CONFIG, key: [glob]})
                    with self.assertRaises(ConfigError) as ctx:
                        apply(self.payload, self.target, COMMIT)
                    self.assertIn(f"{key!r} glob", str(ctx.exception))

    # Fix round 2.
    def test_local_protection_is_case_insensitive_on_every_os(self) -> None:
        # Fail safe: a case variant may name the local file on a case-folding mount, so it is kept, never deleted.
        self.config({**CONFIG, "local": ["notes/**"]})
        self.put(self.target, "Notes/A.md", b"x")
        self.old_manifest({"Notes/A.md": "0" * 64})
        result = apply(self.payload, self.target, COMMIT)
        self.assertEqual(result.deleted, [])
        self.assertTrue((self.target / "Notes/A.md").exists())
        self.assertNotIn("Notes/A.md", self.manifest().files)

    def test_directory_of_empty_subdirectories_makes_way_for_a_file(self) -> None:
        self.put(self.payload, "z.md", b"z\n")
        (self.target / "z.md/sub/deeper").mkdir(parents=True)
        apply(self.payload, self.target, COMMIT)
        self.assertEqual((self.target / "z.md").read_bytes(), b"z\n")

    def test_dropped_files_plus_empty_subdirectory_make_way_for_a_file(self) -> None:
        self.put(self.payload, "x/y.md", b"y\n")
        apply(self.payload, self.target, COMMIT)
        (self.payload / "x/y.md").unlink()
        (self.payload / "x").rmdir()
        self.put(self.payload, "x", b"file\n")
        (self.target / "x/empty").mkdir()
        apply(self.payload, self.target, COMMIT)
        self.assertEqual((self.target / "x").read_bytes(), b"file\n")

    def test_non_canonical_payload_path_refused_up_front(self) -> None:
        for name in ("a:b.md", "sub/.git/x", "a\\b.md"):
            with self.subTest(name=name):
                try:
                    self.put(self.payload, name, b"x")
                except OSError:
                    self.skipTest("this OS cannot create such a file")
                if not (self.payload / name).exists() or "\\" in name and os.name == "nt":
                    self.skipTest("this OS cannot create such a file")
                with self.assertRaises(ApplyError) as ctx:
                    apply(self.payload, self.target, COMMIT)
                self.assertIn("payload", str(ctx.exception))
                self.assertFalse((self.target / ".harness/manifest.json").exists())

    def test_nested_git_manifest_entry_refused(self) -> None:
        self.old_manifest({"sub/.git": "0" * 64})
        with self.assertRaises(ApplyError) as ctx:
            apply(self.payload, self.target, COMMIT)
        self.assertIn(".git", str(ctx.exception))

    def test_linked_harness_directory_refused_before_config_is_read(self) -> None:
        outside = self.target.parent / "elsewhere"
        outside.mkdir()
        self.put(outside, "config.json", json.dumps(CONFIG).encode())
        shutil.rmtree(self.target / ".harness")
        try:
            os.symlink(outside, self.target / ".harness", target_is_directory=True)
        except (OSError, NotImplementedError):
            if os.name != "nt" or subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(self.target / ".harness"), str(outside)], capture_output=True
            ).returncode:
                self.skipTest("this OS refuses to create links")
        with self.assertRaises(ApplyError) as ctx:
            apply(self.payload, self.target, COMMIT)
        self.assertIn("passes through a link", str(ctx.exception))

    # Fix round 3.
    def test_link_inside_directory_at_managed_path_refused_before_any_deletion(self) -> None:
        outside = self.target.parent / "elsewhere"
        outside.mkdir()
        self.put(self.payload, "keep.md", b"k\n")
        self.put(self.payload, "z.md", b"z\n")
        apply(self.payload, self.target, COMMIT)
        (self.payload / "keep.md").unlink()
        (self.target / "z.md").unlink()
        (self.target / "z.md").mkdir()
        link = self.target / "z.md" / "link"
        try:
            os.symlink(outside, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            if os.name != "nt" or subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True
            ).returncode:
                self.skipTest("this OS refuses to create links")
        with self.assertRaises(ApplyError) as ctx:
            apply(self.payload, self.target, COMMIT)
        self.assertIn("link", str(ctx.exception))
        self.assertTrue((self.target / "keep.md").exists())  # no deletion ran
        self.assertTrue(outside.exists())


if __name__ == "__main__":
    unittest.main()
