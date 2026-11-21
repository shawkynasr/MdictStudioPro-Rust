use std::{fs,path::PathBuf,time::Duration};
use studio_application::{Limits,PublishRequest,ConversionRequest,ConverterId,ErrorCode};
use studio_application::runner::{Runner,Config,State};
fn baseline()->PathBuf {PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../baseline")}
fn request(destination:PathBuf)->PublishRequest {PublishRequest {conversion:ConversionRequest {converter:ConverterId::MoeMini,input:baseline().join("xlsx-reader-kit/moe-rows.xlsx"),worksheet:None},destination}}
#[test]
fn real_worker_publishes_exact_txt_and_retains_terminal_status_after_event_drain() {
    let temp=tempfile::tempdir().unwrap();let output=temp.path().join("mini.txt");let r=Runner::new(Config::default()).unwrap();
    let id=r.submit(request(output.clone()),Limits::default()).unwrap();let result=r.wait_for_terminal(&id,Duration::from_secs(20)).unwrap().unwrap();
    assert_eq!(result.state,State::Succeeded);let summary=result.output.unwrap();assert_eq!(summary.entries,2);assert_eq!(summary.destination,output);
    assert_eq!(fs::read(&output).unwrap(),fs::read(baseline().join("expected/moe_mini.txt")).unwrap());
    let events=r.drain_events();assert_eq!(events.len(),1);assert_eq!(events[0].job_id,id);assert_eq!(events[0].state,State::Succeeded);assert!(r.drain_events().is_empty());
    assert_eq!(r.snapshot(&id).unwrap().state,State::Succeeded);r.join().unwrap();
}
#[test]
fn real_failure_is_typed_existing_file_unchanged_and_next_job_runs() {
    let temp=tempfile::tempdir().unwrap();let old=temp.path().join("existing.txt");fs::write(&old,b"KEEP").unwrap();let r=Runner::new(Config::default()).unwrap();
    let id=r.submit(request(old.clone()),Limits::default()).unwrap();let result=r.wait_for_terminal(&id,Duration::from_secs(20)).unwrap().unwrap();
    assert_eq!(result.state,State::Failed);assert_eq!(result.error.unwrap().code,ErrorCode::DestinationExists);assert_eq!(fs::read(old).unwrap(),b"KEEP");
    let next=r.submit(request(temp.path().join("next.txt")),Limits::default()).unwrap();assert_eq!(r.wait_for_terminal(&next,Duration::from_secs(20)).unwrap().unwrap().state,State::Succeeded);r.join().unwrap();
}
