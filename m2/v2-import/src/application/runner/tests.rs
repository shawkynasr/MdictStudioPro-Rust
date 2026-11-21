use super::*;
use crate::{application::{Action,Source},Kind,Header,LookupPolicy};
use std::sync::mpsc;
fn request()->Request {Request {path:"unused.mdx".into(),source:Source::Mdx {policy:LookupPolicy::RawExact},actions:vec![Action::Lookup {query:"apple".into()}],max_results:None,max_entries:None,max_hops:None,max_reply_bytes:None}}
fn response()->Response {Response {header:Header {kind:Kind::Mdx,attributes:BTreeMap::new(),raw_xml:String::new(),raw_utf16le:Vec::new(),case_sensitive:None,strip_key:None},policy:"raw-exact-v1",records:0,results:Vec::new()}}
struct Gate {released:Mutex<bool>,changed:Condvar}
impl Gate {
    fn wait(&self) {let guard=self.released.lock().unwrap();let (guard,timeout)=self.changed.wait_timeout_while(guard,Duration::from_secs(10),|v|!*v).unwrap();assert!(*guard&&!timeout.timed_out(),"Gate timed out");}
    fn release(&self) {*self.released.lock().unwrap()=true;self.changed.notify_all();}
}
fn gated(config:Config)->(Runner,Arc<Gate>,mpsc::Receiver<()>) {
    let gate=Arc::new(Gate {released:Mutex::new(false),changed:Condvar::new()});let worker_gate=gate.clone();let (tx,rx)=mpsc::channel();
    let runner=Runner::with_executor(config,Arc::new(move|_,job| {tx.send(()).unwrap();worker_gate.wait();job.tick("test",1,1)?;Ok(response())})).unwrap();(runner,gate,rx)
}
fn terminal(r:&Runner,id:&str)->Snapshot {r.wait_for_terminal(id,Duration::from_secs(10)).unwrap().expect("Terminal import")}
#[test]
fn queued_and_active_cancellation_are_complete_and_worker_recovers() {
    let (r,gate,rx)=gated(Config::default());let active=r.submit(request()).unwrap();rx.recv_timeout(Duration::from_secs(5)).unwrap();
    let queued=r.submit(request()).unwrap();assert_eq!(r.cancel(&queued).unwrap(),CancelOutcome::Requested);assert_eq!(terminal(&r,&queued).state,State::Cancelled);
    assert_eq!(r.cancel(&active).unwrap(),CancelOutcome::Requested);assert_eq!(r.cancel(&active).unwrap(),CancelOutcome::AlreadyRequested);gate.release();
    assert_eq!(terminal(&r,&active).state,State::Cancelled);assert!(r.take_result(&active).unwrap().is_none());assert!(r.take_result(&queued).unwrap().is_none());
    let recovery=r.submit(request()).unwrap();assert_eq!(terminal(&r,&recovery).state,State::Succeeded);assert!(r.take_result(&recovery).unwrap().is_some());r.join().unwrap();
}
#[test]
fn pending_retention_result_transfer_and_mailbox_are_bounded() {
    let (r,gate,rx)=gated(Config {max_pending:1,max_retained:2});let active=r.submit(request()).unwrap();rx.recv_timeout(Duration::from_secs(5)).unwrap();
    assert_eq!(r.take_result(&active).unwrap_err().code,RunnerErrorCode::StillRunning);assert_eq!(r.forget(&active).unwrap_err().code,RunnerErrorCode::StillRunning);
    let queued=r.submit(request()).unwrap();assert_eq!(r.submit(request()).unwrap_err().code,RunnerErrorCode::QueueFull);
    assert!(r.drain_events().len()<=2);assert!(r.drain_events().is_empty());gate.release();terminal(&r,&active);terminal(&r,&queued);
    assert_eq!(r.submit(request()).unwrap_err().code,RunnerErrorCode::RetentionFull);
    assert!(r.snapshot(&active).unwrap().result_available);assert!(r.take_result(&active).unwrap().is_some());assert!(r.take_result(&active).unwrap().is_none());assert!(!r.snapshot(&active).unwrap().result_available);
    assert_eq!(r.cancel(&active).unwrap(),CancelOutcome::AlreadyFinished);r.forget(&active).unwrap();let next=r.submit(request()).unwrap();assert_ne!(active,next);terminal(&r,&next);r.join().unwrap();
}
#[test]
fn panic_is_typed_and_next_job_succeeds() {
    use std::sync::atomic::{AtomicUsize,Ordering};let count=AtomicUsize::new(0);
    let r=Runner::with_executor(Config::default(),Arc::new(move|_,_| {if count.fetch_add(1,Ordering::SeqCst)==0 {panic!("test panic");}Ok(response())})).unwrap();
    let id=r.submit(request()).unwrap();let failed=terminal(&r,&id);assert_eq!(failed.state,State::Failed);assert_eq!(failed.error.unwrap().detail,"panic");assert!(r.take_result(&id).unwrap().is_none());
    let next=r.submit(request()).unwrap();assert_eq!(terminal(&r,&next).state,State::Succeeded);r.join().unwrap();
}
#[test]
fn shutdown_cancels_queue_and_closes_admission_without_blocking() {
    let (r,gate,rx)=gated(Config::default());let active=r.submit(request()).unwrap();rx.recv_timeout(Duration::from_secs(5)).unwrap();let queued=r.submit(request()).unwrap();
    r.shutdown();assert_eq!(r.submit(request()).unwrap_err().code,RunnerErrorCode::Closed);assert_eq!(terminal(&r,&queued).state,State::Cancelled);gate.release();assert_eq!(terminal(&r,&active).state,State::Cancelled);r.join().unwrap();
}
#[test]
fn drop_does_not_join_a_blocked_executor_and_unknown_ids_are_typed() {
    let (r,gate,rx)=gated(Config::default());assert_eq!(r.snapshot("unknown").unwrap_err().code,RunnerErrorCode::NotFound);
    let id=r.submit(request()).unwrap();rx.recv_timeout(Duration::from_secs(5)).unwrap();assert!(r.wait_for_terminal(&id,Duration::ZERO).unwrap().is_none());drop(r);gate.release();
}
#[test]
fn configuration_request_and_serialized_reply_budgets_are_enforced() {
    assert!(Runner::new(Config {max_pending:0,max_retained:2}).is_err());assert!(Runner::new(Config {max_pending:4,max_retained:9}).is_err());
    let mut invalid=request();invalid.max_entries=Some(1001);assert!(invalid.validate().is_err());invalid=request();invalid.actions=vec![Action::Resource {query:"x".into()}];assert!(invalid.validate().is_err());
    let r=Runner::with_executor(Config::default(),Arc::new(|_,_|Ok(response()))).unwrap();let mut small=request();small.max_reply_bytes=Some(1);let id=r.submit(small).unwrap();
    let failed=terminal(&r,&id);assert_eq!(failed.error.unwrap().code,ErrorCode::LimitExceeded);assert!(r.take_result(&id).unwrap().is_none());r.join().unwrap();
}
