"""Adversarial checks for the literal-policy qualification oracle."""
import copy
import unittest
from minimal_reader_controls import specification, expected_lookup, validate_case
from prepare_sort_experiment import literal_sort_patch
from patched_interop import ROOT


class MinimalControls(unittest.TestCase):
    def fixture(self, name="02-punctuation"):
        spec = next(c for c in specification()["cases"] if c["name"] == name)
        rows = sorted(spec["entries"], key=lambda e: e["key"].lower())
        result = {"rows": rows, "key_blocks": 3, "lookups": [
            {"query": q, "rows": expected_lookup(rows, q)} for q in spec["queries"]]}
        python_rows = [(e["key"], e["text"]) for e in rows]
        attrs = {"KeyCaseSensitive": "No", "StripKey": "No", "StyleSheet": ""}
        return spec, result, python_rows, attrs

    def test_literal_order_does_not_accept_legacy_punctuation_ties(self):
        spec, result, rows, attrs = self.fixture()
        validate_case(spec, result, rows, attrs)
        result["rows"] = sorted(spec["entries"], key=lambda e: ''.join(
            c for c in e["key"].lower() if c.isalnum()))
        with self.assertRaises(AssertionError): validate_case(spec, result, rows, attrs)

    def test_exact_duplicate_and_case_fallback_are_distinct(self):
        spec, result, rows, attrs = self.fixture()
        found = {q["query"]: q["rows"] for q in result["lookups"]}
        self.assertEqual(len(found["apple"]), 1)
        self.assertEqual(len(found["aPpLe"]), 3)
        self.assertEqual(len(found["duplicate"]), 2)
        self.assertEqual(found["a?b"], [])
        for query in ["duplicate", "aPpLe"]:
            broken = copy.deepcopy(result)
            next(q for q in broken["lookups"] if q["query"] == query)["rows"].pop()
            with self.assertRaises(AssertionError): validate_case(spec, broken, rows, attrs)

    def test_flags_and_cross_block_checks_cannot_be_waived(self):
        spec, result, rows, attrs = self.fixture()
        with self.assertRaises(AssertionError): validate_case(spec, result, rows, {**attrs, "StripKey": "Yes"})
        result["key_blocks"] = 1
        with self.assertRaises(AssertionError): validate_case(spec, result, rows, attrs)

    def test_patch_is_reversible_leaving_both_legacy_profiles_intact(self):
        original = (ROOT / "patches/studio_legacy_sort.rs").read_text(encoding="utf-8")
        modified = literal_sort_patch(original)
        self.assertEqual(literal_sort_patch(modified, reverse=True), original)
        self.assertIn('LegacySort::MdxBuilderC => word.to_ascii_lowercase()', modified)
        with self.assertRaises(ValueError): literal_sort_patch(modified)


if __name__ == "__main__": unittest.main()
