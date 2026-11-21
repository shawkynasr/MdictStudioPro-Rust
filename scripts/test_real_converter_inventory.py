import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from openpyxl import Workbook
from m2_real_converter_inventory import PROFILE,protected_sources,text_profile,workbook_profile,inventory,selection_template
class RealConverterInventoryContracts(unittest.TestCase):
    def test_sparse_rectangle_uses_native_allocation_geometry_not_only_stored_cells(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sparse.xlsx';b=Workbook();s=b.active;s['A1']='字詞名';s['C3']='private value';b.save(p);b.close();sheet=workbook_profile(p,{**PROFILE,'workbook_cells':4})['worksheets'][0];self.assertEqual(sheet['observed_cells'],2);self.assertEqual(sheet['declared_rectangle_cells'],9);self.assertIn('workbook_rectangle_cell_cap',sheet['blockers'])
    def test_protected_sources_remain_unchanged(self):self.assertEqual(len(protected_sources()),214)
    def test_cc_cedict_counts_and_entry_cap_without_exposing_definitions(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cedict.u8';p.write_text('# comment\n傳 传 [chuan2] /private definition/\n和 和 [he2] /and/\nbad line\n',encoding='utf-8');data=p.read_bytes();r=text_profile(p,{**PROFILE,'entries':2});self.assertEqual(r['estimated_output_records'],3);self.assertEqual(r['matching_lines'],2);self.assertEqual(r['comments'],1);self.assertIn('converted_entry_cap',r['blockers']);self.assertNotIn('private definition',json.dumps(r));self.assertEqual(p.read_bytes(),data)
    def test_bom_and_long_line_are_explicit_profile_blockers(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source.txt';p.write_bytes(b'\xef\xbb\xbf'+b'a b [a1] /definition/\n');self.assertIn('utf8_bom_outside_native_profile',text_profile(p)['blockers']);r=text_profile(p,{**PROFILE,'line_bytes':8});self.assertFalse(r['scan_complete']);self.assertIn('source_line_or_line_byte_cap',r['blockers'])
    def test_moe_headers_propose_alternatives_without_selecting_or_leaking_cells(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'source.xlsx';b=Workbook();s=b.active;s.append(['字詞名','釋義','private header']);s.append(['字','private definition','secret']);b.save(p);b.close();r=workbook_profile(p);self.assertEqual(r['possible_converters'],['moe_concise','moe_revised','moe_revised_wfg']);self.assertNotIn('private definition',json.dumps(r));self.assertNotIn('private header',json.dumps(r));template=selection_template([{'file':p.name,'blockers':[],'profile':r}]);self.assertEqual(len(template['cases']),3);self.assertTrue(all(not c['selected'] for c in template['cases']))
    def test_zip_expansion_is_checked_before_worksheet_read(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'large.xlsx'
            with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('sheet.xml','x'*1024)
            r=workbook_profile(p,{**PROFILE,'workbook_part_bytes':10});self.assertIn('workbook_part_byte_cap',r['blockers']);self.assertEqual(r['worksheets'],[])
    def test_row_scan_stops_at_lowered_profile_and_counts_are_lower_bounds(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'rows.xlsx';b=Workbook();s=b.active;s.append(['單字']);s.append(['甲']);s.append(['乙']);s.append(['丙']);b.save(p);b.close();sheet=workbook_profile(p,{**PROFILE,'workbook_rows':2})['worksheets'][0];self.assertFalse(sheet['scan_complete']);self.assertIn('workbook_row_cap',sheet['blockers']);self.assertEqual(sheet['observed_row_coordinates'],3)
    def test_selection_stays_in_explicit_input_directory_and_no_files_is_actionable(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'sources';source.mkdir()
            with self.assertRaises(AssertionError):inventory(source)
            outside=root/'outside.u8';outside.write_text('a a [a1] /a/\n');(source/'linked.u8').symlink_to(outside)
            with self.assertRaises(AssertionError):inventory(source)
if __name__=='__main__':unittest.main()
