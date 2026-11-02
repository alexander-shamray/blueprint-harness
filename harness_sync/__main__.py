"""Command line for the harness sync: `py -3.12 -m harness_sync apply|check|open-pr ...`."""

import argparse
import importlib.util
import sys
from pathlib import Path

from harness_sync.apply import ApplyError, apply
from harness_sync.config import ConfigError
from harness_sync.pr import GhCli, SyncError, open_sync_pr
from harness_sync import render
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
    return parser


def _open_pr(args: argparse.Namespace) -> int:
    outcome = open_sync_pr(args.target, args.commit, GhCli(args.target, args.repo), payload=args.payload)
    if outcome.state == "current":
        print(f"harness_sync: {args.repo or args.target} is {outcome.reason}")
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
