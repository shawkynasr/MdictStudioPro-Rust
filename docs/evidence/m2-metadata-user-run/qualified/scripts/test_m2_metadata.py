import html
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zlib
from m2_metadata import protected_sources,header,check_output,source_record_oracle
from v2_import_lock import check_lock

def fixture(xml,tail=b'EXACT BINARY SECTIONS'):
    raw=(xml+'\r\n\0').encode('utf-16le');return struct.pack('>I',len(raw))+raw+struct.pack('<I',zlib.adler32(raw)&0xffffffff)+tail

class MetadataContracts(unittest.TestCase):
    def test_numeric_reference_stylesheet_is_not_given_to_source_record_reader(self):
        original=fixture('<Dictionary Encoding="UTF-8" StyleSheet="1&#10;&lt;b&gt;&#10;&lt;/b&gt;&#10;"/>')
        calls=[]
        def legacy(path,kind):
            calls.append(path);data=path.read_bytes();n,_,_,attrs,_=header(data)
            if attrs.get('StyleSheet'):raise IndexError('Legacy stylesheet triplets')
            self.assertEqual(kind,'mdx');self.assertEqual(data[n+8:],b'EXACT BINARY SECTIONS')
            return [(' spaced ','`1`raw body')]
        with tempfile.TemporaryDirectory() as tmp,patch('m2_metadata.read_legacy_physical',side_effect=legacy):
            source=Path(tmp)/'source.mdx';source.write_bytes(original)
            self.assertEqual(source_record_oracle(source,'mdx'),[(' spaced ','`1`raw body')])
            self.assertEqual(source.read_bytes(),original);self.assertNotEqual(calls[0],source);self.assertFalse(calls[0].exists())
    def test_qualified_source_extensions_and_dependency_graph_are_exact(self):
        self.assertGreaterEqual(len(protected_sources()),120);self.assertEqual(len(check_lock()),61)
    def test_raw_stylesheet_and_standard_XML_values_are_kept_distinct(self):
        data=fixture('<Dictionary Title="A &amp; B" Description="A&#13;&#10;B&#9;&amp;amp;" StyleSheet="1\n&lt;b&gt;\n&lt;/b&gt;\n"/>')
        n,raw,xml,attrs,element=header(data)
        self.assertEqual(attrs['Title'],'A & B');self.assertEqual(attrs['Description'],'A\r\nB\t&amp;');self.assertEqual(element.attrib['Description'],attrs['Description'])
        self.assertEqual(attrs['StyleSheet'],'1\n<b>\n</b>\n');self.assertNotEqual(element.attrib['StyleSheet'],attrs['StyleSheet'])
        damaged=bytearray(data);damaged[n+4]^=1
        with self.assertRaisesRegex(AssertionError,'checksum'):header(damaged)
    def test_output_comparison_rejects_changed_binary_sections_and_metadata(self):
        source=fixture('<Dictionary Title="Old" Description="Old" StyleSheet="1\n&lt;b&gt;\n&lt;/b&gt;\n" Compact="Yes"/>')
        output=fixture('<Dictionary Title="New" Description="A&#10;B" StyleSheet="1\n&lt;b&gt;\n&lt;/b&gt;\n" Compact="Yes"/>')
        n,raw,xml,attrs,_=header(output);summary={'profile':'mdict-v2-metadata-v1','file_bytes':len(output),'records':1,'stylesheet_rules':1,'header':{'attributes':attrs,'raw_utf16le':list(raw),'raw_xml':xml}}
        with tempfile.TemporaryDirectory() as tmp,patch('m2_metadata.audit',return_value={'status':'structural_audit_passed'}),patch('m2_metadata.read_legacy_physical',return_value=[('word','`1`raw')]):
            src=Path(tmp)/'source.mdx';dst=Path(tmp)/'out.mdx';src.write_bytes(source);dst.write_bytes(output)
            check=check_output(src,dst,{'title':'New','description':'A\nB'},summary,'mdx');self.assertTrue(check['binary_sections_exact']);self.assertFalse(check['standard_XML_stylesheet_value_equals_raw'])
            dst.write_bytes(output+b'changed')
            with self.assertRaisesRegex(AssertionError,'binary sections'):check_output(src,dst,{'title':'New','description':'A\nB'},summary,'mdx')
            dst.write_bytes(output)
            with self.assertRaisesRegex(AssertionError,'Header values'):check_output(src,dst,{'title':'Wrong','description':'A\nB'},summary,'mdx')
if __name__=='__main__':unittest.main()
