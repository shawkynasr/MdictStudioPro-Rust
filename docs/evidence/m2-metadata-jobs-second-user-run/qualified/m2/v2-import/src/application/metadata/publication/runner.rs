//! Publication-specific serial worker. Successful execution means the file
//! committed: no cancellation check or fallible reply accounting follows it.
//! Panics carry publication_uncertain; callers must inspect the destination.
use super::{Request,Output as Response,execute};
use crate::{CancellationToken,ImportJob,Progress,ErrorCode};
pub use studio_application::runner::{State,RunnerError,RunnerErrorCode,CancelOutcome};
use serde::Serialize;
use std::{collections::{BTreeMap,VecDeque},panic::{catch_unwind,AssertUnwindSafe},sync::{Arc,Mutex,MutexGuard,Condvar},thread::{self,JoinHandle},time::{Duration,Instant}};
pub type Result<T>=std::result::Result<T,RunnerError>;
fn error(code:RunnerErrorCode,message:&str)->RunnerError {RunnerError {code,message:message.into()}}
fn message(mut value:String)->String {if value.len()>4096 {let mut n=4096;while !value.is_char_boundary(n) {n-=1;}value.truncate(n);}value}
#[derive(Clone,Debug,Serialize)]
pub struct Failure {pub code:ErrorCode,pub detail:&'static str,pub message:String,pub publication_uncertain:bool}
#[derive(Clone,Debug,Serialize)]
pub struct Snapshot {
    pub job_id:String,pub revision:u64,pub state:State,pub cancel_requested:bool,
    pub latest_progress:Option<Progress>,pub error:Option<Failure>,
    pub result_available:bool,pub operation:&'static str,
}
#[derive(Clone,Copy,Debug)]
pub struct Config {pub max_pending:usize,pub max_retained:usize}
impl Default for Config {fn default()->Self {Self {max_pending:2,max_retained:8}}}
struct Record {snapshot:Snapshot,token:CancellationToken,request:Option<Request>,response:Option<Response>,dirty:bool}
impl Record {fn changed(&mut self) {self.snapshot.revision=self.snapshot.revision.saturating_add(1);self.dirty=true;}}
struct Inner {records:BTreeMap<String,Record>,pending:VecDeque<String>,closed:bool,next:u64}
struct Shared {inner:Mutex<Inner>,changed:Condvar,config:Config}
impl Shared {fn lock(&self)->MutexGuard<'_,Inner> {self.inner.lock().unwrap_or_else(|e|e.into_inner())}}
type Executor=dyn for<'a> Fn(&Request,&mut ImportJob<'a>)->crate::Result<Response>+Send+Sync+'static;
pub struct Runner {shared:Arc<Shared>,worker:Option<JoinHandle<()>>}
impl Runner {
    pub fn new(config:Config)->Result<Self> {Self::with_executor(config,Arc::new(execute))}
    fn with_executor(config:Config,executor:Arc<Executor>)->Result<Self> {
        if config.max_pending==0||config.max_pending>4||config.max_retained<=config.max_pending||config.max_retained>8 {
            return Err(error(RunnerErrorCode::InvalidInput,"Require 1..4 pending and pending+1..8 retained publication jobs"));
        }
        let shared=Arc::new(Shared {inner:Mutex::new(Inner {records:BTreeMap::new(),pending:VecDeque::new(),closed:false,next:1}),changed:Condvar::new(),config});
        let worker_shared=shared.clone();
        let worker=thread::Builder::new().name("studio-publication-worker".into()).spawn(move||worker(worker_shared,executor)).map_err(|e|error(RunnerErrorCode::Internal,&e.to_string()))?;
        Ok(Self {shared,worker:Some(worker)})
    }
    pub fn submit(&self,request:Request)->Result<String> {
        request.validate().map_err(|e|error(RunnerErrorCode::InvalidInput,&e.to_string()))?;
        let operation=request.operation();
        let mut inner=self.shared.lock();
        if inner.closed {return Err(error(RunnerErrorCode::Closed,"Publication runner closed"));}
        if inner.pending.len()>=self.shared.config.max_pending {return Err(error(RunnerErrorCode::QueueFull,"Publication queue full"));}
        if inner.records.len()>=self.shared.config.max_retained {return Err(error(RunnerErrorCode::RetentionFull,"Forget terminal publication jobs before submitting more"));}
        let next=inner.next.checked_add(1).ok_or_else(||error(RunnerErrorCode::Internal,"Publication IDs exhausted"))?;
        let id=format!("publish-{:016x}",inner.next);inner.next=next;
        let snapshot=Snapshot {job_id:id.clone(),revision:1,state:State::Queued,cancel_requested:false,latest_progress:None,error:None,result_available:false,operation};
        inner.records.insert(id.clone(),Record {snapshot,token:CancellationToken::default(),request:Some(request),response:None,dirty:true});inner.pending.push_back(id.clone());
        self.shared.changed.notify_all();Ok(id)
    }
    pub fn snapshot(&self,id:&str)->Result<Snapshot> {self.shared.lock().records.get(id).map(|r|r.snapshot.clone()).ok_or_else(||error(RunnerErrorCode::NotFound,"Unknown publication ID"))}
    pub fn drain_events(&self)->Vec<Snapshot> {
        let mut inner=self.shared.lock();let mut out=Vec::new();
        for record in inner.records.values_mut() {if record.dirty {out.push(record.snapshot.clone());record.dirty=false;}}out
    }
    /// Transfers ownership once, releasing the runner's retained reply bytes.
    pub fn take_result(&self,id:&str)->Result<Option<Response>> {
        let mut inner=self.shared.lock();let record=inner.records.get_mut(id).ok_or_else(||error(RunnerErrorCode::NotFound,"Unknown publication ID"))?;
        if !record.snapshot.state.is_terminal() {return Err(error(RunnerErrorCode::StillRunning,"Publication unfinished"));}
        let value=record.response.take();if value.is_some() {record.snapshot.result_available=false;record.changed();self.shared.changed.notify_all();}Ok(value)
    }
    pub fn forget(&self,id:&str)->Result<()> {
        let mut inner=self.shared.lock();let record=inner.records.get(id).ok_or_else(||error(RunnerErrorCode::NotFound,"Unknown publication ID"))?;
        if !record.snapshot.state.is_terminal() {return Err(error(RunnerErrorCode::StillRunning,"Publication unfinished"));}inner.records.remove(id);Ok(())
    }
    pub fn cancel(&self,id:&str)->Result<CancelOutcome> {
        let mut inner=self.shared.lock();let record=inner.records.get_mut(id).ok_or_else(||error(RunnerErrorCode::NotFound,"Unknown publication ID"))?;
        if record.snapshot.state.is_terminal() {return Ok(CancelOutcome::AlreadyFinished);}
        if record.snapshot.cancel_requested {return Ok(CancelOutcome::AlreadyRequested);}
        record.token.cancel();record.snapshot.cancel_requested=true;let queued=record.snapshot.state==State::Queued;
        if queued {cancel_queued(record);}else{record.changed();}
        if queued {inner.pending.retain(|value|value!=id);}self.shared.changed.notify_all();Ok(CancelOutcome::Requested)
    }
    /// Blocking helper for CLI/tests only; never call this from a UI handler.
    pub fn wait_for_terminal(&self,id:&str,timeout:Duration)->Result<Option<Snapshot>> {
        let deadline=Instant::now().checked_add(timeout).ok_or_else(||error(RunnerErrorCode::InvalidInput,"Timeout overflow"))?;
        let mut inner=self.shared.lock();
        loop {
            let record=inner.records.get(id).ok_or_else(||error(RunnerErrorCode::NotFound,"Unknown publication ID"))?;
            if record.snapshot.state.is_terminal() {return Ok(Some(record.snapshot.clone()));}
            let remaining=deadline.saturating_duration_since(Instant::now());if remaining.is_zero() {return Ok(None);}
            inner=self.shared.changed.wait_timeout(inner,remaining).unwrap_or_else(|e|e.into_inner()).0;
        }
    }
    pub fn shutdown(&self) {
        let mut inner=self.shared.lock();if inner.closed {return;}inner.closed=true;inner.pending.clear();
        for record in inner.records.values_mut() {if !record.snapshot.state.is_terminal() {record.token.cancel();record.snapshot.cancel_requested=true;if record.snapshot.state==State::Queued {cancel_queued(record);}else{record.changed();}}}
        self.shared.changed.notify_all();
    }
    /// Join only off the UI thread. Drop requests cancellation and detaches.
    pub fn join(mut self)->Result<()> {self.shutdown();if let Some(worker)=self.worker.take() {worker.join().map_err(|_|error(RunnerErrorCode::Internal,"Publication worker panicked outside execution"))?;}Ok(())}
}
impl Drop for Runner {fn drop(&mut self) {self.shutdown();drop(self.worker.take());}}
fn cancel_queued(record:&mut Record) {
    record.request=None;record.snapshot.state=State::Cancelled;record.snapshot.error=Some(Failure {code:ErrorCode::Cancelled,detail:"cancelled",message:"Cancelled before publication".into(),publication_uncertain:false});record.changed();
}
fn worker(shared:Arc<Shared>,executor:Arc<Executor>) {
    loop {
        let (id,request,token)={
            let mut inner=shared.lock();while inner.pending.is_empty()&&!inner.closed {inner=shared.changed.wait(inner).unwrap_or_else(|e|e.into_inner());}
            let Some(id)=inner.pending.pop_front() else {return;};let record=inner.records.get_mut(&id).expect("Queued publication exists");
            record.snapshot.state=State::Running;record.changed();let request=record.request.take().expect("Queued request exists");let token=record.token.clone();shared.changed.notify_all();(id,request,token)
        };
        let outcome=catch_unwind(AssertUnwindSafe(|| {
            let mut progress=|p:Progress| {let mut inner=shared.lock();if let Some(record)=inner.records.get_mut(&id) {record.snapshot.latest_progress=Some(p);record.changed();}shared.changed.notify_all();};
            let mut job=ImportJob::new(&id,&token,&mut progress);job.check()?;
            // Publication has its own final pre-commit cancellation check.
            // Success must win over cancellation arriving after commit.
            executor(&request,&mut job)
        }));
        let mut inner=shared.lock();let record=inner.records.get_mut(&id).expect("Running publication cannot be forgotten");
        match outcome {
            Ok(Ok(value))=>{record.snapshot.state=State::Succeeded;record.snapshot.result_available=true;record.response=Some(value);},
            Ok(Err(e))=>{record.snapshot.state=if e.code==ErrorCode::Cancelled {State::Cancelled}else{State::Failed};record.snapshot.error=Some(Failure {code:e.code,detail:e.detail,message:message(e.message),publication_uncertain:false});},
            Err(_)=>{record.snapshot.state=State::Failed;record.snapshot.error=Some(Failure {code:ErrorCode::Internal,detail:"panic",message:"Publication worker panicked; inspect the destination before retrying".into(),publication_uncertain:true});},
        }record.changed();shared.changed.notify_all();
    }
}
#[cfg(test)]mod tests;

