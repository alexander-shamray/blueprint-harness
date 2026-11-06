"""The payload's vendored renderer against its owner: the drift gate a target runs imports `.harness/render.py`."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class VendoredRenderTests(unittest.TestCase):
    def test_vendored_render_identical(self) -> None:
        vendored = ROOT / "payload" / ".harness" / "render.py"
        self.assertEqual((ROOT / "harness_sync" / "render.py").read_bytes(), vendored.read_bytes())


if __name__ == "__main__":
    unittest.main()
