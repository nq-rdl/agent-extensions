"""Tests for scripts/_registry.py::normalize_member — the one canonical parser
for a bundle skill member.

A member is either a flat string (leaf == source; the legacy shape) or an
explicit ``{source, leaf}`` mapping that packages a flat upstream skill under a
different leaf (e.g. flat ``go-gh`` -> ``go:gh``). This is the Option-2 grouping
contract: grouping is owned here, the upstream ``skills/`` tree stays flat.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import _registry  # noqa: E402


class TestNormalizeMember(unittest.TestCase):
    def test_flat_string_source_equals_leaf(self):
        self.assertEqual(_registry.normalize_member("sops"), ("sops", "sops"))

    def test_mapping_returns_source_and_leaf(self):
        self.assertEqual(
            _registry.normalize_member({"source": "go-gh", "leaf": "gh"}),
            ("go-gh", "gh"),
        )

    def test_mapping_missing_leaf_is_malformed(self):
        with self.assertRaises(ValueError):
            _registry.normalize_member({"source": "go-gh"})

    def test_mapping_empty_value_is_malformed(self):
        with self.assertRaises(ValueError):
            _registry.normalize_member({"source": "go-gh", "leaf": ""})

    def test_non_string_non_mapping_is_malformed(self):
        with self.assertRaises(ValueError):
            _registry.normalize_member(42)


if __name__ == "__main__":
    unittest.main()
