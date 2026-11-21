use studio_indexed_engine::{*,index::{Index,Policy,BuildOptions}};
use std::path::Path;
fn make(path:&Path,rows:&[(&str,&str)]) {
 let mut b=mdictlib::MdxBuilder::with_options(mdictlib::WriteOptions::new().with_legacy_sort(mdictlib::LegacySort::PreserveInput).with_key_block_target_bytes(32).with_record_block_target_bytes(64));b.header_attribute("Format","Html").unwrap();
 for (k,v) in rows {b.add_entry(k,v).unwrap();}b.finish(&mut std::fs::File::create(path).unwrap()).unwrap();
}
fn open(path:&Path)->Dictionary {Dictionary::open_v2(path,Kind::Mdx,&Limits::default(),&mut ImportJob::new("open",&CancellationToken::default(),&mut |_|{})).unwrap()}
#[test]fn exact_precedence_duplicate_pages_and_frozen_lowercase_survive_reopen() {
 let tmp=tempfile::tempdir().unwrap();let src=tmp.path().join("a.mdx");let cache=tmp.path().join("a.idx");make(&src,&[("apple","one"),("Apple","upper"),("apple","two"),("ΣΟΣ","greek"),("İ","dotted")]);
 let d=open(&src);let token=CancellationToken::default();let mut progress=|_|{};let mut job=ImportJob::new("index",&token,&mut progress);
 let receipt=Index::build(&d,&cache,Policy::HeaderAsciiV1,BuildOptions {run_records:2,..BuildOptions::default()},&mut job).unwrap();assert!(receipt.initial_runs>=6);
 drop(d);let d=open(&src);let mut i=Index::open(&d,&cache,Policy::HeaderAsciiV1,&mut job).unwrap();let p=i.page("apple",0,1,&mut job).unwrap();assert_eq!(p.total,2);assert_eq!(p.basis,"exact");assert_eq!(p.next_offset,Some(1));assert_eq!(p.rows[0].text.as_deref(),Some("one"));let p=i.page("apple",1,1,&mut job).unwrap();assert_eq!(p.rows[0].text.as_deref(),Some("two"));assert_eq!(p.next_offset,None);
 let p=i.page("APPLE",0,128,&mut job).unwrap();assert_eq!(p.total,3);assert_eq!(p.rows.iter().map(|r|r.ordinal).collect::<Vec<_>>(),vec![0,1,2]);assert_eq!(p.basis,"normalized");assert_eq!(i.page("σος",0,2,&mut job).unwrap().total,1);assert_eq!(i.page("i\u{307}",0,2,&mut job).unwrap().total,1);assert_eq!(d.memory_usage().unwrap().locator,0);
}
#[test]fn stale_policy_and_corrupt_artifacts_are_refused() {
 let tmp=tempfile::tempdir().unwrap();let src=tmp.path().join("a.mdx");let cache=tmp.path().join("a.idx");make(&src,&[("apple","one")]);let d=open(&src);let token=CancellationToken::default();let mut progress=|_|{};let mut job=ImportJob::new("index",&token,&mut progress);Index::build(&d,&cache,Policy::RawExact,BuildOptions::default(),&mut job).unwrap();
 assert!(matches!(Index::open(&d,&cache,Policy::HeaderAsciiV1,&mut job),Err(Error {code:ErrorCode::Integrity,..})));
 make(&src,&[("apple","two")]);let changed=open(&src);assert!(matches!(Index::open(&changed,&cache,Policy::RawExact,&mut job),Err(Error {code:ErrorCode::Integrity,..})));
 let mut bytes=std::fs::read(&cache).unwrap();let mid=bytes.len()/2;bytes[mid]^=1;std::fs::write(&cache,bytes).unwrap();assert!(matches!(Index::open(&d,&cache,Policy::RawExact,&mut job),Err(Error {code:ErrorCode::Integrity,..})));
}
#[test]fn cancellation_does_not_publish_and_existing_artifact_is_never_overwritten() {
 let tmp=tempfile::tempdir().unwrap();let src=tmp.path().join("a.mdx");let cache=tmp.path().join("a.idx");make(&src,&[("apple","one")]);let d=open(&src);let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase=="index_publish" {stop.cancel();};
 assert!(matches!(Index::build(&d,&cache,Policy::RawExact,BuildOptions::default(),&mut ImportJob::new("cancel",&token,&mut progress)),Err(Error {code:ErrorCode::Cancelled,..})));assert!(!cache.exists());
 std::fs::write(&cache,b"sentinel").unwrap();assert!(matches!(Index::build(&d,&cache,Policy::RawExact,BuildOptions::default(),&mut ImportJob::new("exists",&CancellationToken::default(),&mut |_|{})),Err(Error {code:ErrorCode::DestinationExists,..})));assert_eq!(std::fs::read(&cache).unwrap(),b"sentinel");
}
#[test]fn page_count_only_bounds_and_complete_byte_refusals() {
 let tmp=tempfile::tempdir().unwrap();let src=tmp.path().join("a.mdx");let cache=tmp.path().join("a.idx");make(&src,&[("apple","one"),("apple","two")]);let d=open(&src);let token=CancellationToken::default();let mut progress=|_|{};let mut job=ImportJob::new("index",&token,&mut progress);Index::build(&d,&cache,Policy::RawExact,BuildOptions::default(),&mut job).unwrap();
 let mut i=Index::open(&d,&cache,Policy::RawExact,&mut job).unwrap();assert_eq!(i.page("apple",0,0,&mut job).unwrap().total,2);assert!(i.page("apple",u64::MAX,2,&mut job).unwrap().rows.is_empty());assert!(matches!(i.page("apple",0,129,&mut job),Err(Error {code:ErrorCode::LimitExceeded,..})));drop(i);
 let mut limits=Limits::default();limits.max_result_bytes=1;let tiny=Dictionary::open_v2(&src,Kind::Mdx,&limits,&mut job).unwrap();let mut i=Index::open(&tiny,&cache,Policy::RawExact,&mut job).unwrap();assert!(matches!(i.page("apple",0,2,&mut job),Err(Error {code:ErrorCode::LimitExceeded,..})));
}
#[test]fn binary_resource_duplicates_and_empty_tail_use_raw_policy() {
 let tmp=tempfile::tempdir().unwrap();let src=tmp.path().join("a.mdd");let cache=tmp.path().join("a.idx");let mut b=mdictlib::MddBuilder::with_options(mdictlib::WriteOptions::new().with_legacy_sort(mdictlib::LegacySort::PreserveInput));b.add_resource("file",&[0,255]).unwrap();b.add_resource("file",&[128]).unwrap();b.add_resource("empty",&[]).unwrap();b.finish(&mut std::fs::File::create(&src).unwrap()).unwrap();
 let token=CancellationToken::default();let mut progress=|_|{};let mut job=ImportJob::new("mdd",&token,&mut progress);let d=Dictionary::open_v2(&src,Kind::Mdd,&Limits::default(),&mut job).unwrap();Index::build(&d,&cache,Policy::RawExact,BuildOptions::default(),&mut job).unwrap();let mut i=Index::open(&d,&cache,Policy::RawExact,&mut job).unwrap();assert_eq!(i.page("file",1,1,&mut job).unwrap().rows[0].bytes.as_deref(),Some(&[128][..]));assert!(i.page("empty",0,1,&mut job).unwrap().rows[0].bytes.as_ref().unwrap().is_empty());
}
