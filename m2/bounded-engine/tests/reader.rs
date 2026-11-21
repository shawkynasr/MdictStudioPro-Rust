use studio_bounded_engine::*;
use std::path::Path;
fn source(dir:&Path)->std::path::PathBuf {
    let path=dir.join("input.mdx");let mut builder=mdictlib::MdxBuilder::with_options(mdictlib::WriteOptions::new().with_key_block_target_bytes(32).with_record_block_target_bytes(64));
    builder.header_attribute("Format","Html").unwrap();
    builder.add_entry("apple","first").unwrap();builder.add_entry("apple","second").unwrap();builder.add_entry("字","文字").unwrap();builder.finish(&mut std::fs::File::create(&path).unwrap()).unwrap();path
}
fn open(path:&Path,limits:&Limits)->Result<Dictionary> {Dictionary::open_v2(path,Kind::Mdx,limits,&mut ImportJob::new("test",&CancellationToken::default(),&mut |_|{}))}
#[test]fn full_scan_retains_no_locator_and_raw_exact_duplicates_are_complete() {
    let temp=tempfile::tempdir().unwrap();let path=source(temp.path());let d=open(&path,&Limits::default()).unwrap();assert_eq!(d.scan().records,3);assert_eq!(d.memory_usage().unwrap().locator,0);
    let token=CancellationToken::default();let mut progress=|_|{};let mut job=ImportJob::new("queries",&token,&mut progress);let rows=d.lookup_exact("apple",&mut job).unwrap();assert_eq!(rows.len(),2);assert_eq!(rows[0].text.as_deref(),Some("first"));assert_eq!(rows[1].text.as_deref(),Some("second"));assert!(d.lookup_exact("APPLE",&mut job).unwrap().is_empty());assert_eq!(d.memory_usage().unwrap().locator,0);
    let mut limits=Limits::default();limits.max_matches=1;let d=open(&path,&limits).unwrap();assert_eq!(d.lookup_exact("apple",&mut job).unwrap_err().code,ErrorCode::LimitExceeded);
}
#[test]fn parser_limits_are_typed_and_cancellation_exposes_no_reader() {
    let temp=tempfile::tempdir().unwrap();let path=source(temp.path());let mut limits=Limits::default();limits.engine=limits.engine.with_working_memory_bytes(1);
    let e=match open(&path,&limits) {Ok(_)=>panic!("Tiny parser budget accepted"),Err(e)=>e};assert_eq!(e.code,ErrorCode::LimitExceeded);assert!(e.limit.is_some());
    let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase=="bounded_scan" {stop.cancel();};
    let result=Dictionary::open_v2(&path,Kind::Mdx,&Limits::default(),&mut ImportJob::new("cancel",&token,&mut progress));assert!(matches!(result,Err(Error {code:ErrorCode::Cancelled,..})));
}
#[test]fn materialization_and_cumulative_scan_caps_are_distinct() {
    let temp=tempfile::tempdir().unwrap();let path=source(temp.path());let mut limits=Limits::default();limits.engine=limits.engine.with_materialized_record_bytes(1);assert!(matches!(open(&path,&limits),Err(Error {code:ErrorCode::LimitExceeded,..})));
    let mut limits=Limits::default();limits.max_scan_bytes=1;assert!(matches!(open(&path,&limits),Err(Error {code:ErrorCode::LimitExceeded,..})));
    let mut limits=Limits::default();limits.max_rows=2;assert!(matches!(open(&path,&limits),Err(Error {code:ErrorCode::LimitExceeded,..})));
}
#[test]fn mdd_binary_duplicates_and_empty_payloads_are_streamed() {
    let temp=tempfile::tempdir().unwrap();let path=temp.path().join("resources.mdd");let mut builder=mdictlib::MddBuilder::with_options(mdictlib::WriteOptions::new().with_legacy_sort(mdictlib::LegacySort::PreserveInput));
    builder.add_resource("data.bin",&[0,255]).unwrap();builder.add_resource("data.bin",&[128]).unwrap();builder.add_resource("empty.bin",&[]).unwrap();builder.finish(&mut std::fs::File::create(&path).unwrap()).unwrap();
    let token=CancellationToken::default();let mut progress=|_|{};let mut job=ImportJob::new("resources",&token,&mut progress);let d=Dictionary::open_v2(&path,Kind::Mdd,&Limits::default(),&mut job).unwrap();assert_eq!(d.scan().records,3);let rows=d.lookup_exact("data.bin",&mut job).unwrap();assert_eq!(rows[0].bytes.as_deref(),Some(&[0,255][..]));assert_eq!(rows[1].bytes.as_deref(),Some(&[128][..]));assert!(d.lookup_exact("empty.bin",&mut job).unwrap()[0].bytes.as_ref().unwrap().is_empty());
}
#[test]fn engine_limit_profile_cannot_be_silently_raised() {
    let temp=tempfile::tempdir().unwrap();let path=source(temp.path());let mut limits=Limits::default();limits.engine=limits.engine.with_locator_entries(1);assert!(matches!(open(&path,&limits),Err(Error {code:ErrorCode::InvalidInput,..})));
}
