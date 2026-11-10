"""Command line for the harness sync: `py -3.12 -m harness_sync apply|check|open-pr|legs ...`."""

import argparse
import importlib.util
import sys
from pathlib import Path

from harness_sync.apply import ApplyError, apply
from harness_sync.config import ConfigError
from harness_sync.legs import should_test
from harness_sync.pr import GhCli, SyncError, open_sync_pr
from harness_sync import render
from harness_sync.ruleset import DATA_PATH, GhApi, RulesetError, load as load_rulesets, run_apply, run_check
from harness_sync.render import RenderError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness_sync")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("apply", help="copy the payload into a target and record its manifest")
    cmd.add_argument("--payload", type=Path, required=True)
    cmd.add_argument("--target", type=Path, required=True)
    cmd.add_argument("--commit", required=True, help="40-hex harness commit the payload was taken from")
    chk = sub.add_parser("check", help="run the drift gate against a target")
    chk.add_argument("--target", type=Path, required=True)
    chk.add_argument("--payload", type=Path, help="the payload/ at the manifest's commit, to compare the manifest with")
    opr = sub.add_parser("open-pr", help="open the sync pull request a harness commit owes a target checkout")
    opr.add_argument("--payload", type=Path, required=True)
    opr.add_argument("--target", type=Path, required=True, help="a clean checkout of the target, on its base branch")
    opr.add_argument("--commit", required=True, help="40-hex harness commit the payload was taken from")
    opr.add_argument("--repo", help="owner/name for gh; inferred from the checkout's origin when omitted")
    opr.add_argument("--harness", type=Path, help="the harness checkout whose history orders commits; default: "
                     "the directory holding --payload")
    opr.add_argument("--run-url", help="the workflow run that opens the pull request, linked from its body")
    leg = sub.add_parser("legs", help="print whether payload-suites tests on its windows and macos legs")
    leg.add_argument("--event", required=True, help="the workflow event name")
    exits = "exit 0: matches; 1: differs, one line per difference; 2: refused (repository outside the data, data below the floor, two matching rulesets) or a gh call failed"
    rck = sub.add_parser("ruleset-check", help="compare the live main ruleset of each repository with rulesets/main.json", epilog=exits)
    rck.add_argument("--effective", action="store_true", help="read the rules in force on main (any token; no bypass list) and compare rules and checks only")
    rck.add_argument("repos", nargs="*", metavar="repo", help="owner/name keys of the data's checks; all when omitted")
    rap = sub.add_parser("ruleset-apply", help="PUT rulesets/main.json to a repository's main ruleset, or POST it when there is none, then check it", epilog=exits)
    rap.add_argument("repo", help="owner/name, a key of the data's checks")
    return parser


def _rulesets(args: argparse.Namespace) -> int:
    try:
        data = load_rulesets(DATA_PATH)
    except RulesetError as exc:
        print(f"harness_sync: {exc}", file=sys.stderr)
        return 2
    if args.command == "ruleset-check":
        return run_check(GhApi(), data, args.repos, args.effective)
    return run_apply(GhApi(), data, args.repo)


def _open_pr(args: argparse.Namespace) -> int:
    outcome = open_sync_pr(args.target, args.commit, GhCli(args.target, args.repo), payload=args.payload,
                           harness=args.harness, run_url=args.run_url)
    if outcome.state == "current":
        stale = "".join(f"; closed stale #{n}" for n in outcome.superseded)
        print(f"harness_sync: {args.repo or args.target} is {outcome.reason}{stale}")
        return 0
    if outcome.state == "held":
        stale = "".join(f"; superseded #{n}" for n in outcome.superseded)
        print(f"harness_sync: {args.repo or args.target}: {outcome.reason}{stale}")
        return 0
    superseded = ", ".join(f"#{n}" for n in outcome.superseded) or "none"
    print(f"harness_sync: sync pull request #{outcome.pr} open for {args.commit[:7]}; superseded {superseded}")
    return 0


def _load_gate():
    """The gate ships in the payload and imports nothing from here, so it is loaded by path, not by import."""
    path = Path(__file__).resolve().parent.parent / "payload/.github/harness-drift/drift_gate.py"
    spec = importlib.util.spec_from_file_location("drift_gate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "check":
        # The harness's own renderer, never the target's: check must not execute code a target controls.
        argv = ["--root", str(args.target)] + (["--payload", str(args.payload)] if args.payload else [])
        return _load_gate().main(argv, render_module=render)
    if args.command == "legs":
        print(f"test={str(should_test(args.event, Path.cwd())).lower()}")
        return 0
    if args.command in ("ruleset-check", "ruleset-apply"):
        return _rulesets(args)
    try:
        if args.command == "open-pr":
            return _open_pr(args)
        result = apply(args.payload, args.target, args.commit)
    except (ApplyError, ConfigError, RenderError, SyncError) as exc:
        print(f"harness_sync: {exc}", file=sys.stderr)
        return 1
    print(f"written {len(result.written)}, deleted {len(result.deleted)}, unchanged {len(result.unchanged)}")
    for rel in result.written:
        print(f"  written  {rel}")
    for rel in result.deleted:
        print(f"  deleted  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
