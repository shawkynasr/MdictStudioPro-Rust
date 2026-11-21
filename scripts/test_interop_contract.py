"""Small data-loss checks for the interop harness, independent of either engine."""
import unittest
from pathlib import Path
import struct
import tempfile
import zlib
from patched_interop import compare, decode, inspect_header, legacy_fixture_records


class ComparisonContract(unittest.TestCase):
    def test_duplicate_multiplicity_is_not_discarded(self):
        compare([("a","one"),("a","two")],[("a","two"),("a","one")])
        with self.assertRaises(AssertionError):
            compare([("a","one"),("a","one")],[("a","one")])
        with self.assertRaises(AssertionError):
            compare([("a","one"),("a","two")],[("a","two"),("a","one")],order=True)

    def test_whitespace_and_binary_payloads_are_exact(self):
        with self.assertRaises(AssertionError):
            compare([("字"," body\n")],[("字","body")])
        with self.assertRaises(AssertionError):
            compare([("blob",b"\x00\xff\x00")],[("blob",b"\x00\xff")])

    def test_reader_utf8_decoding_is_strict(self):
        self.assertEqual(decode("字".encode()),"字")
        with self.assertRaises(UnicodeDecodeError):
            decode(b"\xff")

    def test_header_terminator_is_required_and_counted(self):
        xml='<Dictionary GeneratedByEngineVersion="2.0" Title="字" />'.encode("utf-16le")
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"fixture.mdx"
            path.write_bytes(struct.pack(">I",len(xml))+xml+struct.pack("<I",zlib.adler32(xml)))
            with self.assertRaisesRegex(AssertionError,"terminating"):
                inspect_header(path)
            payload=xml+b"\x00\x00"
            path.write_bytes(struct.pack(">I",len(payload))+payload+struct.pack("<I",zlib.adler32(payload)))
            result=inspect_header(path)
            self.assertEqual(result["payload_bytes"],len(xml)+2)
            self.assertEqual(result["attributes"]["Title"],"字")

    def test_header_crc_must_cover_the_terminator(self):
        xml='<Dictionary GeneratedByEngineVersion="2.0" />'.encode("utf-16le")
        payload=xml+b"\x00\x00"
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"fixture.mdd"
            path.write_bytes(struct.pack(">I",len(payload))+payload+struct.pack("<I",zlib.adler32(xml)))
            with self.assertRaisesRegex(AssertionError,"checksum"):
                inspect_header(path)

    def test_legacy_txt_span_retains_delimiter_preceding_lf(self):
        result=legacy_fixture_records("a\n line \n\n</>\na\nsecond\n</>\n")
        self.assertEqual(result,[("a"," line \n\n"),("a","second\n")])
        with self.assertRaises(AssertionError):
            compare(result,[("a"," line "),("a","second")])

    def test_legacy_fixture_parser_preserves_crlf_and_rejects_incomplete(self):
        self.assertEqual(legacy_fixture_records("字\r\nbody\r\n</>\r\n"),[("字","body\r\n")])
        for text in ["a\nbody\n","a\n</>\n","\nbody\n</>\n"]:
            with self.subTest(text=text), self.assertRaises(AssertionError):
                legacy_fixture_records(text)


if __name__=="__main__":
    unittest.main(verbosity=2)
