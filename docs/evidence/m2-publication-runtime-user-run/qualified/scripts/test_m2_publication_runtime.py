import copy
import unittest
from publication_runtime_lock import check_lock
from m2_publication_runtime import admission,protected_sources,fingerprints
class PublicationRuntimeContracts(unittest.TestCase):
    def test_frozen_runtime_sources_and_dependency_union(self):
        self.assertEqual(len(protected_sources()),190);self.assertEqual(len(check_lock()),66);self.assertIn('m2/publication-runtime/src/runner.rs',fingerprints())
    def test_reader_plus_pack_and_export_have_distinct_memory_charges(self):
        value={'shared':{'active_operations':2,'readers':1,'packings':1,'exports':0,'extractions':0,'reserved_memory_bytes':288*1024*1024,'reserved_temporary_bytes':1536*1024*1024,'max_operations':2,'memory_cap':384*1024*1024,'temporary_cap':4*1024*1024*1024},'readers':{'live_sessions':1,'retained_reply_bytes':0,'retained_reply_cap':8*1024*1024}};admission(value,1,1,0,0)
        wrong=copy.deepcopy(value);wrong['shared']['reserved_memory_bytes']=192*1024*1024
        with self.assertRaises(AssertionError):admission(wrong)
        value['shared'].update(packings=0,exports=1,reserved_memory_bytes=192*1024*1024);admission(value,1,0,1,0)
    def test_serial_publisher_and_cleanup_ledgers_reject_extra_work(self):
        value={'shared':{'active_operations':0,'readers':0,'packings':0,'exports':0,'extractions':0,'reserved_memory_bytes':0,'reserved_temporary_bytes':0,'max_operations':2,'memory_cap':384*1024*1024,'temporary_cap':4*1024*1024*1024},'readers':{'live_sessions':0,'retained_reply_bytes':0,'retained_reply_cap':8*1024*1024}};admission(value,0,0,0,0)
        wrong=copy.deepcopy(value);wrong['shared'].update(packings=1,exports=1,active_operations=2,reserved_memory_bytes=288*1024*1024,reserved_temporary_bytes=1536*1024*1024)
        with self.assertRaises(AssertionError):admission(wrong)
        wrong=copy.deepcopy(value);wrong['shared']['reserved_temporary_bytes']=1
        with self.assertRaises(AssertionError):admission(wrong)
if __name__=='__main__':unittest.main()
