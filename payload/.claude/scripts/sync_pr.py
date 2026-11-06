"""A sync pull request: `list`, `verify <n>`, `review-diff <n> <out>` and `local-suites`.

A branch name proves nothing, so `verify` repeats CI's drift gate checks before a sync is reviewed or launched. What
it reads from GitHub is data, and a read it could not complete fails the check (docs/harness-boundaries.md).
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from dispatch_board import path_which

# harness_sync/pr.py writes these; harness_sync/tests/test_sync_pr_constants.py holds them equal.
HARNESS_REPO = "alexander-shamray/blueprint-harness"
SYNC_HEAD = re.compile(r"chore/harness-sync-[0-9a-f]{7}")
FOOTER = "Opened by the blueprint-harness sync workflow"
FOOTER_LINE = re.compile(re.escape(FOOTER) + r"(?:, in run https://\S+)?\.")

OID = re.compile(r"[0-9a-f]{40}")
HASH = re.compile(r"[0-9a-f]{64}")
MANIFEST = ".harness/manifest.json"
CONFIG = ".harness/config.json"
SETTINGS = ".claude/settings.json"
REVIEW_DIR = "artifacts/review"
ROOT = Path(__file__).resolve().parents[2]
GH_TIMEOUT = 60
GIT_TIMEOUT = 120
LIST_LIMIT = "200"
CITATIONS = 50
TEXT_CAP = 300


class Refusal(Exception):
    """A read that did not complete, or an argument refused; the message is the one line printed."""


def run(argv, cwd=None, timeout=GH_TIMEOUT):
    """The one runner every gh and git call goes through; a suite swaps it. Returns (code, stdout, stderr)."""
    exe = path_which(argv[0])
    if not exe:
        raise Refusal(f"no {argv[0]} on PATH")
    try:
        done = subprocess.run([exe, *argv[1:]], cwd=cwd or ROOT, capture_output=True, encoding="utf-8",
                              errors="replace", timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise Refusal(f"{argv[0]} {' '.join(argv[1:3])} took over {timeout} s") from None
    except OSError as error:
        raise Refusal(f"could not start {argv[0]}: {error}") from None
    return done.returncode, done.stdout, done.stderr


def _line(text, cap=200):
    return " ".join(text.split())[:cap]


def read(argv, timeout=GH_TIMEOUT):
    code, out, err = run(argv, timeout=timeout)
    if code:
        raise Refusal(f"{argv[0]} {' '.join(argv[1:3])} failed: {_line(err or out)}")
    return out


def read_json(argv):
    try:
        return json.loads(read(argv))
    except ValueError:
        raise Refusal(f"{argv[0]} {' '.join(argv[1:3])} returned no JSON") from None


def _glob_regex(glob):
    out, i = [], 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("".join(out))


def glob_match(glob, path):
    """Copy of harness_sync.apply's matcher; the payload cannot import it, and a harness test holds them equal."""
    return _glob_regex(glob).fullmatch(path) is not None


def is_sync_body(body):
    """The body's last line is the footer pr_body writes, with or without a run link; a CRLF body counts."""
    lines = body.replace("\r\n", "\n").rstrip().split("\n")
    return FOOTER_LINE.fullmatch(lines[-1]) is not None


def sync_rows():
    """Open same-repository pull requests into main from a sync branch with the sync footer, oldest first."""
    raw = read_json(["gh", "pr", "list", "--state", "open", "--base", "main", "--limit", LIST_LIMIT, "--json",
                     "number,headRefName,headRefOid,baseRefName,isCrossRepository,body"])
    if not isinstance(raw, list):
        raise Refusal("gh pr list returned no list")
    rows = []
    for pr in raw:
        if not isinstance(pr, dict):
            continue
        number, head, oid, body = (pr.get(k) for k in ("number", "headRefName", "headRefOid", "body"))
        if (isinstance(number, int) and not isinstance(number, bool) and isinstance(head, str)
                and isinstance(oid, str) and isinstance(body, str) and pr.get("isCrossRepository") is False
                and pr.get("baseRefName") == "main" and SYNC_HEAD.fullmatch(head) and OID.fullmatch(oid)
                and is_sync_body(body)):
            rows.append({"number": number, "head": head, "oid": oid})
    return sorted(rows, key=lambda r: r["number"])


