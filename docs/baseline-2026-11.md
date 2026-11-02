# Stop baseline, November 2026

The measuring tool for the anti-goal "agents stop more often" (spec section
4). Every later sync is compared with these numbers: the count per typical
task must not rise in any repository.

## What is counted

`measure/stops.py` reads one session transcript (one `.jsonl` file under
`~/.claude/projects/`) and counts four things: `ask_user` (AskUserQuestion
tool uses), `action_required` (assistant messages whose last line starts
`⚠️ ACTION REQUIRED`, except the `— none` form, which hands over nothing),
`permission_refused` (tool errors whose text is a permission refusal, not a
hook refusal) and `user_turns` (genuine user messages after the first).

A session counts when its transcript file was last modified on or after the
`--since` date and, with `--command`, its first genuine user message is that
slash command. The median is taken per count across the sessions.

## Limits of the measure

- A permission prompt the owner approved leaves no mark in the transcript, so
  only refused prompts and auto-mode blocks are counted. The count is a floor.
- A session that was resumed later has a later modification time, so it can
  enter the window on its last day of use, not its first.
- A median of zero hides a skewed tail; the totals below show it.

## Command lines

`--project` takes a directory name or glob under `~/.claude/projects/`. The
glob `<project>*` takes a project and all its worktree directories at once, so
there are three runs per command, not one per directory. The runs, from the
repository root:

```bash
py -3.12 measure/stops.py --project 'C--dev-ashamray-blueprint-backend*' --since 2026-10-19 --command ship
py -3.12 measure/stops.py --project 'C--dev-ashamray-blueprint-frontend*' --since 2026-10-19 --command ship
py -3.12 measure/stops.py --project 'C--dev-ashamray-blueprint-admin*' --since 2026-10-19 --command ship
```

and the same three with `--command bug-sweep`. Run on 2026-11-02.

## Medians per session, since 2026-10-19

| Repository | Command | Sessions | ask_user | action_required | permission_refused | user_turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| backend | `ship` | 31 | 0 | 0 | 0 | 0 |
| backend | `bug-sweep` | 0 | none | none | none | none |
| frontend | `ship` | 5 | 0 | 0 | 0 | 0 |
| frontend | `bug-sweep` | 1 | 0 | 0 | 0 | 0 |
| admin | `ship` | 11 | 0 | 2 | 0 | 2 |
| admin | `bug-sweep` | 0 | none | none | none | none |

There are no `bug-sweep` sessions in backend or admin in the window, so those
two rows have no median and give no baseline. The frontend `bug-sweep` row is
one session and is not a median in any useful sense.

## Totals and the largest session, `ship` sessions

The medians are mostly zero, so the totals show where the stops fall. Each
cell is the total over the sessions, then the largest in one session.

| Repository | ask_user | action_required | permission_refused | user_turns |
| --- | --- | --- | --- | --- |
| backend | 2, max 1 | 80, max 27 | 8, max 5 | 93, max 43 |
| frontend | 3, max 3 | 5, max 3 | 2, max 2 | 3, max 3 |
| admin | 0, max 0 | 89, max 38 | 6, max 4 | 51, max 29 |

Most `ship` sessions run without a stop; a few long ones carry most of the
handovers. A comparison after the move should read both tables, and should
compare like with like: the same command, the same repository.
