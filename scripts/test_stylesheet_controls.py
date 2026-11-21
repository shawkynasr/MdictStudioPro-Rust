"""Regressions that keep raw storage, substitution and native rendering distinct."""
import copy
import html
import struct
import tempfile
from pathlib import Path
import unittest
from stylesheet_controls import specification, validate_case, raw_stylesheet, official_reference_stylesheet


class StylesheetControls(unittest.TestCase):
    def test_native_reference_requires_one_extra_LF_not_body_changes(self):
        args = self.fixture()
        reference = official_reference_stylesheet()
        self.assertEqual(len(reference), 147)
        self.assertEqual(reference, args[-1] + '\n')
        result = validate_case(*args[:-1], reference, expected_wire_style=reference)
        self.assertFalse(result['raw_stylesheet_preserved'])
        self.assertTrue(result['raw_stylesheet_matches_selected_contract'])
        with self.assertRaises(AssertionError): validate_case(*args, expected_wire_style=reference)

    def test_candidate_does_not_accept_silently_added_definition_newlines(self):
        args = list(self.fixture())
        reference = official_reference_stylesheet()
        args[1] = copy.deepcopy(args[1])
        for row in args[1]['rows']: row['text'] += '\r\n'
        with self.assertRaises(AssertionError): validate_case(*args[:-1], reference, expected_wire_style=reference)

    def fixture(self):
        spec = specification(); case = spec["cases"][0]
        rows = sorted(case["entries"], key=lambda e: e["key"].lower())
        result = {"rows": rows, "key_blocks": 4, "lookups": [
            {"query": q, "rows": [e for e in rows if e["key"] == q]} for q in case["queries"]]}
        raw = [(e["key"], e["text"]) for e in rows]
        styled = [(k, spec["rendered"].get(k, v)) for k, v in raw]
        attrs = {"KeyCaseSensitive": "No", "StripKey": "No", "Compact": "Yes",
                 "StyleSheet": case["stylesheet"].replace("\n", " ")}
        return spec, result, raw, styled, attrs, case["stylesheet"]

    def test_XML_normalization_is_visible_and_not_mistaken_for_native_success(self):
        args = self.fixture()
        result = validate_case(*args)
        self.assertFalse(result["standard_XML_stylesheet_matches_raw"])
        self.assertNotIn("native_passed", result)
        with self.assertRaises(AssertionError): validate_case(*args[:-1], args[-1].replace("\n", " "))

    def test_marker_loss_and_wrong_expansion_fail_independently(self):
        args = list(self.fixture())
        broken = copy.deepcopy(args)
        next(e for e in broken[1]["rows"] if e["key"] == "marker-red")["text"] = "STYLE_ONE_OK"
        with self.assertRaises(AssertionError): validate_case(*broken)
        broken = copy.deepcopy(args)
        broken[3] = [(k, v.replace('STYLE_ONE_OK', 'WRONG')) for k, v in broken[3]]
        with self.assertRaises(AssertionError): validate_case(*broken)

    def test_raw_header_extraction_preserves_line_breaks_and_decodes_entities(self):
        style = specification()["cases"][0]["stylesheet"]
        xml = '<Dictionary StyleSheet="' + html.escape(style, quote=True) + '"/>\r\n\0'
        payload = xml.encode('utf-16le')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'test.mdx'
            path.write_bytes(struct.pack('>I', len(payload)) + payload)
            self.assertEqual(raw_stylesheet(path), style)
            path.write_bytes(struct.pack('>I', len(payload) + 10) + payload)
            with self.assertRaises(AssertionError): raw_stylesheet(path)


if __name__ == "__main__": unittest.main()
