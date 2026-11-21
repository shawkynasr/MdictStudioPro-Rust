use super::*;
use std::{fs,io::Write,path::Path};
fn fixture(dir:&Path)->std::path::PathBuf {
 let p=dir.join("input.jsonl");let mut f=fs::File::create(&p).unwrap();for i in 0..4096 {let key=match i%8 {0=>"Apple".into(),1=>"apple".into(),2=>"ΣΟΣ".into(),3=>"مرحبا".into(),4=>"𠀀".into(),_=>format!("key-{i:08}")};let text=if i==0 {String::new()}else if i==1 {"large".repeat(30000)}else{format!("`1`definition 字 {i}\n\n{}","body".repeat(32))};serde_json::to_writer(&mut f,&serde_json::json!({"key":key,"text":text})).unwrap();f.write_all(b"\n").unwrap();}p
}
fn meta()->Metadata {Metadata {title:"字 مرحبا & title".into(),description:"<description>".into(),stylesheet:"1\n<b>\n</b>\n".into(),extra:std::collections::BTreeMap::new()}}
fn req(source:&Path,destination:&Path,encoding:Encoding)->Request {Request::PackMdx {source:source.into(),destination:destination.into(),encoding,metadata:meta()}}
#[test]fn block_spooled_writer_is_byte_identical_to_qualified_writer_for_both_encodings() {
 for encoding in [Encoding::Utf8,Encoding::Utf16] {
  let dir=tempfile::tempdir().unwrap();let source=fixture(dir.path());let old=dir.path().join("old.mdx");let new=dir.path().join("new.mdx");let token=CancellationToken::default();let mut cb=|_|{};
  let old_request=studio_large_io::Request::PackMdx {source:source.clone(),destination:old.clone(),encoding,metadata:studio_large_io::Metadata {title:meta().title,description:meta().description,stylesheet:meta().stylesheet,extra:meta().extra}};
  let expected=studio_large_io::execute(&old_request,&studio_large_io::IoLimits::default(),&mut studio_large_io::ImportJob::new("old",&token,&mut cb)).unwrap();let actual=execute(&req(&source,&new,encoding),&IoLimits::default(),&mut ImportJob::new("new",&token,&mut cb)).unwrap();
  assert_eq!(fs::read(&old).unwrap(),fs::read(&new).unwrap());assert_eq!(actual.framed_records_sha256,expected.framed_records_sha256);assert_eq!(actual.records,4096);assert_eq!(actual.metadata,expected.metadata);
 }
}
#[test]fn cancellation_at_spooling_compression_assembly_verify_and_precommit_leaves_no_output() {
 for phase in ["input_snapshot","load_records","block_entries","block_compress","assemble_dictionary","verify_records","publish_file"] {
  let dir=tempfile::tempdir().unwrap();let source=fixture(dir.path());let destination=dir.path().join("cancel.mdx");let token=CancellationToken::default();let cancel=token.clone();let mut observed=false;let mut cb=|p:Progress|if p.phase==phase {observed=true;cancel.cancel();};let error=execute(&req(&source,&destination,Encoding::Utf16),&IoLimits::default(),&mut ImportJob::new("cancel",&token,&mut cb)).unwrap_err();assert!(observed);assert_eq!(error.code,ErrorCode::Cancelled);assert!(!destination.exists());assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);
 }
}
#[test]fn profile_growth_overwrite_and_non_MDX_operations_are_refused() {
 let dir=tempfile::tempdir().unwrap();let source=fixture(dir.path());let destination=dir.path().join("out.mdx");let token=CancellationToken::default();let mut cb=|_|{};
 for limits in [IoLimits {max_records:1,..Default::default()},IoLimits {max_decoded_bytes:4,..Default::default()},IoLimits {max_plan_charge:1,..Default::default()},IoLimits {max_output_bytes:16,..Default::default()}] {assert_eq!(execute(&req(&source,&destination,Encoding::Utf8),&limits,&mut ImportJob::new("low",&token,&mut cb)).unwrap_err().code,ErrorCode::LimitExceeded);assert!(!destination.exists());}
 assert!(Tighten {records:Some(250001),..Default::default()}.limits().is_err());assert!(Tighten {decoded_bytes:Some(96*1024*1024+1),..Default::default()}.limits().is_err());
 execute(&req(&source,&destination,Encoding::Utf8),&IoLimits::default(),&mut ImportJob::new("ok",&token,&mut cb)).unwrap();let before=fs::read(&destination).unwrap();assert_eq!(execute(&req(&source,&destination,Encoding::Utf8),&IoLimits::default(),&mut ImportJob::new("overwrite",&token,&mut cb)).unwrap_err().code,ErrorCode::DestinationExists);assert_eq!(before,fs::read(&destination).unwrap());
 let request=Request::ExportJsonl {source:destination,destination:dir.path().join("export")};assert_eq!(execute(&request,&IoLimits::default(),&mut ImportJob::new("wrong",&token,&mut cb)).unwrap_err().code,ErrorCode::UnsupportedPolicy);
}
