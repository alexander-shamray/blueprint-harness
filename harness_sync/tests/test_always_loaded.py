"""The always-loaded budget: `payload/.harness/agent-rules.md` and every file it imports.

Every target's `CLAUDE.md` imports the rules file, so its bytes, and those of whatever it imports in turn, load
into every session in every target before the first prompt. The budget is backend's `CLAUDE.md` at `b57b12d24`
(spec 5.6): the rules may move out of it, but the managed part may not cost a session more than it did.

The resolver follows Claude Code's import rules (code.claude.com/docs/en/memory, *Import additional files*): an
`@path` resolves against the importing file, an `@` inside a code span or a fenced block is not an import, and a
chain stops at four hops. A fifth hop is refused rather than counted, because no session loads it.
"""

import json
import re
import tempfile
import unittest
from pathlib import Path

from harness_sync.apply import glob_match

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ROOT / "payload"
RULES = PAYLOAD / ".harness" / "agent-rules.md"
RULES_REL = ".harness/agent-rules.md"
BUDGET = 8526
MAX_HOPS = 4

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1")
_IMPORT = re.compile(r"(?:^|(?<=\s))@([^\s`]+)")


class ImportError_(Exception):
    """An import the budget cannot count: missing, outside the root, or past the fourth hop."""


def _lf_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def imports(path: Path, root: Path) -> list[Path]:
    """The files `path` imports directly, in order, each resolved against `path`'s directory. An import that
    leaves `root` or names no file raises."""
    found: list[Path] = []
    fence: str | None = None
    for line in _lf_text(path).split("\n"):
        opener = _FENCE.match(line)
        if fence is not None:
            if opener and opener.group(1)[0] == fence[0] and len(opener.group(1)) >= len(fence):
                fence = None
            continue
        if opener:
            fence = opener.group(1)
            continue
        for match in _IMPORT.finditer(_CODE_SPAN.sub("", line)):
            target = (path.parent / match.group(1)).resolve()
            if not target.is_relative_to(root.resolve()):
                raise ImportError_(f"{path}: @{match.group(1)} resolves outside {root}")
            if not target.is_file():
                raise ImportError_(f"{path}: @{match.group(1)} names no file")
            found.append(target)
    return found


def loaded_bytes(path: Path, root: Path) -> int:
    """LF bytes of `path` and every file it imports, each counted once. A file reached only at a fifth hop
    raises, naming it."""
    seen: set[Path] = set()
    total = 0
    frontier = [path.resolve()]
    for hop in range(MAX_HOPS + 2):
        following: list[Path] = []
        for current in frontier:
            if current in seen:
                continue
            if hop > MAX_HOPS:
                raise ImportError_(f"{current} is hop {hop}; Claude Code stops at {MAX_HOPS}")
            seen.add(current)
            total += len(_lf_text(current).encode("utf-8"))
            following.extend(imports(current, root))
        frontier = following
    return total


class BudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, name: str, text: str) -> Path:
        path = self.tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        return path

    def test_budget_holds(self) -> None:
        self.assertLessEqual(loaded_bytes(RULES, PAYLOAD), BUDGET)

    def test_budget_counts_imports(self) -> None:
        self.write("big.md", "x" * 9000)
        small = self.write("small.md", "@big.md\n" + "y" * 92)
        self.assertEqual(len(_lf_text(small)), 100)
        self.assertGreater(loaded_bytes(small, self.tmp), BUDGET)

    def test_import_in_code_span_ignored(self) -> None:
        self.write("big.md", "x" * 9000)
        text = "Write `@big.md` to import.\n\n```\n@big.md\n```\n\n~~~~\n@missing.md\n~~~~\n"
        rules = self.write("rules.md", text)
        self.assertEqual(imports(rules, self.tmp), [])
        self.assertEqual(loaded_bytes(rules, self.tmp), len(text.encode("utf-8")))

    def test_email_is_not_an_import(self) -> None:
        rules = self.write("rules.md", "noreply@anthropic.com\n")
        self.assertEqual(imports(rules, self.tmp), [])

    def test_import_resolves_against_importing_file(self) -> None:
        self.write("a/b.md", "b")
        self.write("a/c.md", "@b.md\n")
        rules = self.write("rules.md", "@a/c.md\n")
        self.assertEqual(loaded_bytes(rules, self.tmp), len("@a/c.md\n") + len("@b.md\n") + 1)

    def test_import_depth_over_four_refused(self) -> None:
        names = [f"f{i}.md" for i in range(6)]
        for here, there in zip(names, names[1:]):
            self.write(here, f"@{there}\n")
        self.write(names[-1], "end\n")
        with self.assertRaises(ImportError_) as ctx:
            loaded_bytes(self.tmp / names[0], self.tmp)
        self.assertIn(names[5], str(ctx.exception))

    def test_import_depth_of_four_counted(self) -> None:
        names = [f"f{i}.md" for i in range(5)]
        for here, there in zip(names, names[1:]):
            self.write(here, f"@{there}\n")
        self.write(names[-1], "end\n")
        self.assertEqual(loaded_bytes(self.tmp / names[0], self.tmp), 4 * len("@f1.md\n") + len("end\n"))

    def test_import_outside_root_refused(self) -> None:
        inner = self.tmp / "inner"
        self.write("outside.md", "x")
        rules = self.write("inner/rules.md", "@../outside.md\n")
        with self.assertRaises(ImportError_):
            imports(rules, inner)

    def test_missing_import_refused(self) -> None:
        rules = self.write("rules.md", "@gone.md\n")
        with self.assertRaises(ImportError_) as ctx:
            imports(rules, self.tmp)
        self.assertIn("gone.md", str(ctx.exception))

    def test_imports_resolve_inside_payload(self) -> None:
        for target in imports(RULES, PAYLOAD):
            self.assertTrue(target.is_relative_to(PAYLOAD.resolve()), target)
        loaded_bytes(RULES, PAYLOAD)

    def test_budget_reads_lf_form(self) -> None:
        lf = self.write("lf.md", "one\ntwo\n")
        crlf = self.write("crlf.md", "one\r\ntwo\r\n")
        self.assertEqual(loaded_bytes(crlf, self.tmp), loaded_bytes(lf, self.tmp))

    def test_agent_rules_is_managed(self) -> None:
        configs = sorted((ROOT / "targets").glob("*.config.json")) + [ROOT / ".harness" / "config.json"]
        for config in configs:
            data = json.loads(config.read_text(encoding="utf-8"))
            for kind in ("exclude", "local"):
                for glob in data.get(kind, []):
                    self.assertFalse(glob_match(glob, RULES_REL), f"{config.name} {kind} {glob} matches it")


if __name__ == "__main__":
    unittest.main()
