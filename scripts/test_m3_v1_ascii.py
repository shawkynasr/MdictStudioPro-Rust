"""Independent v1 ASCII fixture contracts; native execution remains separate."""
import struct,tempfile,unittest,zlib
from pathlib import Path
from m3_v1_ascii_fixture import lzo,block,fixture,decode
ROOT=Path(__file__).resolve().parents[1]
class LegacyAsciiTests(unittest.TestCase):
 def test_multiple_blocks_duplicate_empty_and_metadata(self):
  data,rows,attrs=fixture();p=ROOT/'m3/fixtures/mdx-v1-ascii/ascii.mdx';self.assertEqual(p.read_bytes(),data);self.assertEqual(decode(p),(rows,attrs));self.assertEqual([t for k,t in rows if k=='duplicate'],['first','second']);self.assertEqual(attrs['Encoding'],'ISO8859-1')
 def test_literal_stylesheet_LF_is_preserved(self):
  data,rows,attrs=fixture();size=int.from_bytes(data[:4],'big');raw=data[4:4+size].decode('utf-16le').replace('&#10;','\n').encode('utf-16le');data=struct.pack('>I',len(raw))+raw+struct.pack('<I',zlib.adler32(raw))+data[size+8:]
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'literal.mdx';p.write_bytes(data);self.assertEqual(decode(p),(rows,attrs))
 def test_nonascii_not_guessed_as_utf8_or_latin1(self):
  data,_,_=fixture(True);p=ROOT/'m3/fixtures/mdx-v1-ascii/nonascii.mdx';self.assertEqual(p.read_bytes(),data)
  with self.assertRaises(ValueError):decode(p)
 def test_lzo_literal_and_overlap_vectors_and_truncation(self):
  for raw in [b'a',b'hello',b'x'*20]:self.assertEqual(lzo(bytes([len(raw)+17])+raw+b'\x11\0\0',len(raw)),raw)
  self.assertEqual(lzo(b'\x12a\x40\0\x11\0\0',4),b'aaaa')
  for data,size in [(b'',1),(b'\x12a',1),(b'\x12a\x40\xff',4),(b'\x12a\x11\0\0junk',1),(b'\x12a\x11\0\0',0)]:
   with self.assertRaises(ValueError):lzo(data,size)
 def test_block_checksum_size_and_corrupt_source(self):
  raw=b'hello';b=b'\x01\0\0\0'+struct.pack('>I',zlib.adler32(raw))+bytes([len(raw)+17])+raw+b'\x11\0\0';self.assertEqual(block(b,5),raw)
  with self.assertRaises(ValueError):block(b,4)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'bad.mdx';data,_,_=fixture()
   for bad in [data[:50],data[:-1],data+b'junk']:
    p.write_bytes(bad)
    with self.assertRaises((ValueError,struct.error)):decode(p)
 def test_new_decoder_view_keeps_old_version_and_source_identity(self):
  s=(ROOT/'m3/export-io/src/header.rs').read_text();self.assertIn('128*1024*1024',s);self.assertIn('if name=="Encoding"{"UTF-8"}',s);self.assertNotIn('"GeneratedByEngineVersion"{"2.0"}',s)
  s=(ROOT/'m3/export-io/src/io.rs').read_text();self.assertIn('!e.key().is_ascii()||!e.text().is_ascii()',s)
  self.assertIn('Only declared v2',(ROOT/'m2/v2-import/src/header.rs').read_text())
if __name__=='__main__':unittest.main()
