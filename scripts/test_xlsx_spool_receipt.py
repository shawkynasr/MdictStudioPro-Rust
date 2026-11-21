"""Reject corrupted row parity, disk sizes and gate-scope evidence."""
import copy
import json
import unittest
from m2_sizing import ROOT
from check_xlsx_spool_receipt import review

class RowSpoolReceiptContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory=ROOT/'docs/evidence/m2-xlsx-spool-user-run'
        cls.report=json.loads((directory/'m2-xlsx-spool-report.json').read_text());cls.oracles=json.loads((directory/'review-oracles.json').read_text())
    def test_full_row_digest_all_cases_and_independent_disk_extents_pass(self):
        summary=review(self.report,self.oracles)
        self.assertEqual((summary['full_normalized_rows'],summary['process_cases']),(163909,27))
    def test_mutated_row_content_and_spool_byte_extent_are_rejected(self):
        for mode in ['content','bytes']:
            report=copy.deepcopy(self.report);receipt=report['checks'][-1]['reply']['receipt']
            if mode=='content':receipt['row_digest']['framed_rows_sha256']='0'*64
            else:receipt['row_spool_bytes']+=1
            with self.assertRaises(AssertionError):review(report,self.oracles)
    def test_limit_refusal_options_and_false_dictionary_claim_are_rejected(self):
        for mode in ['limit','scope']:
            report=copy.deepcopy(self.report)
            if mode=='limit':next(c for c in report['checks'] if c['case']=='old-row-cap')['request']['tighten']['rows']=200000
            else:report['Revised_WFG_dictionary_conversion_qualified']=True
            with self.assertRaises(AssertionError):review(report,self.oracles)
if __name__=='__main__':unittest.main()