def _plain_path(path):
    """A manifest path is data: a relative POSIX path of plain segments, never one git or a URL could read as more."""
    if not isinstance(path, str) or not path or path.startswith(("/", "-")) or path.endswith("/"):
        return False
    if "\\" in path or ":" in path or any(ord(c) < 32 or ord(c) == 127 for c in path):
        return False
    return not any(seg in ("", ".", "..") or seg.lower() == ".git" for seg in path.split("/"))


def parse_manifest(text, where):
    try:
        raw = json.loads(text)
    except ValueError:
        raise Refusal(f"{where}: {MANIFEST} is not JSON") from None
    if not isinstance(raw, dict) or set(raw) != {"harness_commit", "files"}:
        raise Refusal(f"{where}: {MANIFEST} must be an object with exactly harness_commit and files")
    commit, files = raw["harness_commit"], raw["files"]
    if not isinstance(commit, str) or not OID.fullmatch(commit):
        raise Refusal(f"{where}: harness_commit must be 40 lowercase hex characters")
    if not isinstance(files, dict):
        raise Refusal(f"{where}: {MANIFEST} files must be an object")
    for path, digest in files.items():
        if not _plain_path(path) or path == CONFIG:
            raise Refusal(f"{where}: manifest path {_line(repr(path), 80)} is not a plain relative path to a managed file")
        if not isinstance(digest, str) or not HASH.fullmatch(digest):
            raise Refusal(f"{where}: manifest path {path} has no 64-hex hash")
    return commit, set(files)


def manifest_at(rev, where):
    return parse_manifest(read(["git", "show", f"{rev}:{MANIFEST}"]), where)


def fetch_head(number):
    """The listed row's head, fetched and confirmed to be the listed oid; every later read is by that oid."""
    row = next((r for r in sync_rows() if r["number"] == number), None)
    if row is None:
        raise Refusal(f"#{number} is not a sync pull request: an open, same-repository pull request into main, "
                      f"from a {SYNC_HEAD.pattern} branch, whose body ends with the sync footer")
    read(["git", "fetch", "-q", "--no-tags", "origin", f"refs/heads/{row['head']}"], GIT_TIMEOUT)
    fetched = read(["git", "rev-parse", "--verify", "--end-of-options", "FETCH_HEAD^{commit}"]).strip()
    if fetched != row["oid"]:
        raise Refusal(f"#{number}: the fetched head {fetched} is not the listed oid {row['oid']}; it moved")
    read(["git", "fetch", "-q", "--no-tags", "origin", "+refs/heads/main:refs/remotes/origin/main"], GIT_TIMEOUT)
    return row["oid"]


def base_of(oid):
    """The commit the pull request was cut from, and the manifest it held there: (None, set()) before a first sync."""
    base = read(["git", "merge-base", "origin/main", oid]).strip()
    if not OID.fullmatch(base):
        raise Refusal("git merge-base returned no commit")
    if not read(["git", "ls-tree", "-z", base, "--", MANIFEST]):
        return base, None, set()
    commit, paths = manifest_at(base, "origin/main")
    return base, commit, paths


def changed_paths(base, oid):
    """{path: status} the head changes against its base, by name and without renames."""
    tokens = read(["git", "diff", "--name-status", "-z", "--no-renames", base, oid]).split("\0")
    return {tokens[i + 1]: tokens[i] for i in range(0, len(tokens) - 1, 2)}


def head_blobs(oid):
    found = {}
    for entry in read(["git", "ls-tree", "-r", "-z", oid], GIT_TIMEOUT).split("\0"):
        meta, _, path = entry.partition("\t")
        parts = meta.split()
        if len(parts) == 3 and parts[1] == "blob":
            found[path] = (parts[0], parts[2])
    return found


def payload_blobs(commit):
    tree = read_json(["gh", "api", f"repos/{HARNESS_REPO}/git/trees/{commit}?recursive=1"])
    if not isinstance(tree, dict) or not isinstance(tree.get("tree"), list):
        raise Refusal("the payload tree has no entries")
    if tree.get("truncated") is not False:
        raise Refusal(f"the payload tree at {commit} is truncated (or does not say it is not), so it cannot be compared")
    found = {}
    for entry in tree["tree"]:
        path = entry.get("path") if isinstance(entry, dict) else None
        if isinstance(path, str) and path.startswith("payload/") and entry.get("type") == "blob":
            found[path[len("payload/"):]] = (entry.get("mode"), entry.get("sha"))
    return found


