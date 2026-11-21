"""Reference fixtures preserve parser differences instead of normalizing them away."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib
from patched_interop import legacy_fixture_records
from reference_builder import source_files, prepare, verify_kit, differences, header_details


class ReferenceBuilder(unittest.TestCase):
    def test_source_and_rust_bodies_match_including_CRLF(self):
        files = source_files()
        self.assertTrue(files['source.txt'].startswith(b'\xff\xfe'))
        self.assertTrue(files['style.txt'].startswith(b'\xff\xfe'))
        source = files['source.txt'][2:].decode('utf-16le')
        style = files['style.txt'][2:].decode('utf-16le')
        self.assertNotIn('\n', source.replace('\r\n', ''))
        self.assertNotIn('\n', style.replace('\r\n', ''))
        self.assertFalse(style.endswith('\n'))
        spec = json.loads(files['rust-spec.json'])['cases'][0]
        self.assertEqual(legacy_fixture_records(source), [(e['key'], e['text']) for e in spec['entries']])
        self.assertEqual(style, spec['stylesheet'])

    def test_modified_kit_is_refused_even_if_manifest_is_updated(self):
        with tempfile.TemporaryDirectory() as tmp:
            kit = Path(tmp)/'kit'; prepare(kit); verify_kit(kit)
            (kit/'style.txt').write_bytes(b'changed')
            with self.assertRaises(AssertionError): verify_kit(kit)

    def test_body_and_stylesheet_newline_differences_remain_visible(self):
        base = {'header': {'attributes': {'StyleSheet': '1\r\n<font>\r\n</font>'}},
                'raw_rows': [{'key':'plain','text':'body\r\n'}],
                'python_expanded_rows': [{'key':'plain','text':'body\r\n'}]}
        changed = copy.deepcopy(base)
        changed['raw_rows'][0]['text'] = 'body\n'
        changed['header']['attributes']['StyleSheet'] = '1\n<font>\n</font>'
        delta = differences(base, changed)
        self.assertFalse(delta['raw_key_payload_multisets_equal'])
        self.assertIn('StyleSheet', delta['header_attributes'])

    def test_v3_reference_and_bad_header_checksum_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'reference.mdx'
            def put(version, checksum_delta=0):
                raw = ('<Dictionary GeneratedByEngineVersion="'+version+'"/>\r\n\0').encode('utf-16le')
                path.write_bytes(struct.pack('>I',len(raw))+raw+struct.pack('<I',(zlib.adler32(raw)^checksum_delta)&0xffffffff))
            put('2.0'); self.assertTrue(header_details(path)['ends_CRLF_NUL'])
            put('3.0')
            with self.assertRaises(AssertionError): header_details(path)
            put('2.0', 1)
            with self.assertRaises(AssertionError): header_details(path)


if __name__ == '__main__': unittest.main()
