"""Every citation in the payload resolves in any target (plan 2 Task 4).

The payload was taken from backend, so its text cited backend's own commands and documents: right in backend,
pointing at nothing in a sibling. A target holds the payload and a few files of its own, so a citation must name
one of those, and a section it names must be a heading that file has.

What a target holds by itself is `CLAUDE.md`, `docs/harness-local.md` (whose four headings
`docs/harness-boundaries.md` *Managed files* fixes), its `.harness/config.json` and `.harness/manifest.json`, the
`.claude/settings.json` rendered from the payload, and the task list its config names. `docs/superpowers/` is the
superpowers plugin's directory in every repository. And until plan 5 moves the stack into config, a site
`IMPORT.md` *Stack mentions left verbatim* lists keeps its backend text; that section is read, not copied here.
"""

import json
import re
import tempfile
import unittest
from pathlib import Path

from harness_sync.apply import glob_match

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ROOT / "payload"
IMPORT = ROOT / "IMPORT.md"
TEXT_SUFFIXES = {".md", ".py", ".sh", ".ps1", ".yml", ".yaml", ".json", ".txt"}
TARGET_HELD = {
    "CLAUDE.md", "docs/harness-local.md", ".harness/config.json", ".harness/manifest.json", ".claude/settings.json",
    ".claude/settings.local.json",
    # The class map `pr-locality.sh` reads: a target with a change contract holds it as its own, and the helper
    # exits 3 where there is none.
    ".github/locality-gate/classes.yml",
}
# Paths an argument invents to show a case — a link anchor, a spelling the edit guard refuses — not files it cites.
EXAMPLES = {
    "docs/tree/helper.sh", ".claude/scripts/helper.sh", "docs/Sub/x.md", "docs/sub/", "docs/x.md",
    ".claude/sandbox/", "docs/../.claude/sandbox/probe-tmp.txt", "docs/../docs/probe-tmp.txt",
}
# A path a file's code names so that it acts on the file where a target has one: a `case` arm that skips backend's
# closed records matches nothing in a target without them.
CODE_NAMES = {
    ".claude/scripts/sweep-slices.sh": {"docs/pr-decision-log.md", "docs/lessons.md"},
}
# A path a target creates as it runs, never one it holds in its tree.
RUNTIME = (".claude/worktrees/", ".claude/projects/", ".claude/cache/")
# A repository path: one of the trees the payload is laid out in, naming a file by its extension or a directory by
# its trailing slash, or the target's CLAUDE.md. A bare `docs/split-by-chapter` is a branch name, not a path.
_PATH = re.compile(
    r"(?<![\w./<>-])((?:\.claude|\.github|\.harness|docs)/[\w./*<>-]*(?:\.[A-Za-z]+|/)|CLAUDE\.md)(?![\w/{-])")