def on_harness_main(commit):
    compare = read_json(["gh", "api", f"repos/{HARNESS_REPO}/compare/main...{commit}"])
    status = compare.get("status") if isinstance(compare, dict) else None
    if status not in ("behind", "identical"):
        raise Refusal(f"harness_commit {commit} is not on the harness's main (compare says {status!r})")


def prove(number):
    """(failures, head): one line per failure; none means the pull request is what the harness released.

    `head` is the oid that was fetched and judged, so a caller that goes on to read it reads what was proved.
    """
    try:
        oid = fetch_head(number)
        commit, paths = manifest_at(oid, f"#{number}")
    except Refusal as error:
        return [str(error)], None
    head = {"oid": oid, "commit": commit, "paths": paths}
    failures = []
    try:
        on_harness_main(commit)
    except Refusal as error:
        failures.append(f"cannot prove harness_commit is on the harness's main: {error}")
    payload = None  # None while unread, so no deletion below can be confirmed
    try:
        payload, in_head = payload_blobs(commit), head_blobs(oid)
        for path in sorted(paths - {SETTINGS}):
            if path not in payload:
                failures.append(f"{path}: not in the payload at {commit}")
            elif path not in in_head:
                failures.append(f"{path}: in the manifest but not on the head")
            elif in_head[path] != payload[path]:
                failures.append(f"{path} differs from the payload at {commit} (head {in_head[path][1]}, "
                                f"payload {payload[path][1]})")
    except Refusal as error:
        payload = None
        failures.append(f"cannot compare the managed files with the payload tree: {error}")
    try:
        base, old_commit, old = base_of(oid)
        changed = changed_paths(base, oid)
    except Refusal as error:
        failures.append(f"cannot read what the head changes: {error}")
        return failures, head
    head.update(base=base, old_commit=old_commit, old=old)
    if old_commit is not None:
        try:
            compare = read_json(["gh", "api", f"repos/{HARNESS_REPO}/compare/{old_commit}...{commit}"])
            status = compare.get("status") if isinstance(compare, dict) else None
            if status not in ("ahead", "identical"):
                failures.append(f"harness_commit {commit} is older than the base's {old_commit} "
                                f"(compare says {status!r}); a sync only moves forward")
        except Refusal as error:
            failures.append(f"cannot prove the sync moves forward from {old_commit}: {error}")
    for path, status in sorted(changed.items()):
        if path == CONFIG:
            failures.append(f"{CONFIG} is edited; the sync never touches the target's own config")
        elif path in paths or path == MANIFEST:
            continue
        elif path in old:
            if status != "D":
                failures.append(f"{path} left the manifest but was changed, not deleted")
            elif payload is None:
                failures.append(f"{path} was deleted and the payload tree could not be read to confirm it is gone")
            elif path in payload:
                failures.append(f"{path} was deleted and dropped from the manifest, but the payload at {commit} "
                                "still has it")
        else:
            failures.append(f"{path} is changed but is outside the manifest")
    return failures, head


def verify(number):
    """(failures, harness commit) of `prove`."""
    failures, head = prove(number)
    return failures, head["commit"] if head else None


def _citations(oid, path, managed):
    """`file:line: text` for each line of a tracked file outside the manifest that names `path`."""
    code, out, err = run(["git", "grep", "-z", "-n", "-I", "-F", "-e", path, oid], timeout=GIT_TIMEOUT)
    if code not in (0, 1):
        raise Refusal(f"git grep failed: {_line(err)}")
    found = []
    for record in out.split("\n"):
        parts = record.split("\0", 2)
        if len(parts) != 3 or not parts[1].isdigit():
            continue
        name = parts[0][len(oid) + 1:] if parts[0].startswith(f"{oid}:") else parts[0]
        if name not in managed and name != MANIFEST:
            found.append(f"{name}:{parts[1]}: {_line(parts[2], TEXT_CAP)}")
    return found


