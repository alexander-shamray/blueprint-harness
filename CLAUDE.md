# blueprint-harness

The shared Claude Code harness for the Blueprint repositories: the hooks,
scripts, commands, gates and working rules they have in common, kept here
once and rendered into each target by an ordinary sync pull request. This
repository is its own sync target too, so its sessions run under the
harness it develops.

- **`payload/`** is the harness, laid out as a target is; `README.md`'s
  *The rendered root* says which root files are rendered from it.
- **`harness_sync/`** is the sync tool, Python 3.12 standard library only,
  and its suites; **`measure/`** the stop counter; **`targets/`** each
  target's draft config.
- **`README.md`** owns the layout, the tests and the sync workflow;
  **`IMPORT.md`** what was taken from backend and why; and
  **`docs/harness-local.md`** what the payload's commands name by role here.

The working rules every target shares:

@.harness/agent-rules.md
