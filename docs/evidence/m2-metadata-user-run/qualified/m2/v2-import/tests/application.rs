use studio_v2_import::{application::{self,Request,Source,Action,Outcome,runner::{Runner,Config,State}},*};
use std::{path::Path,time::Duration};
fn input(dir:&Path)->Request {
    let path=dir.join("ordinary.mdx");let token=CancellationToken::default();
    let entries=vec![Entry {key:"apple".into(),text:"first".into()},Entry {key:"apple".into(),text:"second".into()},Entry {key:"alias".into(),text:"@@@LINK=apple".into()},Entry {key:"cycle".into(),text:"@@@LINK=cycle".into()}];
    studio_core::pack_mdx(&studio_core::PackRequest {title:"Imported".into(),description:"Raw".into(),encoding:studio_core::Encoding::Utf8,entries},&path,&studio_core::Limits::default(),&mut studio_core::JobContext::new(&token,&mut |_|{})).unwrap();
    Request {path,source:Source::Mdx {policy:LookupPolicy::RawExact},actions:vec![Action::Lookup {query:"apple".into()},Action::Resolve {query:"alias".into()},Action::Resolve {query:"cycle".into()}],max_entries:None,max_results:None,max_hops:None,max_reply_bytes:None}
}
fn run(req:&Request)->Result<application::Response> {application::execute(req,&mut ImportJob::new("integration",&CancellationToken::default(),&mut |_|{}))}
#[test]
fn sync_and_background_replies_agree_and_results_move_once() {
    let temp=tempfile::tempdir().unwrap();let req=input(temp.path());let sync=run(&req).unwrap();
    assert!(matches!(&sync.results[0].outcome,Outcome::Entries {entries} if entries.len()==2));
    assert!(matches!(&sync.results[1].outcome,Outcome::Resolutions {results} if results.len()==2));
    assert!(matches!(&sync.results[2].outcome,Outcome::Error {error} if error.detail=="redirect_cycle"));
    let runner=Runner::new(Config::default()).unwrap();let id=runner.submit(req).unwrap();let terminal=runner.wait_for_terminal(&id,Duration::from_secs(10)).unwrap().unwrap();
    assert_eq!(terminal.state,State::Succeeded);assert_eq!(terminal.latest_progress.as_ref().unwrap().job_id,id);assert!(terminal.result_available);
    let reply=runner.take_result(&id).unwrap().unwrap();assert_eq!(serde_json::to_value(sync).unwrap(),serde_json::to_value(reply).unwrap());
    assert!(runner.take_result(&id).unwrap().is_none());runner.forget(&id).unwrap();assert!(runner.snapshot(&id).is_err());runner.join().unwrap();
}
#[test]
fn cancellation_during_action_phase_and_aggregate_cap_return_no_partial_reply() {
    let temp=tempfile::tempdir().unwrap();let req=input(temp.path());let token=CancellationToken::default();let stop=token.clone();
    let mut progress=|p:Progress|if p.phase=="import_actions" {stop.cancel();};
    let error=application::execute(&req,&mut ImportJob::new("cancel-actions",&token,&mut progress)).unwrap_err();assert_eq!(error.code,ErrorCode::Cancelled);
    let mut capped=req.clone();capped.max_reply_bytes=Some(1);assert_eq!(run(&capped).unwrap_err().code,ErrorCode::LimitExceeded);
    let mut limited=req;limited.max_results=Some(1);let reply=run(&limited).unwrap();assert!(matches!(&reply.results[0].outcome,Outcome::Error {error} if error.code==ErrorCode::LimitExceeded));
}
#[test]
fn failed_open_preserves_typed_error_and_worker_accepts_recovery() {
    let temp=tempfile::tempdir().unwrap();let req=input(temp.path());let mut missing=req.clone();missing.path=temp.path().join("missing.mdx");
    let r=Runner::new(Config::default()).unwrap();let id=r.submit(missing).unwrap();let snapshot=r.wait_for_terminal(&id,Duration::from_secs(10)).unwrap().unwrap();
    assert_eq!(snapshot.state,State::Failed);assert_eq!(snapshot.error.unwrap().code,ErrorCode::Io);assert!(r.take_result(&id).unwrap().is_none());
    let next=r.submit(req).unwrap();assert_eq!(r.wait_for_terminal(&next,Duration::from_secs(10)).unwrap().unwrap().state,State::Succeeded);r.join().unwrap();
}
#[test]
fn mdd_resource_actions_preserve_duplicates_and_empty_bytes() {
    let temp=tempfile::tempdir().unwrap();let path=temp.path().join("resources.mdd");
    let resources=vec![Resource {key:"data.bin".into(),bytes:vec![0,255]},Resource {key:"data.bin".into(),bytes:vec![128]},Resource {key:"empty.bin".into(),bytes:vec![]}];
    let mut builder=mdictlib::MddBuilder::with_options(mdictlib::WriteOptions::new().with_legacy_sort(mdictlib::LegacySort::PreserveInput));
    for resource in resources {builder.add_resource(&resource.key,&resource.bytes).unwrap();}builder.finish(&mut std::fs::File::create(&path).unwrap()).unwrap();
    let req=Request {path,source:Source::Mdd,actions:vec![Action::Resource {query:"data.bin".into()},Action::Resource {query:"empty.bin".into()}],max_entries:None,max_results:None,max_hops:None,max_reply_bytes:None};
    let reply=run(&req).unwrap();assert_eq!(reply.records,3);assert!(matches!(&reply.results[0].outcome,Outcome::Resources {resources} if resources.len()==2&&resources[0].bytes==[0,255]));assert!(matches!(&reply.results[1].outcome,Outcome::Resources {resources} if resources.len()==1&&resources[0].bytes.is_empty()));
}
