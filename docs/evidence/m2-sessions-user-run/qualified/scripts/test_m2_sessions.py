import copy
import tempfile
import unittest
from pathlib import Path
from m2_sessions import protected_sources,fingerprints,review_page
from session_lock import check_lock,ROOT
from index_fixtures import make,expected_page

class SessionContracts(unittest.TestCase):
    def test_prior_runtime_and_registry_identities_are_unchanged(self):
        self.assertEqual(len(protected_sources()),153);self.assertEqual(len(check_lock()),63)
        self.assertIn('m2/sessions/src/tests.rs',fingerprints())
        manifest=(ROOT/'m2/sessions/Cargo.toml').read_text();self.assertIn('path = "../indexed-engine"',manifest)
    def test_session_reply_comparison_rejects_lost_duplicate_and_wrong_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=make(Path(tmp)/'f.mdx',duplicates=10);p=expected_page(f['rows'],'apple',1,1);response={'operation':'page','value':p};review_page(response,f,'apple',1,1,'header_ascii_v1')
            bad=copy.deepcopy(response);bad['value']['rows'][0]['ordinal']=1
            with self.assertRaises(AssertionError):review_page(bad,f,'apple',1,1,'header_ascii_v1')
            bad=copy.deepcopy(response);bad['value']['total']=1
            with self.assertRaises(AssertionError):review_page(bad,f,'apple',1,1,'header_ascii_v1')
            bad=copy.deepcopy(response);bad['operation']='opened'
            with self.assertRaises(AssertionError):review_page(bad,f,'apple',1,1,'header_ascii_v1')
    def test_empty_binary_tail_and_out_of_range_pages_still_compare_exactly(self):
        fixture={'rows':[('file',bytes([0,255])),('file',bytes([128])),('empty',b'')],'kind':'mdd'}
        p=expected_page(fixture['rows'],'empty',0,1,'raw_exact',kind='mdd');review_page({'operation':'page','value':p},fixture,'empty',0,1,'raw_exact')
        p=expected_page(fixture['rows'],'file',2**64-1,1,'raw_exact',kind='mdd');review_page({'operation':'page','value':p},fixture,'file',2**64-1,1,'raw_exact')
if __name__=='__main__':unittest.main()
