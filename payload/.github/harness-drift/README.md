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
  `.harness/config.json`. The renderer runs only if its bytes match the
  manifest and, with a payload, the payload; otherwise the gate reports that
  and does not execute it;
- a `local` or `exclude` glob that matches `.harness/settings.base.json` or
  `.harness/render.py`;
- a manifest, config, base or renderer that cannot be read, a renderer that
  refuses the config, a manifest path that is not a canonical relative POSIX
  path, and any fixed path or managed directory that is a link. Each is a
  line of output, never a traceback, and the gate never reads outside the
  root.

With `--payload`, it also refuses:

- a payload file excluded by the config that exists in the tree;
- a payload file, not excluded by the config, that the manifest does not list
  with the payload's hash. The exception is a `local` path whose file in the
  tree is absent or identical to the payload's, as apply allows;
- a `local` path whose file differs from the payload's, which apply would
  have refused;
- a manifest entry other than `.claude/settings.json` that is not a payload
  file with an equal hash.

Without `--payload` it requires the manifest to list the base, the renderer
and the settings.

## Trust model

The manifest and the config sit in the tree a pull request controls, so a
pull request can edit a managed file and its manifest line together, or
delete the line. Three things guard against that, each a different part:

- **The base commit's copy of `drift_gate.py`** judges, so a pull request
  cannot weaken the gate that judges it. It does not cover the manifest or
  the config.
- **The payload fetch** covers the manifest and the config. The workflow reads
  `harness_commit` from the head manifest and fetches that commit's
  `payload/` from the harness repository, only if the commit is on that
  repository's `main` (GitHub serves fork-network commits by SHA, so a SHA
  alone proves nothing) and is the base manifest's commit or a descendant of
  it, so a pull request cannot roll a target back to a weaker real release.
  `--payload` makes the gate compare the manifest with it. A failed fetch or
  a failed test fails the run. A pull request cannot change that repository.
- **The repository ruleset and review** are the backstop for what is left.
  `pull_request` runs the head's copy of `harness-drift.yml`, so a pull
  request can edit the workflow itself, and only the ruleset requiring this
  check, with review of workflow changes, stops that.

The base gate judges the head workflow that calls it, so the gate's command
line flags must stay backward compatible: renaming one makes the sync that
carries the rename red.

Exclude means "not delivered", never "replaced". A payload path the config
excludes that still exists in the tree is refused here and by apply, because
a target keeping its own copy of a managed file, a guard hook for example,
would fork the harness. Use `local` for a file the target keeps.

## How to run it

```bash
py -3.12 .github/harness-drift/drift_gate.py [--root <dir>] [--payload <dir>]
```

It prints one line per problem and exits 1, or prints `harness-drift: clean`
and exits 0. `--root` defaults to the current directory. `--payload` is the
harness repository's `payload/` at the commit in the manifest. The gate is
stdlib only and imports nothing from the harness repository, which a target
does not have. Its hash and glob matcher are copies of the sync tool's; the
harness repository tests that they agree.

## How it runs

[`harness-drift.yml`](../workflows/harness-drift.yml), on every pull request
with no path filter. It takes the gate from the base commit; when the base
carries none, which is the first sync into a target, the head's copy judges
and the run says so. It then fetches the payload, runs the gate, and only then
runs this directory's suite, so head test code cannot tamper with the run
before the gate has judged. A failed fetch fails the run.

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
