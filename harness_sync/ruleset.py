"""The rulesets of `main` as data, and their comparison (spec 5.5).

`rulesets/main.json` holds the floor every repository's `main` ruleset must
meet and, per repository, the status checks it requires. `desired` renders
that into the body the rulesets API takes; `normal_form` reduces a body, or
the API's reading of one, to the fields the floor and the checks name, so
`compare` can set the data against a live ruleset without the ids, the
timestamps and the name.
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BRANCH = "~DEFAULT_BRANCH"

# Every required check is bound to GitHub Actions, as the live rulesets are, so
# a status of that name from another source does not satisfy it.
ACTIONS_INTEGRATION_ID = 15368

# The pull_request fields the floor names; the API's others are not compared.
_PR_KEYS = ("required_approving_review_count", "allowed_merge_methods")

# The rule types the floor requires of every repository, including the
# required_status_checks rule built from its checks. Kept here as well as in
# the data: the data says what to apply, this says what no data may fall below.
_FLOOR_TYPES = (
    "deletion",
    "non_fast_forward",
    "pull_request",
    "required_linear_history",
    "required_status_checks",
)


class RulesetError(Exception):
    """The rulesets file is unreadable or does not match its shape."""


@dataclass(frozen=True)
class Rulesets:
    name: str
    names: tuple[str, ...]
    floor: dict
    checks: dict[str, list[str]]


def load(path: Path) -> Rulesets:
    """Read `rulesets/main.json`; raise RulesetError naming what is wrong."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        name, names, floor = raw["name"], raw["names"], raw["floor"]
        checks = dict(raw["checks"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise RulesetError(f"{path}: {exc!r}") from exc
    if not isinstance(name, str):
        raise RulesetError(f"{path}: 'name' must be a string")
    if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
        raise RulesetError(f"{path}: 'names' must be a non-empty list of strings")
    if not isinstance(floor, dict):
        raise RulesetError(f"{path}: 'floor' must be an object")
    for key in ("enforcement", "target", "conditions", "bypass_actors", "rules"):
        if key not in floor:
            raise RulesetError(f"{path}: floor has no {key!r}")
    if not isinstance(floor["rules"], list):
        raise RulesetError(f"{path}: floor 'rules' must be a list")
    for repo, entry in checks.items():
        if not isinstance(entry, list) or not all(isinstance(c, str) for c in entry):
            raise RulesetError(f"{path}: checks for {repo} must be a list of strings")
    return Rulesets(name, tuple(names), floor, checks)


def desired(data: Rulesets, repo: str) -> dict:
    """The full ruleset body that POST and PUT /repos/{repo}/rulesets take."""
    if repo not in data.checks:
        raise RulesetError(f"no checks entry for {repo}")
    floor = data.floor
    rules = []
    for entry in floor["rules"]:
        entry = {"type": entry} if isinstance(entry, str) else json.loads(json.dumps(entry))
        if entry["type"] == "pull_request":
            # The API requires these four; the floor says nothing of them.
            entry["parameters"] = {
                "dismiss_stale_reviews_on_push": False,
                "require_code_owner_review": False,
                "require_last_push_approval": False,
                "required_review_thread_resolution": False,
                **entry["parameters"],
            }
        rules.append(entry)
    rules.append(
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": False,
                "required_status_checks": [
                    {"context": c, "integration_id": ACTIONS_INTEGRATION_ID} for c in data.checks[repo]
                ],
            },
        }
    )
    return {
        "name": data.name,
        "target": floor["target"],
        "enforcement": floor["enforcement"],
        "conditions": json.loads(json.dumps(floor["conditions"])),
        "bypass_actors": list(floor["bypass_actors"]),
        "rules": rules,
    }


def normal_form(api: dict) -> dict:
    """Keep only what the floor and the checks name.

    A rule type the floor does not name is kept as a bare presence, so
    `compare` can see it and admit it.
    """
    rules: dict[str, dict] = {}
    for entry in api.get("rules", []):
        kind, params = entry["type"], entry.get("parameters") or {}
        if kind == "pull_request":
            rules[kind] = {k: params[k] for k in _PR_KEYS if k in params}
        elif kind == "required_status_checks":
            found = params.get("required_status_checks", [])
            rules[kind] = {"contexts": sorted(
                ((c["context"], c.get("integration_id")) for c in found),
                key=lambda c: (c[0], c[1] is not None, c[1] or 0),
            )}
        else:
            rules[kind] = {}
    ref = (api.get("conditions") or {}).get("ref_name") or {}
    return {
        "target": api.get("target"),
        "enforcement": api.get("enforcement"),
        "ref_name": {"include": sorted(ref.get("include", [])), "exclude": sorted(ref.get("exclude", []))},
        "bypass_actors": list(api.get("bypass_actors") or []),
        "rules": rules,
    }


