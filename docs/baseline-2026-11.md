# Stop baseline, November 2026

The measuring tool for the anti-goal "agents stop more often" (spec section
4). Every later sync is compared with these numbers: the count per typical
task must not rise in any repository.

## What is counted

`measure/stops.py` reads one session transcript (one `.jsonl` file under
`~/.claude/projects/`) and counts four things: `ask_user` (AskUserQuestion
tool uses), `action_required` (assistant messages whose last line starts
`⚠️ ACTION REQUIRED`, except the exact `⚠️ ACTION REQUIRED — none`, which
hands over nothing),
`permission_refused` (tool errors whose text is a permission refusal, not a
hook refusal) and `user_turns` (genuine user messages after the first;
interruption markers, hook and system injections and tool results are not).

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
cell is the total over the sessions, then the largest in one session. They
come from the `total` and `max` fields of the final line the commands above
print for `--command ship`, so the table is reproducible from them.

| Repository | ask_user | action_required | permission_refused | user_turns |
| --- | --- | --- | --- | --- |
| backend | 2, max 1 | 80, max 27 | 8, max 5 | 92, max 43 |
| frontend | 3, max 3 | 5, max 3 | 2, max 2 | 3, max 3 |
| admin | 0, max 0 | 89, max 38 | 6, max 4 | 50, max 29 |

Most `ship` sessions run without a stop; a few long ones carry most of the
handovers. A comparison after the move should read both tables, and should
compare like with like: the same command, the same repository.

## After plan 2

Measured on 2026-11-05, after blueprint-backend's #1750, which made its
`CLAUDE.md` import `.harness/agent-rules.md`, and plan 2's memory triage.
The figures are LF bytes of what every backend session loads before its
first prompt.

| What a backend session loads | Before | After |
| --- | ---: | ---: |
| `CLAUDE.md` with its imports | 8,597 | 12,154 |
| The auto-memory index, `MEMORY.md` | 16,254 | 5,688 |
| `~/.claude/CLAUDE.md` | 2,457 | 4,186 |
| Total | 27,308 | 22,028 |

After, `CLAUDE.md` is 5,968 bytes and its import 6,186. The triage archived
50 of backend's 79 memories, rewrote one to its backend half, and archived
the owner-preference memories of frontend (2) and admin (3), whose rules
`~/.claude/CLAUDE.md` *Owner preferences* now states. Eight backend memories
stay because their destination states their rule only in part. Frontend's
and admin's memories other than their repository facts wait for their first
sync.

The stop count after plan 2 is read from the backend `ship` sessions run
after this measure: the first command line above with `--since 2026-11-06`,
the day after it, so a session run later on 2026-11-05 falls outside it, and
two or more sessions give a median as the tables above do. It is added here
once one has ended; a rise against those tables is a harness defect, filed
in this repository.
