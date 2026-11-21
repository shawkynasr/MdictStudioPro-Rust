use super::*;
use std::path::Path;
fn make(path:&Path,rows:&[(&str,Vec<u8>)]) {
 let mut b=mdictlib::MddBuilder::with_options(mdictlib::WriteOptions::new().with_legacy_sort(mdictlib::LegacySort::PreserveInput).with_record_block_target_bytes(65536));for (key,bytes) in rows {b.add_resource(key,bytes).unwrap();}b.finish(&mut std::fs::File::create(path).unwrap()).unwrap();
}
#[test]fn resources_larger_than_materialization_cap_and_empty_files_extract_exactly() {
 let temp=tempfile::tempdir().unwrap();let src=temp.path().join("a.mdd");let dst=temp.path().join("out");let payload=vec![0x89;3*1024*1024];make(&src,&[("\\images\\big.bin",payload.clone()),("empty.bin",vec![])]);let token=CancellationToken::default();let mut events=Vec::new();let mut cb=|p:Progress|events.push(p.phase);let receipt=extract_mdd(&src,&dst,&ExtractLimits::default(),&mut ImportJob::new("large",&token,&mut cb)).unwrap();drop(cb);
 assert_eq!(std::fs::read(dst.join("images/big.bin")).unwrap(),payload);assert_eq!(std::fs::metadata(dst.join("empty.bin")).unwrap().len(),0);assert_eq!(receipt.resources,2);assert_eq!(receipt.materialized_record_limit,0);assert_eq!(receipt.locator_bytes,0);assert_eq!(events.last().map(String::as_str),Some("publish_directory"));
}
#[test]fn mid_copy_cancellation_rolls_back_staging_directory() {
 let temp=tempfile::tempdir().unwrap();let src=temp.path().join("a.mdd");let dst=temp.path().join("out");make(&src,&[("big.bin",vec![7;3*1024*1024])]);let token=CancellationToken::default();let stop=token.clone();let mut cb=|p:Progress|if p.phase=="copy_resource"&&p.completed>=65536 {stop.cancel();};let e=extract_mdd(&src,&dst,&ExtractLimits::default(),&mut ImportJob::new("cancel",&token,&mut cb)).unwrap_err();assert_eq!(e.code,ErrorCode::Cancelled);assert!(!dst.exists());assert_eq!(std::fs::read_dir(temp.path()).unwrap().count(),1);
}
#[test]fn unsafe_names_aliases_and_file_directory_conflicts_refuse_before_publication() {
 for keys in [vec!["../escape"],vec!["CON.txt"],vec!["a.bin","A.bin"],vec!["a","a/b"],vec!["a","a"],vec!["//server/share"]] {
  let temp=tempfile::tempdir().unwrap();let src=temp.path().join("a.mdd");let dst=temp.path().join("out");make(&src,&keys.iter().map(|k|(*k,vec![1])).collect::<Vec<_>>());let e=extract_mdd(&src,&dst,&ExtractLimits::default(),&mut ImportJob::new("paths",&CancellationToken::default(),&mut |_|{})).unwrap_err();assert!(matches!(e.code,ErrorCode::UnsafePath|ErrorCode::PathCollision));assert!(!dst.exists());assert_eq!(std::fs::read_dir(temp.path()).unwrap().count(),1);
 }
}
#[test]fn plan_and_payload_budgets_are_enforced_before_output() {
 let temp=tempfile::tempdir().unwrap();let src=temp.path().join("a.mdd");make(&src,&[("a/b",vec![1;100])]);
 for mode in 0..5 {let dst=temp.path().join(format!("out-{mode}"));let mut limits=ExtractLimits::default();match mode {0=>limits.max_resources=0,1=>limits.max_resource_bytes=1,2=>limits.max_output_bytes=1,3=>limits.max_plan_charge=1,_=>limits.max_nodes=0};let e=extract_mdd(&src,&dst,&limits,&mut ImportJob::new("limits",&CancellationToken::default(),&mut |_|{})).unwrap_err();assert_eq!(e.code,ErrorCode::LimitExceeded);assert!(!dst.exists());}
}
#[test]fn destination_appearing_at_commit_is_not_replaced() {
 let temp=tempfile::tempdir().unwrap();let src=temp.path().join("a.mdd");let dst=temp.path().join("out");make(&src,&[("ok",vec![1,2,3])]);let mut cb=|p:Progress|if p.phase=="publish_directory" {std::fs::create_dir(&dst).unwrap();std::fs::write(dst.join("sentinel"),b"keep").unwrap();};let e=extract_mdd(&src,&dst,&ExtractLimits::default(),&mut ImportJob::new("exists",&CancellationToken::default(),&mut cb)).unwrap_err();assert_eq!(e.code,ErrorCode::DestinationExists);assert_eq!(std::fs::read(dst.join("sentinel")).unwrap(),b"keep");assert_eq!(std::fs::read_dir(&dst).unwrap().count(),1);assert_eq!(std::fs::read_dir(temp.path()).unwrap().count(),2);
}
