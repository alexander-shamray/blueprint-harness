"""Open the one sync pull request a harness commit owes a target, and close the older ones (spec 5.3)."""

import json
import re
import subprocess
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from harness_sync.apply import CONFIG, MANIFEST, apply
from harness_sync.manifest import Manifest

HARNESS = "alexander-shamray/blueprint-harness"
PREFIX = "chore/harness-sync-"
# Exactly the branch name this module makes. A same-repository head that merely starts with the prefix may be a
# person's branch, so it is never closed, and its suffix is never read as a revision.
SYNC_HEAD = re.compile(r"chore/harness-sync-[0-9a-f]{7}")
# Where the harness checkout keeps main: origin's view first (sync.yml's checkout has both), then a local branch.
MAIN_REFS = ("refs/remotes/origin/main", "refs/heads/main")
# The sync is written by CI, not by a person or a session (spec 5.3); the commit gate demands no identity, so the
# Actions bot's own is used, and only for the sync's commits (`git -c`), never as the checkout's config.
IDENTITY = (
    "-c", "user.name=github-actions[bot]",
    "-c", "user.email=41898+github-actions[bot]@users.noreply.github.com",
)
# No session writes a sync, so it carries no session link: it names the workflow, and the run when one is given.
FOOTER = "Opened by the blueprint-harness sync workflow"
# One page of `gh pr list` is far more open pull requests than a target holds; the closure gate's page size is 100.
LIST_LIMIT = "200"


class SyncError(Exception):
    """The target checkout, git or gh is not in a state the sync can work from."""


class GhRunner(Protocol):
    def run(self, args: list[str]) -> str: ...


@dataclass(frozen=True)
class SyncOutcome:
    state: str  # "current" or "opened"
    pr: int | None
    superseded: list[int] = field(default_factory=list)
    reason: str = ""


class GhCli:
    """`gh` in the target checkout, so the repository is inferred from its origin unless one is named."""

    def __init__(self, cwd: Path, repo: str | None = None) -> None:
        self.cwd, self.repo = Path(cwd), repo

    def run(self, args: list[str]) -> str:
        argv = ["gh", *args, *(["--repo", self.repo] if self.repo else [])]
        done = subprocess.run(argv, cwd=self.cwd, capture_output=True, encoding="utf-8", check=False)
        if done.returncode != 0:
            raise SyncError(f"gh {' '.join(args[:2])} failed: {done.stderr.strip()}")
        return done.stdout


def _git(cwd: Path, *args: str, stdin: str | None = None) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, input=stdin, capture_output=True, encoding="utf-8", check=False)
    if done.returncode != 0:
        verb = next((a for a in args if not a.startswith("-") and "=" not in a), "")
        raise SyncError(f"git {verb} failed: {done.stderr.strip()}")
    return done.stdout


def _remote_tip(target: Path, branch: str) -> str | None:
    out = _git(target, "ls-remote", "origin", f"refs/heads/{branch}").split()
    return out[0] if out else None


def _push(target: Path, branch: str, expected: str | None) -> None:
    """Publish HEAD to the sync branch only, leased on what origin held: an empty lease means it must not exist."""
    lease = f"--force-with-lease=refs/heads/{branch}:{expected or ''}"
    _git(target, "push", "-q", lease, "origin", f"HEAD:refs/heads/{branch}")


def _has_trailer(target: Path, message: str, wanted: str) -> bool:
    # git reads the trailer block, as the commit gate does, so a `PR:` line quoted in the body does not count.
    return wanted in _git(target, "interpret-trailers", "--parse", stdin=message).splitlines()


def _add_trailer(target: Path, branch: str, number: int, expected: str) -> None:
    """git-trailer-pr.sh's shape: `PR: #<n>` appended to the trailer block, published under a lease."""
    _git(target, *IDENTITY, "commit", "-q", "--amend", "--no-edit", "--trailer", f"PR: #{number}")
    _push(target, branch, expected)


