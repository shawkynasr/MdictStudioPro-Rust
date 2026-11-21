"""Independent fixture/real-oracle contracts; no native execution claim."""
import tempfile,unittest,zlib
from pathlib import Path
from m3_keyinfo_fixture import ripemd128,transform,envelope,fixture,decode
ROOT=Path(__file__).resolve().parents[1]
class KeyinfoTests(unittest.TestCase):
 def test_ripemd_published_vectors(self):
  for data,want in [(b'','cdf26213a150dc3ecb610f18f6b38b46'),(b'a','86be7afa339d0fc7cfc785e72f578d33'),(b'abc','c14a12199c66e4ba84636b0f69144c77'),(b'message digest','9e327b3d6e523062afc1132d7df9d1b8'),(b'abcdefghijklmnopqrstuvwxyz','fd2aa607f71dc8f510714922b371834e'),(b'a'*1000000,'4a7f5723f954eba1216c9d8f6320431f')]:self.assertEqual(ripemd128(data).hex(),want)
 def test_fixture_bytes_and_independent_decode(self):
  for name,encoding in [('utf8','UTF-8'),('utf16','UTF-16')]:
   wire,rows,attrs=fixture(encoding);p=ROOT/'m3/fixtures/mdx-keyinfo'/f'{name}.mdx';self.assertEqual(p.read_bytes(),wire);self.assertEqual(decode(p),(rows,attrs));self.assertEqual(sum(k=='字' for k,t in rows),2)
 def test_cipher_and_corruption(self):
  b=envelope(b'hello'*100);self.assertNotEqual(b,transform(b,True));self.assertEqual(transform(transform(b,True)),b)
  with tempfile.TemporaryDirectory() as tmp:
   data,_,_=fixture('UTF-8');p=Path(tmp)/'bad.mdx'
   for offset in [6,len(data)-1]:
    bad=bytearray(data);bad[offset]^=1;p.write_bytes(bad)
    with self.assertRaises((ValueError,UnicodeError,zlib.error)):decode(p)
 def test_protected_header_and_bounded_route(self):
  self.assertIn('Some("no"|"0"|"")',(ROOT/'m2/v2-import/src/header.rs').read_text())
  self.assertNotIn('Some("2")',(ROOT/'m2/v2-import/src/header.rs').read_text())
  text=(ROOT/'m3/txt-runtime/src/keyinfo_export.rs').read_text()
  for field in ['max_records','max_decoded_bytes','max_entry_bytes','max_plan_charge','max_input_bytes','max_output_bytes']:self.assertIn(f'{field}:old.{field}',text)
if __name__=='__main__':unittest.main()
