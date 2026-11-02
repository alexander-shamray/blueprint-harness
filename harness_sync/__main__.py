"""Command line for the harness sync: `py -3.12 -m harness_sync apply ...`."""

import argparse
import sys
from pathlib import Path

from harness_sync.apply import ApplyError, apply
from harness_sync.config import ConfigError
from harness_sync.render import RenderError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness_sync")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("apply", help="copy the payload into a target and record its manifest")
    cmd.add_argument("--payload", type=Path, required=True)
    cmd.add_argument("--target", type=Path, required=True)
    cmd.add_argument("--commit", required=True, help="40-hex harness commit the payload was taken from")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = apply(args.payload, args.target, args.commit)
    except (ApplyError, ConfigError, RenderError) as exc:
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
