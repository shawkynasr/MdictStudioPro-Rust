import copy
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from stream_mdd_fixtures import write,chunks
from stream_extract_lock import check_lock
from m2_stream_extract import protected_sources,compare
from m2_sizing import sha
from bounded_fixtures import mutate
from v2_audit import audit

class StreamingExtractionContracts(unittest.TestCase):
    def test_previous_sources_and_registry_versions_remain_pinned(self):
        self.assertEqual(len(protected_sources()),161);self.assertEqual(len(check_lock()),62)
    def test_resources_cross_record_boundaries_without_writer_materialization(self):
        with tempfile.TemporaryDirectory() as tmp:
            for compressed in [True,False]:
                path=Path(tmp)/f'{compressed}.mdd';f=write(path,[{'key':'\\assets\\prefix.bin','bytes':17,'seed':3},{'key':'字-مرحبا-𠀀.bin','bytes':1048593,'seed':37},{'key':'empty.bin','bytes':0}],compressed,target=1024);a=audit(path)
                self.assertEqual(a['status'],'structural_audit_passed',a);self.assertGreater(f['record_blocks'],1000)
                self.assertEqual([(r['path'],r['bytes'],r['sha256']) for r in a['resources']],[(r['key'],r['bytes'],r['sha256']) for r in f['expected']])
                digest=hashlib.sha256()
                for r in f['expected']:
                    key=r['key'].encode();digest.update(struct.pack('<QQ',r['ordinal'],len(key))+key+struct.pack('<Q',r['bytes'])+bytes.fromhex(r['sha256']))
                self.assertEqual(digest.hexdigest(),f['framed_resources_sha256']);self.assertEqual(f['expected'][-1]['sha256'],hashlib.sha256(b'').hexdigest())
    def test_independent_wire_auditor_refuses_damaged_stream_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/'base.mdd';write(base,[{'key':'file.bin','bytes':100000}],target=65536)
            for mode in ['key_block_checksum','record_block_checksum','record_declared_decoded','truncated']:
                bad=mutate(base,Path(tmp)/(mode+'.mdd'),mode);self.assertEqual(audit(bad)['status'],'failed',mode)
    def test_published_file_comparison_catches_extra_missing_and_changed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);f=write(tmp/'source.mdd',[{'key':'a/b.bin','bytes':100,'seed':4},{'key':'empty','bytes':0}]);dest=tmp/'out';(dest/'a').mkdir(parents=True);(dest/'a/b.bin').write_bytes(b''.join(chunks(100,4)));(dest/'empty').write_bytes(b'')
            receipt={'profile':'mdd-stream-extract-v1','source_sha256':sha(f['path']),**{k:f[k] for k in ['resources','payload_bytes','largest_resource_bytes','framed_resources_sha256']},'locator_bytes':0,'materialized_record_limit':0,'parser_peak_bytes':100,'parser_budget_bytes':200,'plan_charge':1000,'planned_nodes':3};compare(receipt,f,dest)
            bad=copy.deepcopy(receipt);bad['materialized_record_limit']=1
            with self.assertRaises(AssertionError):compare(bad,f,dest)
            (dest/'extra').write_bytes(b'x')
            with self.assertRaises(AssertionError):compare(receipt,f,dest)
            (dest/'extra').unlink();(dest/'a/b.bin').write_bytes(b'changed')
            with self.assertRaises(AssertionError):compare(receipt,f,dest)
            (dest/'a/b.bin').unlink()
            with self.assertRaises(AssertionError):compare(receipt,f,dest)
if __name__=='__main__':unittest.main()
