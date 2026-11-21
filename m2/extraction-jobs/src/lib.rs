//! Shared logical admission for persistent readers and background extraction.
pub mod runner;
pub use studio_sessions::{ApiError,ApiCode,ApiResult,OpenRequest,PageRequest};
pub use studio_stream_extract::{CancellationToken,Progress,ErrorCode,ExtractionReceipt};
use serde::{Serialize,Deserialize};
use std::{collections::BTreeMap,path::PathBuf,sync::{Arc,Mutex,MutexGuard,Condvar},thread::{self,JoinHandle},time::{Duration,Instant}};
#[derive(Debug,Deserialize)]#[serde(deny_unknown_fields)]pub struct Request {pub source:PathBuf,pub destination:PathBuf}
impl Request {fn validate(&self)->ApiResult<()> {if self.source.as_os_str().is_empty()||self.destination.as_os_str().is_empty()||self.source.as_os_str().len()>16384||self.destination.as_os_str().len()>16384 {return Err(error(ApiCode::InvalidInput,"Require nonempty source/destination paths <=16 KiB"));}Ok(())}}
fn execute(request:&Request,job:&mut studio_stream_extract::ImportJob<'_>)->studio_stream_extract::Result<ExtractionReceipt> {studio_stream_extract::extract_mdd(&request.source,&request.destination,&studio_stream_extract::ExtractLimits::default(),job)}
fn error(code:ApiCode,message:&str)->ApiError {ApiError {code,message:message.into()}}
#[derive(Clone,Copy,Debug)]pub struct AdmissionLimits {pub operations:usize,pub memory_bytes:u64,pub temporary_bytes:u64}
impl Default for AdmissionLimits {fn default()->Self {Self {operations:2,memory_bytes:192*1024*1024,temporary_bytes:4*1024*1024*1024}}}
#[derive(Clone,Copy,Debug,Serialize)]#[serde(rename_all="snake_case")]enum Operation {Reader,Extraction}
impl Operation {fn memory(self)->u64 {96*1024*1024}fn temporary(self)->u64 {match self {Self::Reader=>768*1024*1024,Self::Extraction=>3*1024*1024*1024}}}
struct Ledger {next:u64,active:BTreeMap<u64,Operation>,closed:bool}
struct BudgetShared {ledger:Mutex<Ledger>,limits:AdmissionLimits}
#[derive(Clone)]struct Budget(Arc<BudgetShared>);
impl Budget {
 fn new(limits:AdmissionLimits)->ApiResult<Self> {let cap=AdmissionLimits::default();if limits.operations==0||limits.operations>cap.operations||limits.memory_bytes>cap.memory_bytes||limits.temporary_bytes>cap.temporary_bytes {return Err(error(ApiCode::InvalidInput,"Admission may only lower the fixed two-operation profile"));}Ok(Self(Arc::new(BudgetShared {ledger:Mutex::new(Ledger {next:1,active:BTreeMap::new(),closed:false}),limits})))}
 fn lock(&self)->MutexGuard<'_,Ledger> {self.0.ledger.lock().unwrap_or_else(|e|e.into_inner())}
 fn reserve(&self,kind:Operation)->ApiResult<Lease> {
  let mut ledger=self.lock();if ledger.closed {return Err(error(ApiCode::Closed,"Shared admission closed"));}let memory:u64=ledger.active.values().map(|k|k.memory()).sum();let temporary:u64=ledger.active.values().map(|k|k.temporary()).sum();let c=self.0.limits;
  if ledger.active.len()>=c.operations||kind.memory()>c.memory_bytes.saturating_sub(memory)||kind.temporary()>c.temporary_bytes.saturating_sub(temporary) {return Err(error(ApiCode::ResourceLimit,"Shared reader/extraction reservations exhausted"));}
  let id=ledger.next;ledger.next=ledger.next.checked_add(1).ok_or_else(||error(ApiCode::Internal,"Reservation IDs exhausted"))?;ledger.active.insert(id,kind);Ok(Lease {id,budget:self.clone()})
 }
 fn snapshot(&self)->BudgetSnapshot {let l=self.lock();BudgetSnapshot {active_operations:l.active.len(),readers:l.active.values().filter(|v|matches!(v,Operation::Reader)).count(),extractions:l.active.values().filter(|v|matches!(v,Operation::Extraction)).count(),reserved_memory_bytes:l.active.values().map(|k|k.memory()).sum(),reserved_temporary_bytes:l.active.values().map(|k|k.temporary()).sum(),max_operations:self.0.limits.operations,memory_cap:self.0.limits.memory_bytes,temporary_cap:self.0.limits.temporary_bytes,closed:l.closed}}
 fn close(&self) {self.lock().closed=true;}
}
struct Lease {id:u64,budget:Budget}
impl Drop for Lease {fn drop(&mut self) {self.budget.lock().active.remove(&self.id);}}
#[derive(Debug,Serialize)]pub struct BudgetSnapshot {pub active_operations:usize,pub readers:usize,pub extractions:usize,pub reserved_memory_bytes:u64,pub reserved_temporary_bytes:u64,pub max_operations:usize,pub memory_cap:u64,pub temporary_cap:u64,pub closed:bool}
struct Tracked {session:Arc<studio_sessions::Session>,_lease:Lease}
struct ReaderInner {records:BTreeMap<String,Tracked>,closed:bool}
struct ReaderShared {inner:Mutex<ReaderInner>,changed:Condvar}
impl ReaderShared {fn lock(&self)->MutexGuard<'_,ReaderInner> {self.inner.lock().unwrap_or_else(|e|e.into_inner())}}
struct Readers {pool:studio_sessions::Pool,shared:Arc<ReaderShared>,worker:Option<JoinHandle<()>>,budget:Budget}
impl Readers {
 fn new(budget:Budget)->ApiResult<Self> {
  let pool=studio_sessions::Pool::new(studio_sessions::Config::default())?;let shared=Arc::new(ReaderShared {inner:Mutex::new(ReaderInner {records:BTreeMap::new(),closed:false}),changed:Condvar::new()});let reap=shared.clone();
  // The one cleanup monitor is started before any reader can be admitted.
  let worker=thread::Builder::new().name("studio-reader-admission".into()).spawn(move|| {
   let mut inner=reap.lock();loop {
    let done=inner.records.iter().filter(|(_,r)|r.session.wait_closed(Duration::ZERO)).map(|(id,_)|id.clone()).collect::<Vec<_>>();
    for id in done {inner.records.remove(&id);}reap.changed.notify_all();
    if inner.closed&&inner.records.is_empty() {return;}
    if inner.records.is_empty() {inner=reap.changed.wait(inner).unwrap_or_else(|e|e.into_inner());}else{inner=reap.changed.wait_timeout(inner,Duration::from_millis(20)).unwrap_or_else(|e|e.into_inner()).0;}
   }
  }).map_err(|e|error(ApiCode::Internal,&e.to_string()))?;Ok(Self {pool,shared,worker:Some(worker),budget})
 }
 fn open(&self,request:OpenRequest)->ApiResult<Reader> {
  let mut inner=self.shared.lock();if inner.closed {return Err(error(ApiCode::Closed,"Managed reader pool closed"));}let lease=self.budget.reserve(Operation::Reader)?;let session=Arc::new(self.pool.open(request)?);let id=session.id().to_string();inner.records.insert(id,Tracked {session:session.clone(),_lease:lease});self.shared.changed.notify_all();Ok(Reader {session:Some(session),shared:self.shared.clone()})
 }
 fn shutdown(&self) {let mut i=self.shared.lock();i.closed=true;self.pool.shutdown();self.shared.changed.notify_all();}
 fn join(&mut self)->ApiResult<()> {self.shutdown();if let Some(worker)=self.worker.take() {worker.join().map_err(|_|error(ApiCode::Internal,"Reader admission monitor panicked"))?;}Ok(())}
}
impl Drop for Readers {fn drop(&mut self) {self.shutdown();drop(self.worker.take());}}
pub struct Reader {session:Option<Arc<studio_sessions::Session>>,shared:Arc<ReaderShared>}
impl Reader {
 pub fn session(&self)->&studio_sessions::Session {self.session.as_ref().expect("Reader already consumed")}
 pub fn close(&self) {if let Some(session)=&self.session {session.close();self.shared.changed.notify_all();}}
 /// Returns only after both the accepted reader cleanup and shared lease release.
 pub fn wait_closed(&self,timeout:Duration)->bool {
  let Some(deadline)=Instant::now().checked_add(timeout) else {return false;};if !self.session().wait_closed(timeout) {return false;}self.shared.changed.notify_all();let mut inner=self.shared.lock();
  while inner.records.contains_key(self.session().id()) {let left=deadline.saturating_duration_since(Instant::now());if left.is_zero() {return false;}inner=self.shared.changed.wait_timeout(inner,left).unwrap_or_else(|e|e.into_inner()).0;}true
 }
 /// Blocking disposal also joins the underlying actor and releases its metadata.
 pub fn join(mut self)->ApiResult<()> {self.close();if !self.wait_closed(Duration::from_secs(30)) {return Err(error(ApiCode::StillRunning,"Reader cleanup unfinished"));}let session=Arc::try_unwrap(self.session.take().unwrap()).map_err(|_|error(ApiCode::StillRunning,"Reader still referenced during disposal"))?;session.join()}
}
impl Drop for Reader {fn drop(&mut self) {self.close();}}
pub struct Runtime {budget:Budget,readers:Readers,extractor:runner::Runner}
impl Runtime {
 pub fn new(limits:AdmissionLimits,runner:runner::Config)->ApiResult<Self> {let budget=Budget::new(limits)?;let readers=Readers::new(budget.clone())?;let extractor=runner::Runner::new(runner,budget.clone())?;Ok(Self {budget,readers,extractor})}
 pub fn open_reader(&self,request:OpenRequest)->ApiResult<Reader> {self.readers.open(request)}
 pub fn extraction(&self)->&runner::Runner {&self.extractor}
 pub fn admission(&self)->BudgetSnapshot {self.budget.snapshot()}
 pub fn reader_admission(&self)->studio_sessions::Admission {self.readers.pool.admission()}
 pub fn shutdown(&self) {self.budget.close();self.readers.shutdown();self.extractor.shutdown();}
 /// Blocking cleanup helper; use off the UI thread.
 pub fn join(mut self)->ApiResult<()> {self.shutdown();self.extractor.join_worker()?;self.readers.join()}
}
impl Drop for Runtime {fn drop(&mut self) {self.shutdown();}}
#[cfg(test)]mod tests;
