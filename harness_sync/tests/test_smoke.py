"""Smoke test: the package the CI job exists to test can be imported."""

import importlib
import unittest


class SmokeTests(unittest.TestCase):
    def test_package_imports(self) -> None:
        module = importlib.import_module("harness_sync")
        self.assertEqual(module.__name__, "harness_sync")
        # A directory without __init__.py still imports, as a namespace
        # package with no __file__, so the import alone cannot fail red.
        self.assertIsNotNone(module.__file__, "harness_sync is a namespace package")


if __name__ == "__main__":
    unittest.main()