def compare(want: dict, have: dict) -> list[str]:
    """One line per way `have` falls short of `want`; empty when they match.

    Both are normal forms. A rule type `want` does not name is admitted, as it
    only makes `have` stricter; a bypass actor `have` carries is a difference
    whatever `want` says, because the floor has none.
    """
    lines = []
    if have["target"] != want["target"]:
        lines.append(f"target is {have['target']!r}, want {want['target']!r}")
    if have["enforcement"] != want["enforcement"]:
        lines.append(f"enforcement is {have['enforcement']!r}, want {want['enforcement']!r}")
    if have["ref_name"] != want["ref_name"]:
        lines.append(f"condition ref_name is {have['ref_name']}, want {want['ref_name']}")
    for actor in have["bypass_actors"]:
        lines.append(f"bypass actor present: {json.dumps(actor, sort_keys=True)}")
    for kind, params in want["rules"].items():
        if kind not in have["rules"]:
            lines.append(f"rule missing: {kind}")
            continue
        got = have["rules"][kind]
        if kind == "required_status_checks":
            wanted = {tuple(c) for c in params["contexts"]}
            found = {tuple(c) for c in got["contexts"]}
            for context, source in sorted(wanted - found, key=str):
                lines.append(f"required check missing: {context} (integration {source})")
            for context, source in sorted(found - wanted, key=str):
                lines.append(f"required check not in the data: {context} (integration {source})")
            continue
        for key, value in params.items():
            if got.get(key) != value:
                lines.append(f"{kind}.{key} is {got.get(key)!r}, want {value!r}")
    return lines


def floor_breaches(body: dict) -> list[str]:
    """One line per way a body falls below the floor of spec 5.5.

    Takes a `desired` body or the API's reading of a ruleset. It judges the
    body alone, and the minimum is held here in code, apart from the data, as
    the floor's own guard against data that has been weakened.
    """
    have = normal_form(body)
    lines = [f"rule missing: {kind}" for kind in _FLOOR_TYPES if kind not in have["rules"]]
    contexts = have["rules"].get("required_status_checks", {}).get("contexts")
    if contexts == []:
        lines.append("required_status_checks names no check")
    pull = have["rules"].get("pull_request")
    if pull is not None:
        count = pull.get("required_approving_review_count")
        if count != 0:
            lines.append(f"required approving review count is {count!r}, want 0")
        if pull.get("allowed_merge_methods") != ["rebase"]:
            lines.append(f"allowed merge methods are {pull.get('allowed_merge_methods')!r}, want ['rebase']")
    if have["target"] != "branch":
        lines.append(f"target is {have['target']!r}, want 'branch'")
    checks = have["rules"].get("required_status_checks", {}).get("contexts", [])
    for context, source in checks:
        if source != ACTIONS_INTEGRATION_ID:
            lines.append(f"required check {context} has integration {source!r}, want {ACTIONS_INTEGRATION_ID}")
    if have["bypass_actors"]:
        lines.append(f"bypass actors present: {len(have['bypass_actors'])}")
    if have["enforcement"] != "active":
        lines.append(f"enforcement is {have['enforcement']!r}, want 'active'")
    if have["ref_name"] != {"include": [DEFAULT_BRANCH], "exclude": []}:
        lines.append(f"condition ref_name is {have['ref_name']}, want include [{DEFAULT_BRANCH!r}] and no exclude")
    return lines


# ---------------------------------------------------------------------------
# Reading and applying the rulesets over `gh api`.
#
# Exit codes of `ruleset-check` and `ruleset-apply`: 0 the live ruleset
# matches the data; 1 it differs, one line per difference, each prefixed with
# the repository; 2 a refusal or an error: a repository outside the data,
# data below the floor, two rulesets that match one repository, or a `gh`
# call that failed.
# ---------------------------------------------------------------------------

DATA_PATH = Path(__file__).resolve().parent.parent / "rulesets" / "main.json"


