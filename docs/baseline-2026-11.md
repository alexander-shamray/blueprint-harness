# Stop baseline, November 2026

The measuring tool for the anti-goal "agents stop more often" (spec section
4). Every later sync is compared with these numbers, the tables under *After
#297* being the ones the present filter can reproduce: the count per typical
task must not rise in any repository.

## What is counted

`measure/stops.py` reads one session transcript (one `.jsonl` file under
`~/.claude/projects/`) and counts four things: `ask_user` (AskUserQuestion
tool uses), `action_required` (assistant messages whose last line starts
`⚠️ ACTION REQUIRED`, except the exact `⚠️ ACTION REQUIRED — none`, which
hands over nothing),
`permission_refused` (tool errors whose text is a permission refusal, not a
hook refusal) and `user_turns` (genuine user messages after the one that opens
the task; interruption markers, hook and system injections, `/compact`
summaries and tool results are not, and neither is a command Claude Code runs
itself, such as `/clear`, `/model` or `/compact`, wherever it falls).

A session counts when it started on or after the `--since` date and on or before
any `--until` date, both read in UTC, and, with `--command`, its first genuine
user message past any such local command opens with that slash command. Its
start is its first line carrying a `timestamp`. The median is taken per count
across the sessions.

## Limits of the measure

- A permission prompt the owner approved leaves no mark in the transcript, so
  only refused prompts and auto-mode blocks are counted. The count is a floor.
- A session stays in the window it started in, with all it did later. A closed
  window keeps its sessions, but a session resumed afterwards can still raise
  its counts.
- A median of zero hides a skewed tail; the totals below show it.
- Until #297 the window read a modification time in local time, so a session
  counted on its last day of use and a window read later could lose one, and a
  leading local command other than `/clear`, `/model` or `/reload-plugins` hid a
  session, while one of those later in a session counted as a turn. Every table
  the command lines printed ahead of *After #297* was taken that way; *After
  plan 5*'s count by start chose its own sessions.
- Until #276 `--command` read a session's first genuine message and looked for
  the tag anywhere in it, so a session a `/clear` opened dropped out and one
  whose first message only quoted the tag counted, and the `user_turns` of a
  session counted its `/compact` summaries. Every table those command lines
  printed ahead of *After #276* was taken that way; *After plan 5*'s count by
  start chose its own sessions and kept only the `/compact` handling.

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

and the same three with `--command bug-sweep`. Run on 2026-11-02, on the filter
#276 replaced, so these lines no longer print the two tables below; *After
#297* gives the window on the present one.

## Medians per session, since 2026-10-19

| Repository | Command | Sessions | ask_user | action_required | permission_refused | user_turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| backend | `ship` | 31 | 0 | 0 | 0 | 0 |
| backend | `bug-sweep` | 0 | none | none | none | none |
| frontend | `ship` | 5 | 0 | 0 | 0 | 0 |
| frontend | `bug-sweep` | 1 | 0 | 0 | 0 | 0 |
| admin | `ship` | 11 | 0 | 2 | 0 | 2 |
| admin | `bug-sweep` | 0 | none | none | none | none |

That filter read no `bug-sweep` sessions in backend or admin in the window, so
those two rows have no median and give no baseline. The frontend `bug-sweep` row
is one session and is not a median in any useful sense.

## Totals and the largest session, `ship` sessions

The medians were mostly zero, so the totals show where the stops fell. Each
cell is the total over the sessions, then the largest in one session. They
came from the `total` and `max` fields of the final line the commands above
printed for `--command ship` on 2026-11-02.

| Repository | ask_user | action_required | permission_refused | user_turns |
| --- | --- | --- | --- | --- |
| backend | 2, max 1 | 80, max 27 | 8, max 5 | 92, max 43 |
| frontend | 3, max 3 | 5, max 3 | 2, max 2 | 3, max 3 |
| admin | 0, max 0 | 89, max 38 | 6, max 4 | 50, max 29 |

As that filter read them, most `ship` sessions ran without a stop and a few long
ones carried most of the handovers. A comparison after the move should read the
medians and the totals both, and should compare like with like: the same
command, the same repository.

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
and admin's remaining memories, other than their repository facts, wait for
their first sync.

