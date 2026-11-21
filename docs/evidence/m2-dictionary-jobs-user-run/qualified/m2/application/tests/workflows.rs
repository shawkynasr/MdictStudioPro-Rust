use std::{fs,path::{Path,PathBuf}};
use studio_application::*;
fn baseline()->PathBuf {PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../baseline")}
fn source()->PathBuf {baseline().join("xlsx-reader-kit/moe-rows.xlsx")}
fn request(input:PathBuf)->ConversionRequest {ConversionRequest {converter:ConverterId::MoeMini,input,worksheet:None}}
fn publish(destination:&Path)->PublishRequest {PublishRequest {conversion:request(source()),destination:destination.into()}}

#[test]
fn one_job_identity_covers_read_conversion_validation_and_publication() {
    let temp=tempfile::tempdir().unwrap();let output=temp.path().join("result.txt");let token=CancellationToken::default();let mut events=Vec::new();
    let mut callback=|p|events.push(p);
    let value=convert_to_txt(&publish(&output),&Limits::default(),&mut JobContext::new("job-42",&token,&mut callback)).unwrap();
    assert_eq!(value.entries,2);assert_eq!(value.metrics.primary_entries,2);
    assert_eq!(fs::read(&output).unwrap(),fs::read(baseline().join("expected/moe_mini.txt")).unwrap());
    assert!(events.iter().all(|p|p.job_id=="job-42"));
    for stage in [Stage::ReadingWorkbook,Stage::Converting,Stage::ValidatingOutput,Stage::Publishing] {assert!(events.iter().any(|p|p.stage==stage));}
    assert!(events.iter().filter(|p|p.phase=="published").count()==1);
    assert_eq!(events.last().unwrap().stage,Stage::Publishing);assert_eq!(events.last().unwrap().phase,"published");
}
#[test]
fn cancellation_at_read_and_before_publication_leaves_no_output_or_staging_files() {
    for stage in [Stage::ReadingWorkbook,Stage::ValidatingOutput,Stage::Publishing] {
        let temp=tempfile::tempdir().unwrap();let output=temp.path().join("result.txt");let token=CancellationToken::default();let stop=token.clone();
        let mut callback=|p:Progress|if p.stage==stage {stop.cancel();};
        let error=convert_to_txt(&publish(&output),&Limits::default(),&mut JobContext::new("cancel",&token,&mut callback)).unwrap_err();
        assert_eq!(error.code,ErrorCode::Cancelled);assert!(!output.exists());assert_eq!(fs::read_dir(temp.path()).unwrap().count(),0);
    }
    // Cancel during strict reopen, after a temporary file has been written.
    let temp=tempfile::tempdir().unwrap();let output=temp.path().join("result.txt");let token=CancellationToken::default();let stop=token.clone();
    let mut callback=|p:Progress|if p.stage==Stage::Publishing&&p.phase=="verifying" {stop.cancel();};
    assert_eq!(convert_to_txt(&publish(&output),&Limits::default(),&mut JobContext::new("verify-cancel",&token,&mut callback)).unwrap_err().code,ErrorCode::Cancelled);
    assert_eq!(fs::read_dir(temp.path()).unwrap().count(),0);
}
#[test]
fn late_cancel_is_success_and_existing_output_is_never_replaced() {
    let temp=tempfile::tempdir().unwrap();let output=temp.path().join("result.txt");let token=CancellationToken::default();let stop=token.clone();
    let mut callback=|p:Progress|if p.phase=="published" {stop.cancel();};
    let result=convert_to_txt(&publish(&output),&Limits::default(),&mut JobContext::new("late",&token,&mut callback)).unwrap();assert_eq!(result.entries,2);assert!(token.is_cancelled());
    let before=fs::read(&output).unwrap();let token=CancellationToken::default();
    assert_eq!(convert_to_txt(&publish(&output),&Limits::default(),&mut JobContext::new("existing",&token,&mut |_|{})).unwrap_err().code,ErrorCode::DestinationExists);
    assert_eq!(fs::read(&output).unwrap(),before);
}
#[test]
fn shared_output_budget_and_input_errors_are_typed_and_all_or_error() {
    let token=CancellationToken::default();let mut limits=Limits::default();limits.dictionary.max_file_bytes=1;
    assert_eq!(convert(&request(source()),&limits,&mut JobContext::new("budget",&token,&mut |_|{})).unwrap_err().code,ErrorCode::LimitExceeded);
    for (file,code) in [("date.xlsx",ErrorCode::UnsupportedCell),("invalid.xlsx",ErrorCode::MalformedWorkbook),("no-dimension.xlsx",ErrorCode::UnsupportedWorkbook)] {
        assert_eq!(convert(&request(baseline().join("xlsx-reader-kit").join(file)),&Limits::default(),&mut JobContext::new("input-error",&token,&mut |_|{})).unwrap_err().code,code);
    }
    let mut r=request(source());r.worksheet=Some("missing".into());
    assert_eq!(convert(&r,&Limits::default(),&mut JobContext::new("sheet",&token,&mut |_|{})).unwrap_err().code,ErrorCode::SheetNotFound);
    token.cancel();
    assert_eq!(convert(&request(PathBuf::from("does-not-exist")),&Limits::default(),&mut JobContext::new("pre-cancel",&token,&mut |_|{})).unwrap_err().code,ErrorCode::Cancelled);
}
#[test]
fn cedict_uses_same_job_and_error_contract_and_rejects_worksheet_argument() {
    let temp=tempfile::tempdir().unwrap();let input=temp.path().join("cedict.u8");
    fs::write(&input,"# comment\n傳 传 [chuan2] /to pass on/\n").unwrap();
    let token=CancellationToken::default();let mut events=Vec::new();let mut callback=|p|events.push(p);
    let mut r=ConversionRequest {converter:ConverterId::CcCedict,input,worksheet:None};
    let value=convert(&r,&Limits::default(),&mut JobContext::new("cedict",&token,&mut callback)).unwrap();
    assert_eq!(value.entries.iter().map(|e|e.key.as_str()).collect::<Vec<_>>(),["传","傳"]);assert_eq!(value.comments,["# comment"]);assert_eq!(value.metrics.traditional_entries,1);
    assert!(events.iter().all(|p|p.job_id=="cedict"&&matches!(p.stage,Stage::Converting|Stage::ValidatingOutput)));
    r.worksheet=Some("Sheet".into());assert_eq!(convert(&r,&Limits::default(),&mut JobContext::new("bad-option",&token,&mut |_|{})).unwrap_err().code,ErrorCode::InvalidInput);
}
#[test]
fn unknown_backend_error_codes_fail_closed_as_internal_errors() {
    let e=Error::from(studio_xlsx::Error {code:"future_error",message:"diagnostic".into()});assert_eq!(e.code,ErrorCode::Internal);assert!(e.message.contains("future_error"));
}
