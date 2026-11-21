"""Reject corrupted full-source parity, limit and cleanup evidence."""
import copy
import json
import unittest
from m2_sizing import ROOT
from check_concise_full_receipt import review

class ConciseReceiptContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.report=json.loads((ROOT/'docs/evidence/m2-concise-full-user-run/m2-concise-full-report.json').read_text())
    def test_full_normalized_content_and_controller_lifecycle_pass(self):
        summary=review(self.report)
        self.assertEqual((summary['entries'],summary['controller_exchanges']),(44445,893))
    def test_content_mismatch_and_changed_refusal_limit_are_rejected(self):
        for mode in ['content','limit']:
            r=copy.deepcopy(self.report)
            if mode=='content':r['checks'][0]['normalized_record_digest']['framed_records_sha256']='0'*64
            else:r['controller_transcript'][0]['command']['request']['request']['tighten']['workbook_rows']=50000
            with self.assertRaises(AssertionError):review(r)
    def test_retained_reservation_and_missing_result_transfer_are_rejected(self):
        for mode in ['reservation','transfer']:
            r=copy.deepcopy(self.report)
            if mode=='reservation':r['controller_transcript'][-1]['reply']['ok']['shared']['reserved_memory_bytes']=1
            else:r['controller_transcript']=[x for x in r['controller_transcript'] if x['command']['op']!='publish_take']
            with self.assertRaises(AssertionError):review(r)

if __name__=='__main__':unittest.main()