class GhApi:
    """`gh api`, the only place a `gh` argv is built, so tests swap in a fake
    with the same `call`."""

    @staticmethod
    def argv(method: str, path: str, has_body: bool, paginate: bool = False) -> list[str]:
        argv = ["gh", "api", "--method", method]
        if paginate:
            argv += ["--paginate", "--slurp"]
        if has_body:
            argv += ["--input", "-"]
        return [*argv, path]

    def call(self, method: str, path: str, body: dict | None = None, paginate: bool = False):
        """The parsed JSON `gh api` returns; a paginated list comes back flat."""
        has_body = body is not None
        done = subprocess.run(
            self.argv(method, path, has_body, paginate),
            input=json.dumps(body) if has_body else None,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        if done.returncode != 0:
            raise RulesetError(f"gh api {method} {path} failed: {done.stderr.strip()}")
        parsed = json.loads(done.stdout) if done.stdout.strip() else None
        if paginate:
            # --slurp wraps every page in a list.
            return [x for page in parsed for x in page]
        return parsed


def _find(gh, data: Rulesets, repo: str) -> int | None:
    """The id of the one branch ruleset of `repo` whose name is in the data,
    or None; two matches raise."""
    listing = gh.call("GET", f"repos/{repo}/rulesets?per_page=100", paginate=True)
    ids = [r["id"] for r in listing if r.get("target") == "branch" and r.get("name") in data.names]
    if len(ids) > 1:
        raise RulesetError(f"{repo}: rulesets {ids[0]} and {ids[1]} both match the names {list(data.names)}")
    return ids[0] if ids else None


def _merge_effective(rules: list[dict]) -> list[dict]:
    """One rule per type from the flat list of rules in force on a branch.

    Rulesets stack, so the strictest reading of each type is the one that
    holds: the most approvals, the merge methods every pull_request rule
    allows, and the checks of every required_status_checks rule together.
    """
    merged: dict[str, dict] = {}
    for rule in rules:
        kind, params = rule["type"], rule.get("parameters") or {}
        if kind not in merged:
            merged[kind] = {"type": kind, "parameters": json.loads(json.dumps(params))}
            continue
        have = merged[kind]["parameters"]
        if kind == "required_status_checks":
            have["required_status_checks"] = have.get("required_status_checks", []) + params.get(
                "required_status_checks", []
            )
        elif kind == "pull_request":
            count = max(have.get("required_approving_review_count", 0), params.get("required_approving_review_count", 0))
            have["required_approving_review_count"] = count
            if "allowed_merge_methods" in params:
                methods = have.get("allowed_merge_methods", params["allowed_merge_methods"])
                have["allowed_merge_methods"] = [m for m in methods if m in params["allowed_merge_methods"]]
    return list(merged.values())


def _read(gh, data: Rulesets, repo: str, effective: bool) -> dict | None:
    """The live ruleset as a body `normal_form` takes, or None when it does
    not exist.

    The effective reading carries rules only, so the fields it cannot know
    (target, enforcement, condition, bypass) are taken from the data and
    `compare` judges rules and checks alone.
    """
    if effective:
        body = desired(data, repo)
        body["rules"] = _merge_effective(gh.call("GET", f"repos/{repo}/rules/branches/main?per_page=100", paginate=True))
        return body
    found = _find(gh, data, repo)
    return None if found is None else gh.call("GET", f"repos/{repo}/rulesets/{found}")


def check(gh, data: Rulesets, repo: str, effective: bool = False) -> list[str]:
    """One line per difference between the data and the live rules of `repo`,
    each prefixed with the repository; empty when they match."""
    have = _read(gh, data, repo, effective)
    if have is None:
        return [f"{repo}: no branch ruleset named any of {list(data.names)}"]
    return [f"{repo}: {line}" for line in compare(normal_form(desired(data, repo)), normal_form(have))]


def _outside(data: Rulesets, repos: list[str]) -> str | None:
    for repo in repos:
        if repo not in data.checks:
            return f"{repo} is not a repository in rulesets/main.json: {sorted(data.checks)}"
    return None


def run_check(gh, data: Rulesets, repos: list[str] | None, effective: bool) -> int:
    """`ruleset-check`: exit 0 when every repository matches, 1 on a
    difference, 2 on a refusal."""
    repos = list(repos or data.checks)
    refusal = _outside(data, repos)
    if refusal:
        print(f"ruleset-check: {refusal}", file=sys.stderr)
        return 2
    for repo in repos:
        breaches = floor_breaches(desired(data, repo))
        if breaches:
            print(f"ruleset-check: the data for {repo} is below the floor: {'; '.join(breaches)}", file=sys.stderr)
            return 2
    code = 0
    try:
        for repo in repos:
            lines = check(gh, data, repo, effective)
            for line in lines or [f"{repo}: matches"]:
                print(line)
            code = 1 if lines else code
    except RulesetError as exc:
        print(f"ruleset-check: {exc}", file=sys.stderr)
        return 2
    return code


def run_apply(gh, data: Rulesets, repo: str) -> int:
    """`ruleset-apply`: PUT the data's body to the repository's ruleset, or
    POST it when there is none, then run the check and exit with its code."""
    refusal = _outside(data, [repo])
    if refusal:
        print(f"ruleset-apply: {refusal}", file=sys.stderr)
        return 2
    try:
        body = desired(data, repo)
        breaches = floor_breaches(body)
        if breaches:
            print(f"ruleset-apply: the data for {repo} is below the floor: {'; '.join(breaches)}", file=sys.stderr)
            return 2
        found = _find(gh, data, repo)
        if found is None:
            gh.call("POST", f"repos/{repo}/rulesets", body)
        else:
            gh.call("GET", f"repos/{repo}/rulesets/{found}")
            gh.call("PUT", f"repos/{repo}/rulesets/{found}", body)
    except RulesetError as exc:
        print(f"ruleset-apply: {exc}", file=sys.stderr)
        return 2
    return run_check(gh, data, [repo], False)
