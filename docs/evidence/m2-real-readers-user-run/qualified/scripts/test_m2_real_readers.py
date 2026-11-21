import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import bounded_fixtures as wire
from bounded_fixtures import write,mutate
from real_reader_oracle import scan_to_database,page,redact_page
from m2_real_readers import catalog,protected_sources,fingerprints
def fixture(path,count,kind,encoding,size):
    if kind!='mdd':return write(path,count,kind,encoding,size)
    original=wire.rows
    def unique(*args):
        for i,(key,data) in enumerate(original(*args)):yield ('row00000001' if i==1 else key),data
    with patch.object(wire,'rows',unique):return write(path,count,kind,encoding,size)
class RealReaderContracts(unittest.TestCase):
    def test_protected_sources_and_default_four_file_selection(self):
        self.assertEqual(len(protected_sources()),210);self.assertEqual(len(fingerprints()),4)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cases=catalog(root);self.assertEqual(len(cases),4);self.assertEqual([c['kind'] for c in cases],['mdx','mdd','mdx','mdx']);self.assertTrue(all(c['source'].is_relative_to(root) for c in cases))
            manifest=root/'select.json';manifest.write_text(json.dumps({'cases':[{'id':'bad','path':'../escape.mdx'}]}))
            with self.assertRaises(AssertionError):catalog(root,manifest)
    def test_wire_scan_pages_and_binary_empty_tail_match_independent_fixture_recipe(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for kind,encoding in [('mdx','utf8'),('mdx','utf16'),('mdd','utf8')]:
                source=root/(encoding+'.'+kind);f=fixture(source,11,kind,encoding,128);db=sqlite3.connect(':memory:')
                try:
                    scan,queries,resources,frame=scan_to_database(source,kind,['row00000000','absent'],db);self.assertEqual(scan,f['scan']);self.assertIn('row00000000',queries);offset=0 if kind=='mdd' else 1;p=page(db,'row00000000',offset,1,kind);self.assertEqual(p['total'],1 if kind=='mdd' else 2);self.assertEqual(p['rows'][0]['ordinal'],offset);self.assertIsNone(p['next_offset']);self.assertEqual(page(db,'absent',0,1,kind)['rows'],[]);self.assertEqual(page(db,'row00000000',2**64-1,0,kind)['total'],p['total']);self.assertEqual(len(frame),64)
                    if kind=='mdd':self.assertEqual(resources['𠀀']['bytes'],0)
                finally:db.close()
    def test_real_oracle_supports_more_than_previous_100000_row_fixture_cap(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'large.mdd';f=fixture(source,100001,'mdd','utf8',0);db=sqlite3.connect(':memory:')
            try:scan,_,resources,_=scan_to_database(source,'mdd',['absent'],db);self.assertEqual(scan,f['scan']);self.assertEqual(scan['records'],100001)
            finally:db.close()
    def test_corrupt_header_and_record_block_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'good.mdx';write(source,7);data=bytearray(source.read_bytes());data[7]^=1;(root/'header.mdx').write_bytes(data);mutate(source,root/'record.mdx','record_block_checksum')
            for p in [root/'header.mdx',root/'record.mdx']:
                db=sqlite3.connect(':memory:')
                try:
                    with self.assertRaises((AssertionError,ValueError,UnicodeError)):scan_to_database(p,'mdx',[],db)
                finally:db.close()
    def test_report_page_redaction_keeps_identity_and_hash_without_definition(self):
        private=b'private definition';p={'basis':'exact','total':1,'offset':0,'next_offset':None,'rows':[{'ordinal':4,'key':'word','text':private.decode()}]};redacted=redact_page(p);self.assertNotIn(private.decode(),json.dumps(redacted));self.assertEqual(redacted['rows'],[{'ordinal':4,'key':'word','payload_bytes':len(private),'payload_sha256':hashlib.sha256(private).hexdigest()}])
if __name__=='__main__':unittest.main()
