import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import capture


class LegacyCharacterization(unittest.TestCase):
    def test_snapshot_integrity(self):
        manifest = json.loads((HERE / "source-manifest.json").read_text())
        for name, expected in manifest["files"].items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((HERE / "legacy" / name).read_bytes()).hexdigest(), expected)

    def test_all_golden_outputs_reproduce(self):
        subprocess.run([sys.executable, str(HERE / "run.py"), "check"], check=True)

    def test_known_converter_semantics_and_defect(self):
        plugins = capture.load_plugins()
        self.assertEqual(plugins["cc_cedict"].convert_pinyin("nu:3 lu:4 hao3 ma5"), "nǚ lǜ hǎo ma")
        mini = plugins["moe_mini"]
        self.assertIn("<img", mini.replace_inline_images("&sample.png;"))
        # Characterize existing bug. Do NOT fix the oracle to make this pass.
        self.assertEqual(mini.clean_text("&sample.png;"), "&sample.png;")
        self.assertIn("<ruby>", mini.clean_text("&&和ㄏㄜˊ&&"))
        revised = (HERE / "expected" / "moe_revised.txt").read_text(encoding="utf-8")
        self.assertIn("@@@LINK=和", revised)
        self.assertEqual(revised.count("和平\n@@@LINK=和\n"), 1)
        cedict = (HERE / "expected" / "cc_cedict.txt").read_text(encoding="utf-8")
        self.assertEqual(cedict.count("和\n"), 2)
        self.assertIn("传\n", cedict)
        self.assertIn("傳\n", cedict)

    def test_c_locale_sort_profiles_differ_on_non_ascii_case(self):
        import locale
        locale.setlocale(locale.LC_COLLATE, "C")
        keys = ["ä", "Ä"]
        self.assertEqual(capture.sort_oracle(keys, "mdxbuilder", False), ["Ä", "ä"])
        self.assertEqual(capture.sort_oracle(keys, "mdict-utils", False), ["ä", "Ä"])
        self.assertEqual(capture.sort_oracle(["a-b", "ab", "a b"], "mdxbuilder", False), ["a-b", "ab", "a b"])
        # The unescaped legacy character class omits backslash. Preserve this
        # observation until the migration explicitly decides whether to fix it.
        self.assertEqual(capture.sort_oracle(["a", "\\images\\A.png"], "mdict-utils", False), ["\\images\\A.png", "a"])

    def test_cell_normalization_and_encoding_boundaries(self):
        capture.load_plugins()
        from excel_utils import _cell_to_str
        self.assertEqual([_cell_to_str(x) for x in [None, True, 1.0, 1.5, " 001 "]], ["", "True", "1", "1.5", "001"])
        sample = "字和"
        for encoding in ["utf-8", "utf-16le", "big5", "gbk", "gb18030"]:
            self.assertEqual(sample.encode(encoding).decode(encoding), sample)
        with self.assertRaises(UnicodeEncodeError):
            "مرحبا".encode("big5")

    def test_missing_and_invalid_input_fail(self):
        for key, plugin in capture.load_plugins().items():
            with self.subTest(plugin=key), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(Exception):
                    plugin.convert(str(Path(tmp) / "missing"), str(Path(tmp) / "out"), "utf-8", lambda _: None, lambda _: None)
        cedict = capture.load_plugins()["cc_cedict"]
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "bad.u8"
            source.write_bytes(b"\xff\xfe\xff")
            with self.assertRaises(UnicodeDecodeError):
                cedict.convert(str(source), str(Path(tmp) / "out"), "utf-8", lambda _: None, lambda _: None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
