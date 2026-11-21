use std::{fs,path::{Path,PathBuf},time::Duration};
use studio_application::{Limits,JobContext,CancellationToken,Stage,ErrorCode,PublishRequest,ConversionRequest,ConverterId};
use studio_application::runner::{Runner,Config,State,dictionary::{self,Request,Output}};
fn pack(source:&Path,destination:&Path,encoding:studio_core::Encoding)->Request {Request::PackMdx {source:source.into(),destination:destination.into(),title:"job dictionary".into(),description:"bounded test".into(),encoding,profile:studio_core::TxtProfile::CanonicalV1}}
fn execute(request:&Request)->studio_application::Result<Output> {dictionary::execute(request,&Limits::default(),&mut JobContext::new("dictionary-test",&CancellationToken::default(),&mut |_|{}))}
fn manifest(dir:&Path)->PathBuf {
    fs::write(dir.join("one.bin"),[0,255,128]).unwrap();fs::write(dir.join("empty.bin"),[]).unwrap();let path=dir.join("resources.json");
    fs::write(&path,serde_json::to_vec(&serde_json::json!({"title":"resources","description":"binary","resources":[{"key":"\\data\\one.bin","source":"one.bin"},{"key":"\\字\\empty.bin","source":"empty.bin"}]})).unwrap()).unwrap();path
}
#[test]
fn dictionary_jobs_and_conversion_jobs_share_one_worker_and_typed_summaries() {
    let temp=tempfile::tempdir().unwrap();let source=temp.path().join("source.txt");fs::write(&source,"word\nfirst\n</>\nword\nsecond\n</>\n").unwrap();
    let r=Runner::new(Config::default()).unwrap();
    for (i,encoding) in [studio_core::Encoding::Utf8,studio_core::Encoding::Utf16].into_iter().enumerate() {
        let mdx=temp.path().join(format!("{i}.mdx"));let id=r.submit_dictionary(pack(&source,&mdx,encoding),Limits::default()).unwrap();let result=r.wait_for_terminal(&id,Duration::from_secs(20)).unwrap().unwrap();
        assert_eq!(result.state,State::Succeeded);assert_eq!(result.operation,"pack_mdx");assert!(result.output.is_none());
        assert!(matches!(result.dictionary_output,Some(Output::PackMdx {entries:2,..})));
        let target=temp.path().join(format!("{i}-export.txt"));let id=r.submit_dictionary(Request::ExportMdx {source:mdx,destination:target.clone(),profile:studio_core::TxtProfile::CanonicalV1},Limits::default()).unwrap();assert_eq!(r.wait_for_terminal(&id,Duration::from_secs(20)).unwrap().unwrap().state,State::Succeeded);assert_eq!(fs::read(target).unwrap(),fs::read(&source).unwrap());
    }
    let baseline=PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../baseline/xlsx-reader-kit/moe-rows.xlsx");
    let id=r.submit(PublishRequest {conversion:ConversionRequest {converter:ConverterId::MoeMini,input:baseline,worksheet:None},destination:temp.path().join("mini.txt")},Limits::default()).unwrap();
    let result=r.wait_for_terminal(&id,Duration::from_secs(20)).unwrap().unwrap();assert_eq!(result.state,State::Succeeded);assert_eq!(result.operation,"convert_txt");assert!(result.dictionary_output.is_none());assert!(result.output.is_some());r.join().unwrap();
}
#[test]
fn resource_manifest_relative_sources_extract_exact_binary_and_preserve_existing_destination() {
    let temp=tempfile::tempdir().unwrap();let m=manifest(temp.path());let archive=temp.path().join("data.mdd");execute(&Request::PackMdd {manifest:m,destination:archive.clone()}).unwrap();
    let target=temp.path().join("extracted");let req=Request::ExtractMdd {source:archive,destination:target.clone()};let result=execute(&req).unwrap();assert!(matches!(result,Output::ExtractMdd {resources:2,payload_bytes:3,..}));
    assert_eq!(fs::read(target.join("data/one.bin")).unwrap(),[0,255,128]);assert!(fs::read(target.join("字/empty.bin")).unwrap().is_empty());assert_eq!(execute(&req).unwrap_err().code,ErrorCode::DestinationExists);
}
#[test]
fn cancellation_during_mdx_and_mdd_verification_cleans_staged_files() {
    let temp=tempfile::tempdir().unwrap();let source=temp.path().join("source.txt");fs::write(&source,"word\nbody\n</>\n").unwrap();let m=manifest(temp.path());
    for req in [pack(&source,&temp.path().join("cancel.mdx"),studio_core::Encoding::Utf8),Request::PackMdd {manifest:m,destination:temp.path().join("cancel.mdd")}] {
        let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:studio_application::Progress|if p.stage==Stage::Publishing&&p.phase=="verifying" {stop.cancel();};
        assert_eq!(dictionary::execute(&req,&Limits::default(),&mut JobContext::new("cancel",&token,&mut progress)).unwrap_err().code,ErrorCode::Cancelled);assert!(!req.destination().exists());
        assert!(fs::read_dir(temp.path()).unwrap().all(|p|!p.unwrap().file_name().to_string_lossy().starts_with(".tmp")));
    }
}
#[test]
fn cancelled_extraction_removes_its_stage_and_late_cancellation_stays_successful() {
    let temp=tempfile::tempdir().unwrap();let m=manifest(temp.path());let archive=temp.path().join("data.mdd");execute(&Request::PackMdd {manifest:m,destination:archive.clone()}).unwrap();
    let req=Request::ExtractMdd {source:archive.clone(),destination:temp.path().join("cancelled")};let token=CancellationToken::default();let stop=token.clone();
    let mut progress=|p:studio_application::Progress|if p.stage==Stage::Publishing&&p.phase=="extracting"&&p.completed>0 {stop.cancel();};
    assert_eq!(dictionary::execute(&req,&Limits::default(),&mut JobContext::new("extract-cancel",&token,&mut progress)).unwrap_err().code,ErrorCode::Cancelled);assert!(!req.destination().exists());
    assert!(fs::read_dir(temp.path()).unwrap().all(|p|!p.unwrap().file_name().to_string_lossy().starts_with(".studio-extract-")));
    let req=Request::ExtractMdd {source:archive,destination:temp.path().join("late")};let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:studio_application::Progress|if p.phase=="published" {stop.cancel();};
    dictionary::execute(&req,&Limits::default(),&mut JobContext::new("late",&token,&mut progress)).unwrap();assert!(token.is_cancelled());assert!(req.destination().is_dir());
}
#[test]
fn manifest_and_resource_budgets_fail_before_publishing() {
    let temp=tempfile::tempdir().unwrap();let m=manifest(temp.path());let destination=temp.path().join("limited.mdd");let req=Request::PackMdd {manifest:m.clone(),destination:destination.clone()};let mut limits=Limits::default();limits.dictionary.max_entry_bytes=2;
    assert_eq!(dictionary::execute(&req,&limits,&mut JobContext::new("budget",&CancellationToken::default(),&mut |_|{})).unwrap_err().code,ErrorCode::LimitExceeded);assert!(!destination.exists());
    fs::write(&m,vec![b' ';131073]).unwrap();assert_eq!(execute(&req).unwrap_err().code,ErrorCode::LimitExceeded);assert!(!destination.exists());
}
