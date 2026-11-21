"""Folder-route contracts; native binary/resource tests run on the Mac."""
import unittest
from m3_shell import ROOT,check_adapter_lock
class FolderBuildContracts(unittest.TestCase):
 def test_folder_and_packing_share_unchanged_coordinator_budget(self):
  old=(ROOT/'m2/cc-pack-runtime/src/lib.rs').read_text();new=(ROOT/'m3/txt-runtime/src/lib.rs').read_text();start='fn error(code:ApiCode,message:&str)'
  self.assertEqual(old[old.index(start):].split('pub struct Runtime {')[0],new[new.index(start):].split('pub struct Runtime {')[0])
  for text in ['Self::FolderPacking(_)=>Operation::CcPacking','Self::FolderPacking(r)=>{paths.push(&r.resource_root)','folder_packing::execute(r,job).map(Response::FolderPacking)']:self.assertIn(text,new)
  self.assertTrue(check_adapter_lock()['no_unapproved_registry_versions']);self.assertTrue(check_adapter_lock(ROOT/'m3/txt-runtime/Cargo.lock')['no_unapproved_registry_versions'])
 def test_scan_is_bounded_and_accepted_packer_keeps_payload_boundary(self):
  code=(ROOT/'m3/txt-runtime/src/folder_packing.rs').read_text();body=code.split('#[cfg(all(test,unix))]')[0]
  for text in ['fs::symlink_metadata','file_type().is_symlink()','scan.entries>limits.entries','scan.plan_bytes>limits.plan_bytes','scan.manifest_bytes>limits.manifest_bytes','metadata.len()>limits.file_bytes','scan.decoded>limits.decoded_bytes','studio_core::resource_relative_path','Case-aliased resource path','tempfile::NamedTempFile::new()','studio_large_io::Request::PackMdd','studio_large_io::execute','casing::Casing::pinned16()']:self.assertIn(text,body)
  self.assertNotIn('read_to_end',body);self.assertNotIn('read_to_string',body)
  for text in ['manifest_is_deterministic','roundtrip_preserves_nested_unicode_empty_and_binary','folder_preparation_and_packing_cancel_under_one_exclusive_lease']:self.assertIn(text,code)
 def test_folder_default_uses_directory_picker_and_no_user_manifest(self):
  app=(ROOT/'m3/desktop/src/App.svelte').read_text()
  for text in ["mddInput = $state<'folder'|'manifest'>('folder')","folderBuild()?resourceRoot:source","pickInput(folderBuild()?'root':'source')","request={kind:'folder_packing'",'id="mdd-input"',"mddInput==='manifest'"]:self.assertIn(text,app)
  self.assertIn('dictionaryOutputPath(destination',app)
 def test_retention_error_exposes_explicit_dismiss_action(self):
  app=(ROOT/'m3/desktop/src/App.svelte').read_text()
  self.assertIn("issue.code==='retention_full'",app);self.assertIn('async function dismissFinished()',app);self.assertIn('action(dismissFinished)',app)
  self.assertIn('for(const job of jobs)await forget(job.job_id)',app)
if __name__=='__main__':unittest.main()
