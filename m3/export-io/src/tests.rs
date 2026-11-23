use super::*;
use std::{fs,io::{Write,BufRead,BufReader},path::Path};

#[test]fn extended_export_streams_beyond_96_mib_and_keeps_default_failure_atomic() {
 let d=tempfile::tempdir().unwrap();let source=d.path().join("extended.mdx");
 fs::write(&source,include_bytes!("../../fixtures/extended-export/synthetic-145.mdx")).unwrap();
 let body="x".repeat(1024*1024);
 let token=CancellationToken::default();
 let blocked=d.path().join("blocked.jsonl");
 let error=execute(&Request::ExportJsonl {source:source.clone(),destination:blocked.clone()},&IoLimits::default(),&mut ImportJob::new("default",&token,&mut |_|{})).unwrap_err();
 assert_eq!(error.code,ErrorCode::LimitExceeded);let limit=error.limit.unwrap();assert_eq!(limit.name,"decoded_text_bytes");assert_eq!(limit.max,96*1024*1024);assert!(limit.value>limit.max);assert!(!blocked.exists());
 for txt in [false,true] {
  let destination=d.path().join(if txt {"extended.txt"}else{"extended.jsonl"});
  let request=if txt {Request::ExportTxt {source:source.clone(),destination:destination.clone()}}else{Request::ExportJsonl {source:source.clone(),destination:destination.clone()}};
  let receipt=execute_profile(&request,&IoLimits::for_profile(ExportProfile::Extended),ExportProfile::Extended,&mut ImportJob::new("extended",&token,&mut |_|{})).unwrap();
  assert_eq!(receipt.profile,"studio-m3-stream-export-256-v1");assert_eq!(receipt.records,145);assert_eq!(receipt.payload_bytes,145*1024*1024);
  if !txt {
   let mut rows=0;
   for line in BufReader::new(fs::File::open(&destination).unwrap()).lines() {let row:serde_json::Value=serde_json::from_str(&line.unwrap()).unwrap();assert_eq!(row["text"].as_str().unwrap(),body);rows+=1;}
   assert_eq!(rows,145);
  }
 }
 assert_eq!(fs::read_dir(d.path()).unwrap().count(),3); // source + two complete exports, no failed stages
}

