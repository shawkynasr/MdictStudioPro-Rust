"""CC full-data identity, isolation and exclusive admission contracts."""
import copy
import json
import unittest
from m2_sizing import ROOT,sha
from m2_cc_full import REFERENCE,protected_sources,fingerprints,exclusive_admission
from cc_runtime_lock import check_lock

class FullCCContracts(unittest.TestCase):
    def test_accepted_sources_and_dependency_registry_unchanged(self):
        self.assertEqual(len(protected_sources()),229);self.assertEqual(len(check_lock()),66)
        self.assertIn('m2/cc-runtime/src/txt.rs',fingerprints())
        self.assertEqual((ROOT/'m2/cc-runtime/src/runner.rs').read_bytes(),(ROOT/'m2/converter-runtime/src/runner.rs').read_bytes())
        old=(ROOT/'m2/converter-runtime/src/lib.rs').read_text();new=(ROOT/'m2/cc-runtime/src/lib.rs').read_text()
        self.assertEqual(new,old.replace('pub mod converters;','pub mod converters;\nmod txt;').replace('Self::Conversion=>256*1024*1024','Self::Conversion=>384*1024*1024'))
    def test_full_raw_reference_preserves_primary_traditional_records_and_framing(self):
        reference=json.loads((ROOT/REFERENCE).read_text());self.assertFalse(reference['native_run'])
        self.assertEqual(reference['expected_entries'],reference['primary_entries']+reference['traditional_entries'])
        self.assertEqual(reference['expected_entries'],203362);self.assertEqual(reference['comments_count'],30)
        d=reference['record_digest'];self.assertEqual(d['records'],reference['expected_entries'])
        self.assertEqual(d['key_bytes']+d['payload_bytes']+6*d['records'],reference['expected_file_bytes'])
        for name,h in reference['legacy_oracle_sha256'].items():self.assertEqual(sha(ROOT/name),h)
    def test_exclusive_ledger_rejects_undercharge_reader_overlap_and_leaked_reservation(self):
        accepted=json.loads((ROOT/'docs/evidence/m2-concise-full-user-run/m2-concise-full-report.json').read_text())['final_admission']
        exclusive_admission(accepted)
        active=copy.deepcopy(accepted);active['shared'].update(conversions=1,active_operations=1,reserved_memory_bytes=384*1024*1024,reserved_temporary_bytes=768*1024*1024,closed=False);active['readers']['closed']=False;exclusive_admission(active)
        for mode in ['undercharge','overlap','leak']:
            v=copy.deepcopy(active if mode!='leak' else accepted)
            if mode=='undercharge':v['shared']['reserved_memory_bytes']=256*1024*1024
            elif mode=='overlap':v['shared'].update(readers=1,active_operations=2)
            else:v['shared']['reserved_memory_bytes']=1
            with self.assertRaises(AssertionError):exclusive_admission(v)

if __name__=='__main__':unittest.main()
