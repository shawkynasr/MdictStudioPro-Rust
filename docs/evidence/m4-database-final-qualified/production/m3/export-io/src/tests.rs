use super::*;
use std::{fs,io::{Write,BufRead,BufReader},path::Path};
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
