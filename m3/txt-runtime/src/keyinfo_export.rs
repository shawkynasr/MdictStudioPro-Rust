//! Additive M3 export route; preserve all M2 source and bounded-route ceilings.
use crate::{Error,ImportJob,Result};
pub(crate) fn execute(r:&studio_large_io::Request,job:&mut ImportJob<'_>)->Result<studio_large_io::Summary> {
 let request=match r {
  studio_large_io::Request::ExportTxt{source,destination}=>studio_export_io::Request::ExportTxt{source:source.clone(),destination:destination.clone()},
  studio_large_io::Request::ExportJsonl{source,destination}=>studio_export_io::Request::ExportJsonl{source:source.clone(),destination:destination.clone()},
  _=>return studio_large_io::execute(r,&studio_large_io::IoLimits::default(),&mut studio_large_io::ImportJob::new(job.id,job.token,&mut *job.progress)),
 };
 let old=studio_large_io::IoLimits::default();
 let limits=studio_export_io::IoLimits {max_records:old.max_records,max_decoded_bytes:old.max_decoded_bytes,max_entry_bytes:old.max_entry_bytes,max_plan_charge:old.max_plan_charge,max_input_bytes:old.max_input_bytes,max_output_bytes:old.max_output_bytes,..Default::default()};
 let s=studio_export_io::execute(&request,&limits,&mut studio_export_io::ImportJob::new(job.id,job.token,&mut *job.progress))
  .map_err(|e|Error {code:e.code,detail:e.detail,message:e.message,limit:e.limit.map(|l|studio_large_io::LimitFailure{name:l.name,value:l.value,max:l.max})})?;
 let profile=if s.metadata.get("GeneratedByEngineVersion").map(String::as_str)==Some("1.2"){"studio-v1-ascii-export-32-v1"}else if s.metadata.get("Encrypted").map(String::as_str)==Some("2"){"studio-v2-keyinfo-export-32-v1"}else{studio_large_io::PROFILE};
 Ok(studio_large_io::Summary {profile,operation:s.operation,records:s.records,key_bytes:s.key_bytes,payload_bytes:s.payload_bytes,framed_records_sha256:s.framed_records_sha256,file_bytes:s.file_bytes,source_sha256:s.source_sha256,metadata:s.metadata})
}

