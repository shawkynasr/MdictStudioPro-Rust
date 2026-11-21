import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from index_engine_lock import ROOT,check_lock
from index_fixtures import make,expected_page,corrupt,SPECIAL
from m2_index import protected_sources,compare
from v2_audit import audit

class DiskIndexContracts(unittest.TestCase):
    def test_prior_sources_and_dependency_graph_are_unchanged(self):
        self.assertEqual(len(protected_sources()),142);self.assertEqual(len(check_lock()),62)
        # The isolated reader is copied exactly before new modules; earlier
        # accepted source identity remains independently guarded.
        accepted=(ROOT/'m2/bounded-engine/src/lib.rs').read_text()
        self.assertTrue((ROOT/'m2/indexed-engine/src/lib.rs').read_text().startswith(accepted))
    def test_wire_fixtures_preserve_duplicate_order_both_encodings_and_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            for encoding in ['utf8','utf16']:
                f=make(Path(tmp)/(encoding+'.mdx'),encoding,strip=True)
                self.assertEqual(audit(f['path'])['status'],'structural_audit_passed');self.assertEqual(len(f['rows']),416)
                page=expected_page(f['rows'],'duplicate',384,128,strip=True)
                self.assertEqual(page['total'],400);self.assertEqual(len(page['rows']),16);self.assertIsNone(page['next_offset'])
    def test_oracle_exact_precedes_normalization_and_pages_keep_ordinals(self):
        p=expected_page(SPECIAL,'apple',0,128,strip=True);self.assertEqual([r['ordinal'] for r in p['rows']],[1,2]);self.assertEqual(p['basis'],'exact')
        p=expected_page(SPECIAL,'APPLE',1,1);self.assertEqual(p['rows'][0]['ordinal'],1);self.assertEqual(p['total'],3);self.assertEqual(p['next_offset'],2)
        self.assertEqual(expected_page(SPECIAL,'a?b',0,128,strip=True)['total'],4)
        self.assertEqual(expected_page(SPECIAL,'APPLE',0,128,policy='raw_exact')['total'],0)
        self.assertEqual(expected_page(SPECIAL,'σος',0,128)['total'],1)
        self.assertEqual(expected_page(SPECIAL,'apple',2**64-1,128)['rows'],[])
        self.assertEqual(expected_page(SPECIAL,'apple',0,0)['total'],2)
        self.assertEqual(expected_page(SPECIAL,'!!!',0,1,strip=True)['total'],1)
        with self.assertRaises(ValueError):expected_page(SPECIAL,'???',0,1,strip=True)
    def test_semantic_corruption_keeps_valid_digest_but_changes_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            m={'records':2,'revision':'studio-disk-index-v1-frozen16'};meta=json.dumps(m).encode();head=b'STIDX001'+struct.pack('<I',len(meta))+meta;head+=b'\0'*(4096-len(head));table=b''.join(struct.pack('<QII',4160+i,1,i%2) for i in range(4));data=head+table+b'abab';base=Path(tmp)/'good';base.write_bytes(data+hashlib.sha256(data).digest())
            for mode in ['revision','ordinal','token','extent','duplicate-ordinal']:
                bad=corrupt(base,Path(tmp)/mode,mode).read_bytes();self.assertNotEqual(bad,base.read_bytes());self.assertEqual(hashlib.sha256(bad[:-32]).digest(),bad[-32:])
    def test_response_comparison_rejects_lost_duplicate_and_wrong_next_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=make(Path(tmp)/'f.mdx',duplicates=3);q=[{'query':'apple','offset':0,'limit':1}];p=expected_page(f['rows'],'apple',0,1)
            actual={'status':'queried','revision':'studio-disk-index-v1-frozen16','manifest':{'source_sha256':hashlib.sha256(f['path'].read_bytes()).hexdigest(),'policy':'header_ascii_v1'},'memory':{'locator':0,'peak':10,'budget':20},'results':[{'query':'apple','page':p}]};compare(actual,f,q,'header_ascii_v1')
            wrong=copy.deepcopy(actual);wrong['results'][0]['page']['total']=1
            with self.assertRaises(AssertionError):compare(wrong,f,q,'header_ascii_v1')
            wrong=copy.deepcopy(actual);wrong['results'][0]['page']['next_offset']=None
            with self.assertRaises(AssertionError):compare(wrong,f,q,'header_ascii_v1')
if __name__=='__main__':unittest.main()
