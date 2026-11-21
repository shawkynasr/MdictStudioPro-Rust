"""Check immutable dependency/data reuse and independent comparison contracts."""
import unittest
from m2_foundation import check_layout, compare_rows


class FoundationContracts(unittest.TestCase):
    def test_workspace_reuses_the_pinned_dependency_graph(self):
        check_layout()

    def test_independent_comparison_rejects_loss_and_reordered_duplicates(self):
        entries = [{"key": "a", "text": "first\n"}, {"key": "a", "text": "second"}]
        rows = [("a", "first\n"), ("a", "second")]
        compare_rows(entries, rows)
        for bad in [rows[:1], list(reversed(rows)), [("a", "first"), rows[1]]]:
            with self.assertRaises(AssertionError):
                compare_rows(entries, bad)


if __name__ == "__main__":
    unittest.main()
