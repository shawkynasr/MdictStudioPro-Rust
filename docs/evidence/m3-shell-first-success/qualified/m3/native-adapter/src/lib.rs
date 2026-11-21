//! GUI-independent, bounded command boundary over the accepted M2 runtime.
//! Call from a blocking executor; no dictionary work executes on the UI thread.
use serde::Deserialize;
use serde_json::{json, Value};
use std::{collections::{BTreeMap, BTreeSet}, sync::{Mutex, MutexGuard}, time::Duration};
use studio_cc_pack_runtime as native;
pub use native::{ApiCode, ApiError, ApiResult};

pub const MAX_COMMAND_BYTES: usize = 64 * 1024;
const MAX_ID_BYTES: usize = 128;

#[derive(Debug, Deserialize)]
#[serde(tag = "action", rename_all = "snake_case", deny_unknown_fields)]
pub enum Command {
    // Use empty struct variants rather than unit variants: Serde's internally
    // tagged unit decoder can skip extra map fields despite deny_unknown_fields.
    Capabilities {},
    Poll {},
    Submit { request: native::Request },
    Cancel { job_id: String },
    Take { job_id: String },
    Forget { job_id: String },
    OpenReader { request: native::OpenRequest },
    Page { session_id: String, request: native::PageRequest },
    SessionTake { session_id: String, job_id: String },
    SessionCancel { session_id: String, job_id: String },
    SessionForget { session_id: String, job_id: String },
    CloseReader { session_id: String },
    ReleaseReader { session_id: String },
}

struct Reader { native: native::Reader, jobs: BTreeSet<String> }
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
                    "small-moe", "grouped-moe", "indexed-sessions", "stream-mdd-extraction"],
                "metadata_editing": false, "redirect_resolution": false,
                "dictionary_html_rendering": false, "mdx_v3": false,
                "hard_memory_limit": false,
                "scope": "M3 shell slice; native validation pending; M2 qualified caps unchanged"
            }));
        }
        // Only short enqueue/snapshot/transfer operations hold this lock.
        // The native workers perform all parsing, indexing and publication.
        let mut inner = self.lock()?;
        let runtime = inner.runtime.as_ref().ok_or_else(|| error(ApiCode::Closed, "Adapter closed"))?;
        match command {
            Command::Capabilities {} => unreachable!(),
            Command::Poll {} => {
                let jobs = inner.jobs.iter().map(|id| runtime.publication().snapshot(id)).collect::<ApiResult<Vec<_>>>()?;
                let sessions = inner.readers.values().map(|r| {
                    let jobs = r.jobs.iter().map(|id| r.native.session().job(id)).collect::<ApiResult<Vec<_>>>()?;
                    Ok(json!({"session": r.native.session().snapshot(), "jobs": jobs}))
                }).collect::<ApiResult<Vec<Value>>>()?;
                Ok(json!({"jobs": jobs, "sessions": sessions, "admission": runtime.admission(), "readers": runtime.reader_admission()}))
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
                let native = runtime.open_reader(request)?;
                let session_id = native.session().id().to_owned();
                let job_id = native.session().open_job_id();
                inner.readers.insert(session_id.clone(), Reader { native, jobs: BTreeSet::from([job_id.clone()]) });
                Ok(json!({"session_id": session_id, "job_id": job_id}))
            }
            Command::Page { session_id, request } => {
                let job_id = reader(&inner, &session_id)?.native.session().submit_page(request)?;
                inner.readers.get_mut(&session_id).ok_or_else(|| error(ApiCode::NotFound, "Reader disappeared"))?.jobs.insert(job_id.clone());
                Ok(json!({"job_id": job_id}))
            }
            Command::SessionTake { session_id, job_id } => {
                id(&job_id)?; value(reader(&inner, &session_id)?.native.session().take_result(&job_id)?)
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
                reader(&inner, &session_id)?.native.close(); Ok(Value::Null)
            }
            Command::ReleaseReader { session_id } => {
                // A close request alone must not release the shared admission lease.
                if !reader(&inner, &session_id)?.native.wait_closed(Duration::ZERO) {
                    return Err(error(ApiCode::StillRunning, "Reader cleanup in progress; poll and retry"));
                }
                let r = inner.readers.remove(&session_id).ok_or_else(|| error(ApiCode::NotFound, "Unknown reader"))?;
                drop(inner);
                r.native.join()?;
                Ok(Value::Null)
            }
        }
    }
    /// Stops admission and joins all accepted workers. Call off the UI thread.
    /// Taking runtime/readers atomically prevents new commands racing shutdown.
    pub fn shutdown(&self) -> ApiResult<()> {
        let (runtime, readers) = {
            let mut inner = self.lock()?;
            let runtime = inner.runtime.take();
            if let Some(runtime) = &runtime { runtime.shutdown(); }
            let readers = std::mem::take(&mut inner.readers);
            for r in readers.values() { r.native.close(); }
            (runtime, readers)
        };
        let mut failure = None;
        for r in readers.into_values() {
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
    fn boundary_refuses_unknown_fields_profiles_and_oversized_commands() {
        let a = Adapter::new().unwrap();
        for json in [r#"{"action":"poll","surprise":true}"#, r#"{"action":"capabilities","surprise":true}"#, r#"{"action":"submit","request":{"kind":"metadata","request":{}}}"#, r#"{"action":"cancel","job_id":"../escape"}"#] {
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
        assert!(!target.exists()); a.shutdown().unwrap();
    }
}