def review_text(number, head):
    """The review input for the head `prove` judged; `head` is what it returned, never a second fetch."""
    oid, commit, paths = head["oid"], head["commit"], head["paths"]
    base, old_commit, old = head["base"], head["old_commit"], head["old"]
    managed = paths | old | {MANIFEST}
    changed = {p: s for p, s in changed_paths(base, oid).items() if p in managed}
    written = sorted(p for p, s in changed.items() if s != "D")
    deleted = sorted(p for p, s in changed.items() if s == "D")
    lines = [f"# Sync pull request #{number}, head {oid}", "", "## Harness commits", ""]
    if old_commit is None:
        lines.append(f"From: none (a first sync)\nTo:   {commit}")
    else:
        compare = read_json(["gh", "api", f"repos/{HARNESS_REPO}/compare/{old_commit}...{commit}"])
        commits = compare.get("commits") if isinstance(compare, dict) else None
        if not isinstance(commits, list):
            raise Refusal("the harness compare returned no commits")
        lines += [f"From: {old_commit}", f"To:   {commit}", "", "Subjects between them:"]
        for entry in commits:
            body = entry.get("commit") if isinstance(entry, dict) else None
            message = body.get("message") if isinstance(body, dict) else None
            subject = message.split("\n", 1)[0] if isinstance(message, str) else "(no subject)"
            lines.append(f"- {str(entry.get('sha', ''))[:7]} {_line(subject, TEXT_CAP)}")
    lines += ["", f"## Managed paths written ({len(written)}), by name only", ""] + [f"- {p}" for p in written]
    lines += ["", f"## Managed paths deleted ({len(deleted)})", ""]
    for path in deleted:
        lines.append(f"- {path}")
        cites = _citations(oid, path, paths) if path != MANIFEST else []
        lines += [f"    {c}" for c in cites[:CITATIONS]]
        if len(cites) > CITATIONS:
            lines.append(f"    ... and {len(cites) - CITATIONS} more lines name it")
    lines += ["", f"## Diff of {SETTINGS}", ""]
    lines.append(read(["git", "diff", "--no-color", "--no-ext-diff", base, oid, "--", SETTINGS]).rstrip("\n")
                 or "(unchanged)")
    return "\n".join(lines) + "\n"


def review_target(raw):
    """The file review-diff may write: a .diff directly under artifacts/review, in this checkout."""
    path = Path(raw)
    path = path if path.is_absolute() else ROOT / path
    allowed = (ROOT / REVIEW_DIR).resolve()
    if path.suffix != ".diff" or path.resolve().parent != allowed:
        raise Refusal(f"review-diff writes only a .diff file directly under {REVIEW_DIR}/, not {raw}")
    return path


def local_suites():
    """Target-local suites to run from the checkout: tracked test_*.py files `local` matches, minus payload/."""
    try:
        config = json.loads((ROOT / CONFIG).read_text(encoding="utf-8"))
        globs = config.get("local", [])
        if not isinstance(globs, list) or not all(isinstance(g, str) for g in globs):
            raise ValueError
    except (OSError, ValueError, AttributeError):
        raise Refusal(f"cannot read the `local` globs of {CONFIG}") from None
    found = []
    for path in read(["git", "ls-files", "-z"]).split("\0"):
        name = path.rsplit("/", 1)[-1]
        # The harness's own payload suites need a rendered root; CI runs them there, and a harness sync takes this.
        if (re.fullmatch(r"test_[^/]*\.py", name) and not path.lower().startswith("payload/")
                and any(glob_match(g.lower(), path.lower()) for g in globs)):
            found.append(path)
    return sorted(found)


def _number(text):
    if not re.fullmatch(r"[1-9][0-9]{0,8}", text):
        raise argparse.ArgumentTypeError(f"{text!r} is not a pull request number")
    return int(text)


def _parser():
    parser = argparse.ArgumentParser(prog="sync_pr.py", description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("verify").add_argument("number", type=_number)
    review = sub.add_parser("review-diff")
    review.add_argument("number", type=_number)
    review.add_argument("out")
    sub.add_parser("local-suites")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)  # a bad argument exits 2 with nothing read
    try:
        if args.command == "list":
            rows = sync_rows()
            print(json.dumps({"take": rows[-1] if rows else None, "rest": rows[:-1]}))
        elif args.command == "verify":
            failures, commit = verify(args.number)
            if failures:
                print("\n".join(failures))
                return 1
            print(f"verified {args.number} {commit}")
        elif args.command == "review-diff":
            target = review_target(args.out)
            failures, head = prove(args.number)
            if failures:
                print("\n".join(failures))
                return 1
            try:
                text = review_text(args.number, head)
            except Refusal as error:
                print(error, file=sys.stderr)
                return 1
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
            print(args.out)
        else:
            print("\n".join(local_suites()))
    except Refusal as error:
        print(f"sync_pr.py: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
