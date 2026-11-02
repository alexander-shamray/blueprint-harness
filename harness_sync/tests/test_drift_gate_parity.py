"""The drift gate keeps its own copies of the hash and the glob matcher; these keep them equal to apply's.

The gate is standalone because a target has no harness_sync package (shared-harness spec 5.4), so the
copies cannot be imported and a test is the only thing that stops them drifting.
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path

from harness_sync import apply as apply_mod
from harness_sync.manifest import file_hash

GATE = Path(__file__).resolve().parents[2] / "payload/.github/harness-drift/drift_gate.py"

HASH_CASES = [b"", b"a", b"a\nb\n", b"a\r\nb\r\n", b"a\rb", b"\r\n\r\n", b"x\r\r\n", "café\r\n".encode("utf-8")]
GLOB_CASES = [
    ("a.md", "a.md"),
    ("*.md", "a.md"),
    ("*.md", "d/a.md"),
    ("**/*.md", "d/e/a.md"),
    ("**/*.md", "a.md"),
    ("d/**", "d/e/f"),
    ("d/**", "d"),
    ("d/?.md", "d/a.md"),
    ("d/?.md", "d/ab.md"),
    ("d/*/x", "d/e/x"),
    ("d/*/x", "d/e/f/x"),
    ("a.b", "aXb"),
    ("(x)+", "(x)+"),
    ("A.md", "a.md"),
]


def _load():
    spec = importlib.util.spec_from_file_location("drift_gate_under_test", GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DriftGateParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gate = _load()

    def test_hash_agrees(self) -> None:
        for data in HASH_CASES:
            with self.subTest(data=data):
                self.assertEqual(self.gate.file_hash(data), file_hash(data))

    def test_glob_agrees(self) -> None:
        for glob, path in GLOB_CASES:
            with self.subTest(glob=glob, path=path):
                self.assertEqual(self.gate.glob_match(glob, path), apply_mod.glob_match(glob, path))

    def test_case_insensitive_local_match_agrees(self) -> None:
        for glob, path in GLOB_CASES:
            with self.subTest(glob=glob, path=path):
                self.assertEqual(
                    self.gate.is_local((glob,), path),
                    apply_mod._first_match((glob,), path, ignore_case=True) is not None,
                )

    def test_payload_comparison_agrees_with_what_apply_writes(self) -> None:
        """The gate's --payload rules are the ones apply used: a real apply of the real payload checks clean."""
        import json

        from harness_sync.apply import apply

        repo = GATE.parents[3]
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / ".harness").mkdir()
            config = json.loads((repo / "targets/blueprint-backend.config.json").read_text(encoding="utf-8"))
            config["exclude"] = [".github/workflows/*.yml"]
            (target / ".harness/config.json").write_text(json.dumps(config), encoding="utf-8")
            apply(repo / "payload", target, "a" * 40)
            self.assertEqual(self.gate.check(target, repo / "payload"), [])

    def test_an_excluded_file_that_exists_is_refused_by_both(self) -> None:
        """Exclude means not delivered, never replaced: apply refuses it and the gate reports it."""
        import json

        from harness_sync.apply import ApplyError, apply

        repo = GATE.parents[3]
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / ".harness").mkdir()
            config = json.loads((repo / "targets/blueprint-backend.config.json").read_text(encoding="utf-8"))
            (target / ".harness/config.json").write_text(json.dumps(config), encoding="utf-8")
            apply(repo / "payload", target, "a" * 40)
            config["exclude"] = [".claude/hooks/*"]
            (target / ".harness/config.json").write_text(json.dumps(config), encoding="utf-8")
            self.assertTrue(list((target / ".claude/hooks").glob("*")), "the payload ships hooks")
            problems = self.gate.check(target, repo / "payload")
            self.assertTrue(any("excluded but exists" in p for p in problems), problems)
            # With no manifest the hooks are not on their way out as dropped files, so apply refuses, naming all.
            names = sorted(p.name for p in (repo / "payload/.claude/hooks").glob("*") if p.is_file())
            self.assertGreater(len(names), 1, "the test needs more than one hook to show the order does not matter")
            (target / ".harness/manifest.json").unlink()
            with self.assertRaises(ApplyError) as ctx:
                apply(repo / "payload", target, "a" * 40)
            for name in names:
                self.assertIn(name, str(ctx.exception))

    def test_walk_skips_what_apply_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("a/x.md", "a/__pycache__/y.pyc", "a/z.pyc", "a/b/__pycache__/w.txt", "a/b/v.txt"):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_bytes(b"x")
            self.assertEqual(self.gate.walk_files(root / "a"), apply_mod._walk(root / "a"))


if __name__ == "__main__":
    unittest.main()