#[cfg(test)]mod tests {
 use super::*;
 use crate::{CancellationToken,ErrorCode};
 use std::{fs,path::Path};
 pub(super) fn check(source:&Path,out:&Path,expected:Option<&str>,profile:&str) {
  let token=CancellationToken::default();let before=fs::read(source).unwrap();
  let dest=out.join("export.jsonl");
  let receipt=execute(&studio_large_io::Request::ExportJsonl{source:source.into(),destination:dest.clone()},&mut ImportJob::new("keyinfo",&token,&mut |_|{})).unwrap();
  assert_eq!(receipt.profile,profile);assert_eq!(receipt.metadata["Encrypted"],if profile=="studio-v1-ascii-export-32-v1"{"No"}else{"2"});
  if let Some(want)=expected{assert_eq!(fs::read_to_string(&dest).unwrap(),want);}
  let txt=out.join("export.txt");let t=execute(&studio_large_io::Request::ExportTxt{source:source.into(),destination:txt.clone()},&mut ImportJob::new("txt",&token,&mut |_|{}));
  if expected.is_some(){assert_eq!(t.unwrap().framed_records_sha256,receipt.framed_records_sha256);}else if let Err(e)=t{assert_eq!(e.code,ErrorCode::UnrepresentableSource);assert!(!txt.exists());fs::write(out.join("txt-refusal.json"),serde_json::to_vec_pretty(&e).unwrap()).unwrap();}
  let db=out.join("export.db");let d=crate::mdx_database::execute(source,&db,&mut ImportJob::new("db",&token,&mut |_|{})).unwrap();assert_eq!(d.records,receipt.records);assert_eq!(d.source_sha256,receipt.source_sha256);assert_eq!(d.dictionary_metadata.as_ref(),Some(&receipt.metadata));
  fs::write(out.join("native-receipt.json"),serde_json::to_vec_pretty(&receipt).unwrap()).unwrap();
  let saved=fs::read(&dest).unwrap();assert_eq!(execute(&studio_large_io::Request::ExportJsonl{source:source.into(),destination:dest.clone()},&mut ImportJob::new("exists",&token,&mut |_|{})).unwrap_err().code,ErrorCode::DestinationExists);assert_eq!(fs::read(dest).unwrap(),saved);
  for phase in if profile=="studio-v1-ascii-export-32-v1"{vec!["snapshot","legacy_v1_snapshot","export_records","publish_file"]}else{vec!["snapshot","export_records","publish_file"]} {
   let stop=CancellationToken::default();let cancel=stop.clone();let dest=out.join(format!("cancel-{phase}.jsonl"));let mut cb=|p:crate::Progress|if p.phase==phase{cancel.cancel();};
   assert_eq!(execute(&studio_large_io::Request::ExportJsonl{source:source.into(),destination:dest.clone()},&mut ImportJob::new("cancel",&stop,&mut cb)).unwrap_err().code,ErrorCode::Cancelled);assert!(!dest.exists());
  }
  let stop=CancellationToken::default();let cancel=stop.clone();let dest=out.join("cancel.db");let mut cb=|p:crate::Progress|if p.phase=="database_commit"{cancel.cancel();};assert_eq!(crate::mdx_database::execute(source,&dest,&mut ImportJob::new("cancel-db",&stop,&mut cb)).unwrap_err().code,ErrorCode::Cancelled);assert!(!dest.exists());
  assert_eq!(fs::read(source).unwrap(),before);
 }
 #[test]fn encrypted_keyword_index_exports_and_database_preserve_physical_rows() {
  for (bytes,expected) in [(include_bytes!("../../fixtures/mdx-keyinfo/utf8.mdx").as_slice(),include_str!("../../fixtures/mdx-keyinfo/utf8.jsonl")),(include_bytes!("../../fixtures/mdx-keyinfo/utf16.mdx").as_slice(),include_str!("../../fixtures/mdx-keyinfo/utf16.jsonl"))] {
   let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.mdx");fs::write(&source,bytes).unwrap();check(&source,dir.path(),Some(expected),"studio-v2-keyinfo-export-32-v1");
  }
 }
 #[test]fn optional_real_keyword_index_sample() {
  let Some(source)=std::env::var_os("STUDIO_KEYINFO_SAMPLE")else{return;};let out=std::env::var_os("STUDIO_KEYINFO_OUTPUT").expect("Explicit fresh gate output");let out=Path::new(&out);fs::create_dir(out).unwrap();check(Path::new(&source),out,None,"studio-v2-keyinfo-export-32-v1");
 }
}

#[cfg(test)]mod legacy_tests {
 use super::*;use std::{fs,path::Path};
 #[test]fn legacy_v1_ascii_exports_and_database_preserve_duplicates_across_blocks() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("v1.mdx");fs::write(&source,include_bytes!("../../fixtures/mdx-v1-ascii/ascii.mdx")).unwrap();
  super::tests::check(&source,dir.path(),Some(include_str!("../../fixtures/mdx-v1-ascii/ascii.jsonl")),"studio-v1-ascii-export-32-v1");
 }
 #[test]fn optional_real_v1_ascii_sample() {
  let Some(source)=std::env::var_os("STUDIO_V1_ASCII_SAMPLE")else{return;};let output=std::env::var_os("STUDIO_V1_ASCII_OUTPUT").expect("Explicit fresh gate output");let out=Path::new(&output);fs::create_dir(out).unwrap();super::tests::check(Path::new(&source),out,None,"studio-v1-ascii-export-32-v1");
 }
}
