use super::*;
use std::sync::mpsc;
fn request(name:&str)->PublishRequest {PublishRequest {conversion:crate::ConversionRequest {converter:crate::ConverterId::MoeMini,input:"unused.xlsx".into(),worksheet:None},destination:name.into()}}
fn value()->Published {Published {converter:crate::ConverterId::MoeMini,txt_profile:crate::TxtProfile::CanonicalV1,entries:1,file_bytes:1,
    metrics:crate::Metrics {primary_entries:1,alias_redirects:0,traditional_entries:0,skipped_rows_or_lines:0},comments:Vec::new()}}
struct Gate {open:Mutex<bool>,changed:Condvar}
impl Gate {
    fn new()->Arc<Self> {Arc::new(Self {open:Mutex::new(false),changed:Condvar::new()})}
    fn release(&self) {*self.open.lock().unwrap()=true;self.changed.notify_all();}
    fn wait(&self) {let open=self.open.lock().unwrap();let (open,_)=self.changed.wait_timeout_while(open,Duration::from_secs(5),|v|!*v).unwrap();assert!(*open,"Test gate was not released");}
}
fn done(r:&Runner,id:&str)->Snapshot {r.wait_for_terminal(id,Duration::from_secs(5)).unwrap().expect("Job reached terminal state")}