def _restore(target: Path) -> None:
    """The tree was clean before apply, so everything not in HEAD is apply's to take back."""
    _git(target, "reset", "-q", "--hard", "HEAD")
    _git(target, "clean", "-q", "-fd")


def _short(sha: str) -> str:
    return sha[:7]


def commit_message(harness_commit: str, written: list[str], deleted: list[str], unchanged: int) -> str:
    subject = f"chore(harness): sync to blueprint-harness {_short(harness_commit)}"
    body = textwrap.fill(
        f"Takes the payload at blueprint-harness {harness_commit}: {len(written)} managed path(s) written, "
        f"{len(deleted)} deleted, {unchanged} unchanged, and `.harness/manifest.json` records the commit and "
        "every managed file's hash. Written by the harness repository's sync workflow (spec 5.3); the managed "
        "files were reviewed there.",
        width=80, break_long_words=False, break_on_hyphens=False,
    )
    return f"{subject}\n\n{body}\n"


def pr_body(harness_commit: str, written: list[str], deleted: list[str], run_url: str | None = None) -> str:
    link = f"https://github.com/{HARNESS}/commit/{harness_commit}"
    opening = textwrap.fill(
        f"A sync from the harness repository: this pull request rewrites the managed paths to the payload "
        f"released at blueprint-harness [`{_short(harness_commit)}`]({link}), re-renders `.claude/settings.json` "
        "where it changed, and records the commit and every managed file's hash in `.harness/manifest.json` "
        "(shared-harness spec 5.3). The sync workflow wrote it; the managed files were reviewed in the harness "
        "repository, so the review here is of what is specific to this target, and what a review of "
        "this branch reads is `sync_pr.py review-diff`, which names the managed paths and leaves out their content.",
        width=80, break_long_words=False, break_on_hyphens=False,
    )
    touch = ", ".join(f"`{rel}`" for rel in sorted({*written, *deleted, MANIFEST}))

    def listing(paths: list[str]) -> str:
        return "\n".join(f"- `{rel}`" for rel in paths) if paths else "None."

    return (
        f"{opening}\n\n"
        "| | |\n|---|---|\n| Class | D |\n"
        f"| Touch set | {touch} |\n"
        "| Closes | — |\n\n"
        "## What changed\n\n"
        f"**Written ({len(written)})**\n\n{listing(written)}\n\n"
        f"**Deleted ({len(deleted)})**\n\n{listing(deleted)}\n\n"
        f"{FOOTER}{f', in run {run_url}' if run_url else ''}.\n"
    )


def _open_sync_prs(gh: GhRunner) -> list[tuple[int, str]]:
    raw = json.loads(gh.run(["pr", "list", "--state", "open", "--limit", LIST_LIMIT,
                             "--json", "number,headRefName,isCrossRepository"]))
    # A fork can name a branch anything, so only this repository's own branches are sync pull requests, and only
    # those named exactly as this module names them.
    return sorted(
        (pr["number"], pr["headRefName"])
        for pr in raw
        if not pr["isCrossRepository"] and SYNC_HEAD.fullmatch(pr["headRefName"])
    )


def _close(gh: GhRunner, numbers: list[int], note: str) -> list[int]:
    # The branch goes with the pull request: a closed sync is never reopened, a newer one replaces it.
    for number in numbers:
        gh.run(["pr", "close", str(number), "--comment", note, "--delete-branch"])
    return sorted(numbers)


def _supersede(gh: GhRunner, others: list[int], number: int, harness_commit: str) -> list[int]:
    note = (f"Superseded by #{number}, the sync to blueprint-harness {harness_commit} "
            f"(https://github.com/{HARNESS}/commit/{harness_commit}).")
    return _close(gh, others, note)


def _resolve(harness: Path, rev: str) -> str | None:
    # `--end-of-options`: a revision is never read as an option, whatever it starts with.
    done = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "--end-of-options", f"{rev}^{{commit}}"],
                          cwd=harness, capture_output=True, encoding="utf-8", check=False)
    return done.stdout.strip() if done.returncode == 0 else None


