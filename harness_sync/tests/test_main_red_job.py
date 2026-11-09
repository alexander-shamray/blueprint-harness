"""The harness's own `main-red` job, read as `ci.yml` writes it and fed to the helper that reads what it files."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
HELPER = ROOT / "payload" / ".claude" / "scripts" / "main-red-open.sh"


def _jobs(workflow: Path = CI) -> dict[str, str]:
    """Each job's text by id, with its comment lines left out."""
    text = workflow.read_text(encoding="utf-8").split("\njobs:\n", 1)[1]
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    parts = re.split(r"^  ([\w-]+):$", code, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2]))


class TheJobHearsEveryOtherJob(unittest.TestCase):
    def setUp(self) -> None:
        self.jobs = _jobs()
        self.job = self.jobs["main-red"]

    def test_needs_names_every_other_job(self) -> None:
        # A job added to ci.yml and left out of this list could go red on `main` with nobody told.
        needs = re.search(r"^    needs: \[(.+)\]$", self.job, re.MULTILINE)
        self.assertIsNotNone(needs, "main-red spells no one-line needs")
        self.assertEqual(sorted(set(self.jobs) - {"main-red"}), sorted(n.strip() for n in needs.group(1).split(",")))

    def test_a_cancelled_need_files_as_a_failed_one_does(self) -> None:
        # GitHub reports a job past its timeout, or that no runner picked up, as `cancelled`, and `failure()` is false
        # for that, so the condition must read the needs' results and start past one that did not succeed.
        condition = " ".join(re.search(r"^    if: >-\n((?:      .+\n)+)", self.job, re.MULTILINE).group(1).split())
        self.assertIn("always()", condition)
        self.assertIn("github.event_name == 'push'", condition)
        self.assertIn("contains(needs.*.result, 'failure')", condition)
        self.assertIn("contains(needs.*.result, 'cancelled')", condition)
        self.assertNotIn("failure()", condition)

    def test_main_runs_cancel_nothing_so_cancelled_is_never_a_superseded_push(self) -> None:
        # What lets `cancelled` read as red: a run on `main` has a group of its own and no newer run replaces it.
        code = "\n".join(line for line in CI.read_text(encoding="utf-8").splitlines()
                         if not line.lstrip().startswith("#"))
        self.assertIn("github.ref == 'refs/heads/main' && github.sha", code)
        self.assertIn("cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}", code)


class TheHelperReadsWhatTheJobFiles(unittest.TestCase):
    def test_the_title_and_the_label_are_ones_the_helper_stops_on(self) -> None:
        job = _jobs()["main-red"]
        title = re.search(r"title='([^']+)'", job).group(1)
        create = next(line for line in job.splitlines() if "gh issue create" in line)
        self.assertIn("--label bug", create, "the helper lists bug issues alone")
        self.assertIn('--title "$title"', create)
        bash = shutil.which("bash")
        self.assertIsNotNone(bash, "bash is what the helper runs under")
        with tempfile.TemporaryDirectory() as directory:
            stub = Path(directory) / "gh"
            stub.write_text('#!/usr/bin/env bash\nprintf "%s" "$STUB_ROWS"\n', encoding="utf-8", newline="\n")
            stub.chmod(0o755)
            env = {**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"],
                   "STUB_ROWS": json.dumps([{"number": 7, "title": title, "url": "u"}])}
            result = subprocess.run([bash, str(HELPER)], capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(3, result.returncode, result.stderr)
        self.assertEqual("main is red: #7 u\n", result.stdout)


if __name__ == "__main__":
    unittest.main()
