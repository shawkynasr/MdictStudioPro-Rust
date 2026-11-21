use super::*;
use studio_sessions::{DictionaryKind,JobState};
struct Fixture {dir:tempfile::TempDir}
impl Fixture {
 fn new()->Self {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("input.mdd");let mut b=mdictlib::MddBuilder::new();b.add_resource("assets/data.bin",&vec![17;3*1024*1024]).unwrap();b.add_resource("empty",&[]).unwrap();b.finish(std::fs::File::create(source).unwrap()).unwrap();
  let mdx=dir.path().join("reader.mdx");let idx=dir.path().join("reader.idx");let mut b=mdictlib::MdxBuilder::with_options(mdictlib::WriteOptions::new().with_legacy_sort(mdictlib::LegacySort::PreserveInput));b.header_attribute("Format","Html").unwrap();b.add_entry("apple","first").unwrap();b.finish(std::fs::File::create(&mdx).unwrap()).unwrap();
  let token=CancellationToken::default();let mut cb=|_|{};let mut job=studio_indexed_engine::ImportJob::new("seed",&token,&mut cb);let d=studio_indexed_engine::Dictionary::open_v2(&mdx,studio_indexed_engine::Kind::Mdx,&studio_indexed_engine::Limits::default(),&mut job).unwrap();studio_indexed_engine::index::Index::build(&d,&idx,studio_indexed_engine::index::Policy::HeaderAsciiV1,studio_indexed_engine::index::BuildOptions::default(),&mut job).unwrap();Self {dir}
 }
 fn request(&self,name:&str)->Request {Request {source:self.dir.path().join("input.mdd"),destination:self.dir.path().join(name)}}
 fn reader(&self)->OpenRequest {OpenRequest {source:self.dir.path().join("reader.mdx"),artifact:self.dir.path().join("reader.idx"),kind:DictionaryKind::Mdx,policy:studio_sessions::Policy::HeaderAsciiV1}}
}
fn ready(runtime:&Runtime,f:&Fixture)->Reader {let reader=runtime.open_reader(f.reader()).unwrap();let job=reader.session().open_job_id();assert_eq!(reader.session().wait_job(&job,Duration::from_secs(20)).unwrap().unwrap().state,JobState::Succeeded);reader.session().take_result(&job).unwrap();reader.session().forget(&job).unwrap();reader}
fn wait(runner:&runner::Runner,id:&str)->runner::Snapshot {runner.wait_for_terminal(id,Duration::from_secs(30)).unwrap().unwrap()}
struct Gate {state:Mutex<(bool,bool)>,changed:Condvar}
impl Gate {
 fn new()->Arc<Self> {Arc::new(Self {state:Mutex::new((false,false)),changed:Condvar::new()})}
 fn hit(&self) {let mut state=self.state.lock().unwrap();if state.0 {return;}state.0=true;self.changed.notify_all();while !state.1 {state=self.changed.wait(state).unwrap();}}
 fn entered(&self) {let state=self.state.lock().unwrap();let (state,timeout)=self.changed.wait_timeout_while(state,Duration::from_secs(30),|s|!s.0).unwrap();assert!(state.0&&!timeout.timed_out());}
 fn release(&self) {let mut s=self.state.lock().unwrap();s.1=true;self.changed.notify_all();}
}
struct Release(Arc<Gate>);impl Drop for Release {fn drop(&mut self) {self.0.release();}}
#[test]fn shared_profiles_count_memory_and_temp_separately() {
 let budget=Budget::new(AdmissionLimits::default()).unwrap();let a=budget.reserve(Operation::Reader).unwrap();let b=budget.reserve(Operation::Reader).unwrap();assert!(matches!(budget.reserve(Operation::Extraction),Err(ApiError {code:ApiCode::ResourceLimit,..})));drop(b);
 let e=budget.reserve(Operation::Extraction).unwrap();let s=budget.snapshot();assert_eq!(s.readers,1);assert_eq!(s.extractions,1);assert_eq!(s.reserved_memory_bytes,192*1024*1024);assert_eq!(s.reserved_temporary_bytes,3840*1024*1024);drop(e);drop(a);
 let e=budget.reserve(Operation::Extraction).unwrap();assert!(matches!(budget.reserve(Operation::Extraction),Err(ApiError {code:ApiCode::ResourceLimit,..})));drop(e);assert_eq!(budget.snapshot().active_operations,0);
}
#[test]fn real_readers_block_extraction_then_release_allows_verified_publication() {
 let f=Fixture::new();let runtime=Runtime::new(AdmissionLimits::default(),runner::Config::default()).unwrap();let a=ready(&runtime,&f);let b=ready(&runtime,&f);let request=f.request("blocked");let id=runtime.extraction().submit(request).unwrap();let status=wait(runtime.extraction(),&id);assert_eq!(status.state,JobState::Failed);assert_eq!(status.error.unwrap().detail,"resource_admission");assert!(!f.request("blocked").destination.exists());runtime.extraction().forget(&id).unwrap();
 b.close();assert!(b.wait_closed(Duration::from_secs(20)));assert_eq!(runtime.admission().readers,1);let id=runtime.extraction().submit(f.request("published")).unwrap();assert_eq!(wait(runtime.extraction(),&id).state,JobState::Succeeded);let receipt=runtime.extraction().take_result(&id).unwrap().unwrap();assert_eq!(receipt.payload_bytes,3*1024*1024);assert_eq!(std::fs::read(f.request("published").destination.join("assets/data.bin")).unwrap(),vec![17;3*1024*1024]);assert!(runtime.extraction().take_result(&id).unwrap().is_none());assert_eq!(runtime.extraction().cancel(&id).unwrap(),runner::CancelOutcome::AlreadyFinished);a.close();assert!(a.wait_closed(Duration::from_secs(20)));assert_eq!(runtime.admission().active_operations,0);runtime.join().unwrap();
}
#[test]fn successful_commit_wins_over_late_cancel_and_shutdown() {
 let f=Fixture::new();let gate=Gate::new();let _release=Release(gate.clone());let g=gate.clone();let budget=Budget::new(AdmissionLimits::default()).unwrap();let runner=runner::Runner::with_executor(runner::Config::default(),budget.clone(),Arc::new(move|request,job| {let result=execute(request,job)?;g.hit();Ok(result)})).unwrap();let id=runner.submit(f.request("late")).unwrap();gate.entered();assert!(f.request("late").destination.exists());assert_eq!(budget.snapshot().extractions,1);runner.cancel(&id).unwrap();runner.shutdown();gate.release();let s=wait(&runner,&id);assert_eq!(s.state,JobState::Succeeded);assert!(s.cancel_requested);assert!(runner.take_result(&id).unwrap().is_some());assert_eq!(budget.snapshot().active_operations,0);runner.join().unwrap();
}
#[test]fn queued_and_running_cancellation_release_staging_and_admission() {
 let f=Fixture::new();let gate=Gate::new();let _release=Release(gate.clone());let g=gate.clone();let token=CancellationToken::default();let worker_token=token.clone();let budget=Budget::new(AdmissionLimits::default()).unwrap();let runner=runner::Runner::with_executor(runner::Config {max_pending:1,max_retained:3},budget.clone(),Arc::new(move|request,_| {let mut cb=|p:Progress|if p.phase=="copy_resource"&&p.completed>=65536 {g.hit();};execute(request,&mut studio_stream_extract::ImportJob::new("gated-copy",&worker_token,&mut cb))})).unwrap();
 let first=runner.submit_with_token(f.request("cancelled"),token).unwrap();gate.entered();let second=runner.submit(f.request("queued")).unwrap();assert_eq!(runner.submit(f.request("overflow")).unwrap_err().code,ApiCode::QueueFull);runner.cancel(&second).unwrap();let third=runner.submit(f.request("third")).unwrap();runner.cancel(&third).unwrap();assert_eq!(runner.submit(f.request("retained")).unwrap_err().code,ApiCode::RetentionFull);assert_eq!(runner.take_result(&first).unwrap_err().code,ApiCode::StillRunning);assert_eq!(runner.forget(&first).unwrap_err().code,ApiCode::StillRunning);
 runner.cancel(&first).unwrap();gate.release();assert_eq!(wait(&runner,&first).state,JobState::Cancelled);assert_eq!(budget.snapshot().active_operations,0);assert!(!f.request("cancelled").destination.exists());assert!(runner.drain_events().len()<=3);runner.join().unwrap();assert!(!f.dir.path().read_dir().unwrap().any(|p|p.unwrap().file_name().to_string_lossy().starts_with(".studio-stream-extract-")));
}
#[test]fn panic_before_and_after_commit_is_explicitly_uncertain_and_releases_lease() {
 for after in [false,true] {
  let f=Fixture::new();let budget=Budget::new(AdmissionLimits::default()).unwrap();let runner=runner::Runner::with_executor(runner::Config::default(),budget.clone(),Arc::new(move|request,job| {if after {let _=execute(request,job)?;}panic!("Injected publisher panic")})).unwrap();let id=runner.submit(f.request("panic")).unwrap();let s=wait(&runner,&id);assert_eq!(s.state,JobState::Failed);let error=s.error.unwrap();assert_eq!(error.code,ErrorCode::Internal);assert!(error.publication_uncertain);assert_eq!(f.request("panic").destination.exists(),after);assert!(runner.take_result(&id).unwrap().is_none());assert_eq!(budget.snapshot().active_operations,0);runner.join().unwrap();
 }
}
#[test]fn ordinary_failure_pre_cancel_and_followup_success_keep_worker_usable() {
 let f=Fixture::new();let runtime=Runtime::new(AdmissionLimits::default(),runner::Config::default()).unwrap();let mut missing=f.request("missing");missing.source=f.dir.path().join("absent.mdd");let id=runtime.extraction().submit(missing).unwrap();let s=wait(runtime.extraction(),&id);assert_eq!(s.state,JobState::Failed);assert!(!s.error.unwrap().publication_uncertain);assert_eq!(runtime.admission().active_operations,0);runtime.extraction().forget(&id).unwrap();
 let token=CancellationToken::default();token.cancel();let id=runtime.extraction().submit_with_token(f.request("precancel"),token).unwrap();assert_eq!(wait(runtime.extraction(),&id).state,JobState::Cancelled);assert!(!f.request("precancel").destination.exists());let id=runtime.extraction().submit(f.request("success")).unwrap();assert_eq!(wait(runtime.extraction(),&id).state,JobState::Succeeded);runtime.join().unwrap();
}
#[test]fn dropped_reader_and_runtime_shutdown_eventually_release_shared_leases() {
 let f=Fixture::new();let runtime=Runtime::new(AdmissionLimits::default(),runner::Config::default()).unwrap();let budget=runtime.budget.clone();let a=ready(&runtime,&f);let b=ready(&runtime,&f);drop(a);runtime.shutdown();assert!(b.wait_closed(Duration::from_secs(20)));assert!(matches!(runtime.open_reader(f.reader()),Err(ApiError {code:ApiCode::Closed,..})));runtime.join().unwrap();assert_eq!(budget.snapshot().active_operations,0);
}
