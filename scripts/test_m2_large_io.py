import copy
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from large_io_lock import check_lock
from large_io_oracle import digest,ordered,row,compare_export,json_line,wire_rows
from m2_large_io import protected_sources,fingerprints
from bounded_fixtures import write,rows

class LargeIoContracts(unittest.TestCase):
    def test_frozen_sources_and_dependency_identities(self):
        self.assertEqual(len(protected_sources()),180);self.assertEqual(len(check_lock()),62);self.assertIn('m2/large-io/src/io.rs',fingerprints())
    def test_independent_wire_decoder_against_existing_fixture_recipe(self):
        with tempfile.TemporaryDirectory() as d:
            for kind,encoding in [('mdx','utf8'),('mdx','utf16'),('mdd','utf8')]:
                f=write(Path(d)/(encoding+'.'+kind),37,kind,encoding,256)
                got=digest(wire_rows(f['path'],kind));self.assertEqual(got['records'],37)
                # Existing fixture generator has its own framed scan oracle.
                expected=digest((k,v.encode('utf-8') if isinstance(v,str) else v) for k,v in rows(37,kind,256));self.assertEqual(got,expected)
    def test_duplicate_order_and_independent_digest_frames(self):
        rows=ordered(32,'mdx');apple=[p for k,p in rows if k.lower()=='apple'];self.assertEqual(apple,[row(i,'mdx')[1] for i in range(4)])
        h=hashlib.sha256();h.update(struct.pack('<QQ',0,1)+b'a'+struct.pack('<Q',1)+hashlib.sha256(b'b').digest());self.assertEqual(digest([('a',b'b')])['framed_records_sha256'],h.hexdigest())
    def test_export_comparator_rejects_order_body_and_trailing_changes(self):
        rows=[('a',b''),('a',b'body\n\n'),('字',b'last')]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'out'
            for txt in [False,True]:
                data=b''.join(k.encode()+b'\n'+v+b'\n</>\n' if txt else json_line(k,v) for k,v in rows);p.write_bytes(data);compare_export(p,rows,txt)
                for bad in [data+b'x',data.replace(b'body',b'Body'),data[1:]]:
                    p.write_bytes(bad)
                    with self.assertRaises(AssertionError):compare_export(p,rows,txt)
if __name__=='__main__':unittest.main()