The stop count after plan 2 is the first command line above with
`--since 2026-11-06`, which admits the backend `ship` sessions that started on
or after that day. It is added here, as medians and as totals with their
largest session, once two or more have ended; a rise against the baseline is a
harness defect, filed in this repository. *After #297* holds that count and the
baseline it reads against, both on the present filter.

## After plans 3 and 4

Superseded, never taken on their own. Plan 3 asked for *After plan 3*, the
stop count of the next two backend `/ship` sessions, and plan 4 for *After
plan 4*, backend's stop count since its Task 5 Step 2 and the number of syncs
merged with no owner turn. Both windows open after 2026-11-06, so their
sessions are inside backend's *Since a repository's first sync* row of *After
#276* and of *After #297*, read on the filter each names, and *After plan 6*
carries that row on. Plan 4's count of syncs was not taken: a `/ship sync`
session is a `ship` session, so its stops are in those rows, not apart.

## After plan 5

Measured on 2026-11-08, after blueprint-frontend's #382, its first sync,
merged at 04:42 UTC that day, and its #389, which made its `CLAUDE.md` import
`.harness/agent-rules.md` and triaged its memories. Frontend's `main` read at
`bf735c3`.

### Stop count

The second command line above with `--since 2026-11-08`. `--since` takes a
day, and each of the six sessions it admits starts after the merge, the
earliest at 06:01 UTC, so the window holds only sessions since #382.

| Repository | Command | Sessions | ask_user | action_required | permission_refused | user_turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| frontend | `ship` | 6 | 0 | 0.5 | 0 | 0 |

| Repository | ask_user | action_required | permission_refused | user_turns |
| --- | --- | --- | --- | --- |
| frontend | 0, max 0 | 7, max 5 | 0, max 0 | 1, max 1 |

Against the two tables, same command and same repository, `action_required`
rose: the median from 0 to 0.5, the total from 5 to 7, the largest session
from 3 to 5. The other three fell or held. By the plan's rule a rise is a
harness defect, so it is filed, as #272.

Those tables do not hold what they name, on either side, because of how
`--command` picks a session, as *Limits of the measure* says and #276 files. It
drops six sessions on each side that a `/clear` opens. It also keeps two of the
baseline's five that are not `/ship`: security reviews whose first message
quotes the tag. Without those two the baseline's `action_required` median is
already 2, so the rise in the median rests on them. Counted as sessions whose
first genuine message, or the one after a `/clear`, opens with the `/ship` tag,
which no command line offered then, and read at 16:13 UTC with each window's
sessions by when they started, each cell is the median, then the total, then
the largest session, and `user_turns` counts what follows the `/ship`:

| Frontend `ship`, by that count | Sessions | ask_user | action_required | permission_refused | user_turns |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline, to 2026-11-02 | 9 | 0; 3, max 3 | 2; 16, max 6 | 0; 2, max 2 | 0; 8, max 3 |
| Since #382 | 12 | 0; 0, max 0 | 1; 17, max 5 | 0; 3, max 2 | 0; 4, max 1 |

Read that way `action_required` falls per session, from 16 over 9 to 17 over
12, with the median from 2 to 1 and the largest session from 6 to 5. `ask_user`
and `user_turns` fall too. `permission_refused` goes from 2 to 3, the one count
that rises. The rise the two tables show is therefore mostly the filter. What
#272 keeps is the load: of the seventeen, fifteen hand the owner a script
editing a path a session may not, under `.claude/` or `.github/`, a route older
than the sync. This window is one day straight after the sync against the
baseline's fourteen, so the owner met all seventeen in a day, and whether that
lasts is not yet measured.

### What a frontend session loads

LF bytes, as *After plan 2* gives backend's. Before is frontend's `main` ahead
of #389, with its `MEMORY.md` as #389's body gives it; plan 2 had already
raised `~/.claude/CLAUDE.md`, so that row does not move here.

