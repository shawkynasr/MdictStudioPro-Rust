"""Reject corrupted grouped conversion parity and publication evidence."""
import copy
import json
import unittest
from m2_sizing import ROOT
from check_revised_render_receipt import review

class GroupedReceiptContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d=ROOT/'docs/evidence/m2-revised-render-user-run';cls.report=json.loads((d/'m2-revised-render-report.json').read_text());cls.oracles=json.loads((d/'review-oracles.json').read_text())
    def test_both_complete_outputs_and_all_process_cases_pass(self):
        summary=review(self.report,self.oracles);self.assertEqual((summary['full_Revised_entries'],summary['full_WFG_entries'],summary['process_cases']),(162636,161182,30))
    def test_content_and_group_accounting_mutations_are_rejected(self):
        for mode in ['content','group']:
            r=copy.deepcopy(self.report);check=next(c for c in r['checks'] if c['case']=='full-moe_revised')
            if mode=='content':check['normalized_record_digest']['framed_records_sha256']='0'*64
            else:check['reply']['receipt']['largest_group_rows']+=1
            with self.assertRaises(AssertionError):review(r,self.oracles)
    def test_cancel_checkpoint_and_unsupported_background_claim_are_rejected(self):
        for mode in ['cancel','scope']:
            r=copy.deepcopy(self.report)
            if mode=='cancel':next(c for c in r['checks'] if c['case']=='moe_revised-cancel-before_publish')['request']['cancel_phase']='published'
            else:r['application_background_integration_qualified']=True
            with self.assertRaises(AssertionError):review(r,self.oracles)
if __name__=='__main__':unittest.main()
