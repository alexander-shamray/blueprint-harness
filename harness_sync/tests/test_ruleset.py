"""Tests for the rulesets of `main` as data and their comparison."""

import copy
import json
import re
import unittest
from pathlib import Path

from harness_sync.ruleset import compare, desired, floor_breaches, load, normal_form

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
        # Frontend is left out until Task 2 gives it checks; the breach test
        # below pins that its empty entry is reported.
        for repo in (BACKEND, HARNESS, ADMIN):
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

    def test_floor_breaches_names_each_breach(self) -> None:
        """Every desired body is clean, so the data cannot weaken the floor;
        each weakening of a clean body is named once."""
        for repo in self.data.checks:
            lines = floor_breaches(desired(self.data, repo))
            if repo == FRONTEND:
                # Task 2 fills frontend's checks; until then the guard must
                # call the empty entry a breach, not pass it.
                self.assertEqual(lines, ["required_status_checks names no check"])
            else:
                self.assertEqual(lines, [], repo)
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
