//! One serial background worker and bounded, coalescing GUI mailbox.
//! Polling and cancellation never execute dictionary work on the caller.
pub mod dictionary;
use crate::{CancellationToken,Error,ErrorCode,JobContext,Limits,Progress,PublishRequest,Published};
use serde::Serialize;
use std::{collections::{BTreeMap,VecDeque},fmt,panic::{catch_unwind,AssertUnwindSafe},
    path::PathBuf,sync::{Arc,Condvar,Mutex,MutexGuard},thread::{self,JoinHandle},time::{Duration,Instant}};

#[derive(Clone,Copy,Debug,PartialEq,Eq,Serialize)]
#[serde(rename_all="snake_case")]
pub enum State {Queued,Running,Succeeded,Failed,Cancelled}
impl State {pub fn is_terminal(self)->bool {matches!(self,Self::Succeeded|Self::Failed|Self::Cancelled)}}
#[derive(Clone,Copy,Debug,PartialEq,Eq,Serialize)]
#[serde(rename_all="snake_case")]
pub enum RunnerErrorCode {InvalidInput,QueueFull,RetentionFull,Closed,NotFound,StillRunning,Internal}
#[derive(Debug,Serialize)]
pub struct RunnerError {pub code:RunnerErrorCode,pub message:String}
impl fmt::Display for RunnerError {fn fmt(&self,f:&mut fmt::Formatter<'_>)->fmt::Result {write!(f,"{:?}: {}",self.code,self.message)}}
impl std::error::Error for RunnerError {}
pub type Result<T>=std::result::Result<T,RunnerError>;
fn error(code:RunnerErrorCode,message:&str)->RunnerError {RunnerError {code,message:message.into()}}

#[derive(Clone,Debug,Serialize)]
pub struct Failure {pub code:ErrorCode,pub message:String,pub publication_uncertain:bool}
fn message(mut s:String)->String {if s.len()>4096 {let mut n=4096;while !s.is_char_boundary(n) {n-=1;}s.truncate(n);}s}
#[derive(Clone,Debug,Serialize)]
pub struct Output {
    pub destination:PathBuf,pub converter:crate::ConverterId,pub entries:usize,pub file_bytes:usize,
    pub primary_entries:usize,pub alias_redirects:usize,pub traditional_entries:usize,pub skipped_rows_or_lines:usize,
}
#[derive(Clone,Debug,Serialize)]
pub struct Snapshot {
    pub job_id:String,pub revision:u64,pub state:State,pub cancel_requested:bool,
    pub latest_progress:Option<Progress>,pub output:Option<Output>,pub error:Option<Failure>,
    pub operation:&'static str,pub dictionary_output:Option<dictionary::Output>,
}
#[derive(Clone,Copy,Debug)]
pub struct Config {pub max_pending:usize,pub max_retained:usize}
impl Default for Config {fn default()->Self {Self {max_pending:4,max_retained:32}}}
#[derive(Clone,Copy,Debug,PartialEq,Eq,Serialize)]
#[serde(rename_all="snake_case")]
pub enum CancelOutcome {Requested,AlreadyRequested,AlreadyFinished}
enum Work {
    Conversion {request:PublishRequest,limits:Limits},
    Dictionary {request:dictionary::Request,limits:Limits},
}
enum Completion {Conversion(Published,PathBuf),Dictionary(dictionary::Output)}
struct Record {snapshot:Snapshot,token:CancellationToken,work:Option<Work>,dirty:bool}
impl Record {fn changed(&mut self) {self.snapshot.revision=self.snapshot.revision.saturating_add(1);self.dirty=true;}}
struct Inner {records:BTreeMap<String,Record>,pending:VecDeque<String>,closed:bool,next_id:u64}
struct Shared {inner:Mutex<Inner>,changed:Condvar,config:Config}
impl Shared {fn lock(&self)->MutexGuard<'_,Inner> {self.inner.lock().unwrap_or_else(|e|e.into_inner())}}
type Executor=dyn for<'a> Fn(&PublishRequest,&Limits,&mut JobContext<'a>)->crate::Result<Published>+Send+Sync+'static;

/// Own one runner per application session. IDs are unique within that runner.
/// Drop requests cancellation and detaches; use join only off the UI thread.
pub struct Runner {shared:Arc<Shared>,worker:Option<JoinHandle<()>>}
impl Runner {
    pub fn new(config:Config)->Result<Self> {Self::with_executor(config,Arc::new(crate::convert_to_txt))}
    fn with_executor(config:Config,executor:Arc<Executor>)->Result<Self> {
        if config.max_pending==0||config.max_pending>128||config.max_retained<=config.max_pending||config.max_retained>256 {
            return Err(error(RunnerErrorCode::InvalidInput,"Require 1..128 pending jobs and pending+1..256 retained jobs"));
        }
        let shared=Arc::new(Shared {inner:Mutex::new(Inner {records:BTreeMap::new(),pending:VecDeque::new(),closed:false,next_id:1}),changed:Condvar::new(),config});
        let worker_shared=shared.clone();
        let worker=thread::Builder::new().name("studio-conversion-worker".into()).spawn(move||worker(worker_shared,executor))
            .map_err(|e|RunnerError {code:RunnerErrorCode::Internal,message:message(e.to_string())})?;
        Ok(Self {shared,worker:Some(worker)})
    }
    pub fn submit(&self,request:PublishRequest,limits:Limits)->Result<String> {
        // Metadata bounds are independent of caller-supplied processing budgets.
        if request.destination.as_os_str().len()>8192||request.conversion.input.as_os_str().len()>8192||request.conversion.worksheet.as_ref().is_some_and(|s|s.len()>4096) {
            return Err(error(RunnerErrorCode::InvalidInput,"Job paths/sheet name exceed metadata limits"));
        }
        self.enqueue(Work::Conversion {request,limits})
    }
    pub fn submit_dictionary(&self,request:dictionary::Request,limits:Limits)->Result<String> {
        if !request.metadata_valid() {return Err(error(RunnerErrorCode::InvalidInput,"Dictionary request metadata exceeds limits"));}
        self.enqueue(Work::Dictionary {request,limits})
    }
    fn enqueue(&self,work:Work)->Result<String> {
        let operation=match &work {Work::Conversion {..}=>"convert_txt",Work::Dictionary {request,..}=>request.operation()};
        let mut inner=self.shared.lock();
        if inner.closed {return Err(error(RunnerErrorCode::Closed,"Job runner is closed"));}
        if inner.pending.len()>=self.shared.config.max_pending {return Err(error(RunnerErrorCode::QueueFull,"Pending job queue is full"));}
        if inner.records.len()>=self.shared.config.max_retained {return Err(error(RunnerErrorCode::RetentionFull,"Forget completed jobs before submitting more"));}
        let next=inner.next_id.checked_add(1).ok_or_else(||error(RunnerErrorCode::Internal,"Job IDs exhausted"))?;
        let id=format!("job-{:016x}",inner.next_id);inner.next_id=next;
        let snapshot=Snapshot {job_id:id.clone(),revision:1,state:State::Queued,cancel_requested:false,latest_progress:None,output:None,error:None,operation,dictionary_output:None};
        inner.records.insert(id.clone(),Record {snapshot,token:CancellationToken::default(),work:Some(work),dirty:true});inner.pending.push_back(id.clone());
        self.shared.changed.notify_all();Ok(id)
    }
    pub fn snapshot(&self,id:&str)->Result<Snapshot> {
        self.shared.lock().records.get(id).map(|r|r.snapshot.clone()).ok_or_else(||error(RunnerErrorCode::NotFound,"Unknown job ID"))
    }
    pub fn snapshots(&self)->Vec<Snapshot> {self.shared.lock().records.values().map(|r|r.snapshot.clone()).collect()}
    /// At most one update per retained job. Intermediate progress may coalesce;
    /// terminal results remain queryable until explicitly forgotten.
    pub fn drain_events(&self)->Vec<Snapshot> {
        let mut inner=self.shared.lock();let mut out=Vec::new();
        for record in inner.records.values_mut() {if record.dirty {out.push(record.snapshot.clone());record.dirty=false;}}
        out
    }
    pub fn cancel(&self,id:&str)->Result<CancelOutcome> {
        let mut inner=self.shared.lock();let record=inner.records.get_mut(id).ok_or_else(||error(RunnerErrorCode::NotFound,"Unknown job ID"))?;
        if record.snapshot.state.is_terminal() {return Ok(CancelOutcome::AlreadyFinished);}
        if record.snapshot.cancel_requested {return Ok(CancelOutcome::AlreadyRequested);}
        record.token.cancel();record.snapshot.cancel_requested=true;
        let queued=record.snapshot.state==State::Queued;
        if queued {cancel_queued(record);}else{record.changed();}
        if queued {inner.pending.retain(|pending|pending!=id);}
        self.shared.changed.notify_all();Ok(CancelOutcome::Requested)
    }
    pub fn forget(&self,id:&str)->Result<()> {
        let mut inner=self.shared.lock();let record=inner.records.get(id).ok_or_else(||error(RunnerErrorCode::NotFound,"Unknown job ID"))?;
        if !record.snapshot.state.is_terminal() {return Err(error(RunnerErrorCode::StillRunning,"Cannot forget an unfinished job"));}
        inner.records.remove(id);Ok(())
    }
    /// Blocking helper for CLI/tests or a shutdown worker, never a UI handler.
    pub fn wait_for_terminal(&self,id:&str,timeout:Duration)->Result<Option<Snapshot>> {
        let deadline=Instant::now().checked_add(timeout).ok_or_else(||error(RunnerErrorCode::InvalidInput,"Timeout is too large"))?;
        let mut inner=self.shared.lock();
        loop {
            let record=inner.records.get(id).ok_or_else(||error(RunnerErrorCode::NotFound,"Unknown job ID"))?;
            if record.snapshot.state.is_terminal() {return Ok(Some(record.snapshot.clone()));}
            let remaining=deadline.saturating_duration_since(Instant::now());if remaining.is_zero() {return Ok(None);}
            let (guard,_)=self.shared.changed.wait_timeout(inner,remaining).unwrap_or_else(|e|e.into_inner());inner=guard;
        }
    }
    /// Nonblocking: stop admission, cancel pending jobs, request active cancel.
    pub fn shutdown(&self) {
        let mut inner=self.shared.lock();if inner.closed {return;}inner.closed=true;inner.pending.clear();
        for record in inner.records.values_mut() {
            if record.snapshot.state.is_terminal() {continue;}
            record.token.cancel();record.snapshot.cancel_requested=true;
            if record.snapshot.state==State::Queued {cancel_queued(record);}else{record.changed();}
        }self.shared.changed.notify_all();
    }
    pub fn join(mut self)->Result<()> {
        self.shutdown();
        if let Some(worker)=self.worker.take() {worker.join().map_err(|_|error(RunnerErrorCode::Internal,"Background worker panicked outside job execution"))?;}
        Ok(())
    }
}
impl Drop for Runner {fn drop(&mut self) {self.shutdown();drop(self.worker.take());}}
fn cancel_queued(record:&mut Record) {
    record.snapshot.state=State::Cancelled;record.snapshot.error=Some(Failure {code:ErrorCode::Cancelled,message:"Cancelled before start".into(),publication_uncertain:false});record.work=None;record.changed();
}
fn worker(shared:Arc<Shared>,executor:Arc<Executor>) {
    loop {
        let (id,work,token)={
            let mut inner=shared.lock();
            while inner.pending.is_empty()&&!inner.closed {inner=shared.changed.wait(inner).unwrap_or_else(|e|e.into_inner());}
            let Some(id)=inner.pending.pop_front() else {return;};
            let record=inner.records.get_mut(&id).expect("Queued record exists");
            record.snapshot.state=State::Running;record.changed();
            let work=record.work.take().expect("Queued work exists");let token=record.token.clone();shared.changed.notify_all();(id,work,token)
        };
        let outcome=catch_unwind(AssertUnwindSafe(|| {
            let mut progress=|p:Progress|{
                let mut inner=shared.lock();if let Some(record)=inner.records.get_mut(&id) {record.snapshot.latest_progress=Some(p);record.changed();}shared.changed.notify_all();
            };
            let mut job=JobContext::new(&id,&token,&mut progress);
            match &work {
                Work::Conversion {request,limits}=>executor(request,limits,&mut job).map(|v|Completion::Conversion(v,request.destination.clone())),
                Work::Dictionary {request,limits}=>dictionary::execute(request,limits,&mut job).map(Completion::Dictionary),
            }
        }));
        let mut inner=shared.lock();let record=inner.records.get_mut(&id).expect("Active record cannot be forgotten");
        match outcome {
            Ok(Ok(Completion::Conversion(value,destination)))=>{
                record.snapshot.state=State::Succeeded;
                record.snapshot.output=Some(Output {destination,converter:value.converter,entries:value.entries,file_bytes:value.file_bytes,
                    primary_entries:value.metrics.primary_entries,alias_redirects:value.metrics.alias_redirects,traditional_entries:value.metrics.traditional_entries,skipped_rows_or_lines:value.metrics.skipped_rows_or_lines});
            },
            Ok(Ok(Completion::Dictionary(value)))=>{record.snapshot.state=State::Succeeded;record.snapshot.dictionary_output=Some(value);},
            Ok(Err(Error {code,message:detail}))=>{
                record.snapshot.state=if code==ErrorCode::Cancelled {State::Cancelled}else{State::Failed};
                record.snapshot.error=Some(Failure {code,message:message(detail),publication_uncertain:false});
            },
            Err(_)=>{
                record.snapshot.state=State::Failed;record.snapshot.error=Some(Failure {code:ErrorCode::Internal,message:"Worker panicked; inspect the destination before retrying".into(),publication_uncertain:true});
            },
        }record.changed();shared.changed.notify_all();
    }
}

#[cfg(test)]
mod tests;
