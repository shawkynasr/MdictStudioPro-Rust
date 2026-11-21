use super::*;
use crate::{Entry,application::metadata::publication::Metadata};
use std::sync::mpsc;
fn request()->Request {Request::PackMdx {destination:"unused.mdx".into(),encoding:studio_core::Encoding::Utf8,metadata:Metadata {title:"Test".into(),description:"Test".into(),..Metadata::default()},entries:vec![Entry {key:"apple".into(),text:"test".into()}]}}
fn response(req:&Request)->Response {Response {destination:req.destination().into(),operation:req.operation(),records:1,file_bytes:1,profile:super::super::super::PROFILE}}
struct Gate {released:Mutex<bool>,changed:Condvar}
impl Gate {fn wait(&self) {let guard=self.released.lock().unwrap();let (guard,timeout)=self.changed.wait_timeout_while(guard,Duration::from_secs(10),|v|!*v).unwrap();assert!(*guard&&!timeout.timed_out());}fn release(&self) {*self.released.lock().unwrap()=true;self.changed.notify_all();}}
fn gated(config:Config)->(Runner,Arc<Gate>,mpsc::Receiver<()>) {
    let gate=Arc::new(Gate {released:Mutex::new(false),changed:Condvar::new()});let worker_gate=gate.clone();let (tx,rx)=mpsc::channel();
    let r=Runner::with_executor(config,Arc::new(move|req,job| {tx.send(()).unwrap();worker_gate.wait();job.tick("test_precommit",1,1)?;Ok(response(req))})).unwrap();(r,gate,rx)
}
fn terminal(r:&Runner,id:&str)->Snapshot {r.wait_for_terminal(id,Duration::from_secs(10)).unwrap().expect("Terminal publication")}
#[test]fn queued_active_cancellation_and_recovery() {
    let (r,gate,rx)=gated(Config::default());let active=r.submit(request()).unwrap();rx.recv_timeout(Duration::from_secs(5)).unwrap();let queued=r.submit(request()).unwrap();
    assert_eq!(r.cancel(&queued).unwrap(),CancelOutcome::Requested);assert_eq!(terminal(&r,&queued).state,State::Cancelled);r.cancel(&active).unwrap();assert_eq!(r.cancel(&active).unwrap(),CancelOutcome::AlreadyRequested);gate.release();assert_eq!(terminal(&r,&active).state,State::Cancelled);assert!(r.take_result(&active).unwrap().is_none());
    let next=r.submit(request()).unwrap();assert_eq!(terminal(&r,&next).state,State::Succeeded);r.join().unwrap();
}
#[test]fn pending_retention_transfer_and_coalescing_bounds() {
    let (r,gate,rx)=gated(Config {max_pending:1,max_retained:2});let active=r.submit(request()).unwrap();rx.recv_timeout(Duration::from_secs(5)).unwrap();let queued=r.submit(request()).unwrap();
    assert_eq!(r.submit(request()).unwrap_err().code,RunnerErrorCode::QueueFull);assert_eq!(r.take_result(&active).unwrap_err().code,RunnerErrorCode::StillRunning);assert_eq!(r.forget(&active).unwrap_err().code,RunnerErrorCode::StillRunning);assert!(r.drain_events().len()<=2);assert!(r.drain_events().is_empty());gate.release();terminal(&r,&active);terminal(&r,&queued);
    assert_eq!(r.submit(request()).unwrap_err().code,RunnerErrorCode::RetentionFull);assert!(r.take_result(&active).unwrap().is_some());assert!(r.take_result(&active).unwrap().is_none());assert_eq!(r.cancel(&active).unwrap(),CancelOutcome::AlreadyFinished);r.forget(&active).unwrap();let next=r.submit(request()).unwrap();terminal(&r,&next);r.join().unwrap();
}
#[test]fn cancellation_after_publication_keeps_success_and_file() {
    let temp=tempfile::tempdir().unwrap();let dest=temp.path().join("committed.mdx");let output=dest.clone();let gate=Arc::new(Gate {released:Mutex::new(false),changed:Condvar::new()});let worker_gate=gate.clone();let (tx,rx)=mpsc::channel();
    let r=Runner::with_executor(Config::default(),Arc::new(move|req,_| {std::fs::write(&output,b"committed").unwrap();tx.send(()).unwrap();worker_gate.wait();Ok(response(req))})).unwrap();
    let id=r.submit(request()).unwrap();rx.recv_timeout(Duration::from_secs(5)).unwrap();assert_eq!(r.cancel(&id).unwrap(),CancelOutcome::Requested);gate.release();let snapshot=terminal(&r,&id);assert_eq!(snapshot.state,State::Succeeded);assert!(snapshot.cancel_requested);assert_eq!(std::fs::read(&dest).unwrap(),b"committed");assert!(r.take_result(&id).unwrap().is_some());r.join().unwrap();
}
#[test]fn panic_after_publication_is_uncertain_and_next_job_runs() {
    use std::sync::atomic::{AtomicUsize,Ordering};let count=AtomicUsize::new(0);let temp=tempfile::tempdir().unwrap();let dest=temp.path().join("uncertain.mdx");let output=dest.clone();
    let r=Runner::with_executor(Config::default(),Arc::new(move|req,_| {if count.fetch_add(1,Ordering::SeqCst)==0 {std::fs::write(&output,b"inspect me").unwrap();panic!("after commit");}Ok(response(req))})).unwrap();
    let id=r.submit(request()).unwrap();let result=terminal(&r,&id);assert_eq!(result.state,State::Failed);let failure=result.error.unwrap();assert_eq!(failure.code,ErrorCode::Internal);assert!(failure.publication_uncertain);assert_eq!(std::fs::read(&dest).unwrap(),b"inspect me");assert!(r.take_result(&id).unwrap().is_none());let next=r.submit(request()).unwrap();assert_eq!(terminal(&r,&next).state,State::Succeeded);r.join().unwrap();
}
#[test]fn shutdown_cancels_uncommitted_work_and_closes_admission() {
    let (r,gate,rx)=gated(Config::default());let active=r.submit(request()).unwrap();rx.recv_timeout(Duration::from_secs(5)).unwrap();let queued=r.submit(request()).unwrap();r.shutdown();assert_eq!(r.submit(request()).unwrap_err().code,RunnerErrorCode::Closed);assert_eq!(terminal(&r,&queued).state,State::Cancelled);gate.release();assert_eq!(terminal(&r,&active).state,State::Cancelled);r.join().unwrap();
}
#[test]fn drop_is_nonblocking_and_unknown_ids_are_typed() {
    let (r,gate,rx)=gated(Config::default());assert_eq!(r.snapshot("unknown").unwrap_err().code,RunnerErrorCode::NotFound);let id=r.submit(request()).unwrap();rx.recv_timeout(Duration::from_secs(5)).unwrap();assert!(r.wait_for_terminal(&id,Duration::ZERO).unwrap().is_none());drop(r);gate.release();
}
#[test]fn configuration_and_structural_overrides_are_rejected() {
    assert!(Runner::new(Config {max_pending:0,max_retained:2}).is_err());assert!(Runner::new(Config {max_pending:4,max_retained:9}).is_err());
    let mut bad=request();if let Request::PackMdx {metadata,..}=&mut bad {metadata.extra.insert("Stripkey".into(),"Yes".into());}assert!(bad.validate().is_err());
}
