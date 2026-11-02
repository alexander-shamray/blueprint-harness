# The harness drift gate

**The claim: every file the harness manages in this repository is exactly
what the harness put there.** A sync records a SHA-256 per managed file in
`.harness/manifest.json`. The gate recomputes them on every pull request, so
a hand edit to a managed file, or a stray file beside the managed ones, is
caught where it is made and not at the next sync.

## What it refuses

- a manifest path that is missing from the tree;
- a manifest path whose content hash differs (line endings are folded, so a
  Windows checkout passes);
- a file under a managed directory that the manifest does not list and the
  `local` globs in `.harness/config.json` do not cover. The managed
  directories are `.claude/agents`, `.claude/commands`, `.claude/hooks`,
  `.claude/scripts`, `.claude/skills`, `docs/commands` and
  `.github/harness-drift`; `__pycache__/` and `*.pyc` are skipped;
- a `.claude/settings.json` that is not what `.harness/render.py` renders
  from `.harness/settings.base.json` plus the `settings` in
  `.harness/config.json`;
- a manifest, config, base or renderer that cannot be read, a renderer that
  refuses the config, or a manifest path that is not a canonical relative
  POSIX path or that passes through a link. Each is a line of output, never a
  traceback, and the gate never reads outside the root.

## Why settings are rendered, not only hashed

The manifest hash proves the file is what the last sync wrote. The render
check proves that is still what the base and the config say, so a config edit
that was never re-synced shows up here too.

## How to run it

```bash
py -3.12 .github/harness-drift/drift_gate.py [--root <dir>] [--render <file>]
```

It prints one line per problem and exits 1, or prints `harness-drift: clean`
and exits 0. `--root` defaults to the current directory; `--render` names a
renderer other than the root's own, which the workflow uses for the base
commit's copy. The gate is stdlib only and imports nothing from the harness
repository, which a target does not have. Its hash and glob matcher are
copies of the sync tool's; the harness repository tests that they agree.

## How it runs

[`harness-drift.yml`](../workflows/harness-drift.yml), on every pull request
with no path filter. **The gate and renderer that judge are read out of the
base commit**, while the suite runs the branch's copy, so a pull request
cannot supply its own judge. When the base carries no gate, which is the
first sync into a target, the head's copy judges and the run says so.

The suite includes `test_gate_reads_the_shipped_manifest`, which checks the
tree it sits in. It needs a rendered tree and is never run from the harness
repository's raw `payload/`.

## When it is red

Do not edit the managed file in this repository, or the next sync reverts it.

- To change the file for every repository, change it in the harness
  repository and sync.
- To keep it different here, declare its path `local` in
  `.harness/config.json`. A new local file under a managed directory needs
  the same line.
- A settings difference is fixed in `.harness/config.json`'s `settings`, then
  by running the sync, which rewrites `.claude/settings.json` whole.