| What a frontend session loads | Before | After |
| --- | ---: | ---: |
| `CLAUDE.md` with its imports | 13,313 | 17,294 |
| The auto-memory index, `MEMORY.md` | 4,220 | 838 |
| `~/.claude/CLAUDE.md` | 4,186 | 4,186 |
| Total | 21,719 | 22,318 |

After, `CLAUDE.md` is 10,706 bytes and its import 6,588. The triage archived
19 of frontend's 24 memories and rewrote three of the five it kept. The load
rises by 599 bytes: the import brings the hand-over, wait and model-choice
rules the old copy lacked, and the triage takes back most of that. Backend's
22,028 is another repository on an earlier `agent-rules.md`, so it is not the
comparison.

## After #276

Measured on 2026-11-09, on the filter #297 then changed. The tables here and
above stay as the record of what was read then; *After #297* is the comparison.

### The baseline window

The window of *Command lines*, closed at the day it was first run:

```bash
py -3.12 measure/stops.py --project 'C--dev-ashamray-blueprint-backend*' --since 2026-10-19 --until 2026-11-02 --command ship
py -3.12 measure/stops.py --project 'C--dev-ashamray-blueprint-frontend*' --since 2026-10-19 --until 2026-11-02 --command ship
py -3.12 measure/stops.py --project 'C--dev-ashamray-blueprint-admin*' --since 2026-10-19 --until 2026-11-02 --command ship
```

and the same three with `--command bug-sweep`.

| Repository | Command | Sessions | ask_user | action_required | permission_refused | user_turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| backend | `ship` | 94 | 0 | 0 | 0 | 0 |
| backend | `bug-sweep` | 3 | 0 | 0 | 0 | 1 |
| frontend | `ship` | 11 | 0 | 2 | 0 | 1 |
| frontend | `bug-sweep` | 1 | 0 | 0 | 0 | 0 |
| admin | `ship` | 44 | 0 | 3.5 | 0 | 1 |
| admin | `bug-sweep` | 2 | 0 | 5 | 0 | 2 |

| Repository | ask_user | action_required | permission_refused | user_turns |
| --- | --- | --- | --- | --- |
| backend | 5, max 1 | 167, max 27 | 18, max 5 | 218, max 58 |
| frontend | 3, max 3 | 36, max 17 | 3, max 2 | 9, max 2 |
| admin | 0, max 0 | 286, max 67 | 15, max 5 | 95, max 21 |

The filter finds three times what the first run did in backend, 94 against 31,
four times in admin, 44 against 11, and twice in frontend, 11 against 5. Most of
the gain is sessions a `/clear` opens.

### Since a repository's first sync

Admin has had no sync, so it has no row. Each window closes on 2026-11-08, the
last whole day. Backend's is `--since 2026-11-06`, as *After plan 2* names it,
and frontend's `--since 2026-11-08`, as *After plan 5* names it. Each cell but
the count of sessions is the median, then the total, then the largest session.

| Repository | Command | Sessions | ask_user | action_required | permission_refused | user_turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| backend | `ship` | 27 | 0; 0, max 0 | 1; 26, max 5 | 0; 1, max 1 | 0; 9, max 3 |
| frontend | `ship` | 11 | 0; 0, max 0 | 1; 16, max 5 | 0; 3, max 2 | 0; 4, max 1 |

Against the baseline window, `action_required` per session falls in both, from
167 over 94 to 26 over 27 in backend, with the largest session from 27 to 5, and
from 36 over 11 to 16 over 11 in frontend, with its median from 2 to 1.
Backend's median alone rises, from 0 to 1, and by the plan's rule that goes on
#272 with frontend's: most baseline sessions there stop nowhere, and a typical
one since hands something over.

### Against *After plan 5*'s count by start

Frontend's rows differ from that table in what the window reads, and every
difference is accounted for. Its baseline holds two sessions more, `2f9f0e08`
and `7f2aa868`, which started on 2026-10-18 UTC and were last modified on
2026-10-19 with 3 and 17 handovers; without them the row is that table's 16
over 9. Since #382 it holds one less, `2952e181`, which started on 2026-11-08
and was last modified on 2026-11-09, with 1 handover; with it the row is that
table's 17 over 12. Baseline `user_turns` is 7 without those two, not that
table's 8, because `35bca2b1` holds a `/compact` summary the count no longer
takes for a turn.

