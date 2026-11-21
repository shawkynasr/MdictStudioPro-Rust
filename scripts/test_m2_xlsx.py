import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from m2_xlsx import ROOT,check_reader_manifest,protected_sources,compare_table
from xlsx_fixtures import generate,oracle


class XlsxContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        cls.cases=generate(cls.root)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_reader_is_isolated_and_existing_qualified_sources_stay_pinned(self):
        check_reader_manifest();self.assertGreater(len(protected_sources()),32)

    def test_original_helper_distinguishes_active_headers_blanks_and_literal_escapes(self):
        headers=oracle(self.root/'headers.xlsx')
        self.assertIn('1.0',headers['headers']);self.assertIn('1e-05',headers['headers'])
        self.assertEqual(headers['rows'][0]['dup'],'right');self.assertEqual(headers['rows'][0]['col_2'],'explicit')
        self.assertEqual(headers['rows'][0][''],'space')
        self.assertEqual(oracle(self.root/'active.xlsx')['sheet_name'],'العربية & 字')
        self.assertEqual(oracle(self.root/'active.xlsx','First')['rows'],[{'wrong':'ignored'}])
        shared=oracle(self.root/'shared.xlsx')['rows']
        self.assertEqual(shared[1]['value'],'Literal _x000D_ and _x000D_')
        self.assertEqual(shared[2]['value'],'rich & 字');self.assertEqual(shared[3]['value'],'')
        self.assertEqual(oracle(self.root/'empty.xlsx')['headers'],[])
        self.assertEqual(oracle(self.root/'date.xlsx')['rows'][0]['value'],'2020-01-02 03:04:05')
        numeric=oracle(self.root/'numbers.xlsx')['rows']
        self.assertIn({'id':'9','value':'9007199254740993'},numeric)
        self.assertEqual(sum(c['refusal'] is None for c in self.cases),12)

    def test_independent_comparison_rejects_numeric_drift_missing_rows_and_wrong_sheet(self):
        expected={'sheet_name':'Sheet','headers':['number'],'rows':[{'number':'1'}]}
        actual={'profile':'openpyxl-values-v1',**copy.deepcopy(expected)}
        compare_table(actual,expected)
        for key,value in [('rows',[{'number':'1.0'}]),('rows',[]),('sheet_name','First'),('headers',['col_0'])]:
            bad=copy.deepcopy(actual);bad[key]=value
            with self.assertRaises(AssertionError):compare_table(bad,expected)

    def test_bundled_unit_kit_matches_its_manifest(self):
        root=ROOT/'baseline/xlsx-reader-kit';manifest=json.loads((root/'manifest.json').read_text())
        for name,digest in manifest['files'].items():self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),digest,name)


if __name__=='__main__':unittest.main()
