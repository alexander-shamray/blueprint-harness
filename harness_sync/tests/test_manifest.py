"""Tests for the manifest."""

import tempfile
import unittest
from pathlib import Path

from harness_sync.manifest import Manifest, file_hash


class ManifestTests(unittest.TestCase):
    def test_hash_ignores_crlf(self) -> None:
        self.assertEqual(file_hash(b"a\r\nb\n"), file_hash(b"a\nb\n"))

    def test_hash_sees_content(self) -> None:
        self.assertNotEqual(file_hash(b"a\n"), file_hash(b"b\n"))

    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".harness" / "manifest.json"
            Manifest("a" * 40, {"z": "1", "a": "2"}).write(path)
            self.assertEqual(Manifest.read(path), Manifest("a" * 40, {"a": "2", "z": "1"}))

    def test_read_missing_is_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(Manifest.read(Path(tmp) / "nope.json"))


if __name__ == "__main__":
    unittest.main()