def _is_ancestor(harness: Path, older: str, newer: str) -> bool:
    done = subprocess.run(["git", "merge-base", "--is-ancestor", older, newer],
                          cwd=harness, capture_output=True, encoding="utf-8", check=False)
    if done.returncode not in (0, 1):
        raise SyncError(f"cannot compare {older} with {newer} in the harness checkout: {done.stderr.strip()}")
    return done.returncode == 0


def _base_commit(target: Path) -> str | None:
    """The commit the base branch's manifest names, read from HEAD so a link in the tree is never followed."""
    done = subprocess.run(["git", "show", f"HEAD:{MANIFEST}"], cwd=target, capture_output=True,
                          encoding="utf-8", check=False)
    if done.returncode != 0:
        return None
    try:
        commit = json.loads(done.stdout).get("harness_commit")
    except (ValueError, AttributeError):
        return None  # apply refuses a malformed manifest itself, with the reason
    return commit if isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit) else None


def _check_forward(harness: Path, target: Path, harness_commit: str) -> None:
    """A sync only moves forward: the drift gate's ancestry test, applied before anything opens rather than after."""
    if _resolve(harness, harness_commit) != harness_commit:
        raise SyncError(f"harness commit {harness_commit} is not in the harness checkout at {harness}")
    base = _base_commit(target)
    if base is not None and not _is_ancestor(harness, base, harness_commit):
        raise SyncError(
            f"the target's manifest names blueprint-harness {base}, which is not an ancestor of {harness_commit}; "
            "a sync only moves forward, so this run is older than the sync the target already holds"
        )


def _main(harness: Path) -> str:
    for ref in MAIN_REFS:
        if (sha := _resolve(harness, ref)) is not None:
            return sha
    raise SyncError(f"the harness checkout at {harness} has no main ({' or '.join(MAIN_REFS)}) to order syncs by")


def _check_no_newer(harness: Path, harness_commit: str, open_prs: list[tuple[int, str]]) -> None:
    """A run carrying an older commit than an open sync must not close that sync in its own favour."""
    main = _main(harness) if open_prs else ""
    for number, head in open_prs:
        theirs = _resolve(harness, head[len(PREFIX):])
        # Newer means released: a descendant on main. A suffix naming nothing here, or a commit off main (a short
        # sha that happens to match a feature branch's commit, a branch or tag of that name), is stale.
        if (theirs and theirs != harness_commit and _is_ancestor(harness, harness_commit, theirs)
                and _is_ancestor(harness, theirs, main)):
            raise SyncError(
                f"#{number} already syncs blueprint-harness {theirs}, which is newer than {harness_commit}; "
                "this run is older and opens nothing"
            )


def _ensure_trailer(target: Path, branch: str, number: int) -> None:
    """A rerun after a failure between `gh pr create` and the trailer push finishes that push."""
    remote = _remote_tip(target, branch)
    if remote is None:
        raise SyncError(f"#{number} is open for {branch} but origin has no such branch")
    _git(target, "fetch", "-q", "origin", f"+refs/heads/{branch}:refs/remotes/origin/{branch}")
    if _has_trailer(target, _git(target, "show", "-s", "--format=%B", remote), f"PR: #{number}"):
        return
    _git(target, "checkout", "-q", "-B", branch, remote)
    _add_trailer(target, branch, number, remote)


