"""`sync.yml`'s trigger, read as the workflow writes it: a schedule within the bound and a dispatch, never a push."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SYNC = ROOT / ".github" / "workflows" / "sync.yml"
README = ROOT / "README.md"
# The longest a payload change waits for a sync, as README's *The sync workflow* states it.
BOUND_HOURS = 4


def _on_block() -> str:
    found = re.search(r"(?ms)^on:\n(.*?)^\S", SYNC.read_text(encoding="utf-8"))
    if found is None:
        raise AssertionError("sync.yml spells no top-level on: block")
    return found.group(1)


def _hours(field: str) -> set[int]:
    """The hours a cron hour field fires at; the forms GitHub accepts, `*`, `a`, `a-b`, `/n` and lists."""
    hours: set[int] = set()
    for part in field.split(","):
        spread, _, step = part.partition("/")
        if spread == "*":
            low, high = 0, 23
        elif "-" in spread:
            low, high = (int(n) for n in spread.split("-"))
        else:
            low = int(spread)
            high = 23 if step else low
        hours.update(range(low, high + 1, int(step) if step else 1))
    return hours


def _firings(crons: list[str]) -> set[int]:
    """The minutes of the day the crons fire at: two crons at different minutes are not whole hours apart."""
    return {int(cron.split()[0]) + 60 * hour for cron in crons for hour in _hours(cron.split()[1])}


def _longest_gap(minutes: set[int]) -> int:
    """The longest wait in minutes between two firings, around midnight included."""
    ordered = sorted(minutes)
    return max((b - a) % 1440 or 1440 for a, b in zip(ordered, ordered[1:] + ordered[:1]))


class TheTrigger(unittest.TestCase):
    def test_no_push_trigger(self) -> None:
        # A push trigger opens a sync per merge, the churn the schedule replaced.
        self.assertNotRegex(_on_block(), r"(?m)^  (push|pull_request\w*):")

    def test_dispatch_stays_for_an_urgent_sync(self) -> None:
        self.assertRegex(_on_block(), r"(?m)^  workflow_dispatch:")

    def test_every_schedule_fires_within_the_bound(self) -> None:
        crons = re.findall(r"(?m)^    - cron: '([^']+)'$", _on_block())
        self.assertTrue(crons, "sync.yml has no schedule, so a payload change could wait for a dispatch forever")
        for cron in crons:
            minute, hour, day, month, weekday = cron.split()
            self.assertTrue(minute.isdigit(), f"{cron}: one firing an hour, at a fixed minute")
            self.assertEqual((day, month, weekday), ("*", "*", "*"), f"{cron}: every day")
        self.assertLessEqual(_longest_gap(_firings(crons)), BOUND_HOURS * 60)

    def test_gap_reader_reads_the_forms(self) -> None:
        # The subject of the bound test is the reader, so a cron it misreads cannot pass the bound unseen.
        self.assertEqual(_longest_gap(_firings(["0 */4 * * *"])), 240)
        self.assertEqual(_longest_gap(_firings(["15 */6 * * *"])), 360)
        self.assertEqual(_longest_gap(_firings(["0 3 * * *"])), 1440)
        self.assertEqual(_longest_gap(_firings(["0 0,4,8,12,16,20 * * *"])), 240)
        self.assertEqual(_longest_gap(_firings(["0 8-20/4 * * *"])), 720)
        self.assertEqual(_longest_gap(_firings(["0 * * * *"])), 60)
        # Whole hours apart on the hour field, four and a half hours apart on the clock.
        self.assertEqual(_longest_gap(_firings(["0 0,8,16 * * *", "30 4,12,20 * * *"])), 270)

    def test_readme_states_the_bound(self) -> None:
        section = README.read_text(encoding="utf-8").split("## The sync workflow", 1)[1]
        self.assertIn("every four hours", section)
        self.assertIn("four hours on", section)


if __name__ == "__main__":
    unittest.main()
