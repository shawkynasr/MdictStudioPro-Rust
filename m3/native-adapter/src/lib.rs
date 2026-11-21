//! GUI-independent, bounded command boundary over the accepted M2 runtime.
//! Call from a blocking executor; no dictionary work executes on the UI thread.
mod details;
use serde::Deserialize;
use serde_json::{json, Value};
use std::{collections::{BTreeMap, BTreeSet}, sync::{Arc, Mutex, MutexGuard}, time::Duration};
use studio_cc_pack_runtime as native;
pub use native::{ApiCode, ApiError, ApiResult};

pub const MAX_COMMAND_BYTES: usize = 64 * 1024;
const MAX_ID_BYTES: usize = 128;

#[derive(Debug, Deserialize)]
#[serde(tag = "action", rename_all = "snake_case", deny_unknown_fields)]
pub enum Command {
    // Use empty struct variants rather than unit variants: Serde's internally
    // tagged unit decoder can skip extra map fields despite deny_unknown_fields.
    DatabaseOpen {source:std::path::PathBuf},
    DatabaseQuery {reader_id:String,request:native::database_reader::Query},
    DatabasePoll {},
    DatabaseCancel {job_id:String},
    DatabaseTake {job_id:String},
    DatabaseForget {job_id:String},
    DatabaseClose {reader_id:String},
    Capabilities {},
    Poll {},
    Submit { request: native::Request },
    Cancel { job_id: String },
    Take { job_id: String },
    Forget { job_id: String },
    OpenReader { request: native::OpenRequest },
    Page { session_id: String, request: native::PageRequest },
    Resolve { session_id: String, request: native::ResolveRequest },
    SessionTake { session_id: String, job_id: String },
    SessionCancel { session_id: String, job_id: String },
    SessionForget { session_id: String, job_id: String },
    CloseReader { session_id: String },
    ReleaseReader { session_id: String },
    ReaderDetails { session_id: String },
    ExportStylesheet {session_id:String,destination:std::path::PathBuf},
}

struct Reader { native: native::Reader, jobs: BTreeSet<String>, source: std::path::PathBuf, manifest: Option<Value>, details: Option<Value>, task: Arc<details::Task>, closing: bool }
struct Inner {
    runtime: Option<native::Runtime>,
    jobs: BTreeSet<String>,
    readers: BTreeMap<String, Reader>,
}
pub struct Adapter { inner: Mutex<Inner> }

fn error(code: ApiCode, message: impl Into<String>) -> ApiError {
    ApiError { code, message: message.into() }
}
fn value<T: serde::Serialize>(item: T) -> ApiResult<Value> {
    serde_json::to_value(item).map_err(|e| error(ApiCode::Internal, e.to_string()))
}
fn id(id: &str) -> ApiResult<()> {
    if id.is_empty() || id.len() > MAX_ID_BYTES || !id.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-') {
        return Err(error(ApiCode::InvalidInput, "Invalid bounded job/session identifier"));
    }
    Ok(())
}
fn reader<'a>(inner: &'a Inner, key: &str) -> ApiResult<&'a Reader> {
    id(key)?;
    inner.readers.get(key).ok_or_else(|| error(ApiCode::NotFound, "Unknown reader"))
}