def open_sync_pr(
    target_checkout: Path,
    harness_commit: str,
    gh: GhRunner,
    *,
    payload: Path | None = None,
    harness: Path | None = None,
    run_url: str | None = None,
) -> SyncOutcome:
    """`harness` is the checkout whose history judges forward and older; by default the one holding `payload`."""
    target = Path(target_checkout)
    payload = Path(payload) if payload is not None else Path(__file__).resolve().parent.parent / "payload"
    harness = Path(harness) if harness is not None else payload.parent
    if not re.fullmatch(r"[0-9a-f]{40}", harness_commit):
        raise SyncError(f"harness commit must be 40 hex characters, got {harness_commit!r}")
    if not (target / CONFIG).is_file():
        # Onboarding is the target's own change (its config); until then a sync has nothing to render from.
        return SyncOutcome("current", None, [], f"not onboarded (no {CONFIG}); nothing to sync")
    if _git(target, "status", "--porcelain", "--untracked-files=all"):
        raise SyncError("the target checkout is not clean, so what apply changed could not be told apart")
    base = _git(target, "branch", "--show-current").strip()
    if not base:
        raise SyncError("the target checkout is on a detached HEAD; check out the branch the sync is for")
    _check_forward(harness, target, harness_commit)

    # 1-2. Apply, then decide: a manifest whose only change is the commit it names is nothing to review, but a
    # first manifest is the drift gate's whole input and is.
    had_manifest = (target / MANIFEST).is_file()
    try:
        result = apply(payload, target, harness_commit)
        open_prs = _open_sync_prs(gh)
        _check_no_newer(harness, harness_commit, open_prs)
    except BaseException:
        # Nothing is committed before the branch exists, so a failure up to here hands the checkout back as found.
        _restore(target)
        raise
    current = had_manifest and not result.written and not result.deleted
    branch = f"{PREFIX}{_short(harness_commit)}"

    if current:
        _restore(target)
        # Every open sync is stale now: merging one would move the target off a payload it already matches.
        note = (f"blueprint-harness {_short(harness_commit)} leaves this target current; this sync is stale "
                f"(https://github.com/{HARNESS}/commit/{harness_commit}).")
        stale = _close(gh, [number for number, _ in open_prs], note)
        # Read after apply has vetted the manifest's path, and after the restore has put the base's copy back.
        old = Manifest.read(target / MANIFEST)
        at = _short(old.harness_commit) if old else "none"
        return SyncOutcome("current", None, stale, f"current at its manifest's commit {at}; nothing to sync")

    others = [number for number, head in open_prs if head != branch]
    mine = [number for number, head in open_prs if head == branch]
    if mine:
        # A rerun for the same commit: the pull request exists, so finish its trailer and supersede, nothing more.
        _restore(target)
        _ensure_trailer(target, branch, mine[0])
        _git(target, "checkout", "-q", base)
        return SyncOutcome("opened", mine[0], _supersede(gh, others, mine[0], harness_commit))

    # 3-5. Branch from the checkout's HEAD, commit exactly what apply changed, publish.
    _git(target, "checkout", "-q", "-B", branch)
    _git(target, "add", "-f", "--", *result.written, MANIFEST)
    if result.deleted:
        _git(target, "rm", "-q", "--cached", "--ignore-unmatch", "--", *result.deleted)
    message = commit_message(harness_commit, result.written, result.deleted, len(result.unchanged))
    _git(target, *IDENTITY, "commit", "-q", "-F", "-", stdin=message)
    _push(target, branch, _remote_tip(target, branch))  # a branch left by a run that died before create is ours

    # 6-7. Open the pull request, then name it in the commit: the number exists only once the pull request does.
    subject = message.split("\n", 1)[0]
    url = gh.run(["pr", "create", "--base", base, "--head", branch, "--title", subject,
                  "--body", pr_body(harness_commit, result.written, result.deleted, run_url)])
    found = re.search(r"/pull/(\d+)\s*$", url.strip())
    if found is None:
        raise SyncError(f"gh pr create printed no pull request URL: {url.strip()!r}")
    number = int(found.group(1))
    _add_trailer(target, branch, number, _git(target, "rev-parse", "HEAD").strip())
    _git(target, "checkout", "-q", base)

    # 8. Only now is there a newer pull request for the older ones to point at.
    return SyncOutcome("opened", number, _supersede(gh, others, number, harness_commit))
