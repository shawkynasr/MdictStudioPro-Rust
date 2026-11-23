import json
from pathlib import Path
import tempfile
import unittest
from m3_shell import ROOT
from verify_gui_extraction import txt_rows,jsonl_rows,compare_entries,compare_resources
class ExtractGuiChecks(unittest.TestCase):
 def test_fixture_duplicates_blank_bodies_and_crlf_are_compared_exactly(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'source.txt';path.write_bytes(b'\xef\xbb\xbfword\r\nfirst\r\n\r\n</>\r\nword\r\n\r\n</>')
   rows=txt_rows(path);self.assertEqual(rows,[('word','first\n'),('word','')]);self.assertEqual(compare_entries(rows,rows)['status'],'passed')
   self.assertEqual(compare_entries(rows,list(reversed(rows)))['status'],'failed')
   self.assertEqual(compare_entries(rows,rows+rows[:1])['status'],'failed')
   legacy=txt_rows(path,'legacy_body_span_v1');self.assertEqual(legacy[0][1],'first\r\n\r\n')
 def test_malformed_export_and_source_are_not_silently_accepted(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'input';path.write_bytes(b'word\nbody\n')
   with self.assertRaises(ValueError):txt_rows(path)
   for value in ['110\n','{"key":"a","text":1}\n','{"key":"a","text":"x","text":"y"}\n']:
    path.write_text(value)
    with self.assertRaises(ValueError):jsonl_rows(path)
 def test_nested_binary_differences_and_extra_paths_are_detected(self):
  with tempfile.TemporaryDirectory() as d:
   a=Path(d)/'original';b=Path(d)/'extracted'
   for root in [a,b]:
    (root/'fonts').mkdir(parents=True);(root/'fonts/字.ttf').write_bytes(bytes([0,255,1,128]));(root/'empty').write_bytes(b'');(root/'.DS_Store').write_bytes(b'ignored')
   result=compare_resources(a,b);self.assertEqual((result['status'],result['expected_files']),('passed',2))
   (b/'fonts/字.ttf').write_bytes(b'changed');self.assertEqual(compare_resources(a,b)['changed_bytes_paths'],['fonts/字.ttf'])
   (b/'extra').write_bytes(b'x');self.assertEqual(compare_resources(a,b)['unexpected_paths'],['extra'])
 def test_extract_gui_routes_and_destination_controls(self):
  app=(ROOT/'m3/desktop/src/App.svelte').read_text()
  for text in ['chooseExtractParent','resourceDestination(extractParent,extractFolder)',"destination=exportFilePath(destination,extraction)","operation:extraction === 'txt' ? 'export_txt' : 'export_jsonl'","{ kind:'extraction', request:{ source, destination } }",'id="extract-folder"','id="extract-parent"']:self.assertIn(text,app)
  self.assertIn('resourceFolderName(result)',app)
  self.assertIn("exportProfile = $state<'large'|'bounded'|'extended'>('large')",app)
  self.assertIn("request={kind:'large_export'",app)
  runtime=(ROOT/'m3/txt-runtime/src/lib.rs').read_text()
  self.assertIn('Self::LargeExport(_)=>Operation::CcPacking',runtime)
  backend=(ROOT/'m3/txt-runtime/src/large_export.rs').read_text()
  self.assertIn('studio_export_io::IoLimits::for_profile(r.profile)',backend)
  self.assertIn('studio_export_io::execute',backend)
 def test_large_export_is_derived_from_streaming_io_with_an_export_only_guard(self):
  original=(ROOT/'m2/large-io/src/io.rs').read_text()
  current=(ROOT/'m3/export-io/src/io.rs').read_text()
  # Shared parser, snapshot, hashing, staging and no-clobber helpers stay exact.
  # Export execution, row-limit reporting and profile selection are now explicit M3 additions.
  import re
  def functions(text):
   matches=list(re.finditer(r'^fn (\w+)\(',text,re.M))
   return {m[1]:text[m.start():matches[i+1].start() if i+1<len(matches) else len(text)].strip() for i,m in enumerate(matches)}
  old,new=functions(original),functions(current)
  for name in ['key','txt_row','parse_txt','pack']:
   self.assertEqual(new[name],old[name],name)
  self.assertIn('if !matches!(request,Request::ExportTxt {..}|Request::ExportJsonl {..})',current)
  self.assertIn('execute_profile(request,limits,ExportProfile::Large,job)',current)
  self.assertIn('limits.validate(profile)?',current)
  self.assertIn('max_records:250000,max_decoded_bytes:96*1024*1024',current)
  self.assertIn('limits.max_decoded_bytes=256*1024*1024',current)
  self.assertIn('limits.max_output_bytes=512*1024*1024',current)
  self.assertIn('expected.records as u64!=file.len()||file.memory_usage()?.locator_bytes()!=0',current)
  self.assertIn('if found!=digest||want!=(found.0,found.1,found.2)',current)
  self.assertIn('legacy.is_some()&&(!e.key().is_ascii()||!e.text().is_ascii())',current)
  self.assertIn('extended_export_streams_beyond_96_mib_and_keeps_default_failure_atomic',(ROOT/'m3/export-io/src/tests.rs').read_text())
  self.assertIn('streaming_export_really_exceeds_old_32_mib_ceiling',(ROOT/'m3/export-io/src/tests.rs').read_text())
  from m3_shell import check_adapter_lock
  self.assertTrue(check_adapter_lock(ROOT/'m3/export-io/Cargo.lock')['no_unapproved_registry_versions'])
if __name__=='__main__':unittest.main()
