use super::*;
use studio_indexed_engine::index::BuildOptions;
struct Fixture {dir:tempfile::TempDir}
impl Fixture {
 fn new(large:bool)->Self {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.mdx");let artifact=dir.path().join("source.idx");let mut b=mdictlib::MdxBuilder::with_options(mdictlib::WriteOptions::new().with_legacy_sort(mdictlib::LegacySort::PreserveInput));b.header_attribute("Format","Html").unwrap();
  if large {b.add_entry("apple",&"x".repeat(900000)).unwrap();}else {b.add_entry("apple","first").unwrap();b.add_entry("apple","second").unwrap();b.add_entry("字","文字").unwrap();}b.finish(&mut std::fs::File::create(&source).unwrap()).unwrap();
  let token=CancellationToken::default();let mut cb=|_|{};let mut job=ImportJob::new("seed",&token,&mut cb);let d=Dictionary::open_v2(&source,Kind::Mdx,&Limits::default(),&mut job).unwrap();Index::build(&d,&artifact,Policy::HeaderAsciiV1,BuildOptions::default(),&mut job).unwrap();Self {dir}
 }
 fn request(&self)->OpenRequest {OpenRequest {source:self.dir.path().join("source.mdx"),artifact:self.dir.path().join("source.idx"),kind:DictionaryKind::Mdx,policy:Policy::HeaderAsciiV1}}
}
fn page()->PageRequest {PageRequest {query:"apple".into(),offset:0,limit:1}}
fn ready(pool:&Pool,f:&Fixture)->Session {let s=pool.open(f.request()).unwrap();let id=s.open_job_id();assert_eq!(s.wait_job(&id,Duration::from_secs(20)).unwrap().unwrap().state,JobState::Succeeded);assert_eq!(s.snapshot().state,SessionState::Ready);assert!(matches!(s.take_result(&id).unwrap(),Some(Response::Opened(_))));assert!(s.take_result(&id).unwrap().is_none());s.forget(&id).unwrap();s}
struct Gate {state:Mutex<(bool,bool)>,changed:Condvar}
impl Gate {
 fn new()->Arc<Self> {Arc::new(Self {state:Mutex::new((false,false)),changed:Condvar::new()})}
 fn hit(&self) {let mut s=self.state.lock().unwrap();if s.0 {return;}s.0=true;self.changed.notify_all();while !s.1 {s=self.changed.wait(s).unwrap();}}
 fn entered(&self) {let s=self.state.lock().unwrap();let (s,timeout)=self.changed.wait_timeout_while(s,Duration::from_secs(20),|s|!s.0).unwrap();assert!(!timeout.timed_out()&&s.0,"Worker did not enter test gate");}
 fn release(&self) {let mut s=self.state.lock().unwrap();s.1=true;self.changed.notify_all();}
}
struct Release(Arc<Gate>);impl Drop for Release {fn drop(&mut self) {self.0.release();}}
#[test]fn persistent_pages_own_snapshots_and_results_transfer_once() {
 let f=Fixture::new(false);let pool=Pool::new(Config::default()).unwrap();let s=ready(&pool,&f);std::fs::write(f.request().source,b"public source replaced").unwrap();std::fs::write(f.request().artifact,b"public cache replaced").unwrap();
 for offset in [0,1] {let id=s.submit_page(PageRequest {offset,..page()}).unwrap();assert_eq!(s.wait_job(&id,Duration::from_secs(10)).unwrap().unwrap().state,JobState::Succeeded);let Some(Response::Page(p))=s.take_result(&id).unwrap() else {panic!("Missing page")};assert_eq!(p.total,2);assert_eq!(p.rows[0].ordinal,offset);assert_eq!(p.rows[0].text.as_deref(),Some(if offset==0 {"first"}else{"second"}));assert!(s.take_result(&id).unwrap().is_none());s.forget(&id).unwrap();}
 assert_eq!(pool.admission().retained_reply_bytes,0);s.close();assert!(s.wait_closed(Duration::from_secs(10)));assert_eq!(pool.admission().live_sessions,0);assert_eq!(s.submit_page(page()).unwrap_err().code,ApiCode::Closed);s.join().unwrap();
}
#[test]fn opening_close_waits_for_resource_cleanup_and_reservation_release() {
 let f=Fixture::new(false);let gate=Gate::new();let _release=Release(gate.clone());let g=gate.clone();let pool=Pool::with_hook(Config {max_sessions:1,..Config::default()},Arc::new(move|_,p|if p.phase=="header" {g.hit();}));let s=pool.open(f.request()).unwrap();gate.entered();assert_eq!(s.submit_page(page()).unwrap_err().code,ApiCode::NotReady);assert!(matches!(pool.open(f.request()),Err(ApiError {code:ApiCode::ResourceLimit,..})));
 s.close();assert!(!s.wait_closed(Duration::ZERO));assert_eq!(pool.admission().live_sessions,1);gate.release();assert!(s.wait_closed(Duration::from_secs(10)));assert_eq!(pool.admission().live_sessions,0);assert_eq!(s.job(&s.open_job_id()).unwrap().state,JobState::Cancelled);s.join().unwrap();
}
#[test]fn queue_retention_running_cancel_and_shutdown_are_bounded() {
 let f=Fixture::new(false);let gate=Gate::new();let _release=Release(gate.clone());let g=gate.clone();let pool=Pool::with_hook(Config {max_pending:1,max_retained:3,..Config::default()},Arc::new(move|_,p|if p.phase=="index_lookup" {g.hit();}));let s=ready(&pool,&f);let first=s.submit_page(page()).unwrap();gate.entered();let second=s.submit_page(page()).unwrap();assert_eq!(s.submit_page(page()).unwrap_err().code,ApiCode::QueueFull);assert_eq!(s.cancel(&second).unwrap(),CancelOutcome::Requested);let third=s.submit_page(page()).unwrap();s.cancel(&third).unwrap();assert_eq!(s.submit_page(page()).unwrap_err().code,ApiCode::RetentionFull);
 assert_eq!(s.take_result(&first).unwrap_err().code,ApiCode::StillRunning);assert_eq!(s.forget(&first).unwrap_err().code,ApiCode::StillRunning);assert_eq!(s.cancel(&first).unwrap(),CancelOutcome::Requested);assert_eq!(s.cancel(&first).unwrap(),CancelOutcome::AlreadyRequested);pool.shutdown();gate.release();assert!(s.wait_closed(Duration::from_secs(10)));assert_eq!(s.job(&first).unwrap().state,JobState::Cancelled);assert!(s.take_result(&first).unwrap().is_none());assert_eq!(s.cancel(&first).unwrap(),CancelOutcome::AlreadyFinished);assert!(s.drain_events().len()<=3);assert_eq!(pool.admission().live_sessions,0);assert!(matches!(pool.open(f.request()),Err(ApiError {code:ApiCode::Closed,..})));s.join().unwrap();
}
#[test]fn cancellation_after_payload_materialization_discards_the_whole_reply() {
 let f=Fixture::new(false);let gate=Gate::new();let _release=Release(gate.clone());let g=gate.clone();let pool=Pool::with_hook(Config::default(),Arc::new(move|_,p|if p.phase=="session_result_commit" {g.hit();}));let s=ready(&pool,&f);let id=s.submit_page(page()).unwrap();gate.entered();s.cancel(&id).unwrap();gate.release();assert_eq!(s.wait_job(&id,Duration::from_secs(10)).unwrap().unwrap().state,JobState::Cancelled);assert!(s.take_result(&id).unwrap().is_none());assert_eq!(pool.admission().retained_reply_bytes,0);s.join().unwrap();
}
#[test]fn worker_panic_closes_session_and_releases_its_admission() {
 let f=Fixture::new(false);let pool=Pool::with_hook(Config::default(),Arc::new(|_,p|if p.phase=="index_lookup" {panic!("Injected session panic");}));let s=ready(&pool,&f);let id=s.submit_page(page()).unwrap();assert!(s.wait_closed(Duration::from_secs(10)));assert_eq!(s.snapshot().state,SessionState::Failed);let job=s.job(&id).unwrap();assert_eq!(job.state,JobState::Failed);assert_eq!(job.error.unwrap().code,ErrorCode::Internal);assert_eq!(pool.admission().live_sessions,0);assert!(s.take_result(&id).unwrap().is_none());s.join().unwrap();
}
#[test]fn global_retained_byte_admission_is_released_by_transfer_and_drop() {
 let f=Fixture::new(true);let pool=Pool::new(Config::default()).unwrap();let a=ready(&pool,&f);let b=ready(&pool,&f);let mut held=Vec::new();
 for n in 0..9 {let s=if n%2==0 {&a}else{&b};let id=s.submit_page(page()).unwrap();assert_eq!(s.wait_job(&id,Duration::from_secs(10)).unwrap().unwrap().state,JobState::Succeeded);held.push((n%2,id));}
 let id=b.submit_page(page()).unwrap();let result=b.wait_job(&id,Duration::from_secs(10)).unwrap().unwrap();assert_eq!(result.state,JobState::Failed);assert_eq!(result.error.unwrap().detail,"retained_reply_limit");assert!(pool.admission().retained_reply_bytes<=RETAINED_BYTE_CAP);
 let (_,first)=&held[0];drop(a.take_result(first).unwrap());let id=b.submit_page(page()).unwrap();assert_eq!(b.wait_job(&id,Duration::from_secs(10)).unwrap().unwrap().state,JobState::Succeeded);
 a.close();b.close();assert!(a.wait_closed(Duration::from_secs(10)));assert!(b.wait_closed(Duration::from_secs(10)));assert_eq!(pool.admission().live_sessions,0);assert!(pool.admission().retained_reply_bytes>0);a.join().unwrap();b.join().unwrap();assert_eq!(pool.admission().retained_reply_bytes,0);
}
#[test]fn precancelled_open_and_page_jobs_never_retain_success() {
 let f=Fixture::new(false);let pool=Pool::new(Config::default()).unwrap();let token=CancellationToken::default();token.cancel();let s=pool.open_with_token(f.request(),token).unwrap();assert!(s.wait_closed(Duration::from_secs(10)));assert_eq!(s.job(&s.open_job_id()).unwrap().state,JobState::Cancelled);assert_eq!(pool.admission().live_sessions,0);s.join().unwrap();let s=ready(&pool,&f);let token=CancellationToken::default();token.cancel();let id=s.submit_page_with_token(page(),token).unwrap();assert_eq!(s.job(&id).unwrap().state,JobState::Cancelled);assert!(s.take_result(&id).unwrap().is_none());s.join().unwrap();
}
#[test]fn reply_overflow_fails_only_that_job_and_count_only_pages_still_work() {
 let f=Fixture::new(true);let pool=Pool::new(Config {max_reply_bytes:1024,..Config::default()}).unwrap();let s=ready(&pool,&f);let id=s.submit_page(page()).unwrap();let status=s.wait_job(&id,Duration::from_secs(10)).unwrap().unwrap();assert_eq!(status.state,JobState::Failed);assert_eq!(status.error.unwrap().detail,"reply_limit");assert_eq!(s.snapshot().state,SessionState::Ready);assert_eq!(pool.admission().retained_reply_bytes,0);
 let id=s.submit_page(PageRequest {limit:0,..page()}).unwrap();assert_eq!(s.wait_job(&id,Duration::from_secs(10)).unwrap().unwrap().state,JobState::Succeeded);assert!(matches!(s.take_result(&id).unwrap(),Some(Response::Page(_))));s.join().unwrap();
}
#[test]fn closed_session_metadata_handles_are_also_bounded() {
 let f=Fixture::new(false);let pool=Pool::new(Config::default()).unwrap();let mut sessions=Vec::new();
 for _ in 0..MAX_SESSION_HANDLES {let token=CancellationToken::default();token.cancel();let s=pool.open_with_token(f.request(),token).unwrap();assert!(s.wait_closed(Duration::from_secs(10)));sessions.push(s);}
 assert_eq!(pool.admission().live_sessions,0);assert_eq!(pool.admission().retained_session_handles,8);assert!(matches!(pool.open(f.request()),Err(ApiError {code:ApiCode::ResourceLimit,..})));
 sessions.pop().unwrap().join().unwrap();let token=CancellationToken::default();token.cancel();let s=pool.open_with_token(f.request(),token).unwrap();s.join().unwrap();for s in sessions {s.join().unwrap();}assert_eq!(pool.admission().retained_session_handles,0);
}
