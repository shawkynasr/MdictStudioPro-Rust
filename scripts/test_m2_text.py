from pathlib import Path
import json
import tempfile
import unittest
from m2_text import ROOT,reference_rows,load_oracle,oracle_convert,extended_cedict,compare_bytes


class TextContracts(unittest.TestCase):
    def test_profiles_distinguish_body_span_from_structural_newline(self):
        source=b'\xef\xbb\xbfa\r\nbody\r\n\r\n</>\r\n'
        self.assertEqual(reference_rows(source,'canonical_v1'),[{'key':'a','text':'body\n'}])
        self.assertEqual(reference_rows(source,'legacy_body_span_v1'),[{'key':'a','text':'body\r\n\r\n'}])
        with self.assertRaises(AssertionError):reference_rows(b'a\nbody','canonical_v1')

    def test_actual_captured_cedict_oracle_and_extended_fixture_are_read_only(self):
        plugin=load_oracle()
        baseline=json.loads((ROOT/'baseline/cases.json').read_text())['cedict'].encode()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,data in [('baseline',baseline),('extended',extended_cedict())]:
                source=root/(name+'.u8');source.write_bytes(data);output=root/(name+'.txt')
                metrics=oracle_convert(plugin,source,output)
                self.assertEqual(source.read_bytes(),data)
                if name=='baseline':
                    self.assertEqual(output.read_bytes(),(ROOT/'baseline/expected/cc_cedict.txt').read_bytes())
                    self.assertEqual((metrics['primary_entries'],metrics['traditional_entries'],metrics['skipped_lines']),(5,2,1))
                else:
                    self.assertEqual((metrics['primary_entries'],metrics['traditional_entries'],metrics['skipped_lines']),(13,10,2))
                    self.assertIn(b'cc_def_pinyin',output.read_bytes())

    def test_byte_comparison_reports_first_difference_without_accepting_normalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'diff.json'
            compare_bytes(b'body\n',b'body\n',path);self.assertFalse(path.exists())
            with self.assertRaises(AssertionError):compare_bytes(b'body\n',b'body',path)
            self.assertEqual(json.loads(path.read_text())['first_different_byte'],4)


if __name__=='__main__':unittest.main()
