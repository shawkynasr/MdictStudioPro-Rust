"""Source and boundary checks; native tests are authored in m3/txt-runtime."""
import unittest
from m3_shell import ROOT,check_adapter_lock
class TxtBuildContracts(unittest.TestCase):
 def test_routes_preserve_shared_budget_and_dictionary_reader_coordinator(self):
  original=(ROOT/'m2/cc-pack-runtime/src/lib.rs').read_text();new=(ROOT/'m3/txt-runtime/src/lib.rs').read_text()
  self.assertIn('Self::TxtPacking(_)=>Operation::CcPacking',new)
  start='fn error(code:ApiCode,message:&str)'
  self.assertEqual(original[original.index(start):].split('pub struct Runtime {')[0],new[new.index(start):].split('pub struct Runtime {')[0])
  for name in ['concise_disk','index_jobs','cc_packing','converters','txt','runner']:self.assertIn('../../../m2/cc-pack-runtime/src/'+name+'.rs',new)
 def test_registry_graphs_stay_accepted_and_adapter_uses_new_coordinator(self):
  self.assertTrue(check_adapter_lock()['no_unapproved_registry_versions'])
  self.assertTrue(check_adapter_lock(ROOT/'m3/txt-runtime/Cargo.lock')['no_unapproved_registry_versions'])
  manifest=(ROOT/'m3/native-adapter/Cargo.toml').read_text();self.assertIn('package = "studio-desktop-runtime"',manifest);self.assertIn('path = "../txt-runtime"',manifest)
 def test_txt_is_default_and_jsonl_remains_explicit(self):
  app=(ROOT/'m3/desktop/src/App.svelte').read_text()
  for text in ["sourceFormat = $state<'txt'|'jsonl'>('txt')","txtProfile = $state<TxtProfile>('canonical_v1')","request={kind:'txt_packing'",'id="source-format"','id="txt-profile"',"if(sessionId || mddId)throw"]:self.assertIn(text,app)
  self.assertNotIn("{t('inputHint')}",app)
 def test_streaming_preparation_and_commit_contract(self):
  code=(ROOT/'m3/txt-runtime/src/txt_packing.rs').read_text()
  for text in ['INPUT_CAP:u64=128*1024*1024','LINE_COUNT:usize=8_000_000','reader.fill_buf()','tempfile::NamedTempFile::new()','spool_bytes+json.len() as u64+1>INPUT_CAP','studio_large_io::execute','studio_cc_pack_io::execute','source_sha256:prepared.digest','matches_core_for_duplicates_crlf_bom','packing_share_exclusive_admission_with_readers']:self.assertIn(text,code)
  self.assertNotIn('read_to_string',code.split('#[cfg(test)]')[0]);self.assertNotIn('Command::new',code)
if __name__=='__main__':unittest.main()
