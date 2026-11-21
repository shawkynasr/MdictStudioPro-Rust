//! Persistent, read-only indexed sessions. Each actor owns its borrowed index
//! on the worker stack; no self-referential structs or leaked reader lifetimes.
use studio_indexed_engine::{Dictionary,Kind,Limits,ImportJob,Error,index::{Index,Manifest,Page}};
pub use studio_indexed_engine::{CancellationToken,Progress,ErrorCode,index::Policy};
use serde::{Serialize,Deserialize};
use std::{collections::{BTreeMap,VecDeque},sync::{Arc,Weak,Mutex,MutexGuard,Condvar},thread::{self,JoinHandle},time::{Duration,Instant},panic::{catch_unwind,AssertUnwindSafe},path::PathBuf,io::Write};
pub const MEMORY_RESERVATION:usize=96*1024*1024;
pub const TEMP_RESERVATION:u64=768*1024*1024;
pub const RETAINED_BYTE_CAP:usize=8*1024*1024;
pub const MAX_SESSION_HANDLES:usize=8;
#[derive(Clone,Copy,Debug,Serialize,Deserialize)]#[serde(rename_all="snake_case")]
pub enum DictionaryKind {Mdx,Mdd}
#[derive(Debug,Deserialize)]#[serde(deny_unknown_fields)]
pub struct OpenRequest {pub source:PathBuf,pub artifact:PathBuf,pub kind:DictionaryKind,pub policy:Policy}
#[derive(Clone,Debug,Deserialize)]#[serde(deny_unknown_fields)]
pub struct PageRequest {pub query:String,pub offset:u64,pub limit:usize}
impl PageRequest {fn validate(&self)->ApiResult<()> {
 if self.query.is_empty()||self.query.len()>4096||self.query.contains('\0')||self.limit>128 {return Err(api(ApiCode::InvalidInput,"Require nonempty NUL-free query <=4 KiB and page <=128 rows"));}Ok(())
}}
#[derive(Clone,Copy,Debug,Serialize,PartialEq,Eq)]#[serde(rename_all="snake_case")]
pub enum ApiCode {InvalidInput,Closed,NotReady,NotFound,QueueFull,RetentionFull,ResourceLimit,StillRunning,Internal}
#[derive(Debug,Serialize)]pub struct ApiError {pub code:ApiCode,pub message:String}
impl std::fmt::Display for ApiError {fn fmt(&self,f:&mut std::fmt::Formatter<'_>)->std::fmt::Result {write!(f,"{:?}: {}",self.code,self.message)}}
impl std::error::Error for ApiError {}
pub type ApiResult<T>=std::result::Result<T,ApiError>;
fn api(code:ApiCode,message:&str)->ApiError {ApiError {code,message:message.into()}}
#[derive(Clone,Copy,Debug)]pub struct Config {pub max_sessions:usize,pub max_pending:usize,pub max_retained:usize,pub max_reply_bytes:usize}
impl Default for Config {fn default()->Self {Self {max_sessions:2,max_pending:2,max_retained:8,max_reply_bytes:2*1024*1024}}}
#[derive(Clone,Copy,Debug,Serialize,PartialEq,Eq)]#[serde(rename_all="snake_case")]
pub enum JobState {Queued,Running,Succeeded,Failed,Cancelled}
impl JobState {pub fn terminal(self)->bool {matches!(self,Self::Succeeded|Self::Failed|Self::Cancelled)}}
#[derive(Clone,Copy,Debug,Serialize,PartialEq,Eq)]#[serde(rename_all="snake_case")]
pub enum SessionState {Opening,Ready,Closing,Closed,Failed}
impl SessionState {pub fn terminal(self)->bool {matches!(self,Self::Closed|Self::Failed)}}
#[derive(Clone,Debug,Serialize)]pub struct Failure {pub code:ErrorCode,pub detail:&'static str,pub message:String}
fn failure(code:ErrorCode,detail:&'static str,message:&str)->Failure {let mut message=message.to_string();if message.len()>4096 {let mut n=4096;while !message.is_char_boundary(n) {n-=1;}message.truncate(n);}Failure {code,detail,message}}
impl From<Error> for Failure {fn from(e:Error)->Self {failure(e.code,e.detail,&e.message)}}
#[derive(Clone,Debug,Serialize)]pub struct JobSnapshot {pub job_id:String,pub state:JobState,pub revision:u64,pub cancel_requested:bool,pub latest_progress:Option<Progress>,pub error:Option<Failure>,pub result_available:bool,pub result_bytes:usize}
#[derive(Clone,Debug,Serialize)]pub struct SessionSnapshot {pub session_id:String,pub state:SessionState,pub retained_jobs:usize,pub queued_jobs:usize,pub error:Option<Failure>}
#[derive(Debug,Serialize)]#[serde(tag="operation",content="value",rename_all="snake_case")]
pub enum Response {Opened(Manifest),Page(Page)}
#[derive(Clone,Copy,Debug,Serialize,PartialEq,Eq)]#[serde(rename_all="snake_case")]
pub enum CancelOutcome {Requested,AlreadyRequested,AlreadyFinished}
#[derive(Debug,Serialize)]pub struct Admission {pub live_sessions:usize,pub retained_session_handles:usize,pub reserved_memory_bytes:usize,pub reserved_temp_bytes:u64,pub retained_reply_bytes:usize,pub retained_reply_cap:usize,pub closed:bool}
struct Record {snapshot:JobSnapshot,token:CancellationToken,page:Option<PageRequest>,response:Option<Response>,dirty:bool}
impl Record {fn changed(&mut self) {self.snapshot.revision=self.snapshot.revision.saturating_add(1);self.dirty=true;}}
struct Inner {state:SessionState,error:Option<Failure>,records:BTreeMap<String,Record>,queue:VecDeque<String>,closing:bool,next:u64}
struct PoolInner {sessions:BTreeMap<u64,Weak<Shared>>,handles:usize,next:u64,closed:bool,retained:usize}
struct PoolShared {inner:Mutex<PoolInner>,config:Config,#[cfg(test)]hook:Option<Arc<TestHook>>}
#[cfg(test)]type TestHook=dyn Fn(&str,&Progress)+Send+Sync+'static;
impl PoolShared {fn lock(&self)->MutexGuard<'_,PoolInner> {self.inner.lock().unwrap_or_else(|e|e.into_inner())}}
struct Shared {id:String,inner:Mutex<Inner>,changed:Condvar,pool:Arc<PoolShared>}
impl Shared {fn lock(&self)->MutexGuard<'_,Inner> {self.inner.lock().unwrap_or_else(|e|e.into_inner())}}
impl Drop for Shared {fn drop(&mut self) {
 let inner=self.inner.get_mut().unwrap_or_else(|e|e.into_inner());let bytes:usize=inner.records.values().map(|r|r.snapshot.result_bytes).sum();let mut pool=self.pool.lock();pool.retained=pool.retained.saturating_sub(bytes);pool.handles=pool.handles.saturating_sub(1);
}}
struct Permit {id:u64,pool:Arc<PoolShared>}
impl Drop for Permit {fn drop(&mut self) {self.pool.lock().sessions.remove(&self.id);}}
pub struct Pool {shared:Arc<PoolShared>}
impl Pool {
 pub fn new(config:Config)->ApiResult<Self> {
  if config.max_sessions==0||config.max_sessions>2||config.max_pending==0||config.max_pending>4||config.max_retained<=config.max_pending||config.max_retained>8||config.max_reply_bytes==0||config.max_reply_bytes>2*1024*1024 {return Err(api(ApiCode::InvalidInput,"Require 1..2 sessions, 1..4 pending, pending+1..8 retained jobs and 1..2 MiB reply cap"));}
  Ok(Self {shared:Arc::new(PoolShared {inner:Mutex::new(PoolInner {sessions:BTreeMap::new(),handles:0,next:1,closed:false,retained:0}),config,#[cfg(test)]hook:None})})
 }
 pub fn open(&self,request:OpenRequest)->ApiResult<Session> {self.open_with_token(request,CancellationToken::default())}
 pub fn open_with_token(&self,request:OpenRequest,token:CancellationToken)->ApiResult<Session> {
  if request.source.as_os_str().is_empty()||request.artifact.as_os_str().is_empty()||request.source.as_os_str().len()>16384||request.artifact.as_os_str().len()>16384||matches!(request.kind,DictionaryKind::Mdd)&&request.policy!=Policy::RawExact {return Err(api(ApiCode::InvalidInput,"Require bounded source/cache paths and raw_exact for MDD"));}
  let (number,shared)={let mut p=self.shared.lock();if p.closed {return Err(api(ApiCode::Closed,"Session pool closed"));}if p.sessions.len()>=self.shared.config.max_sessions||p.handles>=MAX_SESSION_HANDLES {return Err(api(ApiCode::ResourceLimit,"Live reader or retained session-handle reservations exhausted"));}
   let number=p.next;p.next=p.next.checked_add(1).ok_or_else(||api(ApiCode::Internal,"Session IDs exhausted"))?;let id=format!("session-{number:016x}");let job_id=format!("{id}-job-0000000000000001");let mut records=BTreeMap::new();records.insert(job_id.clone(),record(job_id,token,None));
   let s=Arc::new(Shared {id,inner:Mutex::new(Inner {state:SessionState::Opening,error:None,records,queue:VecDeque::new(),closing:false,next:2}),changed:Condvar::new(),pool:self.shared.clone()});p.handles+=1;p.sessions.insert(number,Arc::downgrade(&s));(number,s)};
  let permit=Permit {id:number,pool:self.shared.clone()};let actor=shared.clone();let worker=thread::Builder::new().name(shared.id.clone()).spawn(move|| {
   let outcome=catch_unwind(AssertUnwindSafe(||worker(&actor,request)));
   // worker/index/reader locals have all dropped before releasing admission.
   drop(permit);let fatal=match outcome {Ok(e)=>e,Err(_)=>Some(failure(ErrorCode::Internal,"panic","Session worker panicked; session closed"))};let mut inner=actor.lock();
   if let Some(e)=&fatal {for r in inner.records.values_mut() {if !r.snapshot.state.terminal() {r.snapshot.state=JobState::Failed;r.snapshot.error=Some(e.clone());r.page=None;r.changed();}}}
   inner.queue.clear();inner.state=if fatal.is_some()&&!inner.closing {SessionState::Failed}else{SessionState::Closed};inner.error=fatal;actor.changed.notify_all();
  }).map_err(|e|api(ApiCode::Internal,&e.to_string()))?;
  Ok(Session {shared,worker:Some(worker)})
 }
 pub fn admission(&self)->Admission {let p=self.shared.lock();Admission {live_sessions:p.sessions.len(),retained_session_handles:p.handles,reserved_memory_bytes:p.sessions.len()*MEMORY_RESERVATION,reserved_temp_bytes:p.sessions.len() as u64*TEMP_RESERVATION,retained_reply_bytes:p.retained,retained_reply_cap:RETAINED_BYTE_CAP,closed:p.closed}}
 pub fn shutdown(&self) {let sessions={let mut p=self.shared.lock();p.closed=true;p.sessions.values().filter_map(Weak::upgrade).collect::<Vec<_>>()};for s in sessions {request_close(&s);}}
 #[cfg(test)]fn with_hook(config:Config,hook:Arc<TestHook>)->Self {let mut pool=Self::new(config).unwrap();Arc::get_mut(&mut pool.shared).unwrap().hook=Some(hook);pool}
}
impl Drop for Pool {fn drop(&mut self) {self.shutdown();}}
pub struct Session {shared:Arc<Shared>,worker:Option<JoinHandle<()>>}
impl Session {
 pub fn id(&self)->&str {&self.shared.id}
 pub fn open_job_id(&self)->String {format!("{}-job-0000000000000001",self.id())}
 pub fn snapshot(&self)->SessionSnapshot {let i=self.shared.lock();SessionSnapshot {session_id:self.id().into(),state:i.state,retained_jobs:i.records.len(),queued_jobs:i.queue.len(),error:i.error.clone()}}
 pub fn job(&self,id:&str)->ApiResult<JobSnapshot> {self.shared.lock().records.get(id).map(|r|r.snapshot.clone()).ok_or_else(||api(ApiCode::NotFound,"Unknown session job"))}
 pub fn drain_events(&self)->Vec<JobSnapshot> {let mut i=self.shared.lock();let mut events=Vec::new();for r in i.records.values_mut() {if r.dirty {events.push(r.snapshot.clone());r.dirty=false;}}events}
 pub fn submit_page(&self,request:PageRequest)->ApiResult<String> {self.submit_page_with_token(request,CancellationToken::default())}
 pub fn submit_page_with_token(&self,request:PageRequest,token:CancellationToken)->ApiResult<String> {
  request.validate()?;let mut i=self.shared.lock();if i.closing||i.state.terminal() {return Err(api(ApiCode::Closed,"Session closed or closing"));}if i.state!=SessionState::Ready {return Err(api(ApiCode::NotReady,"Wait for indexed session to become ready"));}
  let c=self.shared.pool.config;if i.queue.len()>=c.max_pending {return Err(api(ApiCode::QueueFull,"Session page queue full"));}if i.records.len()>=c.max_retained {return Err(api(ApiCode::RetentionFull,"Take results and forget terminal jobs"));}
  let next=i.next.checked_add(1).ok_or_else(||api(ApiCode::Internal,"Job IDs exhausted"))?;let id=format!("{}-job-{:016x}",self.id(),i.next);i.next=next;let cancelled=token.is_cancelled();let mut r=record(id.clone(),token,Some(request));
  if cancelled {cancel_queued(&mut r);}else{i.queue.push_back(id.clone());}i.records.insert(id.clone(),r);self.shared.changed.notify_all();Ok(id)
 }
 pub fn cancel(&self,id:&str)->ApiResult<CancelOutcome> {
  let mut i=self.shared.lock();let r=i.records.get_mut(id).ok_or_else(||api(ApiCode::NotFound,"Unknown session job"))?;
  if r.snapshot.state.terminal() {return Ok(CancelOutcome::AlreadyFinished);}if r.snapshot.cancel_requested {return Ok(CancelOutcome::AlreadyRequested);}
  r.token.cancel();r.snapshot.cancel_requested=true;let queued=r.snapshot.state==JobState::Queued;
  // Opening is executed directly, so its queued record must remain until the
  // actor observes its token. Page requests can be cancelled before dispatch.
  if queued&&r.page.is_some() {cancel_queued(r);i.queue.retain(|v|v!=id);}else{r.changed();}self.shared.changed.notify_all();Ok(CancelOutcome::Requested)
 }
 pub fn take_result(&self,id:&str)->ApiResult<Option<Response>> {
  let mut i=self.shared.lock();let r=i.records.get_mut(id).ok_or_else(||api(ApiCode::NotFound,"Unknown session job"))?;if !r.snapshot.state.terminal() {return Err(api(ApiCode::StillRunning,"Session job unfinished"));}
  let value=r.response.take();if value.is_some() {release_reply(&self.shared,r);r.changed();self.shared.changed.notify_all();}Ok(value)
 }
 pub fn forget(&self,id:&str)->ApiResult<()> {
  let mut i=self.shared.lock();let r=i.records.get(id).ok_or_else(||api(ApiCode::NotFound,"Unknown session job"))?;if !r.snapshot.state.terminal() {return Err(api(ApiCode::StillRunning,"Session job unfinished"));}
  let mut r=i.records.remove(id).unwrap();release_reply(&self.shared,&mut r);Ok(())
 }
 pub fn close(&self) {request_close(&self.shared);}
 /// Blocking helpers belong on tests/CLI/background controllers, never UI handlers.
 pub fn wait_job(&self,id:&str,timeout:Duration)->ApiResult<Option<JobSnapshot>> {
  let deadline=Instant::now().checked_add(timeout).ok_or_else(||api(ApiCode::InvalidInput,"Timeout overflow"))?;let mut i=self.shared.lock();loop {
   let r=i.records.get(id).ok_or_else(||api(ApiCode::NotFound,"Unknown session job"))?;if r.snapshot.state.terminal() {return Ok(Some(r.snapshot.clone()));}let remaining=deadline.saturating_duration_since(Instant::now());if remaining.is_zero() {return Ok(None);}i=self.shared.changed.wait_timeout(i,remaining).unwrap_or_else(|e|e.into_inner()).0;
  }
 }
 pub fn wait_closed(&self,timeout:Duration)->bool {let Some(deadline)=Instant::now().checked_add(timeout) else{return false;};let mut i=self.shared.lock();loop {if i.state.terminal() {return true;}let remaining=deadline.saturating_duration_since(Instant::now());if remaining.is_zero() {return false;}i=self.shared.changed.wait_timeout(i,remaining).unwrap_or_else(|e|e.into_inner()).0;}}
 pub fn join(mut self)->ApiResult<()> {self.close();if let Some(worker)=self.worker.take() {worker.join().map_err(|_|api(ApiCode::Internal,"Worker panicked during cleanup"))?;}Ok(())}
}
impl Drop for Session {fn drop(&mut self) {self.close();drop(self.worker.take());}}
fn record(id:String,token:CancellationToken,page:Option<PageRequest>)->Record {Record {snapshot:JobSnapshot {job_id:id,state:JobState::Queued,revision:1,cancel_requested:false,latest_progress:None,error:None,result_available:false,result_bytes:0},token,page,response:None,dirty:true}}
fn cancel_queued(r:&mut Record) {r.token.cancel();r.page=None;r.snapshot.cancel_requested=true;r.snapshot.state=JobState::Cancelled;r.snapshot.error=Some(failure(ErrorCode::Cancelled,"cancelled","Cancelled before page dispatch"));r.changed();}
fn request_close(shared:&Shared) {
 let mut i=shared.lock();if i.state.terminal()||i.closing {return;}i.closing=true;i.state=SessionState::Closing;i.queue.clear();
 for r in i.records.values_mut() {if !r.snapshot.state.terminal() {r.token.cancel();r.snapshot.cancel_requested=true;if r.snapshot.state==JobState::Queued&&r.page.is_some() {cancel_queued(r);}else{r.changed();}}}shared.changed.notify_all();
}
fn release_reply(shared:&Shared,r:&mut Record) {let mut p=shared.pool.lock();p.retained=p.retained.saturating_sub(r.snapshot.result_bytes);r.snapshot.result_bytes=0;r.snapshot.result_available=false;}
struct Counter {bytes:usize,cap:usize}
impl Write for Counter {fn write(&mut self,b:&[u8])->std::io::Result<usize> {self.bytes=self.bytes.checked_add(b.len()).ok_or_else(||std::io::Error::other("Reply overflow"))?;if self.bytes>self.cap {return Err(std::io::Error::other("Reply cap"));}Ok(b.len())}fn flush(&mut self)->std::io::Result<()> {Ok(())}}
fn complete(shared:&Shared,id:&str,result:std::result::Result<Response,Failure>)->Option<Failure> {
 let mut i=shared.lock();let closing=i.closing;let r=i.records.get_mut(id).expect("Active job cannot be forgotten");r.snapshot.cancel_requested|=r.token.is_cancelled();
 let result=if closing||r.token.is_cancelled() {Err(failure(ErrorCode::Cancelled,"cancelled","Session job cancelled before result commit"))}else{result};
 let result=result.and_then(|response| {let mut counter=Counter {bytes:0,cap:shared.pool.config.max_reply_bytes};serde_json::to_writer(&mut counter,&response).map_err(|_|failure(ErrorCode::LimitExceeded,"reply_limit","Serialized session response exceeds cap"))?;
  if r.token.is_cancelled() {return Err(failure(ErrorCode::Cancelled,"cancelled","Session job cancelled before result commit"));}
  let mut p=shared.pool.lock();if counter.bytes>RETAINED_BYTE_CAP.saturating_sub(p.retained) {return Err(failure(ErrorCode::LimitExceeded,"retained_reply_limit","Pool retained reply byte cap reached"));}p.retained+=counter.bytes;Ok((response,counter.bytes))});
 match result {Ok((response,bytes))=>{r.snapshot.state=JobState::Succeeded;r.snapshot.result_bytes=bytes;r.snapshot.result_available=true;r.response=Some(response);},Err(e)=>{r.snapshot.state=if e.code==ErrorCode::Cancelled {JobState::Cancelled}else{JobState::Failed};r.snapshot.error=Some(e);}}r.changed();let error=r.snapshot.error.clone();
 if id.ends_with("-job-0000000000000001")&&error.is_none() {i.state=SessionState::Ready;}shared.changed.notify_all();error
}
fn progress(shared:&Shared,id:&str,p:Progress) {
 {let mut i=shared.lock();if let Some(r)=i.records.get_mut(id) {r.snapshot.latest_progress=Some(p.clone());r.changed();}shared.changed.notify_all();}
 #[cfg(test)]if let Some(hook)=&shared.pool.hook {hook(id,&p);}
}
fn worker(shared:&Shared,request:OpenRequest)->Option<Failure> {
 let open_id=format!("{}-job-0000000000000001",shared.id);let token={let mut i=shared.lock();let r=i.records.get_mut(&open_id).unwrap();r.snapshot.state=JobState::Running;r.changed();r.token.clone()};shared.changed.notify_all();
 let mut callback=|p|progress(shared,&open_id,p);let mut job=ImportJob::new(&open_id,&token,&mut callback);
 let dictionary=match Dictionary::open_v2(&request.source,match request.kind {DictionaryKind::Mdx=>Kind::Mdx,DictionaryKind::Mdd=>Kind::Mdd},&Limits::default(),&mut job) {Ok(d)=>d,Err(e)=>{let e=Failure::from(e);complete(shared,&open_id,Err(e.clone()));return Some(e);}};
 let mut index=match Index::open(&dictionary,&request.artifact,request.policy,&mut job) {Ok(d)=>d,Err(e)=>{let e=Failure::from(e);complete(shared,&open_id,Err(e.clone()));return Some(e);}};drop(job);drop(callback);
 if let Some(e)=complete(shared,&open_id,Ok(Response::Opened(index.manifest().clone()))) {return Some(e);}
 loop {
  let (id,page,token)={let mut i=shared.lock();while i.queue.is_empty()&&!i.closing {i=shared.changed.wait(i).unwrap_or_else(|e|e.into_inner());}if i.closing {return None;}let id=i.queue.pop_front().unwrap();let r=i.records.get_mut(&id).unwrap();r.snapshot.state=JobState::Running;r.changed();let page=r.page.take().unwrap();let token=r.token.clone();shared.changed.notify_all();(id,page,token)};
  let mut callback=|p|progress(shared,&id,p);let mut job=ImportJob::new(&id,&token,&mut callback);let result=index.page(&page.query,page.offset,page.limit,&mut job).map(Response::Page).map_err(Failure::from);drop(job);drop(callback);
  #[cfg(test)]if let Some(hook)=&shared.pool.hook {hook(&id,&Progress {job_id:id.clone(),stage:studio_indexed_engine::Stage::Converting,phase:"session_result_commit".into(),completed:1,total:1});}
  let _=complete(shared,&id,result);
 }
}
#[cfg(test)]mod tests;
