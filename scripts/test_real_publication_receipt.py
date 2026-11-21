"""Adversarial review checks for bounded real packing and admitted indexing."""
import copy
import json
import unittest
from check_real_publication_receipt import DIRECTORY,review
class RealPublicationReceipt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.report=json.loads((DIRECTORY/'m2-real-publication-report.json').read_text())
    def test_full_scope_and_CC_refusal_cannot_be_waived(self):
        self.assertEqual(review(self.report)['controller_exchanges'],925)
        bad=copy.deepcopy(self.report);bad['checks'][0]['packing_refusal']=None
        with self.assertRaises(AssertionError):review(bad)
        bad=copy.deepcopy(self.report);bad['checks'].pop()
        with self.assertRaises(AssertionError):review(bad)
    def test_wire_and_index_identity_must_match(self):
        bad=copy.deepcopy(self.report);bad['checks'][1]['packing'][0]['wire_verification']['records']['framed_records_sha256']='0'*64
        with self.assertRaises(AssertionError):review(bad)
        bad=copy.deepcopy(self.report);bad['checks'][2]['index_verifier_reply']['manifest']['source_sha256']='0'*64
        with self.assertRaises(AssertionError):review(bad)
    def test_memory_and_one_transfer_remain_required(self):
        bad=copy.deepcopy(self.report);bad['checks'][2]['peak_RSS_bytes']=384*1024**2+1
        with self.assertRaises(AssertionError):review(bad)
        bad=copy.deepcopy(self.report);c=bad['checks'][1];take=next(e for e in c['controller_transcript'] if e['command']['op']=='publish_take' and e['reply'].get('ok') is not None);c['controller_transcript'].append(copy.deepcopy(take))
        with self.assertRaises(AssertionError):review(bad)
if __name__=='__main__':unittest.main()
