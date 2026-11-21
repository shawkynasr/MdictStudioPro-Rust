//! One persistent SQLite actor, charged to shared admission for its entire life.
use crate::{ApiCode,ApiResult,Budget,Lease,Operation,CancellationToken,error};
use serde::{Deserialize,Serialize};
use std::{path::PathBuf,sync::{Arc,Mutex,Condvar},thread::{self,JoinHandle}};
use studio_database::{Reader,ReaderInfo,ReaderQuery,Page,Progress,Job};

#[derive(Clone,Copy,Debug,Default,Deserialize)]#[serde(rename_all="snake_case")]
pub enum Matching {#[default]Literal,Unicode16Lower}
#[derive(Debug,Deserialize)]#[serde(deny_unknown_fields)]
pub struct Query {pub query:Option<String>,#[serde(default)]pub prefix:bool,#[serde(default)]pub wildcard:bool,#[serde(default)]pub definition:bool,#[serde(default)]pub matching:Matching,pub offset:u64,pub limit:usize}
impl Query {
 fn validate(&self)->ApiResult<()> {
  if ((self.prefix||self.wildcard||self.definition)&&self.query.is_none())||([self.prefix,self.wildcard,self.definition].iter().filter(|&&v|v).count()>1)||self.limit==0||self.limit>128||self.offset>100000||self.query.as_ref().is_some_and(|q|q.is_empty()||q.len()>4096||q.contains('\0')) {
   return Err(error(ApiCode::InvalidInput,"Require literal key <=4 KiB, page 1..128 and offset <=100,000"));
  }Ok(())
 }
}
#[derive(Debug,Serialize)]#[serde(tag="operation",content="value",rename_all="snake_case")]
pub enum Reply {Opened(ReaderInfo),Page(Page)}
#[derive(Clone,Debug,Serialize)]
pub struct Failure {pub code:String,pub message:String}
#[derive(Clone,Debug,Serialize)]
pub struct Snapshot {pub reader_id:Option<String>,pub state:&'static str,pub job_id:Option<String>,pub job_state:&'static str,pub result_available:bool,pub cancel_requested:bool,pub error:Option<Failure>,pub latest_progress:Option<Progress>}
enum Work {Open(PathBuf,Lease),Page(Query)}
struct Inner {snapshot:Snapshot,next:u64,pending:Option<Work>,result:Option<Reply>,token:CancellationToken,closing:bool,shutdown:bool}
struct Shared {inner:Mutex<Inner>,changed:Condvar,#[cfg(test)]cancel_phase:Mutex<Option<&'static str>>}
impl Shared {fn lock(&self)->std::sync::MutexGuard<'_,Inner>{self.inner.lock().unwrap_or_else(|e|e.into_inner())}}
pub struct Manager {shared:Arc<Shared>,worker:Option<JoinHandle<()>>,budget:Budget}
fn mapped(e:studio_database::Error)->crate::ApiError {
 error(match e.code {"cancelled"=>ApiCode::NotReady,"limit_exceeded"=>ApiCode::ResourceLimit,"closed"=>ApiCode::Closed,_=>ApiCode::InvalidInput},&format!("{}: {}",e.code,e.message))
}
impl Manager {
 pub(crate) fn new(budget:Budget)->ApiResult<Self> {
  let shared=Arc::new(Shared {inner:Mutex::new(Inner {snapshot:Snapshot {reader_id:None,state:"closed",job_id:None,job_state:"idle",result_available:false,cancel_requested:false,error:None,latest_progress:None},next:1,pending:None,result:None,token:CancellationToken::default(),closing:false,shutdown:false}),changed:Condvar::new(),#[cfg(test)]cancel_phase:Mutex::new(None)});
  let actor=shared.clone();let worker=thread::Builder::new().name("studio-database-reader".into()).spawn(move||worker(actor)).map_err(|_|error(ApiCode::Internal,"Cannot start database reader worker"))?;
  Ok(Self {shared,worker:Some(worker),budget})
 }
 fn idle(i:&Inner)->ApiResult<()> {
  if i.shutdown||i.closing {return Err(error(ApiCode::Closed,"Database reader is closing"));}
  if i.snapshot.job_id.is_some(){return Err(error(ApiCode::StillRunning,"Collect and forget the previous database reader job"));}Ok(())
 }
 fn enqueue(i:&mut Inner,work:Work)->ApiResult<String> {
  let n=i.next;i.next=n.checked_add(1).ok_or_else(||error(ApiCode::Internal,"Database job IDs exhausted"))?;
  let id=format!("database-job-{n}");i.token=CancellationToken::default();i.result=None;i.pending=Some(work);
  i.snapshot.job_id=Some(id.clone());i.snapshot.job_state="queued";i.snapshot.result_available=false;i.snapshot.cancel_requested=false;i.snapshot.error=None;i.snapshot.latest_progress=None;Ok(id)
 }
 pub fn open(&self,source:PathBuf)->ApiResult<(String,String)> {
  if source.as_os_str().is_empty()||source.as_os_str().len()>16384{return Err(error(ApiCode::InvalidInput,"Require source path 1..16384 bytes"));}
  let mut i=self.shared.lock();Self::idle(&i)?;if i.snapshot.reader_id.is_some(){return Err(error(ApiCode::ResourceLimit,"Close the open database snapshot first"));}
  // Keep the conservative, exclusive database charge through all idle/page time.
  let lease=self.budget.reserve(Operation::CcPacking)?;
  let reader_id=format!("database-reader-{}",i.next);let job_id=Self::enqueue(&mut i,Work::Open(source,lease))?;
  i.snapshot.reader_id=Some(reader_id.clone());i.snapshot.state="opening";self.shared.changed.notify_all();Ok((reader_id,job_id))
 }
 fn matches(i:&Inner,id:&str)->ApiResult<()> {if i.snapshot.reader_id.as_deref()!=Some(id){return Err(error(ApiCode::NotFound,"Unknown database reader"));}Ok(())}
 pub fn page(&self,id:&str,query:Query)->ApiResult<String> {
  query.validate()?;let mut i=self.shared.lock();Self::matches(&i,id)?;Self::idle(&i)?;
  if i.snapshot.state!="ready"{return Err(error(ApiCode::NotReady,"Database reader is not ready"));}
  let job=Self::enqueue(&mut i,Work::Page(query))?;i.snapshot.state="busy";self.shared.changed.notify_all();Ok(job)
 }
 pub fn snapshot(&self)->Snapshot {self.shared.lock().snapshot.clone()}
 pub fn cancel(&self,job:&str)->ApiResult<()> {
  let mut i=self.shared.lock();if i.snapshot.job_id.as_deref()!=Some(job){return Err(error(ApiCode::NotFound,"Unknown database reader job"));}
  if matches!(i.snapshot.job_state,"queued"|"running"){i.token.cancel();i.snapshot.cancel_requested=true;}Ok(())
 }
 pub fn take(&self,job:&str)->ApiResult<Option<Reply>> {
  let mut i=self.shared.lock();if i.snapshot.job_id.as_deref()!=Some(job){return Err(error(ApiCode::NotFound,"Unknown database reader job"));}
  if matches!(i.snapshot.job_state,"queued"|"running"){return Err(error(ApiCode::StillRunning,"Database job is running"));}
  let reply=i.result.take();i.snapshot.result_available=false;Ok(reply)
 }
 pub fn forget(&self,job:&str)->ApiResult<()> {
  let mut i=self.shared.lock();if i.snapshot.job_id.as_deref()!=Some(job){return Err(error(ApiCode::NotFound,"Unknown database reader job"));}
  if matches!(i.snapshot.job_state,"queued"|"running"){return Err(error(ApiCode::StillRunning,"Database job is running"));}
  i.result=None;i.snapshot.job_id=None;i.snapshot.job_state="idle";i.snapshot.result_available=false;i.snapshot.error=None;Ok(())
 }
 pub fn close(&self,id:&str)->ApiResult<()> {
  let mut i=self.shared.lock();Self::matches(&i,id)?;i.closing=true;i.token.cancel();i.snapshot.cancel_requested=true;i.snapshot.state="closing";self.shared.changed.notify_all();Ok(())
 }
 pub(crate) fn shutdown(&self) {let mut i=self.shared.lock();i.shutdown=true;i.closing=true;i.token.cancel();i.snapshot.state="closing";self.shared.changed.notify_all();}
 pub(crate) fn join(&mut self)->ApiResult<()> {self.shutdown();if let Some(w)=self.worker.take(){w.join().map_err(|_|error(ApiCode::Internal,"Database reader worker panicked"))?;}Ok(())}
}
impl Drop for Manager {fn drop(&mut self){self.shutdown();}}

fn worker(shared:Arc<Shared>) {
 let mut retained:Option<(Reader,Lease)>=None;
 loop {
  let (work,token)={
   let mut i=shared.lock();
   loop {
    if i.closing {
     // Close the connection, unlink the snapshot, and release admission before
     // making the closed state observable. Pending opens own a lease too.
     i.pending=None;retained=None;i.result=None;i.snapshot.reader_id=None;i.snapshot.state="closed";i.snapshot.job_id=None;i.snapshot.job_state="idle";i.snapshot.result_available=false;i.snapshot.error=None;i.closing=false;shared.changed.notify_all();
     if i.shutdown{return;}
    }
    if let Some(work)=i.pending.take(){i.snapshot.job_state="running";break(work,i.token.clone());}
    i=shared.changed.wait(i).unwrap_or_else(|e|e.into_inner());
   }
  };
  let mut progress=|p:Progress|{
   #[cfg(test)]if *shared.cancel_phase.lock().unwrap()==Some(p.phase){token.cancel();}
   shared.lock().snapshot.latest_progress=Some(p);
  };
  let result=std::panic::catch_unwind(std::panic::AssertUnwindSafe(||->ApiResult<Reply>{
   let mut job=Job::new(&token,&mut progress);
   match work {
    Work::Open(source,lease)=>{let reader=Reader::open(&source,&mut job).map_err(mapped)?;let info=reader.info().map_err(mapped)?;retained=Some((reader,lease));Ok(Reply::Opened(info))},
    Work::Page(query)=>{let r=&mut retained.as_mut().ok_or_else(||error(ApiCode::Closed,"Database reader is closed"))?.0;let q=match (query.query.as_deref(),query.prefix,query.matching){(Some(q),_,Matching::Unicode16Lower) if query.definition=>ReaderQuery::LowerDefinition(q),(Some(q),_,_) if query.definition=>ReaderQuery::Definition(q),(Some(q),_,Matching::Unicode16Lower) if query.wildcard=>ReaderQuery::LowerPattern(q),(Some(q),_,_) if query.wildcard=>ReaderQuery::Pattern(q),(Some(q),true,Matching::Unicode16Lower)=>ReaderQuery::LowerPrefix(q),(Some(q),false,Matching::Unicode16Lower)=>ReaderQuery::LowerExact(q),(Some(q),true,_)=>ReaderQuery::Prefix(q),(Some(q),false,_)=>ReaderQuery::Exact(q),(None,_,_)=>ReaderQuery::All};r.page(q,query.offset,query.limit,&mut job).map(Reply::Page).map_err(mapped)},
   }
  }));
  let mut i=shared.lock();
  if i.closing{continue;}
  let result=match result {Ok(r)=>r,Err(_)=>{retained=None;Err(error(ApiCode::Internal,"Database reader worker operation panicked"))}};
  // A late cancellation also discards an open result and its retained lease.
  let result=if token.is_cancelled(){if matches!(&result,Ok(Reply::Opened(_))){retained=None;}Err(error(ApiCode::NotReady,"Database reader operation cancelled"))}else{result};
  match result {
   Ok(reply)=>{i.result=Some(reply);i.snapshot.job_state="succeeded";i.snapshot.result_available=true;},
   Err(e)=>{i.snapshot.job_state=if token.is_cancelled(){"cancelled"}else{"failed"};i.snapshot.error=Some(Failure {code:if token.is_cancelled(){"cancelled".into()}else{serde_json::to_value(e.code).ok().and_then(|v|v.as_str().map(str::to_owned)).unwrap_or_else(||"internal".into())},message:e.message});i.snapshot.result_available=false;},
  }
  if retained.is_some(){i.snapshot.state="ready";}else{i.snapshot.reader_id=None;i.snapshot.state="closed";}
  shared.changed.notify_all();
 }
}

#[cfg(test)]mod tests {
 use super::*;
 use crate::AdmissionLimits;
 use std::time::{Duration,Instant};
 fn seed(path:&std::path::Path){std::fs::write(path,include_bytes!("../../fixtures/database-prefix.txt")).unwrap();}
 fn database(dir:&std::path::Path)->PathBuf {
  let txt=dir.join("input.txt");seed(&txt);let db=dir.join("dict.db");
  studio_database::execute(&studio_database::Request::TxtToDb {source:txt,destination:db.clone(),profile:studio_core::TxtProfile::CanonicalV1},&mut Job::new(&CancellationToken::default(),&mut |_|{})).unwrap();db
 }
 fn wait(m:&Manager)->Snapshot {let end=Instant::now()+Duration::from_secs(10);loop{let s=m.snapshot();if !matches!(s.job_state,"queued"|"running"){return s;}assert!(Instant::now()<end,"{s:?}");thread::sleep(Duration::from_millis(1));}}
 fn closed(m:&Manager){let end=Instant::now()+Duration::from_secs(10);while m.snapshot().state!="closed"{assert!(Instant::now()<end);thread::sleep(Duration::from_millis(1));}}
 fn query()->Query{Query {query:Some("app".into()),prefix:true,wildcard:false,definition:false,matching:Matching::Literal,offset:0,limit:2}}
 fn ready(m:&Manager,db:PathBuf)->String {let (id,job)=m.open(db).unwrap();assert_eq!(wait(m).job_state,"succeeded");assert!(matches!(m.take(&job).unwrap(),Some(Reply::Opened(_))));m.forget(&job).unwrap();id}
 #[test]fn definition_requests_validate_cancel_and_retry_with_matching_policy() {
  let dir=tempfile::tempdir().unwrap();let db=database(dir.path());let mut m=Manager::new(Budget::new(AdmissionLimits::default()).unwrap()).unwrap();let id=ready(&m,db);
  let mut q=query();q.definition=true;assert_eq!(m.page(&id,q).unwrap_err().code,ApiCode::InvalidInput);
  let mut q=query();q.definition=true;q.prefix=false;q.wildcard=true;assert_eq!(m.page(&id,q).unwrap_err().code,ApiCode::InvalidInput);
  let mut q=query();q.definition=true;q.prefix=false;q.query=None;assert_eq!(m.page(&id,q).unwrap_err().code,ApiCode::InvalidInput);
  for (matching,total) in [(Matching::Literal,0),(Matching::Unicode16Lower,3)] {
   let mut q=query();q.prefix=false;q.definition=true;q.query=Some("APPLE".into());q.matching=matching;let job=m.page(&id,q).unwrap();assert_eq!(wait(&m).job_state,"succeeded");let Some(Reply::Page(p))=m.take(&job).unwrap()else{panic!()};assert_eq!(p.total,total);m.forget(&job).unwrap();
  }
  *m.shared.cancel_phase.lock().unwrap()=Some("database_definition_scan");let mut q=query();q.prefix=false;q.definition=true;q.query=Some("definition".into());let job=m.page(&id,q).unwrap();assert_eq!(wait(&m).job_state,"cancelled");m.forget(&job).unwrap();
  *m.shared.cancel_phase.lock().unwrap()=None;let job=m.page(&id,query()).unwrap();assert_eq!(wait(&m).job_state,"succeeded");m.forget(&job).unwrap();assert_eq!(m.snapshot().reader_id.as_deref(),Some(id.as_str()));m.join().unwrap();
 }
 #[test]fn wildcard_requests_validate_page_cancel_and_retry_on_same_snapshot() {
  let dir=tempfile::tempdir().unwrap();let db=database(dir.path());let mut m=Manager::new(Budget::new(AdmissionLimits::default()).unwrap()).unwrap();let id=ready(&m,db);
  let mut q=query();q.wildcard=true;assert_eq!(m.page(&id,q).unwrap_err().code,ApiCode::InvalidInput);
  let mut q=query();q.prefix=false;q.wildcard=true;q.query=None;assert_eq!(m.page(&id,q).unwrap_err().code,ApiCode::InvalidInput);
  let mut q=query();q.prefix=false;q.wildcard=true;q.query=Some("aPp*".into());q.matching=Matching::Unicode16Lower;q.offset=2;
  let job=m.page(&id,q).unwrap();assert_eq!(wait(&m).job_state,"succeeded");let Some(Reply::Page(p))=m.take(&job).unwrap()else{panic!()};assert_eq!(p.total,4);assert_eq!(p.rows.iter().map(|r|r.rowid.as_str()).collect::<Vec<_>>(),["3","4"]);m.forget(&job).unwrap();
  *m.shared.cancel_phase.lock().unwrap()=Some("database_pattern_scan");let mut q=query();q.prefix=false;q.wildcard=true;q.query=Some("*".into());let job=m.page(&id,q).unwrap();assert_eq!(wait(&m).job_state,"cancelled");m.forget(&job).unwrap();
  *m.shared.cancel_phase.lock().unwrap()=None;let job=m.page(&id,query()).unwrap();assert_eq!(wait(&m).job_state,"succeeded");m.forget(&job).unwrap();assert_eq!(m.snapshot().reader_id.as_deref(),Some(id.as_str()));m.join().unwrap();
 }
 #[test]fn lowercase_policy_switches_on_one_snapshot_and_cancellation_can_retry() {
  let dir=tempfile::tempdir().unwrap();let db=database(dir.path());let budget=Budget::new(AdmissionLimits::default()).unwrap();let mut m=Manager::new(budget).unwrap();let id=ready(&m,db);
  assert!(serde_json::from_str::<Query>(r#"{"query":"app","matching":"full_casefold","offset":0,"limit":2}"#).is_err());
  for (matching,total,offset,ids) in [(Matching::Literal,3,0,vec!["1","2"]),(Matching::Unicode16Lower,4,0,vec!["1","2"]),(Matching::Unicode16Lower,4,2,vec!["3","4"])]{
   let mut q=query();q.matching=matching;q.offset=offset;let job=m.page(&id,q).unwrap();assert_eq!(wait(&m).job_state,"succeeded");let Some(Reply::Page(p))=m.take(&job).unwrap()else{panic!()};assert_eq!(p.total,total);assert_eq!(p.rows.iter().map(|r|r.rowid.as_str()).collect::<Vec<_>>(),ids);m.forget(&job).unwrap();
  }
  *m.shared.cancel_phase.lock().unwrap()=Some("database_case_scan");let mut q=query();q.matching=Matching::Unicode16Lower;let job=m.page(&id,q).unwrap();assert_eq!(wait(&m).job_state,"cancelled");m.forget(&job).unwrap();
  *m.shared.cancel_phase.lock().unwrap()=None;let job=m.page(&id,query()).unwrap();assert_eq!(wait(&m).job_state,"succeeded");m.forget(&job).unwrap();assert_eq!(m.snapshot().reader_id.as_deref(),Some(id.as_str()));m.join().unwrap();
 }
 #[test]fn retained_lease_excludes_publications_until_actual_close() {
  let dir=tempfile::tempdir().unwrap();let db=database(dir.path());let budget=Budget::new(AdmissionLimits::default()).unwrap();let mut m=Manager::new(budget.clone()).unwrap();let id=ready(&m,db.clone());
  assert_eq!(budget.snapshot().active_operations,1);assert!(budget.reserve(Operation::Reader).is_err());assert!(budget.reserve(Operation::CcPacking).is_err());
  std::fs::remove_file(db).unwrap();
  for offset in [0,2] {let mut q=query();q.offset=offset;let job=m.page(&id,q).unwrap();assert_eq!(wait(&m).job_state,"succeeded");let Some(Reply::Page(p))=m.take(&job).unwrap()else{panic!()};assert_eq!(p.total,3);assert_eq!(p.rows.len(),if offset==0{2}else{1});assert_eq!(m.snapshot().latest_progress.unwrap().phase,"database_page");m.forget(&job).unwrap();}
  m.close(&id).unwrap();closed(&m);assert_eq!(budget.snapshot().active_operations,0);assert!(budget.reserve(Operation::CcPacking).is_ok());m.join().unwrap();
 }
 #[test]fn cancelled_open_releases_lease_and_allows_recovery() {
  let dir=tempfile::tempdir().unwrap();let db=database(dir.path());let budget=Budget::new(AdmissionLimits::default()).unwrap();let mut m=Manager::new(budget.clone()).unwrap();*m.shared.cancel_phase.lock().unwrap()=Some("database_reader_ready");
  let (_,job)=m.open(db.clone()).unwrap();let s=wait(&m);assert_eq!(s.job_state,"cancelled");assert!(!s.result_available);assert_eq!(budget.snapshot().active_operations,0);assert!(m.take(&job).unwrap().is_none());m.forget(&job).unwrap();
  *m.shared.cancel_phase.lock().unwrap()=None;let id=ready(&m,db);m.close(&id).unwrap();closed(&m);m.join().unwrap();
 }
 #[test]fn cancelled_page_retains_snapshot_and_can_retry_without_reopen() {
  let dir=tempfile::tempdir().unwrap();let db=database(dir.path());let budget=Budget::new(AdmissionLimits::default()).unwrap();let mut m=Manager::new(budget.clone()).unwrap();let id=ready(&m,db);
  *m.shared.cancel_phase.lock().unwrap()=Some("database_page");let job=m.page(&id,query()).unwrap();let s=wait(&m);assert_eq!(s.job_state,"cancelled");assert_eq!(s.state,"ready");assert_eq!(s.error.unwrap().code,"cancelled");assert_eq!(budget.snapshot().active_operations,1);m.forget(&job).unwrap();
  *m.shared.cancel_phase.lock().unwrap()=None;let job=m.page(&id,query()).unwrap();assert_eq!(wait(&m).job_state,"succeeded");m.forget(&job).unwrap();m.join().unwrap();assert_eq!(budget.snapshot().active_operations,0);
 }
 #[test]fn stale_handles_retention_and_invalid_queries_are_refused() {
  let dir=tempfile::tempdir().unwrap();let db=database(dir.path());let budget=Budget::new(AdmissionLimits::default()).unwrap();let mut m=Manager::new(budget.clone()).unwrap();let (id,job)=m.open(db.clone()).unwrap();wait(&m);
  assert_eq!(m.page(&id,query()).unwrap_err().code,ApiCode::StillRunning);assert_eq!(m.open(db.clone()).unwrap_err().code,ApiCode::StillRunning);m.forget(&job).unwrap();
  let mut q=query();q.limit=129;assert_eq!(m.page(&id,q).unwrap_err().code,ApiCode::InvalidInput);assert_eq!(m.page("stale",query()).unwrap_err().code,ApiCode::NotFound);
  m.close(&id).unwrap();closed(&m);let newer=ready(&m,db);assert_ne!(id,newer);assert_eq!(m.close(&id).unwrap_err().code,ApiCode::NotFound);assert_eq!(m.snapshot().reader_id.as_deref(),Some(newer.as_str()));m.join().unwrap();assert_eq!(budget.snapshot().active_operations,0);
 }
 #[test]fn shutdown_drains_queued_open_and_releases_its_reservation() {
  let dir=tempfile::tempdir().unwrap();let db=database(dir.path());let budget=Budget::new(AdmissionLimits::default()).unwrap();let mut m=Manager::new(budget.clone()).unwrap();m.open(db.clone()).unwrap();m.join().unwrap();assert_eq!(m.snapshot().state,"closed");assert_eq!(budget.snapshot().active_operations,0);assert_eq!(m.open(db).unwrap_err().code,ApiCode::Closed);
 }
}
