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
  self.assertIn("exportProfile = $state<'large'|'bounded'>('large')",app)
  self.assertIn("request={kind:'large_export'",app)
  runtime=(ROOT/'m3/txt-runtime/src/lib.rs').read_text()
  self.assertIn('Self::LargeExport(_)=>Operation::CcPacking',runtime)
  backend=(ROOT/'m3/txt-runtime/src/large_export.rs').read_text()
  self.assertIn('studio_export_io::IoLimits::default()',backend)
  self.assertIn('studio_export_io::execute',backend)
 def test_large_export_is_derived_from_streaming_io_with_an_export_only_guard(self):
  original=(ROOT/'m2/large-io/src/io.rs').read_text()
  expected=original.replace('max_records:100000,max_decoded_bytes:32*1024*1024','max_records:250000,max_decoded_bytes:96*1024*1024').replace('job.check()?;limits.validate()?;destination(request.destination())?;', 'job.check()?;limits.validate()?;if !matches!(request,Request::ExportTxt {..}|Request::ExportJsonl {..}) {return Err(crate::unsupported("This profile accepts MDX TXT/JSONL exports only"));}destination(request.destination())?;')
  # The v1 ASCII view is an additive, checksum-preserving decoder adapter.
  # Keep the full derivation check and bind its two exact export-only edits.
  expected=expected.replace('let file=MdxFile::open_with_options(snapshot.path(),&options)?;if file.len()>limits.max_records as u64','let legacy=crate::header::legacy_ascii_view(&snapshot,&header,job)?;let file=MdxFile::open_with_options(legacy.as_ref().map_or(snapshot.path(),|f|f.path()),&options)?;if file.len()>limits.max_records as u64')
  expected=expected.replace('let e=entry?;if e.ordinal().get()!=expected.records as u64','let e=entry?;if legacy.is_some()&&(!e.key().is_ascii()||!e.text().is_ascii()){return Err(crate::unsupported("Non-ASCII v1.2 ISO8859-1 content requires a separately qualified encoding profile"));}if e.ordinal().get()!=expected.records as u64')
  self.assertEqual((ROOT/'m3/export-io/src/io.rs').read_text(),expected)
  self.assertIn('streaming_export_really_exceeds_old_32_mib_ceiling',(ROOT/'m3/export-io/src/tests.rs').read_text())
  from m3_shell import check_adapter_lock
  self.assertTrue(check_adapter_lock(ROOT/'m3/export-io/Cargo.lock')['no_unapproved_registry_versions'])
if __name__=='__main__':unittest.main()