#[test]
fn serial_admission_queue_limit_and_queued_cancel_are_deterministic() {
    let gate=Gate::new();let hold=gate.clone();let (tx,rx)=mpsc::sync_channel(1);
    let executor:Arc<Executor>=Arc::new(move|request,_,job|{
        if request.destination==PathBuf::from("first") {tx.send(()).unwrap();hold.wait();}
        job.check()?;Ok(value())
    });
    let r=Runner::with_executor(Config {max_pending:1,max_retained:4},executor).unwrap();
    let first=r.submit(request("first"),Limits::default()).unwrap();rx.recv_timeout(Duration::from_secs(5)).unwrap();
    let second=r.submit(request("second"),Limits::default()).unwrap();
    assert_eq!(r.snapshot(&first).unwrap().state,State::Running);assert_eq!(r.snapshot(&second).unwrap().state,State::Queued);
    assert_eq!(r.submit(request("third"),Limits::default()).unwrap_err().code,RunnerErrorCode::QueueFull);
    assert_eq!(r.forget(&first).unwrap_err().code,RunnerErrorCode::StillRunning);
    assert_eq!(r.cancel(&second).unwrap(),CancelOutcome::Requested);assert_eq!(done(&r,&second).state,State::Cancelled);
    assert_eq!(r.cancel(&second).unwrap(),CancelOutcome::AlreadyFinished);
    let third=r.submit(request("third"),Limits::default()).unwrap();gate.release();
    assert_eq!(done(&r,&first).state,State::Succeeded);assert_eq!(done(&r,&third).state,State::Succeeded);r.join().unwrap();
}
#[test]
fn cancellation_is_per_job_and_never_turns_late_success_into_cancelled() {
    let gate=Gate::new();let hold=gate.clone();let (tx,rx)=mpsc::sync_channel(1);
    let executor:Arc<Executor>=Arc::new(move|request,_,job| {
        if request.destination==PathBuf::from("active") {tx.send(()).unwrap();hold.wait();job.check()?;}
        Ok(value())
    });
    let r=Runner::with_executor(Config::default(),executor).unwrap();let active=r.submit(request("active"),Limits::default()).unwrap();rx.recv_timeout(Duration::from_secs(5)).unwrap();
    let next=r.submit(request("next"),Limits::default()).unwrap();assert_eq!(r.cancel(&active).unwrap(),CancelOutcome::Requested);assert_eq!(r.cancel(&active).unwrap(),CancelOutcome::AlreadyRequested);gate.release();
    assert_eq!(done(&r,&active).state,State::Cancelled);assert_eq!(done(&r,&next).state,State::Succeeded);r.join().unwrap();
    // Simulate cancellation racing after a commit. The executor returns a
    // committed success even when its token was set while it was finishing.
    let gate=Gate::new();let hold=gate.clone();let (tx,rx)=mpsc::sync_channel(1);
    let executor:Arc<Executor>=Arc::new(move|_,_,job|{job.forward(crate::Stage::Publishing,"published",1,1);tx.send(()).unwrap();hold.wait();Ok(value())});
    let r=Runner::with_executor(Config::default(),executor).unwrap();let id=r.submit(request("committed"),Limits::default()).unwrap();rx.recv_timeout(Duration::from_secs(5)).unwrap();r.cancel(&id).unwrap();gate.release();
    let result=done(&r,&id);assert_eq!(result.state,State::Succeeded);assert!(result.cancel_requested);assert!(result.error.is_none());r.join().unwrap();
}
#[test]
fn progress_flood_coalesces_and_retention_requires_explicit_forget() {
    let executor:Arc<Executor>=Arc::new(|_,_,job|{for i in 0..10_000 {job.forward(crate::Stage::Converting,"tick",i,10_000);}Ok(value())});
    let r=Runner::with_executor(Config {max_pending:1,max_retained:2},executor).unwrap();let a=r.submit(request("a"),Limits::default()).unwrap();done(&r,&a);
    let updates=r.drain_events();assert_eq!(updates.len(),1);assert_eq!(updates[0].state,State::Succeeded);assert_eq!(updates[0].latest_progress.as_ref().unwrap().completed,9999);
    assert!(updates[0].revision>=10_002);assert!(r.drain_events().is_empty());assert_eq!(r.snapshot(&a).unwrap().state,State::Succeeded);
    let b=r.submit(request("b"),Limits::default()).unwrap();done(&r,&b);assert_eq!(r.submit(request("c"),Limits::default()).unwrap_err().code,RunnerErrorCode::RetentionFull);
    r.forget(&a).unwrap();assert_eq!(r.snapshot(&a).unwrap_err().code,RunnerErrorCode::NotFound);let c=r.submit(request("c"),Limits::default()).unwrap();done(&r,&c);r.join().unwrap();
}
#[test]
fn worker_failure_and_panic_do_not_prevent_later_jobs() {
    let executor:Arc<Executor>=Arc::new(|request,_,_|{
        if request.destination==PathBuf::from("panic") {panic!("Injected task panic");}
        if request.destination==PathBuf::from("bad") {return Err(Error::new(ErrorCode::MalformedSource,"Typed failure"));}
        Ok(value())
    });
    let r=Runner::with_executor(Config::default(),executor).unwrap();
    for (name,code,uncertain) in [("bad",ErrorCode::MalformedSource,false),("panic",ErrorCode::Internal,true)] {
        let id=r.submit(request(name),Limits::default()).unwrap();let result=done(&r,&id);assert_eq!(result.state,State::Failed);let e=result.error.unwrap();assert_eq!(e.code,code);assert_eq!(e.publication_uncertain,uncertain);
    }
    let id=r.submit(request("good"),Limits::default()).unwrap();assert_eq!(done(&r,&id).state,State::Succeeded);r.join().unwrap();
}
#[test]
fn shutdown_rejects_admission_cancels_queue_and_requests_active_cancel() {
    let gate=Gate::new();let hold=gate.clone();let (tx,rx)=mpsc::sync_channel(1);
    let executor:Arc<Executor>=Arc::new(move|_,_,job|{tx.send(()).unwrap();hold.wait();job.check()?;Ok(value())});
    let r=Runner::with_executor(Config::default(),executor).unwrap();let active=r.submit(request("active"),Limits::default()).unwrap();rx.recv_timeout(Duration::from_secs(5)).unwrap();let pending=r.submit(request("pending"),Limits::default()).unwrap();
    r.shutdown();assert_eq!(r.submit(request("closed"),Limits::default()).unwrap_err().code,RunnerErrorCode::Closed);assert_eq!(done(&r,&pending).state,State::Cancelled);gate.release();assert_eq!(done(&r,&active).state,State::Cancelled);r.join().unwrap();
}
#[test]
fn invalid_config_unknown_jobs_timeout_and_nonblocking_drop_are_safe() {
    assert!(Runner::new(Config {max_pending:0,max_retained:2}).is_err());
    let gate=Gate::new();let hold=gate.clone();let (tx,rx)=mpsc::sync_channel(1);
    let executor:Arc<Executor>=Arc::new(move|_,_,job|{tx.send(()).unwrap();hold.wait();job.check()?;Ok(value())});
    let r=Runner::with_executor(Config::default(),executor).unwrap();assert_eq!(r.cancel("unknown").unwrap_err().code,RunnerErrorCode::NotFound);
    let id=r.submit(request("active"),Limits::default()).unwrap();rx.recv_timeout(Duration::from_secs(5)).unwrap();assert!(r.wait_for_terminal(&id,Duration::ZERO).unwrap().is_none());
    drop(r);gate.release(); // Drop cannot join while the executor is gated.
}
