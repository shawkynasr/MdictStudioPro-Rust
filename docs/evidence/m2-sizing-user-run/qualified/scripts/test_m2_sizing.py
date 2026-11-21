import copy
import tempfile
import unittest
from pathlib import Path
from bounded_fixtures import write,mutate,digest_row
from bounded_engine_lock import check_lock
from m2_sizing import protected_sources,peak_rss,compare_success
from v2_audit import audit

class BoundedSizingContracts(unittest.TestCase):
    def test_accepted_sources_and_registry_graph_stay_pinned(self):
        self.assertEqual(len(protected_sources()),133);self.assertEqual(len(check_lock()),62)
    def test_fixture_wire_for_both_encodings_and_binary_empty_tail_is_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            for kind,encoding,compressed in [('mdx','utf8',True),('mdx','utf16',True),('mdd','utf8',True),('mdx','utf8',False)]:
                path=Path(tmp)/f'{kind}-{encoding}-{compressed}.{kind}';f=write(path,12,kind,encoding,payload_size=128,target=128,compression=compressed);result=audit(path)
                self.assertEqual(result['status'],'structural_audit_passed',result);self.assertEqual(result['records'],12);self.assertGreater(result['key_blocks'],1);self.assertGreater(result['record_blocks'],1)
                self.assertEqual(len(f['queries']['row00000000']),2)
                if kind=='mdd':self.assertEqual(f['queries']['𠀀'][0]['bytes'],[])
            self.assertNotEqual(digest_row(1,0,'ab',b'c'),digest_row(1,0,'a',b'bc'))
    def test_malformed_declarations_and_checksum_changes_fail_wire_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/'base.mdx';write(base,12)
            for mode in ['header_length','key_info_packed','key_info_decoded','key_block_entries','record_declared_decoded','key_block_checksum','record_block_checksum','truncated']:
                bad=mutate(base,Path(tmp)/(mode+'.mdx'),mode);self.assertEqual(audit(bad)['status'],'failed',mode)
    def test_RSS_units_are_explicit_and_partial_duplicate_results_are_rejected(self):
        self.assertEqual(peak_rss('  123456 maximum resident set size\n','Darwin'),123456)
        self.assertEqual(peak_rss('Maximum resident set size (kbytes): 123\n','Linux'),123*1024)
        with self.assertRaises(AssertionError):peak_rss('missing','Darwin')
        fixture={'scan':{'records':2},'queries':{'word':[{'ordinal':0},{'ordinal':1}]}}
        actual={'profile':'bounded-lazy-scan-v1','lookup_policy':'raw-exact-bounded-scan-v1','scan':fixture['scan'],'memory':{'locator':0,'peak':100,'budget':200},'queries':[{'query':'word','rows':fixture['queries']['word']}]}
        compare_success(actual,fixture)
        wrong=copy.deepcopy(actual);wrong['queries'][0]['rows'].pop()
        with self.assertRaises(AssertionError):compare_success(wrong,fixture)
        wrong=copy.deepcopy(actual);wrong['memory']['locator']=1
        with self.assertRaises(AssertionError):compare_success(wrong,fixture)
if __name__=='__main__':unittest.main()
