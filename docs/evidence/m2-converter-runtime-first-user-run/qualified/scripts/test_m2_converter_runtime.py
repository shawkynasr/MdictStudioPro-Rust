import copy
from pathlib import Path
import tempfile
import unittest
from converter_runtime_lock import check_lock
from converter_runtime_fixtures import generate,original,compare_output,record_digest,moe_rows
from m2_converter_runtime import protected_sources,admission
class ConverterRuntimeContracts(unittest.TestCase):
    def test_registry_graph_is_identical_except_local_facade(self):self.assertEqual(len(check_lock()),66);self.assertEqual(len(protected_sources()),199)
    def test_generated_sources_and_captured_oracles_have_valid_canonical_framing(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for case in generate(p,4,8):
                output=p/(case['kind']+'.txt');entries,metrics,comments=original(case['source'],case['kind'],output);self.assertGreater(len(entries),0);self.assertEqual(record_digest(entries,case['kind']),compare_output(output,entries,case['kind']));self.assertEqual(len(entries),metrics['primary_entries']+metrics['alias_redirects']+metrics['traditional_entries']);self.assertEqual(comments,int(case['kind']=='cc_cedict'));self.assertFalse(Path(str(case['source'])+'_log.txt').exists())
    def test_conversion_reservation_counts_352_MiB_with_one_reader(self):
        value={'shared':{'active_operations':2,'readers':1,'packings':0,'exports':0,'extractions':0,'conversions':1,'reserved_memory_bytes':352*1024*1024,'reserved_temporary_bytes':1536*1024*1024,'max_operations':2,'memory_cap':384*1024*1024,'temporary_cap':4*1024*1024*1024},'readers':{'live_sessions':1,'retained_reply_bytes':0,'retained_reply_cap':8*1024*1024}};admission(value,1,1)
        for field,bad in [('reserved_memory_bytes',192*1024*1024),('reserved_temporary_bytes',768*1024*1024),('active_operations',1)]:
            wrong=copy.deepcopy(value);wrong['shared'][field]=bad
            with self.assertRaises(AssertionError):admission(wrong)
    def test_comparator_refuses_changed_definition_and_duplicate_order(self):
        expected=[{'key':'a','text':'one'},{'key':'a','text':'two'}]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'out';p.write_text('a\ntwo\n</>\na\none\n</>\n')
            with self.assertRaises(AssertionError):compare_output(p,expected,'cc_cedict')
    def test_larger_moe_recipe_groups_two_polyphones_and_preserves_numeric_cells(self):
        rows=list(moe_rows(4));self.assertEqual(rows[0]['字詞名'],rows[1]['字詞名']);self.assertNotEqual(rows[1]['字詞名'],rows[2]['字詞名']);self.assertEqual([r['多音排序'] for r in rows],[1,2,1,2]);self.assertIsInstance(rows[0]['總筆畫數'],int)
if __name__=='__main__':unittest.main()