## After #297

Measured on 2026-11-09, on the filter *What is counted* describes. A later sync
is compared with these, same command and same repository.

### The baseline window

The command lines of *After #276*'s baseline window, unchanged.

| Repository | Command | Sessions | ask_user | action_required | permission_refused | user_turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| backend | `ship` | 98 | 0 | 0 | 0 | 0 |
| backend | `bug-sweep` | 2 | 0 | 0 | 1 | 1.5 |
| frontend | `ship` | 9 | 0 | 2 | 0 | 0 |
| frontend | `bug-sweep` | 1 | 0 | 0 | 0 | 0 |
| admin | `ship` | 44 | 0 | 3.5 | 0 | 1 |
| admin | `bug-sweep` | 1 | 0 | 1 | 0 | 0 |

| Repository | ask_user | action_required | permission_refused | user_turns |
| --- | --- | --- | --- | --- |
| backend | 5, max 1 | 178, max 27 | 18, max 5 | 216, max 56 |
| frontend | 3, max 3 | 16, max 6 | 2, max 2 | 7, max 2 |
| admin | 0, max 0 | 286, max 67 | 15, max 5 | 89, max 16 |

### Since a repository's first sync

The windows of *After #276*, closing on 2026-11-08. Each cell but the count of
sessions is the median, then the total, then the largest session.

| Repository | Command | Sessions | ask_user | action_required | permission_refused | user_turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| backend | `ship` | 29 | 0; 0, max 0 | 1; 29, max 5 | 0; 1, max 1 | 0; 10, max 3 |
| frontend | `ship` | 12 | 0; 0, max 0 | 1; 17, max 5 | 0; 3, max 2 | 0; 4, max 1 |

Against the baseline window, `action_required` per session falls in both, from
178 over 98 to 29 over 29 in backend, with the largest session from 27 to 5, and
from 16 over 9 to 17 over 12 in frontend, with its median from 2 to 1 and the
largest session from 6 to 5. Backend's median alone rises, from 0 to 1, which
stays on #272. Frontend's `permission_refused` goes from 2 over 9 to 3 over 12,
the one rate that rises, as *After plan 5* read it.

### Against *After #276*

Every difference is the window or the turn count, and frontend now matches
*After plan 5*'s count by start: 16 over 9 and 17 over 12. Its one difference
there is the `user_turns` *After #276* accounts for.

| Row | Sessions | Left: started before `--since` | Came: started inside, last modified outside |
| --- | ---: | --- | --- |
| backend `ship`, baseline | 94 to 98 | none | 4, with 11 handovers |
| backend `bug-sweep`, baseline | 3 to 2 | 1, with 1 handover | none |
| frontend `ship`, baseline | 11 to 9 | 2, with 20 handovers | none |
| admin `bug-sweep`, baseline | 2 to 1 | 1, with 9 handovers | none |
| backend `ship`, since sync | 27 to 29 | none | 2, with 3 handovers |
| frontend `ship`, since sync | 11 to 12 | none | 1, with 1 handover |

No session came through the opening rather than the window: in these rows no
leading local command beyond the old three hid a session. Where a session stays
in both, `user_turns` falls only by local commands later in it: by 12 in backend
`ship`, 6 in admin `ship` and 1 in backend `bug-sweep`.

## After plan 6

Measured on 2026-11-13, after admin's first sync, blueprint-admin#655, merged
at 09:26 UTC on 2026-11-09, and its #657, which made its `CLAUDE.md` import
`.harness/agent-rules.md` and triaged its memories. With it every target syncs
(`IMPORT.md`, *Rollout closed*).

### Stop count since each first sync

On the filter *What is counted* describes, each window closing on 2026-11-12,
the last whole day:

```bash
py -3.12 measure/stops.py --project 'C--dev-ashamray-blueprint-backend*' --since 2026-11-06 --until 2026-11-12 --command ship
py -3.12 measure/stops.py --project 'C--dev-ashamray-blueprint-frontend*' --since 2026-11-08 --until 2026-11-12 --command ship
py -3.12 measure/stops.py --project 'C--dev-ashamray-blueprint-admin*' --since 2026-11-09 --until 2026-11-12 --command ship
```

