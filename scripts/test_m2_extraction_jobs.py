import copy
import unittest
from extraction_jobs_lock import check_lock
from m2_extraction_jobs import admission,protected_sources,fingerprints

class ExtractionJobContracts(unittest.TestCase):
    def test_previous_sources_and_dependency_identities_are_unchanged(self):
        self.assertEqual(len(protected_sources()),171);self.assertEqual(len(check_lock()),65);self.assertIn('m2/extraction-jobs/src/runner.rs',fingerprints())
    def test_shared_admission_checks_distinct_memory_and_disk_charges(self):
        value={'shared':{'active_operations':2,'readers':1,'extractions':1,'reserved_memory_bytes':192*1024*1024,'reserved_temporary_bytes':3840*1024*1024,'max_operations':2,'memory_cap':192*1024*1024,'temporary_cap':4*1024*1024*1024},'readers':{'live_sessions':1,'retained_reply_bytes':0,'retained_reply_cap':8*1024*1024}}
        admission(value,1,1)
        for field,badvalue in [('reserved_memory_bytes',96*1024*1024),('reserved_temporary_bytes',1536*1024*1024),('active_operations',1),('temporary_cap',3*1024*1024*1024)]:
            wrong=copy.deepcopy(value);wrong['shared'][field]=badvalue
            with self.assertRaises(AssertionError):admission(wrong)
    def test_two_readers_and_zero_operation_cleanup_have_exact_reservations(self):
        value={'shared':{'active_operations':2,'readers':2,'extractions':0,'reserved_memory_bytes':192*1024*1024,'reserved_temporary_bytes':1536*1024*1024,'max_operations':2,'memory_cap':192*1024*1024,'temporary_cap':4*1024*1024*1024},'readers':{'live_sessions':2,'retained_reply_bytes':0,'retained_reply_cap':8*1024*1024}}
        admission(value,2,0)
        for key in ['active_operations','readers','reserved_memory_bytes','reserved_temporary_bytes']:value['shared'][key]=0
        value['readers']['live_sessions']=0;admission(value,0,0)
        wrong=copy.deepcopy(value);wrong['shared']['reserved_temporary_bytes']=1
        with self.assertRaises(AssertionError):admission(wrong,0,0)
if __name__=='__main__':unittest.main()
