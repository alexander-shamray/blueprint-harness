# Transcript field shapes

What `stops.py` and `replay_guard.py` read, taken from real session transcripts
under `~/.claude/projects/<project>/<session>.jsonl`: one JSON object per line,
and the shapes only, no content.

- **A session** is one `.jsonl` file. Lines of interest have `type` of `user` or
  `assistant`; the rest (`attachment`, `ai-title`, `api-request` ...) are
  bookkeeping and ignored.
- **AskUserQuestion**: an `assistant` line whose `message.content` is a list
  holding `{"type": "tool_use", "name": "AskUserQuestion", "input": {...}}`.
- **Handover**: an `assistant` line holding `{"type": "text", "text": ...}`
  whose last non-empty line starts `⚠️ ACTION REQUIRED`. The convention also
  writes `⚠️ ACTION REQUIRED — none` when nothing is owed; that is not a stop
  and is not counted.
- **Tool result**: a `user` line whose `message.content` is a list holding
  `{"type": "tool_result", "is_error": true, "content": <str or list>}`. The
  line also carries `toolDenialKind` (`user-rejected`, `automode-blocked`,
  `automode-unavailable`, or `permission-rule`) and `permissionDecision`. A hook
  refusal is `is_error: true` and `toolDenialKind: "permission-rule"` too, so
  the flags cannot tell it from a permission refusal; only the text can.
  Permission refusals start "Permission for this action was denied", "The user
  doesn't want to proceed" or "The server-side auto mode classifier gave no
  verdict". Hook refusals start "PreToolUse:<Tool> hook error:".
- **Genuine user message**: a `user` line with `isMeta` absent, no
  `isSidechain`, no `isCompactSummary`, `origin` absent or `{"kind": "human"}`,
  and `message.content` either a string or a list of `text`/`image` parts with
  no `tool_result`. Not genuine: tool results; `isMeta: true` lines (skill and
  system-reminder expansions); a `/compact` summary, a string line carrying
  `isCompactSummary` and `isVisibleInTranscriptOnly`; `origin.kind` other than
  human (`task-notification`, `plugin`); strings opening `<local-command`,
  `<bash-input>`, `<bash-stdout>`, `<task-notification>` or `<system-reminder>`.
- **Interruption marker**: a `user` line whose content is a list holding one
  `text` part opening `[Request interrupted`; no `origin` or `isMeta`.
- **Slash command**: a genuine string message opening
  `<command-name>/<name></command-name>`, or `<command-message>` and then that
  tag. A diff or fixture quoting the tag holds it later in the message.
- **A session a `/clear` opens**: the new transcript's first genuine message is
  the `/clear`, an ordinary slash command message, and no later message in the
  file is one. `/model` or `/reload-plugins` can follow it before the task's own
  command.