#[test]fn extended_export_lowered_cap_cancellation_and_no_clobber_stay_atomic() {
 let d=tempfile::tempdir().unwrap();let source=fixture(d.path());let token=CancellationToken::default();
 let destination=d.path().join("existing.jsonl");fs::write(&destination,b"keep").unwrap();
 let request=Request::ExportJsonl {source:source.clone(),destination:destination.clone()};
 assert_eq!(execute_profile(&request,&IoLimits::for_profile(ExportProfile::Extended),ExportProfile::Extended,&mut ImportJob::new("existing",&token,&mut |_|{})).unwrap_err().code,ErrorCode::DestinationExists);
 assert_eq!(fs::read(&destination).unwrap(),b"keep");
 let mut limits=IoLimits::for_profile(ExportProfile::Extended);limits.max_decoded_bytes=1;
 let cap=d.path().join("cap.jsonl");
 let error=execute_profile(&Request::ExportJsonl {source:source.clone(),destination:cap.clone()},&limits,ExportProfile::Extended,&mut ImportJob::new("cap",&token,&mut |_|{})).unwrap_err();
 assert_eq!(error.limit.unwrap().max,1);assert!(!cap.exists());
 let mut raised=IoLimits::for_profile(ExportProfile::Extended);raised.max_decoded_bytes+=1;
 assert!(execute_profile(&request,&raised,ExportProfile::Extended,&mut ImportJob::new("raised",&token,&mut |_|{})).is_err());
 for phase in ["export_records","publish_file"] {
  let token=CancellationToken::default();let cancel=token.clone();let mut cb=|p:Progress|if p.phase==phase {cancel.cancel();};
  let destination=d.path().join("cancel.txt");
  assert_eq!(execute_profile(&Request::ExportTxt {source:source.clone(),destination:destination.clone()},&IoLimits::for_profile(ExportProfile::Extended),ExportProfile::Extended,&mut ImportJob::new("cancel",&token,&mut cb)).unwrap_err().code,ErrorCode::Cancelled);assert!(!destination.exists());
 }
}
fn fixture(dir:&Path)->std::path::PathBuf {
 let source=dir.join("source.jsonl");fs::write(&source,"{\"key\":\"字\",\"text\":\"first\\n\"}\n{\"key\":\"字\",\"text\":\"\"}\n").unwrap();
 let mdx=dir.join("source.mdx");let token=CancellationToken::default();
 studio_cc_pack_io::execute(&studio_cc_pack_io::Request::PackMdx {source,destination:mdx.clone(),encoding:studio_core::Encoding::Utf8,metadata:studio_cc_pack_io::Metadata {title:"export".into(),..Default::default()}},&studio_cc_pack_io::IoLimits::default(),&mut studio_cc_pack_io::ImportJob::new("pack",&token,&mut |_|{})).unwrap();mdx
}
#[test]fn only_exports_are_admitted_and_lowered_caps_still_fail_without_output() {
 let d=tempfile::tempdir().unwrap();let source=fixture(d.path());let token=CancellationToken::default();let destination=d.path().join("out.jsonl");
 let packing=Request::PackMdx {source:source.clone(),destination:destination.clone(),encoding:studio_core::Encoding::Utf8,metadata:Metadata::default()};
 assert_eq!(execute(&packing,&IoLimits::default(),&mut ImportJob::new("reject",&token,&mut |_|{})).unwrap_err().code,ErrorCode::UnsupportedPolicy);
 let request=Request::ExportJsonl {source,destination:destination.clone()};let mut limits=IoLimits::default();limits.max_records=1;
 assert_eq!(execute(&request,&limits,&mut ImportJob::new("lower",&token,&mut |_|{})).unwrap_err().code,ErrorCode::LimitExceeded);assert!(!destination.exists());
 let mut too_high=IoLimits::default();too_high.max_decoded_bytes+=1;assert!(execute(&request,&too_high,&mut ImportJob::new("raise",&token,&mut |_|{})).is_err());assert!(!destination.exists());
}
#[test]fn export_cancellation_before_commit_leaves_no_file_and_late_cancel_keeps_success() {
 for phase in ["export_records","publish_file"] {
  let d=tempfile::tempdir().unwrap();let source=fixture(d.path());let destination=d.path().join("cancel.txt");let token=CancellationToken::default();let cancel=token.clone();let mut cb=|p:Progress|if p.phase==phase {cancel.cancel();};
  assert_eq!(execute(&Request::ExportTxt {source,destination:destination.clone()},&IoLimits::default(),&mut ImportJob::new("cancel",&token,&mut cb)).unwrap_err().code,ErrorCode::Cancelled);assert!(!destination.exists());
 }
 let d=tempfile::tempdir().unwrap();let source=fixture(d.path());let destination=d.path().join("done.txt");let token=CancellationToken::default();
 let receipt=execute(&Request::ExportTxt {source,destination:destination.clone()},&IoLimits::default(),&mut ImportJob::new("done",&token,&mut |_|{})).unwrap();token.cancel();assert_eq!(receipt.records,2);assert!(destination.exists());
}
#[test]fn streaming_export_really_exceeds_old_32_mib_ceiling() {
 let d=tempfile::tempdir().unwrap();let source=d.path().join("large.jsonl");let mut file=fs::File::create(&source).unwrap();let body="x".repeat(1024*1024);
 for i in 0..33 {serde_json::to_writer(&mut file,&serde_json::json!({"key":format!("word-{i:02}"),"text":&body})).unwrap();file.write_all(b"\n").unwrap();}file.flush().unwrap();drop(file);
 let mdx=d.path().join("large.mdx");let token=CancellationToken::default();
 studio_cc_pack_io::execute(&studio_cc_pack_io::Request::PackMdx {source,destination:mdx.clone(),encoding:studio_core::Encoding::Utf8,metadata:studio_cc_pack_io::Metadata::default()},&studio_cc_pack_io::IoLimits::default(),&mut studio_cc_pack_io::ImportJob::new("pack-large",&token,&mut |_|{})).unwrap();
 let output=d.path().join("export.jsonl");let receipt=execute(&Request::ExportJsonl {source:mdx,destination:output.clone()},&IoLimits::default(),&mut ImportJob::new("export-large",&token,&mut |_|{})).unwrap();
 assert_eq!(receipt.records,33);assert_eq!(receipt.payload_bytes,33*1024*1024);assert!(receipt.payload_bytes>32*1024*1024);assert_eq!(IoLimits::default().max_decoded_bytes,96*1024*1024);
 let mut count=0;for line in BufReader::new(fs::File::open(output).unwrap()).lines(){let row:serde_json::Value=serde_json::from_str(&line.unwrap()).unwrap();assert_eq!(row["text"].as_str().unwrap().len(),1024*1024);count+=1;}assert_eq!(count,33);
}