impl Adapter {
    pub fn new() -> ApiResult<Self> {
        let runtime = native::Runtime::new(native::AdmissionLimits::default(), native::runner::Config::default())?;
        Ok(Self { inner: Mutex::new(Inner { runtime: Some(runtime), jobs: BTreeSet::new(), readers: BTreeMap::new() }) })
    }
    fn lock(&self) -> ApiResult<MutexGuard<'_, Inner>> {
        self.inner.lock().map_err(|_| error(ApiCode::Internal, "Adapter lock poisoned; restart required"))
    }
    pub fn call_json(&self, input: &str) -> ApiResult<Value> {
        // Validate before decoding nested native requests. No request can raise caps.
        if input.len() > MAX_COMMAND_BYTES {
            return Err(error(ApiCode::InvalidInput, "Command exceeds 64 KiB"));
        }
        let command: Command = serde_json::from_str(input)
            .map_err(|e| error(ApiCode::InvalidInput, format!("Invalid command: {e}")))?;
        self.call(command)
    }
    pub fn call(&self, command: Command) -> ApiResult<Value> {
        if matches!(&command, Command::Capabilities {}) {
            return Ok(json!({
                "adapter": "studio-native-command-v1", "max_command_bytes": MAX_COMMAND_BYTES,
                "max_retained_jobs": 8, "max_pending_jobs": 2, "poll_interval_ms": 400,
                "profiles": ["large-dictionary-io-v1", "cc-mdx-block-spool-v1",
                    "cc-cedict-owned-chunked-txt-v1", "moe-concise-disk-groups-txt-v1",
                    "small-moe", "grouped-moe", "indexed-sessions", "stream-mdd-extraction", "txt-utf8-mdx-v1", "folder-mdd-v1", "large-mdx-export-v1", "trusted-python-converter-v1"],
                "database": "studio-sqlite-text-v1", "database_operations": ["db_add_entry","db_delete_entry","db_edit_entry","db_edit_metadata","jsonl_to_db","txt_to_db","db_to_txt","db_to_jsonl","mdx_to_db","db_to_mdx"], "database_reading": "sqlite-persistent-reader-v1", "database_matching": ["literal","unicode16_lower"], "database_wildcards": "unicode-scalar-glob-v1", "database_definition_search": "stored-text-substring-v1",
                "stylesheet_export": "reader-stylesheet-utf8-v1", "python_plugins": "trusted-python-converter-v1", "python_inspection": "trusted-python-inspection-v1", "python_folder": "trusted-python-folder-v1", "python_probe": "trusted-python-probe-v1", "metadata_editing": true, "metadata_profile": "bounded-copy-v1", "redirect_resolution": true, "redirect_profile": "indexed-selected-record-v1",
                "dictionary_html_rendering": "static-sandbox-v1", "mdx_v3": false,
                "mdx_export_encryption": ["none", "v2-keyword-index-2"],
                "mdx_legacy_export": "v1.2-ISO8859-1-ASCII-only",
                "hard_memory_limit": false,
                "scope": "M3 desktop integration; latest native validation pending; M2 sources and caps unchanged"
            }));
        }
        if let Command::ReaderDetails { session_id } = &command { return self.reader_details(session_id); }
        // Only short enqueue/snapshot/transfer operations hold this lock.
        // The native workers perform all parsing, indexing and publication.
        let mut inner = self.lock()?;
        let runtime = inner.runtime.as_ref().ok_or_else(|| error(ApiCode::Closed, "Adapter closed"))?;
        match command {
            Command::Capabilities {} | Command::ReaderDetails { .. } => unreachable!(),
            Command::DatabaseOpen {source}=>{let (reader_id,job_id)=runtime.database_reader().open(source)?;Ok(json!({"reader_id":reader_id,"job_id":job_id}))},
            Command::DatabaseQuery {reader_id,request}=>{id(&reader_id)?;let job_id=runtime.database_reader().page(&reader_id,request)?;Ok(json!({"job_id":job_id}))},
            Command::DatabasePoll {}=>value(runtime.database_reader().snapshot()),
            Command::DatabaseCancel {job_id}=>{id(&job_id)?;runtime.database_reader().cancel(&job_id)?;Ok(Value::Null)},
            Command::DatabaseTake {job_id}=>{id(&job_id)?;value(runtime.database_reader().take(&job_id)?)},
            Command::DatabaseForget {job_id}=>{id(&job_id)?;runtime.database_reader().forget(&job_id)?;Ok(Value::Null)},
            Command::DatabaseClose {reader_id}=>{id(&reader_id)?;runtime.database_reader().close(&reader_id)?;Ok(Value::Null)},
            Command::Poll {} => {
                for r in inner.readers.values() { if r.closing && !r.task.busy() { r.native.close(); } }
                let jobs = inner.jobs.iter().map(|id| runtime.publication().snapshot(id)).collect::<ApiResult<Vec<_>>>()?;
                let sessions = inner.readers.values().map(|r| {
                    let jobs = r.jobs.iter().map(|id| r.native.session().job(id)).collect::<ApiResult<Vec<_>>>()?;
                    let mut snapshot=value(r.native.session().snapshot())?;
                    if r.closing && r.task.busy() {snapshot["state"]=json!("closing");}
                    Ok(json!({"session": snapshot, "jobs": jobs}))
                }).collect::<ApiResult<Vec<Value>>>()?;
                Ok(json!({"jobs": jobs, "sessions": sessions, "admission": runtime.admission(), "readers": runtime.reader_admission()}))
            }
            Command::ExportStylesheet {session_id,destination} => {
                let r=reader(&inner,&session_id)?;
                if r.closing {return Err(error(ApiCode::Closed,"Reader closing"));}
                let manifest=r.manifest.as_ref().ok_or_else(||error(ApiCode::NotReady,"Collect reader-open result first"))?;
                if manifest["kind"]!="mdx" {return Err(error(ApiCode::InvalidInput,"Numeric stylesheets belong to MDX dictionaries"));}
                let info=r.details.as_ref().ok_or_else(||error(ApiCode::NotReady,"Wait for verified reader metadata"))?;
                let attrs=info["attributes"].as_object().ok_or_else(||error(ApiCode::Internal,"Missing cached header attributes"))?;
                let mut matches=attrs.iter().filter(|(k,_)|k.eq_ignore_ascii_case("stylesheet"));
                let stylesheet=matches.next().and_then(|(_,v)|v.as_str()).filter(|s|!s.is_empty()).ok_or_else(||error(ApiCode::NotFound,"This dictionary has no numeric stylesheet; external CSS is stored separately"))?.to_owned();
                if matches.next().is_some(){return Err(error(ApiCode::InvalidInput,"Ambiguous stylesheet attributes"));}
                let source_sha256=info["source_sha256"].as_str().ok_or_else(||error(ApiCode::Internal,"Missing verified snapshot digest"))?.to_owned();
                let job_id=runtime.publication().submit(native::Request::Stylesheet(native::stylesheet_export::Request {destination,stylesheet,source_sha256}))?;
                inner.jobs.insert(job_id.clone());Ok(json!({"job_id":job_id}))
            }
            Command::Submit { request } => {
                let job_id = runtime.publication().submit(request)?;
                inner.jobs.insert(job_id.clone());
                Ok(json!({"job_id": job_id}))
            }
            Command::Cancel { job_id } => { id(&job_id)?; value(runtime.publication().cancel(&job_id)?) }
            Command::Take { job_id } => { id(&job_id)?; value(runtime.publication().take_result(&job_id)?) }
            Command::Forget { job_id } => {
                id(&job_id)?; runtime.publication().forget(&job_id)?; inner.jobs.remove(&job_id); Ok(Value::Null)
            }
            Command::OpenReader { request } => {
                let source=request.source.clone();
                let native = runtime.open_reader(request)?;
                let session_id = native.session().id().to_owned();
                let job_id = native.session().open_job_id();
                inner.readers.insert(session_id.clone(), Reader { native, jobs: BTreeSet::from([job_id.clone()]), source, manifest:None, details:None, task:Arc::new(details::Task::default()), closing:false });
                Ok(json!({"session_id": session_id, "job_id": job_id}))
            }
            Command::Page { session_id, request } => {
                if reader(&inner, &session_id)?.closing {return Err(error(ApiCode::Closed,"Reader closing"));}
                let job_id = reader(&inner, &session_id)?.native.session().submit_page(request)?;
                inner.readers.get_mut(&session_id).ok_or_else(|| error(ApiCode::NotFound, "Reader disappeared"))?.jobs.insert(job_id.clone());
                Ok(json!({"job_id": job_id}))
            }
            Command::Resolve { session_id, request } => {
                let r=reader(&inner,&session_id)?;
                if r.closing {return Err(error(ApiCode::Closed,"Reader closing"));}
                let job_id=r.native.session().submit_resolve(request)?;
                inner.readers.get_mut(&session_id).ok_or_else(||error(ApiCode::NotFound,"Reader disappeared"))?.jobs.insert(job_id.clone());
                Ok(json!({"job_id":job_id}))
            }
            Command::SessionTake { session_id, job_id } => {
                id(&job_id)?;
                let result=value(reader(&inner, &session_id)?.native.session().take_result(&job_id)?)?;
                if result["operation"]=="opened" {if let Some(r)=inner.readers.get_mut(&session_id) {r.manifest=Some(result["value"].clone());}}
                Ok(result)
            }
            Command::SessionCancel { session_id, job_id } => {
                id(&job_id)?; value(reader(&inner, &session_id)?.native.session().cancel(&job_id)?)
            }
            Command::SessionForget { session_id, job_id } => {
                id(&job_id)?; reader(&inner, &session_id)?.native.session().forget(&job_id)?;
                if let Some(r) = inner.readers.get_mut(&session_id) { r.jobs.remove(&job_id); }
                Ok(Value::Null)
            }
            Command::CloseReader { session_id } => {
                reader(&inner, &session_id)?;
                if let Some(r)=inner.readers.get_mut(&session_id) {r.closing=true;r.task.cancel();if !r.task.busy() {r.native.close();}}
                Ok(Value::Null)
            }
            Command::ReleaseReader { session_id } => {
                // A close request alone must not release the shared admission lease.
                if reader(&inner, &session_id)?.task.busy() || !reader(&inner, &session_id)?.native.wait_closed(Duration::ZERO) {
                    return Err(error(ApiCode::StillRunning, "Reader cleanup in progress; poll and retry"));
                }
                let r = inner.readers.remove(&session_id).ok_or_else(|| error(ApiCode::NotFound, "Unknown reader"))?;
                drop(inner);
                r.native.join()?;
                Ok(Value::Null)
            }
        }
    }
    fn reader_details(&self, session_id: &str) -> ApiResult<Value> {
        // Retain the reader lease until the cancellable metadata task stops.
        // Neither file I/O nor its fixed-buffer digest holds the adapter mutex.
        let (source, manifest, task, _guard) = {
            let inner=self.lock()?;
            if inner.runtime.is_none() {return Err(error(ApiCode::Closed,"Adapter closed"));}
            let r=reader(&inner,session_id)?;
            if r.closing {return Err(error(ApiCode::Closed,"Reader closing"));}
            if let Some(info)=&r.details {return Ok(info.clone());}
            (r.source.clone(),r.manifest.clone().ok_or_else(||error(ApiCode::NotReady,"Collect reader-open result first"))?,r.task.clone(),r.task.start()?)
        };
        let digest=manifest["source_sha256"].as_str().ok_or_else(||error(ApiCode::Internal,"Reader manifest lacks digest"))?;
        let mut info=details::read(&source,digest,&task)?;
        info["manifest"]=manifest;
        let mut inner=self.lock()?;
        if let Some(r)=inner.readers.get_mut(session_id) {if !r.closing {r.details=Some(info.clone());return Ok(info);}}
        Err(error(ApiCode::Closed,"Reader closed during metadata read"))
    }
    /// Stops admission and joins all accepted workers. Call off the UI thread.
    /// Taking runtime/readers atomically prevents new commands racing shutdown.
    pub fn shutdown(&self) -> ApiResult<()> {
        let (runtime, readers) = {
            let mut inner = self.lock()?;
            let runtime = inner.runtime.take();
            if let Some(runtime) = &runtime { runtime.publication().shutdown(); }
            let readers = std::mem::take(&mut inner.readers);
            for r in readers.values() { r.task.cancel(); }
            (runtime, readers)
        };
        let mut failure = None;
        for r in readers.into_values() {
            if let Err(e)=r.task.wait() {failure=Some(e);}
            r.native.close();
            if let Err(e) = r.native.join() { failure = Some(e); }
        }
        if let Some(runtime) = runtime {
            if let Err(e) = runtime.join() { failure = Some(e); }
        }
        failure.map_or(Ok(()), Err)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{thread, time::Instant};
    #[test]fn sqlite_jsonl_jobs_require_reader_release_and_publish_without_clobber() {
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.txt");let db=dir.path().join("source.db");let out=dir.path().join("rows.jsonl");std::fs::write(&source,include_bytes!("../../fixtures/build-source.txt")).unwrap();
        let create=call(&a,json!({"action":"submit","request":{"kind":"database","request":{"operation":"txt_to_db","source":source,"destination":db,"profile":"canonical_v1"}}}));let id=create["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"succeeded");call(&a,json!({"action":"forget","job_id":id}));
        let open=call(&a,json!({"action":"database_open","source":db}));assert_eq!(database_wait(&a)["job_state"],"succeeded");call(&a,json!({"action":"database_forget","job_id":open["job_id"]}));
        let request=json!({"action":"submit","request":{"kind":"database","request":{"operation":"db_to_jsonl","source":db,"destination":out}}});
        let blocked=call(&a,request.clone());let id=blocked["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"failed");assert!(!out.exists());call(&a,json!({"action":"forget","job_id":id}));call(&a,json!({"action":"database_close","reader_id":open["reader_id"]}));
        let end=Instant::now()+Duration::from_secs(5);while call(&a,json!({"action":"database_poll"}))["state"]!="closed"{assert!(Instant::now()<end);thread::sleep(Duration::from_millis(2));}
        let exported=call(&a,request.clone());let id=exported["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"succeeded");let receipt=call(&a,json!({"action":"take","job_id":id}));assert_eq!(receipt["receipt"]["operation"],"db_to_jsonl");assert_eq!(receipt["receipt"]["value"]["records"],5);call(&a,json!({"action":"forget","job_id":id}));
        let before=std::fs::read(&out).unwrap();let text=std::str::from_utf8(&before).unwrap();assert_eq!(text.lines().count(),5);assert_eq!(text.lines().map(|line|serde_json::from_str::<Value>(line).unwrap()).filter(|row|row["key"]=="字").count(),2);
        let existing=call(&a,request);let id=existing["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"failed");assert_eq!(std::fs::read(&out).unwrap(),before);call(&a,json!({"action":"forget","job_id":id}));
        let imported=dir.path().join("imported.db");let request=json!({"action":"submit","request":{"kind":"database","request":{"operation":"jsonl_to_db","source":out,"destination":imported}}});
        let submitted=call(&a,request.clone());let id=submitted["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"succeeded");let receipt=call(&a,json!({"action":"take","job_id":id}));assert_eq!(receipt["receipt"]["operation"],"jsonl_to_db");assert_eq!(receipt["receipt"]["value"]["records"],5);call(&a,json!({"action":"forget","job_id":id}));
        let before=std::fs::read(&imported).unwrap();let submitted=call(&a,request);let id=submitted["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"failed");assert_eq!(std::fs::read(imported).unwrap(),before);call(&a,json!({"action":"forget","job_id":id}));assert_eq!(call(&a,json!({"action":"poll"}))["admission"]["active_operations"],0);a.shutdown().unwrap();
    }
    #[test]fn entry_copy_jobs_target_the_selected_duplicate_and_release_admission() {
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();let source=dir.path().join("rows.jsonl");let db=dir.path().join("source.db");let dest=dir.path().join("edited.db");std::fs::write(&source,include_bytes!("../../fixtures/entries.jsonl")).unwrap();
        let submitted=call(&a,json!({"action":"submit","request":{"kind":"database","request":{"operation":"jsonl_to_db","source":source,"destination":db}}}));let id=submitted["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"succeeded");call(&a,json!({"action":"forget","job_id":id}));let opened=call(&a,json!({"action":"database_open","source":db}));assert_eq!(database_wait(&a)["job_state"],"succeeded");let info=call(&a,json!({"action":"database_take","job_id":opened["job_id"]}));call(&a,json!({"action":"database_forget","job_id":opened["job_id"]}));
        let request=json!({"kind":"database","request":{"operation":"db_edit_entry","source":db,"destination":dest,"expected_source_sha256":info["value"]["source_sha256"],"rowid":"2","text":"edited second 字"}});let blocked=call(&a,json!({"action":"submit","request":request}));let id=blocked["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"failed");assert!(!dest.exists());call(&a,json!({"action":"forget","job_id":id}));call(&a,json!({"action":"database_close","reader_id":opened["reader_id"]}));let end=Instant::now()+Duration::from_secs(5);while call(&a,json!({"action":"database_poll"}))["state"]!="closed"{assert!(Instant::now()<end);thread::sleep(Duration::from_millis(2));}
        let submitted=call(&a,json!({"action":"submit","request":request}));let id=submitted["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"succeeded");let receipt=call(&a,json!({"action":"take","job_id":id}));assert_eq!(receipt["receipt"]["operation"],"db_edit_entry");assert_eq!(receipt["receipt"]["value"]["source_rowid"],"2");assert_eq!(receipt["receipt"]["value"]["output_rowid"],"2");assert_eq!(receipt["receipt"]["value"]["records"],4);call(&a,json!({"action":"forget","job_id":id}));assert_eq!(call(&a,json!({"action":"poll"}))["admission"]["active_operations"],0);a.shutdown().unwrap();
    }
    #[test]fn entry_rename_jobs_preserve_collisions_and_release_admission() {
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();let source=dir.path().join("rows.jsonl");let db=dir.path().join("source.db");let dest=dir.path().join("edited.db");std::fs::write(&source,include_bytes!("../../fixtures/entries.jsonl")).unwrap();
        let submitted=call(&a,json!({"action":"submit","request":{"kind":"database","request":{"operation":"jsonl_to_db","source":source,"destination":db}}}));let id=submitted["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"succeeded");call(&a,json!({"action":"forget","job_id":id}));let opened=call(&a,json!({"action":"database_open","source":db}));assert_eq!(database_wait(&a)["job_state"],"succeeded");let info=call(&a,json!({"action":"database_take","job_id":opened["job_id"]}));call(&a,json!({"action":"database_forget","job_id":opened["job_id"]}));
        let request=json!({"kind":"database","request":{"operation":"db_edit_entry","source":db,"destination":dest,"expected_source_sha256":info["value"]["source_sha256"],"rowid":"2","text":"edited second 字","key":"字"}});let blocked=call(&a,json!({"action":"submit","request":request}));let id=blocked["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"failed");assert!(!dest.exists());call(&a,json!({"action":"forget","job_id":id}));call(&a,json!({"action":"database_close","reader_id":opened["reader_id"]}));let end=Instant::now()+Duration::from_secs(5);while call(&a,json!({"action":"database_poll"}))["state"]!="closed"{assert!(Instant::now()<end);thread::sleep(Duration::from_millis(2));}
        let submitted=call(&a,json!({"action":"submit","request":request}));let id=submitted["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"succeeded");let receipt=call(&a,json!({"action":"take","job_id":id}));assert_eq!(receipt["receipt"]["operation"],"db_edit_entry");assert_eq!(receipt["receipt"]["value"]["source_rowid"],"2");assert_eq!(receipt["receipt"]["value"]["output_rowid"],"2");assert_eq!(receipt["receipt"]["value"]["records"],4);call(&a,json!({"action":"forget","job_id":id}));assert_eq!(call(&a,json!({"action":"poll"}))["admission"]["active_operations"],0);let jsonl=dir.path().join("renamed.jsonl");let submitted=call(&a,json!({"action":"submit","request":{"kind":"database","request":{"operation":"db_to_jsonl","source":dest,"destination":jsonl}}}));let id=submitted["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"succeeded");let values:Vec<Value>=std::fs::read_to_string(jsonl).unwrap().lines().map(|line|serde_json::from_str(line).unwrap()).collect();assert_eq!(values.len(),4);assert_eq!(values[0]["key"],"字");assert_eq!(values[1]["key"],"字");assert_eq!(values[1]["text"],"edited second 字");a.shutdown().unwrap();
    }
    #[test]fn entry_delete_jobs_remove_exact_duplicate_and_release_admission() {
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();let source=dir.path().join("rows.jsonl");let db=dir.path().join("source.db");let dest=dir.path().join("edited.db");std::fs::write(&source,include_bytes!("../../fixtures/entries.jsonl")).unwrap();
        let submitted=call(&a,json!({"action":"submit","request":{"kind":"database","request":{"operation":"jsonl_to_db","source":source,"destination":db}}}));let id=submitted["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"succeeded");call(&a,json!({"action":"forget","job_id":id}));let opened=call(&a,json!({"action":"database_open","source":db}));assert_eq!(database_wait(&a)["job_state"],"succeeded");let info=call(&a,json!({"action":"database_take","job_id":opened["job_id"]}));call(&a,json!({"action":"database_forget","job_id":opened["job_id"]}));
        let request=json!({"kind":"database","request":{"operation":"db_delete_entry","source":db,"destination":dest,"expected_source_sha256":info["value"]["source_sha256"],"rowid":"2"}});let blocked=call(&a,json!({"action":"submit","request":request}));let id=blocked["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"failed");assert!(!dest.exists());call(&a,json!({"action":"forget","job_id":id}));call(&a,json!({"action":"database_close","reader_id":opened["reader_id"]}));let end=Instant::now()+Duration::from_secs(5);while call(&a,json!({"action":"database_poll"}))["state"]!="closed"{assert!(Instant::now()<end);thread::sleep(Duration::from_millis(2));}
        let submitted=call(&a,json!({"action":"submit","request":request}));let id=submitted["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"succeeded");let receipt=call(&a,json!({"action":"take","job_id":id}));assert_eq!(receipt["receipt"]["operation"],"db_delete_entry");assert_eq!(receipt["receipt"]["value"]["source_rowid"],"2");assert!(receipt["receipt"]["value"].get("output_rowid").is_none());assert_eq!(receipt["receipt"]["value"]["records"],3);call(&a,json!({"action":"forget","job_id":id}));assert_eq!(call(&a,json!({"action":"poll"}))["admission"]["active_operations"],0);let jsonl=dir.path().join("renamed.jsonl");let submitted=call(&a,json!({"action":"submit","request":{"kind":"database","request":{"operation":"db_to_jsonl","source":dest,"destination":jsonl}}}));let id=submitted["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"succeeded");let values:Vec<Value>=std::fs::read_to_string(jsonl).unwrap().lines().map(|line|serde_json::from_str(line).unwrap()).collect();assert_eq!(values.len(),3);assert_eq!(values[0]["key"],"字");assert_eq!(values[0]["text"],"<p>First definition</p>");assert_eq!(values[1]["key"],"مرحبا");assert_eq!(values[2]["key"],"Apple");a.shutdown().unwrap();
    }
    #[test]fn entry_add_jobs_append_duplicate_and_release_admission() {
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();let source=dir.path().join("rows.jsonl");let db=dir.path().join("source.db");let dest=dir.path().join("edited.db");std::fs::write(&source,include_bytes!("../../fixtures/entries.jsonl")).unwrap();
        let submitted=call(&a,json!({"action":"submit","request":{"kind":"database","request":{"operation":"jsonl_to_db","source":source,"destination":db}}}));let id=submitted["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"succeeded");call(&a,json!({"action":"forget","job_id":id}));let opened=call(&a,json!({"action":"database_open","source":db}));assert_eq!(database_wait(&a)["job_state"],"succeeded");let info=call(&a,json!({"action":"database_take","job_id":opened["job_id"]}));call(&a,json!({"action":"database_forget","job_id":opened["job_id"]}));
        let request=json!({"kind":"database","request":{"operation":"db_add_entry","source":db,"destination":dest,"expected_source_sha256":info["value"]["source_sha256"],"key":"字","text":"third definition"}});let blocked=call(&a,json!({"action":"submit","request":request}));let id=blocked["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"failed");assert!(!dest.exists());call(&a,json!({"action":"forget","job_id":id}));call(&a,json!({"action":"database_close","reader_id":opened["reader_id"]}));let end=Instant::now()+Duration::from_secs(5);while call(&a,json!({"action":"database_poll"}))["state"]!="closed"{assert!(Instant::now()<end);thread::sleep(Duration::from_millis(2));}
        let submitted=call(&a,json!({"action":"submit","request":request}));let id=submitted["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"succeeded");let receipt=call(&a,json!({"action":"take","job_id":id}));assert_eq!(receipt["receipt"]["operation"],"db_add_entry");assert!(receipt["receipt"]["value"].get("source_rowid").is_none());assert_eq!(receipt["receipt"]["value"]["output_rowid"],"5");assert_eq!(receipt["receipt"]["value"]["records"],5);call(&a,json!({"action":"forget","job_id":id}));assert_eq!(call(&a,json!({"action":"poll"}))["admission"]["active_operations"],0);let jsonl=dir.path().join("renamed.jsonl");let submitted=call(&a,json!({"action":"submit","request":{"kind":"database","request":{"operation":"db_to_jsonl","source":dest,"destination":jsonl}}}));let id=submitted["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"succeeded");let values:Vec<Value>=std::fs::read_to_string(jsonl).unwrap().lines().map(|line|serde_json::from_str(line).unwrap()).collect();assert_eq!(values.len(),5);assert_eq!(values[0]["key"],"字");assert_eq!(values[0]["text"],"<p>First definition</p>");assert_eq!(values[1]["key"],"字");assert_eq!(values[1]["text"],"<p>Second definition, same headword</p>");assert_eq!(values[2]["key"],"مرحبا");assert_eq!(values[3]["key"],"Apple");assert_eq!(values[4]["key"],"字");assert_eq!(values[4]["text"],"third definition");a.shutdown().unwrap();
    }
    #[test]fn metadata_copy_jobs_release_reader_and_preserve_selected_header_edits() {
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();let source=dir.path().join("rows.jsonl");let mdx=dir.path().join("source.mdx");let db=dir.path().join("source.db");let dest=dir.path().join("edited.db");std::fs::write(&source,include_bytes!("../../fixtures/entries.jsonl")).unwrap();
        let publish=|request:Value|{let submitted=call(&a,json!({"action":"submit","request":request}));let id=submitted["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"succeeded");let receipt=call(&a,json!({"action":"take","job_id":id}));call(&a,json!({"action":"forget","job_id":id}));receipt};
        publish(json!({"kind":"dictionary","request":{"operation":"pack_mdx","source":source,"destination":mdx,"encoding":"utf8","metadata":{"title":"original","description":"keep description","stylesheet":"1\n<strong>\n</strong>\n2\n<span style=\"color:#0000ff\">\n</span>\n"}}}));
        publish(json!({"kind":"database","request":{"operation":"mdx_to_db","source":mdx,"destination":db}}));
        let opened=call(&a,json!({"action":"database_open","source":db}));assert_eq!(database_wait(&a)["job_state"],"succeeded");let info=call(&a,json!({"action":"database_take","job_id":opened["job_id"]}));call(&a,json!({"action":"database_forget","job_id":opened["job_id"]}));
        let request=json!({"kind":"database","request":{"operation":"db_edit_metadata","source":db,"destination":dest,"expected_source_sha256":info["value"]["source_sha256"],"edits":{"title":"edited 字","stylesheet":"1\n<strong>\n</strong>\n2\n<span style=\"color:#008000\">\n</span>\n"}}});
        let blocked=call(&a,json!({"action":"submit","request":request}));let id=blocked["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"failed");assert!(!dest.exists());call(&a,json!({"action":"forget","job_id":id}));call(&a,json!({"action":"database_close","reader_id":opened["reader_id"]}));
        let end=Instant::now()+Duration::from_secs(5);while call(&a,json!({"action":"database_poll"}))["state"]!="closed"{assert!(Instant::now()<end);thread::sleep(Duration::from_millis(2));}
        let receipt=publish(request);assert_eq!(receipt["receipt"]["operation"],"db_edit_metadata");assert_eq!(receipt["receipt"]["value"]["dictionary_metadata"]["Title"],"edited 字");assert_eq!(receipt["receipt"]["value"]["dictionary_metadata"]["Description"],"keep description");assert!(receipt["receipt"]["value"]["dictionary_metadata"]["StyleSheet"].as_str().unwrap().contains("#008000"));assert_eq!(receipt["receipt"]["value"]["rows_sha256"],info["value"]["rows_sha256"]);a.shutdown().unwrap();
    }
    #[test]fn definition_search_commands_preserve_pages_and_reader_identity() {
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();let source=dir.path().join("rows.jsonl");let db=dir.path().join("source.db");std::fs::write(&source,include_bytes!("../../fixtures/database-definition.jsonl")).unwrap();
        let submitted=call(&a,json!({"action":"submit","request":{"kind":"database","request":{"operation":"jsonl_to_db","source":source,"destination":db}}}));let id=submitted["job_id"].as_str().unwrap();assert_eq!(wait(&a,id)["state"],"succeeded");call(&a,json!({"action":"forget","job_id":id}));
        let open=call(&a,json!({"action":"database_open","source":db}));assert_eq!(database_wait(&a)["job_state"],"succeeded");call(&a,json!({"action":"database_forget","job_id":open["job_id"]}));
        for (offset,ids) in [(0,vec!["1","2"]),(2,vec!["3"])] {
            let query=call(&a,json!({"action":"database_query","reader_id":open["reader_id"],"request":{"query":"nEeDlE","definition":true,"matching":"unicode16_lower","offset":offset,"limit":2}}));assert_eq!(database_wait(&a)["job_state"],"succeeded");let result=call(&a,json!({"action":"database_take","job_id":query["job_id"]}));let page=&result["value"];assert_eq!(page["total"],3);assert_eq!(page["rows"].as_array().unwrap().iter().map(|r|r["rowid"].as_str().unwrap()).collect::<Vec<_>>(),ids);call(&a,json!({"action":"database_forget","job_id":query["job_id"]}));
        }
        let invalid=a.call_json(&json!({"action":"database_query","reader_id":open["reader_id"],"request":{"query":"needle","definition":true,"wildcard":true,"offset":0,"limit":2}}).to_string());assert!(invalid.is_err());assert_eq!(call(&a,json!({"action":"database_poll"}))["reader_id"],open["reader_id"]);a.shutdown().unwrap();
    }
    fn database_wait(a:&Adapter)->Value {
        let end=Instant::now()+Duration::from_secs(30);
        loop {let s=call(a,json!({"action":"database_poll"}));if !["queued","running"].contains(&s["job_state"].as_str().unwrap()){return s;}assert!(Instant::now()<end);thread::sleep(Duration::from_millis(2));}
    }
    #[test]fn persistent_database_commands_reuse_snapshot_and_release_shared_admission() {
        let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.txt");let db=dir.path().join("dict.db");std::fs::write(&source,include_bytes!("../../fixtures/database-prefix.txt")).unwrap();let a=Adapter::new().unwrap();
        let publication=call(&a,json!({"action":"submit","request":{"kind":"database","request":{"operation":"txt_to_db","source":source,"destination":db,"profile":"canonical_v1"}}}));let job=publication["job_id"].as_str().unwrap();assert_eq!(wait(&a,job)["state"],"succeeded");call(&a,json!({"action":"forget","job_id":job}));
        let opened=call(&a,json!({"action":"database_open","source":db}));let id=opened["reader_id"].as_str().unwrap();assert_eq!(database_wait(&a)["job_state"],"succeeded");let info=call(&a,json!({"action":"database_take","job_id":opened["job_id"]}));assert_eq!(info["operation"],"opened");assert_eq!(info["value"]["records"],8);call(&a,json!({"action":"database_forget","job_id":opened["job_id"]}));
        assert_eq!(call(&a,json!({"action":"poll"}))["admission"]["active_operations"],1);
        let blocked=call(&a,json!({"action":"submit","request":{"kind":"database","request":{"operation":"db_to_txt","source":db,"destination":dir.path().join("blocked.txt")}}}));let blocked_id=blocked["job_id"].as_str().unwrap();assert_eq!(wait(&a,blocked_id)["state"],"failed");assert!(!dir.path().join("blocked.txt").exists());call(&a,json!({"action":"forget","job_id":blocked_id}));
        std::fs::remove_file(&db).unwrap();
        for (offset,expected) in [(0,vec!["1","2"]),(2,vec!["4"])] {
            let job=call(&a,json!({"action":"database_query","reader_id":id,"request":{"query":"app","prefix":true,"offset":offset,"limit":2}}));let s=database_wait(&a);assert_eq!(s["job_state"],"succeeded");assert_eq!(s["latest_progress"]["phase"],"database_page");
            let reply=call(&a,json!({"action":"database_take","job_id":job["job_id"]}));assert_eq!(reply["operation"],"page");assert_eq!(reply["value"]["total"],3);assert_eq!(reply["value"]["source_sha256"],info["value"]["source_sha256"]);assert_eq!(reply["value"]["rows"].as_array().unwrap().iter().map(|r|r["rowid"].as_str().unwrap()).collect::<Vec<_>>(),expected);call(&a,json!({"action":"database_forget","job_id":job["job_id"]}));
        }
        let lower=call(&a,json!({"action":"database_query","reader_id":id,"request":{"query":"aPp","prefix":true,"matching":"unicode16_lower","offset":2,"limit":2}}));assert_eq!(database_wait(&a)["job_state"],"succeeded");let reply=call(&a,json!({"action":"database_take","job_id":lower["job_id"]}));assert_eq!(reply["value"]["total"],4);assert_eq!(reply["value"]["rows"][0]["rowid"],"3");assert_eq!(reply["value"]["rows"][1]["rowid"],"4");call(&a,json!({"action":"database_forget","job_id":lower["job_id"]}));
        let pattern=call(&a,json!({"action":"database_query","reader_id":id,"request":{"query":"a?b","prefix":false,"wildcard":true,"offset":0,"limit":2}}));assert_eq!(database_wait(&a)["job_state"],"succeeded");let reply=call(&a,json!({"action":"database_take","job_id":pattern["job_id"]}));assert_eq!(reply["value"]["total"],2);assert_eq!(reply["value"]["rows"][0]["key"],"a%b");assert_eq!(reply["value"]["rows"][1]["key"],"a_b");call(&a,json!({"action":"database_forget","job_id":pattern["job_id"]}));
        call(&a,json!({"action":"database_close","reader_id":id}));let end=Instant::now()+Duration::from_secs(5);while call(&a,json!({"action":"database_poll"}))["state"]!="closed"{assert!(Instant::now()<end);thread::sleep(Duration::from_millis(2));}
        assert_eq!(call(&a,json!({"action":"poll"}))["admission"]["active_operations"],0);a.shutdown().unwrap();
    }
    #[test]fn persistent_database_boundary_rejects_unknown_fields_and_shutdown_cleans_opening() {
        let a=Adapter::new().unwrap();for request in [json!({"action":"database_open","source":"x","limit":1000}),json!({"action":"database_query","reader_id":"x","request":{"query":null,"prefix":false,"offset":0,"limit":2,"source":"other"}})]{assert_eq!(a.call_json(&request.to_string()).unwrap_err().code,ApiCode::InvalidInput);}
        let dir=tempfile::tempdir().unwrap();let source=dir.path().join("bad.db");std::fs::write(&source,b"bad").unwrap();call(&a,json!({"action":"database_open","source":source}));a.shutdown().unwrap();assert_eq!(a.call_json(r#"{"action":"database_poll"}"#).unwrap_err().code,ApiCode::Closed);
    }
    fn call(a: &Adapter, command: Value) -> Value { a.call_json(&command.to_string()).unwrap() }
    fn wait(a: &Adapter, job: &str) -> Value {
        let start = Instant::now();
        loop {
            let poll = call(a, json!({"action":"poll"}));
            let row = poll["jobs"].as_array().unwrap().iter().find(|r| r["job_id"] == job).unwrap().clone();
            if ["succeeded", "failed", "cancelled"].contains(&row["state"].as_str().unwrap()) { return row; }
            assert!(start.elapsed() < Duration::from_secs(30));
            thread::sleep(Duration::from_millis(5));
        }
    }
    fn submit(a: &Adapter, source: &std::path::Path, destination: &std::path::Path) -> String {
        call(a, json!({"action":"submit","request":{"kind":"dictionary","request":{
            "operation":"pack_mdx","source":source,"destination":destination,"encoding":"utf8",
            "metadata":{"title":"字 / مرحبا","description":"adapter fixture"}
        }}}))["job_id"].as_str().unwrap().into()
    }
    #[test]
    fn database_prefix_queries_page_through_shared_jobs() {
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();
        let source=dir.path().join("prefix.txt");let db=dir.path().join("prefix.db");
        std::fs::write(&source,include_bytes!("../../fixtures/database-prefix.txt")).unwrap();
        let job=call(&a,json!({"action":"submit","request":{"kind":"database","request":{"operation":"txt_to_db","source":source,"destination":db,"profile":"canonical_v1"}}}))["job_id"].as_str().unwrap().to_owned();
        assert_eq!(wait(&a,&job)["state"],"succeeded");call(&a,json!({"action":"take","job_id":job}));call(&a,json!({"action":"forget","job_id":job}));
        let before=std::fs::read(&db).unwrap();let mut digest=Value::Null;
        for (prefix,query,offset,total,rowids) in [(true,"app",0,3,vec!["1","2"]),(true,"app",2,3,vec!["4"]),(false,"app",0,0,vec![]),(true,"a%",0,1,vec!["5"]),(true,"字",0,1,vec!["7"]),(true,"مر",0,1,vec!["8"])] {
            let job=call(&a,json!({"action":"submit","request":{"kind":"database_page","request":{"source":db,"query":query,"prefix":prefix,"offset":offset,"limit":2,"expected_source_sha256":digest}}}))["job_id"].as_str().unwrap().to_owned();
            let terminal=wait(&a,&job);assert_eq!(terminal["state"],"succeeded","{terminal}");
            let page=call(&a,json!({"action":"take","job_id":job}));assert_eq!(page["receipt"]["total"],total);
            let actual:Vec<_>=page["receipt"]["rows"].as_array().unwrap().iter().map(|r|r["rowid"].as_str().unwrap()).collect();assert_eq!(actual,rowids);
            digest=page["receipt"]["source_sha256"].clone();call(&a,json!({"action":"forget","job_id":job}));
        }
        assert_eq!(std::fs::read(db).unwrap(),before);a.shutdown().unwrap();
    }
    #[test]
    fn database_failure_publications_preserve_files_and_allow_recovery() {
        let adapter = Adapter::new().unwrap();
        let dir = tempfile::tempdir().unwrap();
        let source = dir.path().join("entries.jsonl");
        let mdx = dir.path().join("source.mdx");
        let db = dir.path().join("source.db");
        std::fs::write(&source, "{\"key\":\"字\",\"text\":\"first\"}\n{\"key\":\"字\",\"text\":\"second\"}\n").unwrap();
        let initial = std::fs::read(&source).unwrap();
        let job = submit(&adapter, &source, &mdx);
        assert_eq!(wait(&adapter, &job)["state"], "succeeded");
        assert_eq!(call(&adapter, json!({"action":"take","job_id":job}))["receipt"]["records"], 2);
        call(&adapter, json!({"action":"forget","job_id":job}));

        // Every request uses the desktop's shared worker and result lifecycle.
        let publish = |operation: &str, input: &std::path::Path, output: &std::path::Path, expected: Option<&str>| {
            let job = call(&adapter, json!({"action":"submit","request":{"kind":"database","request":{
                "operation":operation,"source":input,"destination":output
            }}}))["job_id"].as_str().unwrap().to_owned();
            let terminal = wait(&adapter, &job);
            match expected {
                Some(code) => {
                    assert_eq!(terminal["state"], "failed", "{terminal}");
                    assert_eq!(terminal["error"]["code"], code, "{terminal}");
                    assert!(call(&adapter, json!({"action":"take","job_id":job})).is_null());
                }
                None => {
                    assert_eq!(terminal["state"], "succeeded", "{terminal}");
                    let receipt = call(&adapter, json!({"action":"take","job_id":job}));
                    assert_eq!(receipt["receipt"]["value"]["records"], 2);
                    assert!(call(&adapter, json!({"action":"take","job_id":job})).is_null());
                }
            }
            call(&adapter, json!({"action":"forget","job_id":job}));
            assert!(call(&adapter, json!({"action":"poll"}))["jobs"].as_array().unwrap().is_empty());
        };
        publish("mdx_to_db", &mdx, &db, None);
        let mdx_before = std::fs::read(&mdx).unwrap();
        let db_before = std::fs::read(&db).unwrap();
        let sentinel_db = dir.path().join("existing.db");
        let sentinel_mdx = dir.path().join("existing.mdx");
        std::fs::write(&sentinel_db, b"existing database sentinel").unwrap();
        std::fs::write(&sentinel_mdx, b"existing dictionary sentinel").unwrap();
        publish("mdx_to_db", &mdx, &sentinel_db, Some("destination_exists"));
        publish("db_to_mdx", &db, &sentinel_mdx, Some("destination_exists"));

        let bad_mdx = dir.path().join("bad-checksum.mdx");
        let mut damaged = mdx_before.clone();
        let length = u32::from_be_bytes(damaged[..4].try_into().unwrap()) as usize;
        damaged[4 + length] ^= 1;
        std::fs::write(&bad_mdx, &damaged).unwrap();
        let bad_db = dir.path().join("invalid.db");
        std::fs::write(&bad_db, [0u8; 100]).unwrap();
        let absent_db = dir.path().join("must-not-exist.db");
        let absent_mdx = dir.path().join("must-not-exist.mdx");
        let before_failure: BTreeSet<_> = std::fs::read_dir(dir.path()).unwrap()
            .map(|entry| entry.unwrap().file_name()).collect();
        publish("mdx_to_db", &bad_mdx, &absent_db, Some("integrity"));
        publish("db_to_mdx", &bad_db, &absent_mdx, Some("invalid_input"));
        assert!(!absent_db.exists() && !absent_mdx.exists());
        let after_failure: BTreeSet<_> = std::fs::read_dir(dir.path()).unwrap()
            .map(|entry| entry.unwrap().file_name()).collect();
        assert_eq!(after_failure, before_failure, "Failed jobs left staging artifacts");

        // Reuse the failed destinations: failure must release leases and handles.
        publish("mdx_to_db", &mdx, &absent_db, None);
        publish("db_to_mdx", &db, &absent_mdx, None);
        assert_eq!(std::fs::read(source).unwrap(), initial);
        assert_eq!(std::fs::read(mdx).unwrap(), mdx_before);
        assert_eq!(std::fs::read(db).unwrap(), db_before);
        assert_eq!(std::fs::read(bad_mdx).unwrap(), damaged);
        assert_eq!(std::fs::read(bad_db).unwrap(), [0u8; 100]);
        assert_eq!(std::fs::read(sentinel_db).unwrap(), b"existing database sentinel");
        assert_eq!(std::fs::read(sentinel_mdx).unwrap(), b"existing dictionary sentinel");
        adapter.shutdown().unwrap();
    }
    #[test]
    fn database_roundtrip_uses_retained_shared_publication_jobs() {
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();let source=dir.path().join("in.txt");let db=dir.path().join("out.db");let out=dir.path().join("out.txt");
        let content="字\nfirst\n\nline\n</>\n字\nsecond\n</>\n";std::fs::write(&source,content).unwrap();
        for request in [json!({"operation":"txt_to_db","source":source,"destination":db,"profile":"canonical_v1"}),json!({"operation":"db_to_txt","source":db,"destination":out})] {
            let job=call(&a,json!({"action":"submit","request":{"kind":"database","request":request}}))["job_id"].as_str().unwrap().to_owned();
            let terminal=wait(&a,&job);assert_eq!(terminal["state"],"succeeded","{terminal}");
            let result=call(&a,json!({"action":"take","job_id":job}));assert_eq!(result["kind"],"database");assert_eq!(result["receipt"]["value"]["records"],2);
            call(&a,json!({"action":"forget","job_id":job}));
        }
        assert_eq!(std::fs::read_to_string(&out).unwrap(),content);assert_eq!(std::fs::read_to_string(&source).unwrap(),content);
        let before=std::fs::read(&db).unwrap();let mut digest=Value::Null;
        for (offset,query) in [(0,Value::Null),(1,json!("字"))] {
            let job=call(&a,json!({"action":"submit","request":{"kind":"database_page","request":{"source":db,"query":query,"offset":offset,"limit":1,"expected_source_sha256":digest}}}))["job_id"].as_str().unwrap().to_owned();
            let result=wait(&a,&job);assert_eq!(result["state"],"succeeded","{result}");let page=call(&a,json!({"action":"take","job_id":job}));assert_eq!(page["kind"],"database_page");assert_eq!(page["receipt"]["total"],2);assert_eq!(page["receipt"]["rows"][0]["rowid"],(offset+1).to_string());digest=page["receipt"]["source_sha256"].clone();
            call(&a,json!({"action":"forget","job_id":job}));
        }
        assert_eq!(std::fs::read(&db).unwrap(),before);a.shutdown().unwrap();
    }
    #[test]
    fn mdx_database_import_routes_verified_metadata_through_shared_jobs() {
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();let source=dir.path().join("rows.jsonl");let mdx=dir.path().join("source.mdx");let db=dir.path().join("result.db");
        std::fs::write(&source,"{\"key\":\"字\",\"text\":\"first\"}\n{\"key\":\"字\",\"text\":\"second\"}\n").unwrap();
        let packed=submit(&a,&source,&mdx);assert_eq!(wait(&a,&packed)["state"],"succeeded");call(&a,json!({"action":"forget","job_id":packed}));
        let job=call(&a,json!({"action":"submit","request":{"kind":"database","request":{"operation":"mdx_to_db","source":mdx,"destination":db}}}))["job_id"].as_str().unwrap().to_owned();
        let result=wait(&a,&job);assert_eq!(result["state"],"succeeded","{result}");let receipt=call(&a,json!({"action":"take","job_id":job}));assert_eq!(receipt["receipt"]["operation"],"mdx_to_db");assert_eq!(receipt["receipt"]["value"]["records"],2);assert_eq!(receipt["receipt"]["value"]["dictionary_metadata"]["Title"],"字 / مرحبا");call(&a,json!({"action":"forget","job_id":job}));
        let rebuilt=dir.path().join("rebuilt.mdx");let job=call(&a,json!({"action":"submit","request":{"kind":"database","request":{"operation":"db_to_mdx","source":db,"destination":rebuilt}}}))["job_id"].as_str().unwrap().to_owned();let status=wait(&a,&job);assert_eq!(status["state"],"succeeded","{status}");let receipt=call(&a,json!({"action":"take","job_id":job}));assert_eq!(receipt["receipt"]["operation"],"db_to_mdx");assert_eq!(receipt["receipt"]["value"]["records"],2);assert_eq!(receipt["receipt"]["value"]["dictionary_metadata"]["Title"],"字 / مرحبا");a.shutdown().unwrap();
    }
    #[test]
    fn metadata_copy_preserves_data_sections_duplicates_and_refuses_invalid_styles() {
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();
        let source=dir.path().join("entries.jsonl");let original=dir.path().join("original.mdx");
        std::fs::write(&source,"{\"key\":\"字\",\"text\":\"first\"}\n{\"key\":\"字\",\"text\":\"`1`blue\"}\n").unwrap();
        let job=call(&a,json!({"action":"submit","request":{"kind":"dictionary","request":{"operation":"pack_mdx","source":source,"destination":original,"encoding":"utf16","metadata":{"title":"Original","description":"preserve me","stylesheet":"1\n<b>\n</b>\n"}}}}))["job_id"].as_str().unwrap().to_owned();
        assert_eq!(wait(&a,&job)["state"],"succeeded");call(&a,json!({"action":"forget","job_id":job}));
        let before=std::fs::read(&original).unwrap();let edited=dir.path().join("edited.mdx");
        let request=json!({"kind":"metadata","request":{"source":original,"destination":edited,"kind":"mdx","edits":{"title":"字 / مرحبا","stylesheet":"1\n<span style=\"color:blue\">\n</span>\n"}}});
        let job=call(&a,json!({"action":"submit","request":request}))["job_id"].as_str().unwrap().to_owned();
        let result=wait(&a,&job);assert_eq!(result["state"],"succeeded","{result}");
        let receipt=call(&a,json!({"action":"take","job_id":job}));
        assert_eq!(receipt["receipt"]["records"],2);assert_eq!(receipt["receipt"]["header"]["attributes"]["Title"],"字 / مرحبا");
        assert_eq!(receipt["receipt"]["header"]["attributes"]["Description"],"preserve me");
        let after=std::fs::read(&edited).unwrap();
        fn data(bytes:&[u8])->&[u8] {let n=u32::from_be_bytes(bytes[..4].try_into().unwrap()) as usize;&bytes[8+n..]}
        assert_eq!(data(&before),data(&after));assert_eq!(std::fs::read(&original).unwrap(),before);
        call(&a,json!({"action":"forget","job_id":job}));
        let job=call(&a,json!({"action":"submit","request":request}))["job_id"].as_str().unwrap().to_owned();
        assert_eq!(wait(&a,&job)["error"]["code"],"destination_exists");assert_eq!(std::fs::read(&edited).unwrap(),after);
        call(&a,json!({"action":"forget","job_id":job}));
        let invalid=dir.path().join("invalid.mdx");
        let job=call(&a,json!({"action":"submit","request":{"kind":"metadata","request":{"source":original,"destination":invalid,"kind":"mdx","edits":{"stylesheet":""}}}}))["job_id"].as_str().unwrap().to_owned();
        assert_eq!(wait(&a,&job)["error"]["code"],"invalid_input");assert!(!invalid.exists());
        a.shutdown().unwrap();
    }
    #[test]
    fn selected_redirect_command_runs_in_the_open_indexed_session() {
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();let source=dir.path().join("entries.jsonl");let mdx=dir.path().join("dict.mdx");let artifact=dir.path().join("dict.idx");
        std::fs::write(&source,"{\"key\":\"alias\",\"text\":\"@@@LINK=target\"}\n{\"key\":\"target\",\"text\":\"definition\"}\n").unwrap();
        let id=submit(&a,&source,&mdx);assert_eq!(wait(&a,&id)["state"],"succeeded");call(&a,json!({"action":"forget","job_id":id}));
        let id=call(&a,json!({"action":"submit","request":{"kind":"index","request":{"source":mdx,"destination":artifact,"kind":"mdx","policy":"raw_exact"}}}))["job_id"].as_str().unwrap().to_owned();
        assert_eq!(wait(&a,&id)["state"],"succeeded");call(&a,json!({"action":"forget","job_id":id}));
        fn finish(a:&Adapter,sid:&str,id:&str) {
            let start=Instant::now();loop {let p=call(a,json!({"action":"poll"}));let s=p["sessions"].as_array().unwrap().iter().find(|s|s["session"]["session_id"]==sid).unwrap();let row=s["jobs"].as_array().unwrap().iter().find(|j|j["job_id"]==id).unwrap();
                if ["succeeded","failed","cancelled"].contains(&row["state"].as_str().unwrap()) {assert_eq!(row["state"],"succeeded","{row}");return;}assert!(start.elapsed()<Duration::from_secs(30));thread::sleep(Duration::from_millis(5));
            }
        }
        let opened=call(&a,json!({"action":"open_reader","request":{"source":mdx,"artifact":artifact,"kind":"mdx","policy":"raw_exact"}}));let sid=opened["session_id"].as_str().unwrap();let id=opened["job_id"].as_str().unwrap();finish(&a,sid,id);
        call(&a,json!({"action":"session_take","session_id":sid,"job_id":id}));call(&a,json!({"action":"session_forget","session_id":sid,"job_id":id}));
        let id=call(&a,json!({"action":"resolve","session_id":sid,"request":{"query":"alias","ordinal":0}}))["job_id"].as_str().unwrap().to_owned();finish(&a,sid,&id);
        let result=call(&a,json!({"action":"session_take","session_id":sid,"job_id":id}));assert_eq!(result["operation"],"resolved");assert_eq!(result["value"]["results"][0]["row"]["text"],"definition");assert_eq!(result["value"]["results"][0]["chain"][0]["target"],"target");
        assert!(call(&a,json!({"action":"session_take","session_id":sid,"job_id":id})).is_null());call(&a,json!({"action":"session_forget","session_id":sid,"job_id":id}));a.shutdown().unwrap();
    }
    #[cfg(unix)]#[test]
    fn python_plugin_command_publishes_one_bundle_and_transfers_receipt_once() {
        let python=std::env::var_os("STUDIO_TEST_PYTHON").map(std::path::PathBuf::from).unwrap_or_else(||{
            let result=std::process::Command::new("python3").args(["-c","import sys;print(sys.executable)"]).output().unwrap();assert!(result.status.success());std::path::PathBuf::from(String::from_utf8(result.stdout).unwrap().trim())
        });
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.txt");let plugin=dir.path().join("plugin.py");let destination=dir.path().join("result");
        std::fs::write(&source,include_bytes!("../../fixtures/build-source.txt")).unwrap();std::fs::write(&plugin,include_bytes!("../../fixtures/noisy_plugin.py")).unwrap();
        let mut request=json!({"kind":"python_plugin","request":{"python":python,"plugin":plugin,"source":source,"class_name":"NoisyPlugin","destination":destination,"trusted":false}});
        assert_eq!(a.call_json(&json!({"action":"submit","request":request}).to_string()).unwrap_err().code,ApiCode::InvalidInput);
        request["request"]["trusted"]=json!(true);let id=call(&a,json!({"action":"submit","request":request}))["job_id"].as_str().unwrap().to_owned();
        let state=wait(&a,&id);assert_eq!(state["state"],"succeeded","{state}");let receipt=call(&a,json!({"action":"take","job_id":id}));assert_eq!(receipt["receipt"]["records"],5);assert!(receipt["receipt"]["stdout_tail"].as_str().unwrap().contains("Native stdout write"));
        assert_eq!(std::fs::read(destination.join("output.txt")).unwrap(),std::fs::read(&source).unwrap());assert!(call(&a,json!({"action":"take","job_id":id})).is_null());call(&a,json!({"action":"forget","job_id":id}));a.shutdown().unwrap();
    }
    #[cfg(unix)]#[test]
    fn plugin_inspection_routes_through_jobs_and_transfers_source_bound_catalog_once() {
        let python=std::env::var_os("STUDIO_TEST_PYTHON").map(std::path::PathBuf::from).unwrap_or_else(||{
            let result=std::process::Command::new("python3").args(["-c","import sys;print(sys.executable)"]).output().unwrap();assert!(result.status.success());std::path::PathBuf::from(String::from_utf8(result.stdout).unwrap().trim())
        });
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();let plugin=dir.path().join("plugin.py");let destination=dir.path().join("inspection");
        std::fs::write(&plugin,include_bytes!("../../fixtures/noisy_plugin.py")).unwrap();
        let mut request=json!({"kind":"python_inspection","request":{"python":python,"plugin":plugin,"destination":destination,"trusted":false}});
        assert_eq!(a.call_json(&json!({"action":"submit","request":request}).to_string()).unwrap_err().code,ApiCode::InvalidInput);
        request["request"]["trusted"]=json!(true);
        let id=call(&a,json!({"action":"submit","request":request}))["job_id"].as_str().unwrap().to_owned();
        let state=wait(&a,&id);assert_eq!(state["state"],"succeeded","{state}");assert_eq!(state["operation"],"python_inspection");
        let receipt=call(&a,json!({"action":"take","job_id":id}));assert_eq!(receipt["kind"],"python_inspection");assert_eq!(receipt["receipt"]["catalog"]["classes"].as_array().unwrap().len(),4);assert_eq!(receipt["receipt"]["plugin_sha256"].as_str().unwrap().len(),64);
        assert!(destination.join("catalog.json").is_file());assert!(!destination.join("output.txt").exists());assert!(call(&a,json!({"action":"take","job_id":id})).is_null());
        call(&a,json!({"action":"forget","job_id":id}));a.shutdown().unwrap();
    }
    #[cfg(unix)]#[test]
    fn folder_inspection_requires_trust_and_retains_file_errors_in_one_receipt() {
        let python=std::env::var_os("STUDIO_TEST_PYTHON").map(std::path::PathBuf::from).unwrap_or_else(||{
            let out=std::process::Command::new("python3").args(["-c","import sys;print(sys.executable)"]).output().unwrap();assert!(out.status.success());std::path::PathBuf::from(String::from_utf8(out.stdout).unwrap().trim())
        });
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();let folder=dir.path().join("plugins");std::fs::create_dir(&folder).unwrap();let destination=dir.path().join("scan");
        std::fs::write(folder.join("options.py"),include_bytes!("../../fixtures/noisy_plugin.py")).unwrap();std::fs::write(folder.join("broken.py"),"raise RuntimeError('folder adapter fixture failure')").unwrap();
        let mut request=json!({"kind":"python_folder","request":{"python":python,"folder":folder,"destination":destination,"trusted":false}});
        assert_eq!(a.call_json(&json!({"action":"submit","request":request}).to_string()).unwrap_err().code,ApiCode::InvalidInput);
        request["request"]["trusted"]=json!(true);let id=call(&a,json!({"action":"submit","request":request}))["job_id"].as_str().unwrap().to_owned();let state=wait(&a,&id);assert_eq!(state["state"],"succeeded","{state}");assert_eq!(state["operation"],"python_folder");
        let result=call(&a,json!({"action":"take","job_id":id}));assert_eq!(result["kind"],"python_folder");assert_eq!(result["receipt"]["entries"].as_array().unwrap().len(),2);assert!(result["receipt"]["entries"][0]["error"]["message"].as_str().unwrap().contains("folder adapter fixture failure"));assert_eq!(result["receipt"]["entries"][1]["catalog"]["classes"].as_array().unwrap().len(),4);
        assert!(destination.join("catalog.json").exists());assert!(call(&a,json!({"action":"take","job_id":id})).is_null());call(&a,json!({"action":"forget","job_id":id}));a.shutdown().unwrap();
    }
    #[cfg(unix)]#[test]
    fn simple_plugin_import_is_a_read_only_job_without_a_destination() {
        let python=std::env::var_os("STUDIO_TEST_PYTHON").map(std::path::PathBuf::from).unwrap_or_else(||{let out=std::process::Command::new("python3").args(["-c","import sys;print(sys.executable)"]).output().unwrap();assert!(out.status.success());std::path::PathBuf::from(String::from_utf8(out.stdout).unwrap().trim())});
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();let plugin=dir.path().join("options.py");std::fs::write(&plugin,include_bytes!("../../fixtures/plugin-folder/options.py")).unwrap();
        let mut request=json!({"kind":"python_probe","request":{"python":python,"plugin":plugin,"trusted":false}});
        assert_eq!(a.call_json(&json!({"action":"submit","request":request}).to_string()).unwrap_err().code,ApiCode::InvalidInput);
        request["request"]["trusted"]=json!(true);let id=call(&a,json!({"action":"submit","request":request}))["job_id"].as_str().unwrap().to_owned();let state=wait(&a,&id);assert_eq!(state["state"],"succeeded","{state}");assert_eq!(state["operation"],"python_probe");
        let result=call(&a,json!({"action":"take","job_id":id}));assert_eq!(result["kind"],"python_probe");assert_eq!(result["receipt"]["catalog"]["classes"][0]["class_name"],"OptionsPlugin");assert!(result["receipt"].get("destination").is_none());assert_eq!(std::fs::read_dir(dir.path()).unwrap().count(),1);assert!(call(&a,json!({"action":"take","job_id":id})).is_null());call(&a,json!({"action":"forget","job_id":id}));a.shutdown().unwrap();
    }
    #[test]
    fn stylesheet_export_uses_verified_reader_header_and_publishes_exact_utf8() {
        for encoding in ["utf8","utf16"] {
            let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();let source=dir.path().join("entries.jsonl");let mdx=dir.path().join("styles.mdx");let artifact=dir.path().join("styles.idx");let destination=dir.path().join("styles.txt");
            let style="1\n<span title=\"字 & العربية\">\n</span>\n";
            std::fs::write(&source,"{\"key\":\"marker\",\"text\":\"`1`blue\"}\n").unwrap();
            let id=call(&a,json!({"action":"submit","request":{"kind":"dictionary","request":{"operation":"pack_mdx","source":source,"destination":mdx,"encoding":encoding,"metadata":{"title":"Style export","description":"fixture","stylesheet":style}}}}))["job_id"].as_str().unwrap().to_owned();
            assert_eq!(wait(&a,&id)["state"],"succeeded");call(&a,json!({"action":"forget","job_id":id}));
            let id=call(&a,json!({"action":"submit","request":{"kind":"index","request":{"source":mdx,"destination":artifact,"kind":"mdx","policy":"raw_exact"}}}))["job_id"].as_str().unwrap().to_owned();
            assert_eq!(wait(&a,&id)["state"],"succeeded");call(&a,json!({"action":"forget","job_id":id}));
            let opened=call(&a,json!({"action":"open_reader","request":{"source":mdx,"artifact":artifact,"kind":"mdx","policy":"raw_exact"}}));let sid=opened["session_id"].as_str().unwrap();let open_id=opened["job_id"].as_str().unwrap();let start=Instant::now();
            loop {let poll=call(&a,json!({"action":"poll"}));let row=poll["sessions"][0]["jobs"].as_array().unwrap().iter().find(|j|j["job_id"]==open_id).unwrap();if row["state"]=="succeeded"{break;}assert_ne!(row["state"],"failed","{poll}");assert!(start.elapsed()<Duration::from_secs(30));thread::sleep(Duration::from_millis(5));}
            call(&a,json!({"action":"session_take","session_id":sid,"job_id":open_id}));call(&a,json!({"action":"session_forget","session_id":sid,"job_id":open_id}));
            assert_eq!(a.call_json(&json!({"action":"export_stylesheet","session_id":sid,"destination":destination}).to_string()).unwrap_err().code,ApiCode::NotReady);
            let info=call(&a,json!({"action":"reader_details","session_id":sid}));assert_eq!(info["attributes"]["StyleSheet"],style);
            // The export belongs to the verified cached snapshot, even when the
            // public path changes afterwards. It does not re-read another file.
            std::fs::write(&mdx,b"replacement public file").unwrap();
            let id=call(&a,json!({"action":"export_stylesheet","session_id":sid,"destination":destination}))["job_id"].as_str().unwrap().to_owned();let state=wait(&a,&id);assert_eq!(state["state"],"succeeded","{state}");
            let receipt=call(&a,json!({"action":"take","job_id":id}));assert_eq!(receipt["receipt"]["snapshot_source_sha256"],info["source_sha256"]);assert_eq!(std::fs::read(&destination).unwrap(),style.as_bytes());assert!(call(&a,json!({"action":"take","job_id":id})).is_null());call(&a,json!({"action":"forget","job_id":id}));
            let id=call(&a,json!({"action":"export_stylesheet","session_id":sid,"destination":destination}))["job_id"].as_str().unwrap().to_owned();assert_eq!(wait(&a,&id)["error"]["code"],"destination_exists");assert_eq!(std::fs::read(&destination).unwrap(),style.as_bytes());a.shutdown().unwrap();
        }
    }
    #[test]
    fn boundary_refuses_unknown_fields_profiles_and_oversized_commands() {
        let a = Adapter::new().unwrap();
        for json in [r#"{"action":"submit","request":{"kind":"stylesheet","request":{"destination":"made-up.txt","stylesheet":"x","source_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}}"#, r#"{"action":"poll","surprise":true}"#, r#"{"action":"capabilities","surprise":true}"#, r#"{"action":"submit","request":{"kind":"metadata","request":{}}}"#, r#"{"action":"cancel","job_id":"../escape"}"#] {
            assert_eq!(a.call_json(json).expect_err(json).code, ApiCode::InvalidInput);
        }
        assert!(a.call_json(r#"{"action":"poll"}"#).is_ok());
        assert!(a.call_json(r#"{"action":"capabilities"}"#).is_ok());
        assert_eq!(a.call_json(&" ".repeat(MAX_COMMAND_BYTES + 1)).unwrap_err().code, ApiCode::InvalidInput);
        a.shutdown().unwrap();
        assert_eq!(a.call(Command::Poll {}).unwrap_err().code, ApiCode::Closed);
    }
    #[test]
    fn real_publication_one_transfer_no_clobber_and_late_cancel() {
        let a = Adapter::new().unwrap(); let dir = tempfile::tempdir().unwrap();
        let source = dir.path().join("entries.jsonl"); let output = dir.path().join("out.mdx");
        std::fs::write(&source, "{\"key\":\"字\",\"text\":\"one\"}\n{\"key\":\"字\",\"text\":\"two\"}\n{\"key\":\"مرحبا\",\"text\":\"hello\"}\n").unwrap();
        let job = submit(&a, &source, &output); assert_eq!(wait(&a, &job)["state"], "succeeded");
        let receipt = call(&a, json!({"action":"take","job_id":job}));
        assert_eq!(receipt["receipt"]["records"], 3);
        assert!(call(&a, json!({"action":"take","job_id":job})).is_null());
        assert_eq!(call(&a, json!({"action":"cancel","job_id":job})), "already_finished");
        let before = std::fs::read(&output).unwrap();
        let duplicate = submit(&a, &source, &output);
        let failed = wait(&a, &duplicate); assert_eq!(failed["state"], "failed");
        assert_eq!(failed["error"]["code"], "destination_exists");
        assert_eq!(std::fs::read(&output).unwrap(), before);
        call(&a, json!({"action":"forget","job_id":job}));
        call(&a, json!({"action":"forget","job_id":duplicate}));
        assert!(call(&a, json!({"action":"poll"}))["jobs"].as_array().unwrap().is_empty());
        a.shutdown().unwrap();
    }
    #[test]
    fn failed_reader_close_releases_handles_before_shutdown() {
        let a = Adapter::new().unwrap(); let dir = tempfile::tempdir().unwrap();
        let opened = call(&a, json!({"action":"open_reader","request":{
            "source":dir.path().join("absent.mdx"),"artifact":dir.path().join("absent.idx"),"kind":"mdx","policy":"raw_exact"
        }}));
        let sid = opened["session_id"].as_str().unwrap();
        call(&a, json!({"action":"close_reader","session_id":sid}));
        let start = Instant::now();
        loop {
            match a.call_json(&json!({"action":"release_reader","session_id":sid}).to_string()) {
                Ok(_) => break,
                Err(e) => { assert_eq!(e.code, ApiCode::StillRunning); assert!(start.elapsed() < Duration::from_secs(30)); thread::sleep(Duration::from_millis(5)); }
            }
        }
        let poll = call(&a, json!({"action":"poll"}));
        assert_eq!(poll["admission"]["active_operations"], 0);
        assert_eq!(poll["readers"]["retained_session_handles"], 0);
        a.shutdown().unwrap(); a.shutdown().unwrap();
    }
    #[test]
    fn indexed_duplicate_pages_share_admission_with_exclusive_packing() {
        let a = Adapter::new().unwrap(); let dir = tempfile::tempdir().unwrap();
        let source = dir.path().join("source.jsonl"); let mdx = dir.path().join("reader.mdx");
        let index = dir.path().join("reader.idx");
        std::fs::write(&source, "{\"key\":\"字\",\"text\":\"first\"}\n{\"key\":\"字\",\"text\":\"second\"}\n").unwrap();
        let pack = submit(&a, &source, &mdx); assert_eq!(wait(&a, &pack)["state"], "succeeded");
        call(&a, json!({"action":"forget","job_id":pack}));
        let built = call(&a, json!({"action":"submit","request":{"kind":"index","request":{
            "source":mdx,"destination":index,"kind":"mdx","policy":"raw_exact"
        }}}));
        let jid = built["job_id"].as_str().unwrap(); assert_eq!(wait(&a, jid)["state"], "succeeded");
        call(&a, json!({"action":"forget","job_id":jid}));
        let opened = call(&a, json!({"action":"open_reader","request":{
            "source":mdx,"artifact":index,"kind":"mdx","policy":"raw_exact"
        }}));
        let sid = opened["session_id"].as_str().unwrap();
        let start = Instant::now();
        loop {
            let p = call(&a, json!({"action":"poll"}));
            let state = &p["sessions"][0]["session"]["state"];
            if state == "ready" { break; }
            assert!(state != "failed", "{p}"); assert!(start.elapsed() < Duration::from_secs(30));
            thread::sleep(Duration::from_millis(5));
        }
        call(&a, json!({"action":"session_take","session_id":sid,"job_id":opened["job_id"]}));
        call(&a, json!({"action":"session_forget","session_id":sid,"job_id":opened["job_id"]}));
        let info=call(&a,json!({"action":"reader_details","session_id":sid}));
        assert_eq!(info["attributes"]["Title"],"字 / مرحبا");
        assert_eq!(info["manifest"]["records"],2);
        let no_style=dir.path().join("no-style.txt");assert_eq!(a.call_json(&json!({"action":"export_stylesheet","session_id":sid,"destination":no_style}).to_string()).unwrap_err().code,ApiCode::NotFound);assert!(!no_style.exists());
        let page = call(&a, json!({"action":"page","session_id":sid,"request":{"query":"字","offset":0,"limit":1}}));
        let page_id = page["job_id"].as_str().unwrap(); let start = Instant::now();
        loop {
            let p = call(&a, json!({"action":"poll"}));
            let row = p["sessions"][0]["jobs"].as_array().unwrap().iter().find(|j|j["job_id"] == page_id).unwrap();
            if row["state"] == "succeeded" { break; }
            assert!(row["state"] != "failed", "{p}"); assert!(start.elapsed() < Duration::from_secs(30)); thread::sleep(Duration::from_millis(5));
        }
        let result = call(&a, json!({"action":"session_take","session_id":sid,"job_id":page_id}));
        assert_eq!(result["operation"], "page"); assert_eq!(result["value"]["total"], 2);
        assert_eq!(result["value"]["rows"].as_array().unwrap().len(), 1);
        assert_eq!(result["value"]["next_offset"], 1);
        assert!(call(&a, json!({"action":"session_take","session_id":sid,"job_id":page_id})).is_null());
        call(&a, json!({"action":"session_forget","session_id":sid,"job_id":page_id}));
        let target = dir.path().join("blocked.mdx");
        let blocked = call(&a, json!({"action":"submit","request":{"kind":"cc_packing","request":{
            "source":source,"destination":target,"encoding":"utf8","metadata":{"title":"blocked","description":""}
        }}}));
        let refused = wait(&a, blocked["job_id"].as_str().unwrap());
        assert_eq!(refused["state"], "failed"); assert_eq!(refused["error"]["detail"], "resource_admission");
        assert!(!target.exists());
        let export=dir.path().join("blocked-export.txt");
        let blocked=call(&a,json!({"action":"submit","request":{"kind":"large_export","request":{"source":mdx,"destination":export,"format":"txt"}}}));
        assert_eq!(wait(&a,blocked["job_id"].as_str().unwrap())["error"]["detail"],"resource_admission");assert!(!export.exists());
        let metadata_output=dir.path().join("blocked-metadata.mdx");
        let blocked=call(&a,json!({"action":"submit","request":{"kind":"metadata","request":{"source":mdx,"destination":metadata_output,"kind":"mdx","edits":{"title":"blocked"}}}}));
        assert_eq!(wait(&a,blocked["job_id"].as_str().unwrap())["error"]["detail"],"resource_admission");assert!(!metadata_output.exists());
        let plugin_destination=dir.path().join("blocked-plugin");
        let blocked=call(&a,json!({"action":"submit","request":{"kind":"python_plugin","request":{"python":source,"plugin":source,"source":source,"class_name":"NoisyPlugin","destination":plugin_destination,"trusted":true}}}));
        assert_eq!(wait(&a,blocked["job_id"].as_str().unwrap())["error"]["detail"],"resource_admission");assert!(!plugin_destination.exists());
        a.shutdown().unwrap();
    }
    #[cfg(unix)]
    #[test]
    fn gui_export_and_resource_extraction_routes_roundtrip_and_refuse_overwrite() {
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();
        let source=dir.path().join("source.jsonl");let mdx=dir.path().join("dictionary.mdx");
        let rows=[json!({"key":"apple","text":"<p>A fruit.</p>"}),json!({"key":"字","text":"first\n"}),json!({"key":"字","text":"second"}),json!({"key":"مرحبا","text":"أهلاً"}),json!({"key":"empty","text":""})];
        std::fs::write(&source,rows.iter().map(|r|r.to_string()+"\n").collect::<String>()).unwrap();
        let id=submit(&a,&source,&mdx);assert_eq!(wait(&a,&id)["state"],"succeeded");call(&a,json!({"action":"forget","job_id":id}));
        for large in [false,true] {for (operation,name,format) in [("export_txt","export.txt","txt"),("export_jsonl","export.jsonl","jsonl")] {
            let destination=dir.path().join(if large {format!("large-{name}")}else{name.to_owned()});
            let make_request=||if large {json!({"kind":"large_export","request":{"source":mdx,"destination":destination,"format":format}})}else{json!({"kind":"dictionary","request":{"operation":operation,"source":mdx,"destination":destination}})};
            let id=call(&a,json!({"action":"submit","request":make_request()}))["job_id"].as_str().unwrap().to_owned();
            let result=wait(&a,&id);assert_eq!(result["state"],"succeeded","{result}");
            let receipt=call(&a,json!({"action":"take","job_id":id}));assert_eq!(receipt["receipt"]["records"],5);assert_eq!(receipt["receipt"]["metadata"]["Title"],"字 / مرحبا");
            assert!(call(&a,json!({"action":"take","job_id":id})).is_null());call(&a,json!({"action":"forget","job_id":id}));
            let before=std::fs::read(&destination).unwrap();
            let duplicate=call(&a,json!({"action":"submit","request":make_request()}))["job_id"].as_str().unwrap().to_owned();
            assert_eq!(wait(&a,&duplicate)["error"]["code"],"destination_exists");assert_eq!(before,std::fs::read(&destination).unwrap());call(&a,json!({"action":"forget","job_id":duplicate}));
        }
        }
        assert_eq!(std::fs::read(dir.path().join("export.txt")).unwrap(),std::fs::read(dir.path().join("large-export.txt")).unwrap());
        assert_eq!(std::fs::read(dir.path().join("export.jsonl")).unwrap(),std::fs::read(dir.path().join("large-export.jsonl")).unwrap());
        let exported:Vec<Value>=std::fs::read_to_string(dir.path().join("export.jsonl")).unwrap().lines().map(|r|serde_json::from_str(r).unwrap()).collect();
        assert_eq!(exported.iter().filter(|r|r["key"]=="字").count(),2);
        let expected=exported.iter().map(|r|format!("{}\n{}\n</>\n",r["key"].as_str().unwrap(),r["text"].as_str().unwrap())).collect::<String>();
        assert_eq!(std::fs::read_to_string(dir.path().join("export.txt")).unwrap(),expected);
        let assets=dir.path().join("assets");std::fs::create_dir(&assets).unwrap();std::fs::create_dir(assets.join("fonts")).unwrap();std::fs::create_dir(assets.join("css")).unwrap();
        std::fs::write(assets.join("fonts/字.ttf"),[0u8,255,1,128]).unwrap();std::fs::write(assets.join("css/main.css"),b"body{color:blue}").unwrap();std::fs::write(assets.join("empty.bin"),b"").unwrap();
        let mdd=dir.path().join("dictionary.mdd");
        let id=call(&a,json!({"action":"submit","request":{"kind":"folder_packing","request":{"resource_root":assets,"destination":mdd,"metadata":{"title":"resources","description":"fixture"}}}}))["job_id"].as_str().unwrap().to_owned();
        assert_eq!(wait(&a,&id)["state"],"succeeded");call(&a,json!({"action":"forget","job_id":id}));
        let edited_mdd=dir.path().join("edited.mdd");let before_mdd=std::fs::read(&mdd).unwrap();
        let id=call(&a,json!({"action":"submit","request":{"kind":"metadata","request":{"source":mdd,"destination":edited_mdd,"kind":"mdd","edits":{"title":"موارد 字","description":""}}}}))["job_id"].as_str().unwrap().to_owned();
        let result=wait(&a,&id);assert_eq!(result["state"],"succeeded","{result}");let receipt=call(&a,json!({"action":"take","job_id":id}));
        assert_eq!(receipt["receipt"]["records"],3);assert_eq!(receipt["receipt"]["header"]["attributes"]["Description"],"");call(&a,json!({"action":"forget","job_id":id}));
        let after_mdd=std::fs::read(&edited_mdd).unwrap();let old_offset=8+u32::from_be_bytes(before_mdd[..4].try_into().unwrap()) as usize;let new_offset=8+u32::from_be_bytes(after_mdd[..4].try_into().unwrap()) as usize;
        assert_eq!(&before_mdd[old_offset..],&after_mdd[new_offset..]);assert_eq!(std::fs::read(&mdd).unwrap(),before_mdd);
        let destination=dir.path().join("extracted");
        let id=call(&a,json!({"action":"submit","request":{"kind":"extraction","request":{"source":mdd,"destination":destination}}}))["job_id"].as_str().unwrap().to_owned();
        assert_eq!(wait(&a,&id)["state"],"succeeded");let receipt=call(&a,json!({"action":"take","job_id":id}));assert_eq!(receipt["receipt"]["resources"],3);assert_eq!(receipt["receipt"]["materialized_record_limit"],0);call(&a,json!({"action":"forget","job_id":id}));
        for name in ["fonts/字.ttf","css/main.css","empty.bin"] {assert_eq!(std::fs::read(destination.join(name)).unwrap(),std::fs::read(assets.join(name)).unwrap());}
        let id=call(&a,json!({"action":"submit","request":{"kind":"extraction","request":{"source":mdd,"destination":destination}}}))["job_id"].as_str().unwrap().to_owned();
        assert_eq!(wait(&a,&id)["error"]["code"],"destination_exists");assert_eq!(std::fs::read(destination.join("fonts/字.ttf")).unwrap(),[0u8,255,1,128]);call(&a,json!({"action":"forget","job_id":id}));
        let invalid=dir.path().join("invalid.jsonl");let id=call(&a,json!({"action":"submit","request":{"kind":"dictionary","request":{"operation":"export_jsonl","source":mdd,"destination":invalid}}}))["job_id"].as_str().unwrap().to_owned();
        assert_eq!(wait(&a,&id)["state"],"failed");assert!(!invalid.exists());call(&a,json!({"action":"forget","job_id":id}));
        a.shutdown().unwrap();
    }

    #[test]
    fn unrepresentable_txt_export_preserves_source_via_jsonl_instead() {
        let a=Adapter::new().unwrap();let dir=tempfile::tempdir().unwrap();let source=dir.path().join("input.jsonl");let mdx=dir.path().join("input.mdx");
        let text="before\n</>\nafter";std::fs::write(&source,json!({"key":"word","text":text}).to_string()+"\n").unwrap();
        let id=submit(&a,&source,&mdx);assert_eq!(wait(&a,&id)["state"],"succeeded");call(&a,json!({"action":"forget","job_id":id}));
        for format in ["txt","jsonl"] {
            let destination=dir.path().join(format!("export.{format}"));
            let id=call(&a,json!({"action":"submit","request":{"kind":"large_export","request":{"source":mdx,"destination":destination,"format":format}}}))["job_id"].as_str().unwrap().to_owned();
            let state=wait(&a,&id);
            if format=="txt" {assert_eq!(state["error"]["code"],"unrepresentable_source");assert!(!destination.exists());}
            else {assert_eq!(state["state"],"succeeded");let row:Value=serde_json::from_str(&std::fs::read_to_string(destination).unwrap()).unwrap();assert_eq!(row["text"],text);}
            call(&a,json!({"action":"forget","job_id":id}));
        }
        a.shutdown().unwrap();
    }

}
