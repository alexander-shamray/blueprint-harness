"""Tests for the rulesets of `main` as data and their comparison."""

import contextlib
import copy
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from harness_sync.__main__ import main
from harness_sync.ruleset import (
    RulesetError,
    compare,
    desired,
    floor_breaches,
    load,
    normal_form,
    run_apply,
    run_check,
)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "rulesets" / "main.json"
FIXTURE = Path(__file__).parent / "fixtures" / "backend-ruleset.json"
BACKEND = "alexander-shamray/blueprint-backend"
HARNESS = "alexander-shamray/blueprint-harness"
FRONTEND = "alexander-shamray/blueprint-frontend"
ADMIN = "alexander-shamray/blueprint-admin"


def rule(body: dict, kind: str) -> dict:
    return next(r for r in body["rules"] if r["type"] == kind)


class RulesetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = load(DATA)

    def want(self) -> dict:
        return normal_form(desired(self.data, BACKEND))

    def test_floor_names_every_rule_the_spec_requires(self) -> None:
        """The floor is spec 5.5 and nothing less: a repository that drops one
        of these is no longer protected, and every repository carries the
        fifth rule, its own required checks."""
        for repo in (BACKEND, HARNESS, FRONTEND, ADMIN):
            body = desired(self.data, repo)
            self.assertEqual(
                sorted(r["type"] for r in body["rules"]),
                [
                    "deletion",
                    "non_fast_forward",
                    "pull_request",
                    "required_linear_history",
                    "required_status_checks",
                ],
            )
            params = rule(body, "pull_request")["parameters"]
            self.assertEqual(params["required_approving_review_count"], 0)
            self.assertEqual(params["allowed_merge_methods"], ["rebase"])
            self.assertEqual(body["bypass_actors"], [])
            self.assertEqual(body["enforcement"], "active")
            self.assertEqual(
                body["conditions"],
                {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
            )
            checks = rule(body, "required_status_checks")["parameters"]["required_status_checks"]
            self.assertEqual([c["context"] for c in checks], self.data.checks[repo])
            self.assertEqual({c["integration_id"] for c in checks}, {15368})
            self.assertEqual((body["name"], body["target"]), ("main", "branch"))

    def test_every_repository_has_a_checks_entry(self) -> None:
        """A repository with no entry is one whose protection the tool cannot
        state: targets.json's two, plus the two that follow, and no others."""
        targets = {t["repo"] for t in json.loads((ROOT / "targets.json").read_text(encoding="utf-8"))}
        self.assertEqual(targets, {BACKEND, HARNESS})
        self.assertEqual(set(self.data.checks), targets | {FRONTEND, ADMIN})

    def test_harness_checks_are_its_job_ids(self) -> None:
        """A required check is a job id; a renamed job leaves every pull
        request waiting for a check that never reports. Read from the
        workflows, so the data and the job ids cannot drift apart."""
        legs: set[str] = set()
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            lines = path.read_text(encoding="utf-8").splitlines()
            if "jobs:" not in lines:
                continue
            job = ""
            for line in lines[lines.index("jobs:") + 1 :]:
                found = re.fullmatch(r"  ([A-Za-z0-9_-]+):\s*", line)
                if found:
                    job = found.group(1)
                    legs.add(job)
                    continue
                matrix = re.fullmatch(r"\s+os:\s*\[(.*)\]\s*", line)
                if matrix and job:
                    legs.discard(job)
                    legs.update(f"{job} ({name.strip()})" for name in matrix.group(1).split(","))
        missing = set(self.data.checks[HARNESS]) - legs
        self.assertEqual(missing, set(), f"not a job id or matrix leg: {sorted(missing)}")

    def test_compare_reports_a_missing_rule(self) -> None:
        """A floor rule absent from the live ruleset is a hole."""
        have = self.want()
        del have["rules"]["non_fast_forward"]
        lines = compare(self.want(), have)
        self.assertEqual(len(lines), 1)
        self.assertIn("non_fast_forward", lines[0])

    def test_compare_reports_a_missing_check(self) -> None:
        have = self.want()
        have["rules"]["required_status_checks"]["contexts"].remove(("build", 15368))
        lines = compare(self.want(), have)
        self.assertEqual(len(lines), 1)
        self.assertIn("build", lines[0])

    def test_compare_reports_an_extra_check(self) -> None:
        """Equal as sets in both directions: a check the data does not name
        blocks merges for a job that may not exist."""
        have = self.want()
        have["rules"]["required_status_checks"]["contexts"].append(("ghost", 15368))
        lines = compare(self.want(), have)
        self.assertEqual(len(lines), 1)
        self.assertIn("ghost", lines[0])

    def test_compare_reports_a_check_from_another_source(self) -> None:
        """A check bound to another source, or to any source, is not the one
        the data names: a status of that name from elsewhere would satisfy it."""
        for source in (1, None):
            have = self.want()
            contexts = have["rules"]["required_status_checks"]["contexts"]
            contexts[contexts.index(("build", 15368))] = ("build", source)
            lines = compare(self.want(), have)
            self.assertEqual(len(lines), 2, lines)
            self.assertTrue(all("build" in line for line in lines), lines)

    def test_compare_reports_raised_approvals(self) -> None:
        have = self.want()
        have["rules"]["pull_request"]["required_approving_review_count"] = 1
        lines = compare(self.want(), have)
        self.assertEqual(len(lines), 1)
        self.assertIn("required_approving_review_count", lines[0])

    def test_compare_reports_a_bypass_actor(self) -> None:
        have = self.want()
        have["bypass_actors"] = [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]
        lines = compare(self.want(), have)
        self.assertEqual(len(lines), 1)
        self.assertIn("bypass", lines[0])

    def test_compare_admits_an_extra_rule_type(self) -> None:
        """A rule the floor does not name only makes the ruleset stricter."""
        have = self.want()
        have["rules"]["required_signatures"] = {}
        self.assertEqual(compare(self.want(), have), [])

    def test_normal_form_reads_the_api_shape(self) -> None:
        """Recorded from the live backend ruleset: the API's extra fields (ids,
        timestamps, the name) are dropped, so the data's body
        and the live one compare equal."""
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(compare(self.want(), normal_form(fixture)), [])

    def test_compare_and_floor_report_a_target_other_than_branch(self) -> None:
        """A ruleset on tags protects no branch, whatever else it says."""
        body = desired(self.data, BACKEND)
        body["target"] = "tag"
        self.assertEqual(len(compare(self.want(), normal_form(body))), 1)
        self.assertEqual(len(floor_breaches(body)), 1)
        self.assertIn("target", floor_breaches(body)[0])

    def test_floor_breaches_flags_a_check_without_the_actions_source(self) -> None:
        """A check bound to another source, or to none, is satisfied by a
        status of that name from anywhere."""
        for source in (1, None):
            body = desired(self.data, BACKEND)
            check = rule(body, "required_status_checks")["parameters"]["required_status_checks"][0]
            if source is None:
                del check["integration_id"]
            else:
                check["integration_id"] = source
            lines = floor_breaches(body)
            self.assertEqual(len(lines), 1, lines)
            self.assertIn(check["context"], lines[0])

    def test_normal_form_sorts_a_context_with_and_without_an_id(self) -> None:
        """One context bound and unbound must not sort by comparing None."""
        found = [{"context": "a", "integration_id": 15368}, {"context": "a"}]
        api = {"rules": [{"type": "required_status_checks", "parameters": {"required_status_checks": found}}]}
        contexts = normal_form(api)["rules"]["required_status_checks"]["contexts"]
        self.assertEqual(contexts, [("a", None), ("a", 15368)])

    def test_load_rejects_a_malformed_file(self) -> None:
        """A hand-edited file fails with RulesetError, not a TypeError, and a
        string is never read as a list of characters."""
        good = json.loads(DATA.read_text(encoding="utf-8"))
        bad = {
            "string names": {"names": "main"},
            "non-iterable names": {"names": 5},
            "string checks entry": {"checks": {BACKEND: "build"}},
        }
        for key in ("rules", "target", "conditions", "bypass_actors"):
            bad[f"floor without {key}"] = {"floor": {k: v for k, v in good["floor"].items() if k != key}}
        for label, change in bad.items():
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "main.json"
                path.write_text(json.dumps({**good, **change}), encoding="utf-8")
                with self.assertRaises(RulesetError, msg=label):
                    load(path)

    def test_floor_breaches_names_each_breach(self) -> None:
        """Every desired body is clean, so the data cannot weaken the floor;
        each weakening of a clean body is named once."""
        for repo in self.data.checks:
            lines = floor_breaches(desired(self.data, repo))
            self.assertEqual(lines, [], repo)
        empty = copy.deepcopy(self.data)
        empty.checks[FRONTEND].clear()
        self.assertEqual(floor_breaches(desired(empty, FRONTEND)), ["required_status_checks names no check"])
        weak = copy.deepcopy(desired(self.data, BACKEND))
        weak["rules"] = [r for r in weak["rules"] if r["type"] != "deletion"]
        rule(weak, "pull_request")["parameters"]["required_approving_review_count"] = 1
        rule(weak, "pull_request")["parameters"]["allowed_merge_methods"] = ["merge"]
        weak["bypass_actors"] = [{"actor_id": 5}]
        weak["enforcement"] = "evaluate"
        weak["conditions"]["ref_name"]["include"] = ["refs/heads/dev"]
        lines = floor_breaches(weak)
        for word in ("deletion", "approving", "merge methods", "bypass", "enforcement", "condition"):
            self.assertEqual(sum(word in line for line in lines), 1, (word, lines))
        self.assertEqual(len(lines), 6)


if __name__ == "__main__":
    unittest.main()


class FakeGh:
    """Answers the `gh api` calls the ruleset commands make, and records them.

    `rulesets` maps a repository to its live rulesets by id; a PUT or POST
    stores the body it is given, as GitHub does, so a check after an apply
    reads it back.
    """

    def __init__(self, rulesets: dict[str, dict[int, dict]] | None = None, effective: dict[str, list] | None = None):
        self.rulesets = rulesets or {}
        self.effective = effective or {}
        self.calls: list[tuple[str, str, dict | None]] = []

    def call(self, method: str, path: str, body: dict | None = None, paginate: bool = False):
        self.calls.append((method, path, body))
        route = path.split("?")[0].split("/")
        repo = "/".join(route[1:3])
        live = self.rulesets.setdefault(repo, {})
        if route[3:] == ["rules", "branches", "main"]:
            return self.effective[repo]
        if method == "GET" and route[3:] == ["rulesets"]:
            return [{"id": i, "name": b["name"], "target": b["target"]} for i, b in live.items()]
        if method == "GET":
            return live[int(route[4])]
        if method == "PUT":
            live[int(route[4])] = {**body, "id": int(route[4])}
            return live[int(route[4])]
        if method == "POST":
            new = max(live, default=100) + 1
            live[new] = {**body, "id": new}
            return live[new]
        raise AssertionError(f"unexpected gh call {method} {path}")

    def writes(self) -> list[tuple[str, str, dict | None]]:
        return [c for c in self.calls if c[0] != "GET"]


def live(data, repo: str, name: str = "protect-main", ref: str = "refs/heads/main") -> dict:
    """The ruleset a repository holds today: the data's body under an old name and condition."""
    body = copy.deepcopy(desired(data, repo))
    body["name"] = name
    body["conditions"]["ref_name"]["include"] = [ref]
    return body


def run(fn, *args) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fn(*args)
    return code, out.getvalue(), err.getvalue()


class RulesetCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = load(DATA)

    def test_apply_refuses_data_below_the_floor(self) -> None:
        weak = copy.deepcopy(self.data)
        weak.floor["rules"].remove("deletion")
        gh = FakeGh()
        code, _, err = run(run_apply, gh, weak, FRONTEND)
        self.assertEqual(code, 2)
        self.assertIn("deletion", err)
        self.assertEqual(gh.calls, [])

    def test_apply_puts_to_a_ruleset_found_by_a_live_name(self) -> None:
        other = live(self.data, FRONTEND, "unrelated")
        gh = FakeGh({FRONTEND: {7: live(self.data, FRONTEND), 8: other}})
        code, out, _ = run(run_apply, gh, self.data, FRONTEND)
        self.assertEqual(code, 0, out)
        self.assertEqual([(c[0], c[1]) for c in gh.writes()], [("PUT", f"repos/{FRONTEND}/rulesets/7")])
        self.assertEqual(gh.writes()[0][2], desired(self.data, FRONTEND))
        self.assertIn(("GET", f"repos/{FRONTEND}/rulesets/7", None), gh.calls)
        self.assertEqual(gh.rulesets[FRONTEND][8], other)

    def test_apply_ignores_a_tag_ruleset_with_a_matching_name(self) -> None:
        tag = live(self.data, FRONTEND)
        tag["target"] = "tag"
        gh = FakeGh({FRONTEND: {7: live(self.data, FRONTEND), 8: tag}})
        code, _, _ = run(run_apply, gh, self.data, FRONTEND)
        self.assertEqual(code, 0)
        self.assertEqual([c[1] for c in gh.writes()], [f"repos/{FRONTEND}/rulesets/7"])

    def test_apply_posts_when_no_name_matches(self) -> None:
        gh = FakeGh({FRONTEND: {5: live(self.data, FRONTEND, "unrelated")}})
        code, _, _ = run(run_apply, gh, self.data, FRONTEND)
        self.assertEqual(code, 0)
        self.assertEqual([(c[0], c[1]) for c in gh.writes()], [("POST", f"repos/{FRONTEND}/rulesets")])

    def test_apply_refuses_two_matching_rulesets(self) -> None:
        gh = FakeGh({FRONTEND: {3: live(self.data, FRONTEND), 4: live(self.data, FRONTEND, "main")}})
        code, _, err = run(run_apply, gh, self.data, FRONTEND)
        self.assertEqual(code, 2)
        self.assertIn("3", err)
        self.assertIn("4", err)
        self.assertEqual(gh.writes(), [])

    def test_check_reads_bypass_actors(self) -> None:
        body = live(self.data, BACKEND, "main", "~DEFAULT_BRANCH")
        body["bypass_actors"] = [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]
        gh = FakeGh({BACKEND: {1: body}})
        code, out, _ = run(run_check, gh, self.data, [BACKEND], False)
        self.assertEqual(code, 1)
        self.assertIn(f"{BACKEND}: bypass actor present", out)
        self.assertEqual(gh.writes(), [])

    def test_check_effective_ignores_bypass(self) -> None:
        flat = [dict(r, ruleset_id=1, ruleset_source=BACKEND) for r in desired(self.data, BACKEND)["rules"]]
        gh = FakeGh({BACKEND: {1: {**live(self.data, BACKEND), "bypass_actors": [{"actor_id": 5}]}}},
                    {BACKEND: flat})
        code, out, _ = run(run_check, gh, self.data, [BACKEND], True)
        self.assertEqual((code, out), (0, f"{BACKEND}: matches\n"))
        self.assertEqual([c[1].split("?")[0] for c in gh.calls], [f"repos/{BACKEND}/rules/branches/main"])

    def test_check_effective_merges_rules_of_several_rulesets(self) -> None:
        rules = desired(self.data, BACKEND)["rules"]
        extra = {"type": "required_status_checks", "ruleset_id": 2, "parameters": {
            "required_status_checks": [{"context": "extra", "integration_id": 15368}]}}
        first = [dict(r, ruleset_id=1) for r in rules]
        code, out, _ = run(run_check, FakeGh(effective={BACKEND: first + [extra]}), self.data, [BACKEND], True)
        self.assertEqual(code, 1)
        self.assertEqual(out.count("\n"), 1)
        self.assertIn("required check not in the data: extra", out)

    def test_check_exits_1_with_one_line_per_difference(self) -> None:
        body = live(self.data, FRONTEND)
        rule(body, "required_status_checks")["parameters"]["required_status_checks"].pop()
        gh = FakeGh({FRONTEND: {7: body}, BACKEND: {1: {**desired(self.data, BACKEND)}}})
        code, out, _ = run(run_check, gh, self.data, [FRONTEND, BACKEND], False)
        self.assertEqual(code, 1)
        lines = out.splitlines()
        self.assertEqual(len(lines), 3, out)
        self.assertTrue(lines[0].startswith(f"{FRONTEND}: condition ref_name"))
        self.assertTrue(lines[1].startswith(f"{FRONTEND}: required check missing: web"))
        self.assertEqual(lines[2], f"{BACKEND}: matches")

    def test_check_reports_a_repository_with_no_ruleset(self) -> None:
        code, out, _ = run(run_check, FakeGh(), self.data, [BACKEND], False)
        self.assertEqual(code, 1)
        self.assertIn(f"{BACKEND}: no branch ruleset named", out)

    def test_repo_outside_the_data_is_refused(self) -> None:
        gh = FakeGh()
        for fn, args in ((run_apply, ("o/other",)), (run_check, (["o/other"], False))):
            code, _, err = run(fn, gh, self.data, *args)
            self.assertEqual(code, 2)
            self.assertIn("o/other", err)
        self.assertEqual(gh.calls, [])
        code, _, err = run(main, ["ruleset-apply", "o/other"])
        self.assertEqual(code, 2)
        self.assertIn("o/other", err)
