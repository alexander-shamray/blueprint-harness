"""The drift gate keeps its own copies of the hash and the glob matcher; these keep them equal to apply's.

The gate is standalone because a target has no harness_sync package (shared-harness spec 5.4), so the
copies cannot be imported and a test is the only thing that stops them drifting.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from harness_sync import apply as apply_mod
from harness_sync.manifest import file_hash

REPO = Path(__file__).resolve().parents[2]
GATE = REPO / "payload/.github/harness-drift/drift_gate.py"
REAL_BASE = json.loads((REPO / "payload/.harness/settings.base.json").read_text(encoding="utf-8"))

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
            config["exclude"] = [".github/workflows/c*.yml"]
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
            config["exclude"] = [".claude/agents/*"]
            (target / ".harness/config.json").write_text(json.dumps(config), encoding="utf-8")
            self.assertTrue(list((target / ".claude/agents").glob("*")), "the payload ships agents")
            problems = self.gate.check(target, repo / "payload")
            self.assertTrue(any("excluded but exists" in p for p in problems), problems)
            # With no manifest the agents are not on their way out as dropped files, so apply refuses, naming all.
            names = sorted(p.name for p in (repo / "payload/.claude/agents").glob("*") if p.is_file())
            self.assertGreater(len(names), 1, "the test needs more than one agent to show the order does not matter")
            (target / ".harness/manifest.json").unlink()
            with self.assertRaises(ApplyError) as ctx:
                apply(repo / "payload", target, "a" * 40)
            for name in names:
                self.assertIn(name, str(ctx.exception))

    def test_the_protected_paths_agree(self) -> None:
        self.assertEqual(self.gate.GATE_FILES, apply_mod.GATE_FILES)
        hook = {"type": "command", "command": """bash "$D/.claude/hooks/a.sh" x.py && py -c '/.claude/scripts/b.py'"""}
        bases = [REAL_BASE, {}, [], "x", {"hooks": []}, {"hooks": {"E": "x"}}, {"hooks": {"E": [{"hooks": 3}]}},
                 {"hooks": {"E": [{"hooks": [{"command": 3}, "x", hook]}]}}]
        for base in bases:
            with self.subTest(base=base):
                self.assertEqual(self.gate.hook_paths(base), apply_mod.hook_paths(base))
        # `x.py` is passed to `a.sh` by bare name, which `a.sh` loads from its own directory.
        self.assertEqual(
            apply_mod.hook_paths(bases[-1]), [".claude/hooks/a.sh", ".claude/hooks/x.py", ".claude/scripts/b.py"]
        )

    def test_hook_paths_resolve_bare_names_and_strip_dot_slash(self) -> None:
        cases = {
            'bash "${D}/.claude/hooks/hint-bound.sh" PreToolUse index-search-hint.py':
                [".claude/hooks/hint-bound.sh", ".claude/hooks/index-search-hint.py"],
            "bash ./.claude/hooks/a.sh ./b.py": [".claude/hooks/a.sh", "b.py"],
            "bash ./tool.sh run.py": ["run.py", "tool.sh"],
            "python ./scripts/run.py": ["scripts/run.py"],
            "python lone.py": [],  # no script path received it, so there is no directory to resolve against
            'bash "$D/.claude/hooks/a.sh" .claude/scripts/b.py c.sh': [
                ".claude/hooks/a.sh", ".claude/scripts/b.py", ".claude/scripts/c.sh"],
            "echo done.txt && bash a/b.sh": ["a/b.sh"],
        }
        for command, expected in cases.items():
            base = {"hooks": {"E": [{"hooks": [{"type": "command", "command": command}]}]}}
            with self.subTest(command=command):
                self.assertEqual(apply_mod.hook_paths(base), expected)
                self.assertEqual(self.gate.hook_paths(base), expected)

    def test_the_gate_files_are_the_payloads_gate(self) -> None:
        """A file added to the gate's directory is protected only once GATE_FILES names it."""
        payload = REPO / "payload"
        shipped = {rel for rel in apply_mod._walk(payload) if rel.startswith(".github/harness-drift/")}
        shipped |= {".github/workflows/harness-drift.yml", ".harness/settings.base.json", ".harness/render.py"}
        self.assertEqual(set(apply_mod.GATE_FILES), shipped)
        self.assertTrue(all((payload / rel).is_file() for rel in shipped))

    def test_every_path_a_real_hook_names_is_a_payload_file(self) -> None:
        paths = apply_mod.hook_paths(REAL_BASE)
        self.assertIn(".claude/hooks/guard-git-argv.py", paths)
        for rel in paths:
            with self.subTest(rel=rel):
                self.assertTrue((REPO / "payload" / rel).is_file())

    def test_a_protected_glob_is_refused_by_both(self) -> None:
        from harness_sync.apply import ApplyError, apply

        globs = (".github/harness-drift/**", ".github/workflows/harness-drift.yml", ".claude/hooks/guard-git-argv.py")
        for key in ("local", "exclude"):
            for glob in globs:
                with self.subTest(key=key, glob=glob), tempfile.TemporaryDirectory() as tmp:
                    target = Path(tmp)
                    (target / ".harness").mkdir()
                    config = json.loads((REPO / "targets/blueprint-backend.config.json").read_text(encoding="utf-8"))
                    (target / ".harness/config.json").write_text(json.dumps(config), encoding="utf-8")
                    apply(REPO / "payload", target, "a" * 40)
                    config[key] = [*config[key], glob]
                    (target / ".harness/config.json").write_text(json.dumps(config), encoding="utf-8")
                    with self.assertRaises(ApplyError):
                        apply(REPO / "payload", target, "a" * 40)
                    problems = self.gate.check(target, REPO / "payload")
                    self.assertTrue(any(glob.rstrip("*") in p and "which" in p for p in problems), problems)

    def test_the_real_configs_protect_nothing(self) -> None:
        for path in (REPO / ".harness/config.json", REPO / "targets/blueprint-backend.config.json"):
            config = json.loads(path.read_text(encoding="utf-8"))
            for rel in [*apply_mod.GATE_FILES, *apply_mod.hook_paths(REAL_BASE)]:
                with self.subTest(config=path.name, rel=rel):
                    self.assertFalse(any(apply_mod.glob_match(g, rel) for g in config["local"] + config["exclude"]))

    def test_the_config_shapes_agree(self) -> None:
        """The gate must not pass a config apply refuses; `settings` is the renderer's, run by both."""
        from harness_sync.config import ConfigError, load_config

        good = {"repo": "o/r", "task_list": "t"}
        cases = [good, {**good, "local": ["a/**"], "exclude": ["b.md"], "settings": {}}, [], "x", None, {},
                 {"task_list": "t"}, {"repo": "o/r"}, {**good, "repo": 1}, {**good, "task_list": None},
                 {**good, "extra": 1}, {**good, "local": "a"}, {**good, "exclude": [1]}, {**good, "local": ["a\\b"]},
                 {**good, "exclude": ["/a"]}, {**good, "local": ["ok", "/a"]}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            for raw in cases:
                with self.subTest(raw=raw):
                    path.write_text(json.dumps(raw), encoding="utf-8")
                    try:
                        load_config(path)
                        refused = False
                    except ConfigError:
                        refused = True
                    self.assertEqual(bool(self.gate.config_problems(raw)), refused)

    def test_a_config_apply_refuses_is_a_problem_for_the_gate(self) -> None:
        from harness_sync.apply import apply
        from harness_sync.config import ConfigError

        bad = [{"extra": 1}, {"repo": None}, {"local": ["/a"]}, {"exclude": ["a\\b"]}, {"settings": {"x": 1}},
               {"settings": {"hooks": {"E": "x"}}}]
        config = json.loads((REPO / "targets/blueprint-backend.config.json").read_text(encoding="utf-8"))
        for change in bad:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp)
                (target / ".harness").mkdir()
                (target / ".harness/config.json").write_text(json.dumps(config), encoding="utf-8")
                apply(REPO / "payload", target, "a" * 40)
                self.assertEqual(self.gate.check(target, REPO / "payload"), [])
                (target / ".harness/config.json").write_text(json.dumps({**config, **change}), encoding="utf-8")
                with self.assertRaises(ConfigError):
                    apply(REPO / "payload", target, "a" * 40)
                self.assertTrue(self.gate.check(target, REPO / "payload"))

    def test_walk_skips_what_apply_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("a/x.md", "a/__pycache__/y.pyc", "a/z.pyc", "a/b/__pycache__/w.txt", "a/b/v.txt"):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_bytes(b"x")
            self.assertEqual(self.gate.walk_files(root / "a"), apply_mod._walk(root / "a"))


if __name__ == "__main__":
    unittest.main()