# A cited path, written bare, in a code span or as a link's text, then its section in italics.
_LINKED = r"`?(?:\]\([^)\s]*\))?(?:'s)?,? \*"
_SECTION = re.compile(r"`?((?:\.claude|\.github|\.harness|docs)/[\w./-]+\.md|CLAUDE\.md)" + _LINKED + r"([^*]+)\*")
_CLAUDE_SECTION = re.compile(r"`?CLAUDE\.md" + _LINKED + r"[^*]+\*")
_HEADING = re.compile(r"^#{1,6} (.+?)\s*#*\s*$", re.MULTILINE)
_STACK_TOKEN = re.compile(r"`([^`\s]+)`")
# A Markdown link's target, inline or a reference definition, which resolves against the linking file's directory.
_LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)\s]*)?\)|^\s*\[[^\]]+\]:\s*<?([^>\s#]+)")


def payload_files(payload: Path = PAYLOAD) -> list[Path]:
    """The payload's text files, but its suites: a path in a test is a fixture, data and not a citation."""
    return sorted(p for p in payload.rglob("*") if p.is_file() and p.suffix in TEXT_SUFFIXES
                  and "__pycache__" not in p.parts and not p.name.startswith("test_"))


def _task_lists() -> set[str]:
    configs = sorted((ROOT / "targets").glob("*.config.json")) + [ROOT / ".harness" / "config.json"]
    return {json.loads(c.read_text(encoding="utf-8")).get("task_list", "") for c in configs} - {""}


def stack_sites(text: str) -> tuple[set[str], set[tuple[str, int]]]:
    """The directories and the (file, line) sites `IMPORT.md` *Stack mentions left verbatim* lists."""
    section = text.split("## Stack mentions left verbatim", 1)[1].split("\n## ", 1)[0]
    dirs: set[str] = set()
    sites: set[tuple[str, int]] = set()
    last_dir = ""
    for token in _STACK_TOKEN.findall(section):
        path, _, spec = token.partition(":")
        if "/" not in path and last_dir:
            path = last_dir + path
        if path.endswith("/"):
            dirs.add(path)
            last_dir = path
            continue
        if "/" in path:
            last_dir = path.rsplit("/", 1)[0] + "/"
        for part in filter(None, spec.split(",")):
            low, _, high = part.partition("-")
            if low.isdigit():
                sites.update((path, n) for n in range(int(low), int(high or low) + 1))
    return dirs, sites


def _normalise(cited: str) -> str | None:
    """The cited path as a payload-relative glob, or None for a path that is not a repository file."""
    cited = cited.rstrip(".,;:)")
    if cited.startswith(RUNTIME) or "$" in cited:
        return None
    return re.sub(r"<[^<>]*>|\{[^{}]*\}", "*", cited)


def resolves(cited: str, payload: Path, held: set[str], rel: str = "") -> bool:
    glob = _normalise(cited)
    if glob is None or glob in held or glob in EXAMPLES or glob in CODE_NAMES.get(rel, ()):
        return True
    if glob.startswith("docs/superpowers/"):
        return True
    if "*" not in glob:
        return (payload / glob).exists()
    if glob.endswith("/"):
        glob += "**"
    return any(glob_match(glob, p.relative_to(payload).as_posix()) for p in payload.rglob("*"))


def unresolved(payload: Path, held: set[str], import_text: str) -> list[str]:
    dirs, sites = stack_sites(import_text)
    found = []
    for path in payload_files(payload):
        rel = path.relative_to(payload).as_posix()
        if any(rel.startswith(d) for d in dirs):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if (rel, number) in sites:
                continue
            for match in _PATH.finditer(line):
                if not resolves(match.group(1), payload, held, rel):
                    found.append(f"{rel}:{number}: {match.group(1)}")
            if path.suffix != ".md":
                continue
            for match in _LINK.finditer(line):
                link = match.group(1) or match.group(2)
                if "://" in link or link.startswith("mailto:"):
                    continue
                target = (path.parent / link).resolve()
                inside = target.is_relative_to(payload.resolve())
                cited = target.relative_to(payload.resolve()).as_posix() if inside else link
                if not inside or not resolves(cited, payload, held):
                    found.append(f"{rel}:{number}: ({link})")
    return found


_COMMENT_LEAD = re.compile(r"^[ 	]*#+[ 	]?", re.MULTILINE)


def _collapsed(path: Path) -> str:
    """The file's text on one line, a script's comment markers dropped so a citation wrapped across them reads whole."""
    text = path.read_text(encoding="utf-8")
    if path.suffix != ".md":
        text = _COMMENT_LEAD.sub("", text)
    return " ".join(text.split())


def missing_sections(payload: Path) -> list[str]:
    found = []
    for path in payload_files(payload):
        for cited, heading in _SECTION.findall(_collapsed(path)):
            target = payload / cited
            if not target.is_file():
                continue
            headings = {" ".join(h.split()) for h in _HEADING.findall(target.read_text(encoding="utf-8"))}
            if heading not in headings:
                found.append(f"{path.relative_to(payload).as_posix()}: {cited}, *{heading}*")
    return found


def local_commands() -> set[str]:
    names = set()
    for config in sorted((ROOT / "targets").glob("*.config.json")):
        for glob in json.loads(config.read_text(encoding="utf-8")).get("local", []):
            match = re.fullmatch(r"\.claude/commands/([\w-]+)\.md", glob)
            if match:
                names.add(match.group(1))
    return names


def local_commands_named(payload: Path, names: set[str]) -> list[str]:
    if not names:
        return []
    pattern = re.compile(r"(?<![\w/.-])/(" + "|".join(sorted(map(re.escape, names))) + r")(?![\w-])")
    return [f"{p.relative_to(payload).as_posix()}: /{m.group(1)}"
            for p in payload_files(payload) for m in pattern.finditer(p.read_text(encoding="utf-8"))]


def claude_sections_cited(payload: Path) -> list[str]:
    return [f"{p.relative_to(payload).as_posix()}: {m.group(0)}"
            for p in payload_files(payload) for m in _CLAUDE_SECTION.finditer(_collapsed(p))]


class PayloadReferences(unittest.TestCase):
    def held(self) -> set[str]:
        return TARGET_HELD | _task_lists()

    def test_payload_cites_only_what_a_target_has(self) -> None:
        self.assertEqual(unresolved(PAYLOAD, self.held(), IMPORT.read_text(encoding="utf-8")), [])

    def test_cited_section_exists(self) -> None:
        self.assertEqual(missing_sections(PAYLOAD), [])

    def test_local_command_not_named(self) -> None:
        names = local_commands()
        self.assertIn("review-branch", names, "the local-command list stopped reading the target configs")
        self.assertEqual(local_commands_named(PAYLOAD, names), [])

    def test_claude_md_section_not_cited(self) -> None:
        self.assertEqual(claude_sections_cited(PAYLOAD), [])


class PlantedCitations(unittest.TestCase):
    """Each check reports a citation planted in a scratch payload, and passes the shape beside it that resolves."""

    NO_STACK = "## Stack mentions left verbatim\n\n- none\n"

    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.payload = Path(scratch.name)

    def plant(self, rel: str, text: str) -> None:
        path = self.payload / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_unresolved_path_and_link_are_reported(self) -> None:
        self.plant("docs/harness/real.md", "# Real\n")
        self.plant(".github/gate/README.md", "\n".join([
            "Read `docs/harness/real.md` and `docs/harness-local.md`.",
            "Read `docs/gone.md`.",
            "See [the rule](../../docs/harness/real.md) and [a lost one](../../docs/lost.md).",
            "[ref]: ../../docs/also-lost.md",
            "An invented `docs/x.md` shows a case.",
        ]))
        self.assertEqual(unresolved(self.payload, TARGET_HELD, self.NO_STACK), [
            ".github/gate/README.md:2: docs/gone.md",
            ".github/gate/README.md:3: (../../docs/lost.md)",
            ".github/gate/README.md:4: (../../docs/also-lost.md)",
        ])

    def test_code_name_is_allowed_only_in_its_own_file(self) -> None:
        self.plant(".claude/scripts/sweep-slices.sh", "case $f in docs/lessons.md) ;; esac\n")
        self.plant(".claude/scripts/other.sh", "case $f in docs/lessons.md) ;; esac\n")
        self.assertEqual(unresolved(self.payload, TARGET_HELD, self.NO_STACK),
                         [".claude/scripts/other.sh:1: docs/lessons.md"])

    def test_missing_section_is_reported_even_wrapped_in_a_comment(self) -> None:
        self.plant("docs/harness/real.md", "# Real\n\n## Present heading\n")
        self.plant(".claude/hooks/guard.py", "\n".join([
            "# (`docs/harness/real.md`, *Present",
            "# heading*) and (`docs/harness/real.md`, *Absent",
            "# heading*)",
        ]))
        self.assertEqual(missing_sections(self.payload),
                         [".claude/hooks/guard.py: docs/harness/real.md, *Absent heading*"])

    def test_local_command_is_reported_but_not_its_path(self) -> None:
        self.plant(".claude/commands/ship.md", "Run `/validate-blueprint` per docs/commands/validate-blueprint.md.\n")
        self.assertEqual(local_commands_named(self.payload, {"validate-blueprint"}),
                         [".claude/commands/ship.md: /validate-blueprint"])

    def test_claude_md_section_is_reported_bare_or_linked(self) -> None:
        self.plant(".github/gate/README.md", "\n".join([
            "`CLAUDE.md`'s *Style* and [`CLAUDE.md`](../../CLAUDE.md)'s *Plans* rule;",
            "`CLAUDE.md` carries the pointer.",
        ]))
        self.assertEqual(claude_sections_cited(self.payload), [
            ".github/gate/README.md: `CLAUDE.md`'s *Style*",
            ".github/gate/README.md: `CLAUDE.md`](../../CLAUDE.md)'s *Plans*",
        ])


if __name__ == "__main__":
    unittest.main()