Backend's and frontend's windows open where *After #297*'s did. Admin's
admits 23 sessions, and one, `2bc538fc`, started at 04:38 UTC, before #655
merged, with 6 handovers and 1 turn; the row leaves it out, so it holds only
sessions since the sync. Each cell but the count of sessions is the median,
then the total, then the largest session.

| Repository | Command | Sessions | ask_user | action_required | permission_refused | user_turns |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| backend | `ship` | 63 | 0; 0, max 0 | 0; 51, max 6 | 0; 4, max 2 | 0; 26, max 4 |
| frontend | `ship` | 35 | 0; 0, max 0 | 1; 35, max 5 | 0; 4, max 2 | 0; 20, max 3 |
| admin | `ship` | 22 | 0; 0, max 0 | 0; 14, max 3 | 0; 2, max 1 | 0; 12, max 3 |

Against *After #297*'s baseline window, same command and same repository,
no count per session rises. `action_required` falls from 178 over 98 to 51
over 63 in backend, with the largest session from 27 to 6, from 16 over 9 to
35 over 35 in frontend, with the median from 2 to 1, and from 286 over 44 to
14 over 22 in admin, with the median from 3.5 to 0 and the largest session
from 67 to 3. `permission_refused` and `user_turns` fall in all three, and
`ask_user` is 0 in all three. Backend's median, which *After #297* read rising
to 1 and left on #272, is 0 again. One cell rises: frontend's largest session
takes 3 turns against the baseline's 2, a tail of one session against a median
of 0 on both sides, so nothing is filed.

### What each session loads

LF bytes, as *After plan 2* gives backend's, read on each `main` on
2026-11-13. Each `CLAUDE.md` imports only `.harness/agent-rules.md`, 7,088
bytes now.

| Repository | `CLAUDE.md` with its imports | `MEMORY.md` | `~/.claude/CLAUDE.md` | Total | Earlier |
| --- | ---: | ---: | ---: | ---: | --- |
| backend | 13,056 | 6,831 | 4,186 | 24,073 | 22,028 after plan 2 |
| frontend | 17,893 | 1,114 | 4,186 | 23,193 | 22,318 after plan 5 |
| admin | 17,679 | 918 | 4,186 | 22,783 | 17,777 before #657 |

Admin's earlier figure is #657's body: `CLAUDE.md` 10,605 with no import and
`MEMORY.md` 2,986. Its load rises by 5,006 bytes, the import's 7,088 less the
triage's 2,068 and `CLAUDE.md`'s 14. Backend's rises by 2,045: the import has
grown by 902 bytes since plan 2's 6,186 and `MEMORY.md` by 1,143 since its
triage. Frontend's rises by 875: the import by 500 since plan 5's 6,588,
`MEMORY.md` by 276 and `CLAUDE.md` by 99. The three now load within 1,290
bytes of each other.

### Red required checks on `main`

Read with `gh run list --branch main` over plan 6's dates, 2026-11-08 to
2026-11-13, in all four repositories, each run as its last attempt reads. A
required check was red on `main` in two of them:

| Repository | Runs still red that carry a required check | `main is red` issues opened in the window |
| --- | --- | --- |
| harness | `payload-suites` on macOS twice and Windows once, 2026-11-12 and 13; at `acec84e` on 2026-11-09, a `Rulesets` run that started no job and a `CI` run that ran one leg, green | #424, #429, #440, #442, #449, #450, #459, #465, all closed |
| frontend | `harness` on Windows and macOS, 2026-11-13 | blueprint-frontend#405, #452, #514 closed, #520 open |
| backend | none: one `CI` run's `integration` legs and one `CodeQL` run were red, and neither is required | blueprint-backend#1895, #1945, both closed |
| admin | none | none |

More issues than red runs: a run its rerun turned green reads green here and
kept its issue. So the rollout did not keep every `main` green. Of the issues
the main-red jobs opened, only blueprint-frontend#520 is still open, and it is
that repository's to close.
