"""Adversarial checks for the accepted full official-source receipt review."""
import copy
import json
import unittest
from m2_sizing import ROOT
from check_official_converters_receipt import review

class OfficialReceiptReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=json.loads((ROOT/'docs/evidence/m2-official-converters-user-run/m2-official-converters-report.json').read_text())
    def test_full_report_is_bound_to_original_Python_and_complete_lifecycle(self):
        summary=review(self.report)
        self.assertEqual((summary['records'],summary['controller_exchanges']),(9800,732))
    def test_mutated_native_hash_and_missing_receipt_transfer_are_rejected(self):
        for change in ['hash','transfer']:
            report=copy.deepcopy(self.report);case=report['checks'][0]
            if change=='hash':case['native_output_sha256']='0'*64
            else:case['controller_transcript']=[x for x in case['controller_transcript'] if x['command']['op']!='publish_take']
            with self.assertRaises(AssertionError):review(report)
    def test_reservation_leak_and_unrequested_higher_profile_are_rejected(self):
        for change in ['leak','profile']:
            report=copy.deepcopy(self.report);case=report['checks'][0]
            if change=='leak':case['controller_transcript'][-1]['reply']['ok']['shared']['reserved_memory_bytes']=1
            else:case['controller_transcript'][0]['command']['request']['request']['tighten']={'entries':200000}
            with self.assertRaises(AssertionError):review(report)

if __name__=='__main__':unittest.main()
