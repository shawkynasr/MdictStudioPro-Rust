"""Reject corrupted full CC-CEDICT parity, limits and exclusive admission evidence."""
import copy
import json
import unittest
from m2_sizing import ROOT
from check_cc_full_receipt import review
from unittest.mock import patch
import check_cc_full_receipt as checker

class FullCCReceiptContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.report=json.loads((ROOT/'docs/evidence/m2-cc-full-user-run/m2-cc-full-report.json').read_text())
    def test_complete_output_and_controller_lifecycle_pass(self):
        summary=review(self.report)
        self.assertEqual((summary['entries'],summary['controller_exchanges']),(203362,1440))
    def test_finder_metadata_is_excluded_but_extra_and_changed_sources_fail(self):
        actual=dict(self.report['source_sha256'])
        with patch.object(checker,'fingerprints',return_value={**actual,'m2/cc-runtime/.DS_Store':'0'*64}):
            self.assertEqual(review(self.report)['entries'],203362)
        for bad in [{**actual,'m2/cc-runtime/unexpected.rs':'0'*64}, {**actual,next(iter(actual)):'0'*64}]:
            with patch.object(checker,'fingerprints',return_value=bad),self.assertRaises(AssertionError):
                review(self.report)

    def test_native_hash_and_changed_old_limit_are_rejected(self):
        for mode in ['hash','limit']:
            r=copy.deepcopy(self.report)
            if mode=='hash':r['checks'][0]['native_output_sha256']='0'*64
            else:r['controller_transcript'][0]['command']['request']['request']['tighten']['entries']=250000
            with self.assertRaises(AssertionError):review(r)
    def test_undercharge_and_uncollected_result_are_rejected(self):
        for mode in ['charge','transfer']:
            r=copy.deepcopy(self.report)
            if mode=='charge':
                x=next(x for x in r['controller_transcript'] if x['command']['op']=='admission' and x['reply']['ok']['shared']['conversions']==1)
                x['reply']['ok']['shared']['reserved_memory_bytes']=256*1024*1024
            else:r['controller_transcript']=[x for x in r['controller_transcript'] if x['command']['op']!='publish_take']
            with self.assertRaises(AssertionError):review(r)

if __name__=='__main__':unittest.main()
