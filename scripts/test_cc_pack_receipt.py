"""Adversarial checks for complete CC packing qualification."""
import copy
import json
import unittest
from check_cc_pack_receipt import DIRECTORY,review
class CcPackReceipt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.report=json.loads((DIRECTORY/'m2-cc-pack-report.json').read_text())
    def test_complete_encodings_and_input_scope_are_required(self):
        self.assertEqual(review(self.report)['controller_exchanges'],1273)
        bad=copy.deepcopy(self.report);bad['checks'].pop()
        with self.assertRaises(AssertionError):review(bad)
        bad=copy.deepcopy(self.report);bad['independent_preparation']['inventory']['records']-=1
        with self.assertRaises(AssertionError):review(bad)
    def test_output_digest_and_memory_cannot_be_waived(self):
        bad=copy.deepcopy(self.report);bad['checks'][0]['independent_wire']['records']['framed_records_sha256']='0'*64
        with self.assertRaises(AssertionError):review(bad)
        bad=copy.deepcopy(self.report);bad['peak_RSS_bytes']=384*1024**2+1
        with self.assertRaises(AssertionError):review(bad)
    def test_results_transfer_once_and_source_identity_remains_bound(self):
        bad=copy.deepcopy(self.report);entry=next(e for e in bad['controller_transcript'] if e['command']['op']=='publish_take' and e['reply'].get('ok') is not None);bad['controller_transcript'].append(copy.deepcopy(entry))
        with self.assertRaises(AssertionError):review(bad)
        bad=copy.deepcopy(self.report);bad['source_sha256']['m2/cc-pack-io/src/block_writer.rs']='0'*64
        with self.assertRaises(AssertionError):review(bad)
if __name__=='__main__':unittest.main()
