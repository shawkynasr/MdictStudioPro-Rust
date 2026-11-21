"""Adversarial checks for the accepted six-converter integration review."""
import copy
import json
import unittest
from check_full_converters_receipt import DIRECTORY,review
class FullConverterReceipt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.report=json.loads((DIRECTORY/'m2-full-converters-report.json').read_text())
    def test_full_report_scope_and_source_binding(self):
        self.assertEqual(review(self.report)['controller_exchanges'],2726)
        bad=copy.deepcopy(self.report);bad['source_sha256']['m2/full-converter-runtime/src/concise_text.rs']='0'*64
        with self.assertRaises(AssertionError):review(bad)
        bad=copy.deepcopy(self.report);bad['checks'].pop()
        with self.assertRaises(AssertionError):review(bad)
    def test_memory_and_independent_row_oracle_cannot_be_waived(self):
        bad=copy.deepcopy(self.report);bad['checks'][3]['peak_RSS_bytes']=384*1024**2+1
        with self.assertRaises(AssertionError):review(bad)
        bad=copy.deepcopy(self.report);bad['concise_row_normalization']['reply']['receipt']['row_digest']['rows']-=1
        with self.assertRaises(AssertionError):review(bad)
    def test_duplicate_transfer_and_wrong_receipt_are_rejected(self):
        bad=copy.deepcopy(self.report);case=bad['checks'][0];take=next(e for e in case['controller_transcript'] if e['command']['op']=='publish_take' and e['reply'].get('ok') is not None);case['controller_transcript'].append(copy.deepcopy(take))
        with self.assertRaises(AssertionError):review(bad)
        bad=copy.deepcopy(self.report);bad['checks'][3]['receipt']['receipt']['receipt']['profile']='moe-concise-owned-v1'
        with self.assertRaises(AssertionError):review(bad)
if __name__=='__main__':unittest.main()
