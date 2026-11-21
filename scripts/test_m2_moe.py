import copy
import ast
import json
from pathlib import Path
import tempfile
import unittest
from moe_fixtures import ROOT,KINDS,generate,oracle,compare,parse_txt,extended_rows
from m2_moe import fingerprints
from m2_xlsx import protected_sources

class MoeContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);cls.cases=generate(cls.root/'inputs')
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_bundled_expectations_are_the_actual_original_plugins(self):
        expected=json.loads((ROOT/'baseline/moe-converter-kit/expected.json').read_text())
        for kind in KINDS:
            actual=oracle(self.cases[0]['file'],kind,self.root/(kind+'.txt'))
            compare(actual,expected[kind],kind)
            compare(actual,parse_txt((ROOT/'baseline/expected'/f'{kind}.txt').read_bytes()),kind)

    def test_comparator_allows_only_documented_reference_and_alias_order(self):
        a=[{'key':'main','text':'<span class="polyref"><b>相似詞：</b>乙；甲</span>'},
           {'key':'b','text':'@@@LINK=main'},{'key':'a','text':'@@@LINK=main'}]
        b=[{'key':'main','text':'<span class="polyref"><b>相似詞：</b>甲；乙</span>'},a[2],a[1]]
        compare(a,b,'moe_revised')
        for mutation in ('target','missing','content','duplicate'):
            bad=copy.deepcopy(b)
            if mutation=='target':bad[1]['text']='@@@LINK=other'
            elif mutation=='missing':bad.pop()
            elif mutation=='content':bad[0]['text']=bad[0]['text'].replace('甲','丙')
            else:bad.append(copy.deepcopy(bad[1]))
            with self.assertRaises(AssertionError):compare(a,bad,'moe_revised')
        for kind in ['moe_revised_wfg','moe_mini','moe_idioms']:
            with self.assertRaises(AssertionError):compare(a,b,kind)

    def test_extended_fixture_hits_every_idiom_section_and_numeric_layout_fallback(self):
        for kind in KINDS:
            records=oracle(self.cases[1]['file'],kind,self.root/(kind+'-extended.txt'))
            self.assertEqual(len(records),7 if kind=='moe_revised' else 3)
        idiom=oracle(self.cases[1]['file'],'moe_idioms',self.root/'idiom-check.txt')[0]['text']
        for marker in ['source-num','annotation-list','compare-table','main-entry-mark','entry://參乙','(21)','<em>同心協力</em>']:
            self.assertIn(marker,idiom)
        wfg=oracle(self.cases[1]['file'],'moe_revised_wfg',self.root/'wfg-check.txt')[0]['text']
        for marker in ['class="li"','class="yz"','(21)','class="pos1"']:self.assertIn(marker,wfg)

    def test_source_protection_and_fingerprints_cover_new_code_without_dependency_changes(self):
        self.assertGreater(len(protected_sources()),32)
        paths=fingerprints()
        for name in ['m2/xlsx-reader/src/moe/mini-head.html','m2/xlsx-reader/src/bin/studio-moe.rs','m2/xlsx-reader/src/moe/layouts.rs','m2/xlsx-reader/Cargo.lock']:
            self.assertIn(name,paths)
        report=json.loads((ROOT/'docs/evidence/m2-xlsx-user-run/m2-xlsx-report.json').read_text())
        self.assertEqual(paths['m2/xlsx-reader/Cargo.lock'],report['source_sha256']['m2/xlsx-reader/Cargo.lock'])

    def test_second_Mac_failure_is_only_the_already_documented_reference_order(self):
        report=json.loads((ROOT/'docs/evidence/m2-moe-second-user-run/m2-moe-report.json').read_text())
        log=report['steps'][0]['failure_log_tail']
        left=ast.literal_eval(log.split('  left: ',1)[1].split('\n',1)[0])
        right=ast.literal_eval(log.split('\n right: ',1)[1].split('\n',1)[0])
        self.assertNotEqual(left,right)
        compare([{'key':k,'text':v} for k,v in left],[{'key':k,'text':v} for k,v in right],'moe_revised')

if __name__=='__main__':unittest.main()
