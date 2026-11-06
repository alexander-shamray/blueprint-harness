#!/usr/bin/env bash
# Remove the /branch worktree a run forked under .claude/worktrees/, without
# -f, once no code-index refresh holds it. A prefix grant on `git worktree
# remove` also buys the `-f` that discards what git's refusal protects; here the
# command is fixed and both arguments shape-checked, so no flag can arrive.
#
# Registration is not ownership: a path alone would remove any clean linked
# worktree under the directory, another run's included. So the caller names the
# branch it forked too, and the worktree at that path must hold it, the pair
# git-worktree-fork.sh wrote. A caller that already knows another run's path
# and branch together still passes; /ship passes the branch it created.
set -euo pipefail
[ "$#" -eq 2 ] ||
  { echo "usage: git-worktree-remove.sh <path> <branch>" >&2; exit 2; }
path="$1"
branch="$2"
[[ "$path" =~ ^\.claude/worktrees/[A-Za-z0-9][A-Za-z0-9._-]*$ ]] ||
  { echo "path must be .claude/worktrees/<name>" >&2; exit 2; }
# Admits `()`, which the helpers that make a name do not: `.claude/scripts` is
# common to every target, and one may still hold a branch cut with a scope, which
# removing must not wait on a rename for.
[[ "$branch" =~ ^[A-Za-z0-9][A-Za-z0-9._/()-]*$ ]] && [[ "$branch" != *..* ]] ||
  { echo "not a branch name this helper will take: $branch" >&2; exit 2; }
# Folded, as git-rebase-onto-main.sh folds it: a case-insensitive host's `Main`
# is `main`'s ref.
[ "$(printf %s "$branch" | tr '[:upper:]' '[:lower:]')" != main ] ||
  { echo "main is never a forked branch: $branch" >&2; exit 2; }
git rev-parse --git-dir >/dev/null 2>&1 ||
  { echo "not in a git repository" >&2; exit 2; }
[ -z "$(git rev-parse --show-prefix)" ] ||
  { echo "run from the checkout root" >&2; exit 2; }
[ "$(git rev-parse --git-dir)" = "$(git rev-parse --git-common-dir)" ] ||
  { echo "run from the main checkout, not a linked worktree" >&2; exit 2; }
[ -d "$path" ] || { echo "not an existing directory: $path" >&2; exit 3; }
# Asked of git, because `git worktree list` paths are not comparable with the
# shell's under MSYS. A plain directory answers with this checkout's own git
# directory, found by walking up, and so reads as no linked worktree.
common_here=$(git rev-parse --path-format=absolute --git-common-dir)
common_there=$(git -C "$path" rev-parse --path-format=absolute --git-common-dir) &&
  dir_there=$(git -C "$path" rev-parse --path-format=absolute --git-dir) ||
  { echo "not a git worktree: $path" >&2; exit 3; }
[ "$common_there" = "$common_here" ] && [ "$dir_there" != "$common_there" ] ||
  { echo "not a linked worktree of this repository: $path" >&2; exit 3; }
# The branch is asked of the worktree itself, as git answers there, which holds
# on Windows where a comparison of directory spellings does not. A detached
# worktree has no symbolic HEAD and holds no branch, so it is refused too.
[ "$(git -C "$path" symbolic-ref --quiet HEAD || :)" = "refs/heads/$branch" ] ||
  { echo "not the worktree of this repository holding ${branch}: $path" >&2; exit 3; }
# Every refresh worker holds this lock for its whole run, the index update
# included, and Windows will not delete a file held open: a remove meanwhile
# deletes part of the tree and fails. So the lock is taken first, with the
# hook's own primitive, and one still held at the bound removes nothing.
cache="$path/.claude/cache/codebase-index"
if [ -f "$cache/refresh.lock" ] || [ -f "$cache/refresh.pending" ]; then
  python=python3
  command -v py >/dev/null 2>&1 && python="py -3.12"
  if ! $python -I - "$cache" <<'PY'; then
import os, sys, time
lock, pending = (os.path.join(sys.argv[1], name) for name in ("refresh.lock", "refresh.pending"))
bound, grace = 30, 2
if sys.platform == "win32":
    import msvcrt
    def grab(handle):
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    def release(handle):
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl
    def grab(handle):
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    def release(handle):
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
start, unclaimed = time.monotonic(), None
while True:
    now = time.monotonic()
    with open(lock, "a+b") as handle:
        try:
            grab(handle)
        except OSError:
            unclaimed = None
        else:
            try:
                if not os.path.exists(pending):
                    sys.exit(0)
                # A request with the lock free is a worker on its way to the
                # lock, or one a failed refresh put back that nobody will take.
                unclaimed = now if unclaimed is None else unclaimed
                if now - unclaimed >= grace:
                    try:
                        os.remove(pending)
                    except FileNotFoundError:
                        pass
                    sys.exit(0)
            finally:
                release(handle)
    # A grace already begun runs out first, so the message is never said of a
    # tree that nothing holds.
    if now - start >= bound and unclaimed is None:
        sys.exit(f"a code-index refresh still holds the worktree after {bound} s")
    time.sleep(0.2)
PY
    echo "nothing removed: $path; run this again once the refresh ends" >&2
    exit 5
  fi
fi
# Windows refuses a path past 260 characters unless git asks for long paths:
# git then refuses a worktree holding files it cannot read, or, failing to
# delete one, unregisters the worktree anyway and leaves its directory behind.
# The status is captured, so the checks below run whatever git exits.
status=0
git -c core.longpaths=true worktree remove "$path" || status=$?
# The directory is checked as well as git's exit, and registration tells the two
# leftovers apart. A directory git still registers is the dirty-tree refusal,
# which keeps git's own status and message. One it no longer registers is a
# failed delete, and a teardown read as done would leave a directory nobody
# looks at, which the next `/branch` on that slug stops on. Registration is
# asked by the branch, which a worktree holds alone and which needs no
# comparison of directory spellings.
if [ -e "$path" ]; then
  listed=$(git worktree list --porcelain) ||
    { echo "cannot read the worktree list, so whether $path is still registered is unknown" >&2
      exit "$((status == 0 ? 1 : status))"; }
  if ! grep -Fxq "branch refs/heads/$branch" <<<"$listed"; then
    # Git can fail after it has deleted the files and the registration, with
    # only the directory left. `rmdir` refuses one holding anything, so an
    # empty directory goes and the removal succeeded, and any other is named.
    if rmdir "$path" 2>/dev/null; then
      [ "$status" -eq 0 ] ||
        echo "git exited $status after deleting $path; the empty directory is removed" >&2
      exit 0
    fi
    echo "unregistered but not deleted: $path is still there; remove it by hand" >&2
    exit 4
  fi
fi
exit "$status"
