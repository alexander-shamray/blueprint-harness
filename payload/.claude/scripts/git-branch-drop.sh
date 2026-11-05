#!/usr/bin/env bash
# Delete one local branch once it has landed: `/ship` step 0's finished
# predicate, made the only route to `git branch -D`, whose raw spellings stay
# denied. Guards, each before the delete: the name is not `main` in any
# spelling; the branch exists and is checked out in no worktree; and
# pr-for-branch.sh reports a pull request for it MERGED into `main` whose head
# is the branch's tip, so no commit on it is one the merge did not take.
#
# Exit codes, in git-rebase-onto-main.sh's meanings where one fits:
#   0  dropped
#   2  usage, or a name this helper will not take
#   3  the branch is `main`, however it is spelled
#   4  the branch is checked out in a worktree, this one included
#   6  there is no local branch of that name: nothing to drop
#   7  it has not landed: no MERGED row into `main` at its tip
#   12 its pull requests could not be read, so whether it landed is unknown
set -euo pipefail

[ "$#" -eq 1 ] || { echo "usage: git-branch-drop.sh <branch>" >&2; exit 2; }
branch="$1"
case "$branch" in
  -*) echo "branch name may not start with '-'" >&2; exit 2 ;;
  *..*) echo "branch name may not contain '..'" >&2; exit 2 ;;
esac
# pr-for-branch.sh's own shape, which it would refuse the name by in any case.
[[ "$branch" =~ ^[A-Za-z0-9][A-Za-z0-9._/()-]*$ ]] ||
  { echo "not a branch name this helper will take: $branch" >&2; exit 2; }

# By name, before anything reads the checkout, folded and spelled out as
# git-rebase-onto-main.sh does: on this host's case-insensitive filesystem
# `Main` is `main`'s ref, and one string compare is one spelling.
lowered=$(printf %s "$branch" | tr '[:upper:]' '[:lower:]')
case "$lowered" in
  main|heads/main|refs/heads/main|origin/main|refs/remotes/origin/main)
    echo "refusing to delete main, spelled $branch" >&2; exit 3 ;;
esac

tip=$(git rev-parse -q --verify "refs/heads/$branch^{commit}") ||
  { echo "no local branch $branch: nothing to drop" >&2; exit 6; }

# Every worktree, this one included. git refuses to delete a branch checked
# out, but only as spelled; folded here, so a worktree on `Feat/x` keeps
# `feat/x` on a filesystem where the two are one ref.
worktrees=$(git worktree list --porcelain) ||
  { echo "cannot list the worktrees, so whether $branch is checked out is unknown" >&2; exit 4; }
held=$(printf '%s\n' "$worktrees" | tr -d '\r' | tr '[:upper:]' '[:lower:]' |
  grep -cxF -- "branch refs/heads/$lowered" || true)
[ "$held" = 0 ] ||
  { echo "$branch is checked out in a worktree (git worktree list): it is in use, and kept" >&2; exit 4; }

# The row is pr-for-branch.sh's, which keeps only this repository's pull
# requests, so a fork's same-named one cannot land this branch. The head is
# compared with the tip read above: a commit added after the merge is work no
# merge holds, and a branch merged into anything but `main` has not landed.
rows=$(bash "$(dirname "${BASH_SOURCE[0]}")/pr-for-branch.sh" "$branch") ||
  { echo "cannot read the pull requests for $branch, so whether it landed is unknown; it is kept" >&2; exit 12; }
landed=$(printf '%s' "$rows" | jq --arg tip "$tip" \
  '[ .[] | select(.state == "MERGED" and .baseRefName == "main" and .headRefOid == $tip) ] | length') ||
  { echo "cannot read pr-for-branch.sh's answer for $branch, so whether it landed is unknown; it is kept" >&2
    exit 12; }
landed=${landed%$'\r'}
[[ "$landed" =~ ^[0-9]+$ ]] && [ "$landed" -gt 0 ] ||
  { echo "$branch has not landed: no pull request merged it into main at its tip $tip; it is kept" >&2
    exit 7; }

git branch -D -- "$branch"
echo "dropped $branch, merged into main at $tip"
