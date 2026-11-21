"""Prevent closeout from dropping evidence or expanding the supported scope."""
import copy
import json
import unittest
from m2_sizing import ROOT
from m2_closeout import DECISION,review
class M2Closeout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.decision=json.loads((ROOT/DECISION).read_text())
    def test_all_five_criteria_remain_bound_to_receipts(self):
        result=review(self.decision);self.assertTrue(result['M2_complete']);self.assertEqual(result['accepted_criteria'],5);self.assertEqual(result['unique_receipt_bindings'],23)
        bad=copy.deepcopy(self.decision);bad['criteria'].pop('representative_full_inputs')
        with self.assertRaises(AssertionError):review(bad)
    def test_completion_does_not_imply_release_GUI_or_other_platforms(self):
        for field in ['production_release_ready','Tauri_GUI_integrated','all_formats_or_platforms_qualified','hard_OS_memory_enforcement']:
            bad=copy.deepcopy(self.decision);bad[field]=True
            with self.assertRaises(AssertionError):review(bad)
    def test_stale_source_or_receipt_bindings_are_rejected(self):
        bad=copy.deepcopy(self.decision);name=next(iter(bad['receipt_bindings']));bad['receipt_bindings'][name]['sha256']='0'*64
        with self.assertRaises(AssertionError):review(bad)
        bad=copy.deepcopy(self.decision);name=next(iter(bad['accepted_source_sha256']));bad['accepted_source_sha256'][name]='0'*64
        with self.assertRaises(AssertionError):review(bad)
if __name__=='__main__':unittest.main()