#[test]fn keyword_index_policy_limits_corruption_and_source_integrity() {
 let seed=include_bytes!("../../fixtures/mdx-keyinfo/utf8.mdx");
 let d=tempfile::tempdir().unwrap();let source=d.path().join("source.mdx");fs::write(&source,seed).unwrap();let token=CancellationToken::default();
 let mut limits=IoLimits::default();limits.max_records=4;let dest=d.path().join("cap.jsonl");assert_eq!(execute(&Request::ExportJsonl{source:source.clone(),destination:dest.clone()},&limits,&mut ImportJob::new("cap",&token,&mut |_|{})).unwrap_err().code,ErrorCode::LimitExceeded);assert!(!dest.exists());
 limits=IoLimits::default();limits.max_decoded_bytes=1;let dest=d.path().join("bytes.jsonl");assert_eq!(execute(&Request::ExportJsonl{source:source.clone(),destination:dest.clone()},&limits,&mut ImportJob::new("bytes",&token,&mut |_|{})).unwrap_err().code,ErrorCode::LimitExceeded);assert!(!dest.exists());
 let header_size=u32::from_be_bytes(seed[..4].try_into().unwrap()) as usize;
 for (name,offset) in [("header",6),("summary",4+header_size+8),("keyinfo",4+header_size+8+44+10)] {
  let mut broken=seed.to_vec();broken[offset]^=1;let path=d.path().join(format!("{name}.mdx"));fs::write(&path,&broken).unwrap();let dest=d.path().join(format!("{name}.jsonl"));assert!(execute(&Request::ExportJsonl{source:path.clone(),destination:dest.clone()},&IoLimits::default(),&mut ImportJob::new("broken",&token,&mut |_|{})).is_err());assert!(!dest.exists());assert_eq!(fs::read(path).unwrap(),broken);
 }
 assert_eq!(fs::read(source).unwrap(),seed);
}

#[test]fn legacy_nonascii_and_corruption_fail_without_publication() {
 let d=tempfile::tempdir().unwrap();let token=CancellationToken::default();
 for (i,bytes) in [include_bytes!("../../fixtures/mdx-v1-ascii/nonascii.mdx").as_slice(),&include_bytes!("../../fixtures/mdx-v1-ascii/ascii.mdx")[..50]].into_iter().enumerate() {
  let source=d.path().join(format!("bad-{i}.mdx"));let destination=d.path().join(format!("bad-{i}.jsonl"));fs::write(&source,bytes).unwrap();assert!(execute(&Request::ExportJsonl{source:source.clone(),destination:destination.clone()},&IoLimits::default(),&mut ImportJob::new("reject",&token,&mut |_|{})).is_err());assert!(!destination.exists());assert_eq!(fs::read(source).unwrap(),bytes);
 }
 let source=d.path().join("cap.mdx");fs::write(&source,include_bytes!("../../fixtures/mdx-v1-ascii/ascii.mdx")).unwrap();let destination=d.path().join("cap.jsonl");let mut limits=IoLimits::default();limits.max_records=4;assert_eq!(execute(&Request::ExportJsonl{source,destination:destination.clone()},&limits,&mut ImportJob::new("cap",&token,&mut |_|{})).unwrap_err().code,ErrorCode::LimitExceeded);assert!(!destination.exists());
}
