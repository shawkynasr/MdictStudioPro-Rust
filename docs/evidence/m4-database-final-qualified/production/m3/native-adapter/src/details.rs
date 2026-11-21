//! Read-only metadata, bound to the already admitted reader's source digest.
//! No parser state or dictionary records are retained here.
use crate::{error, ApiCode, ApiResult};
use serde_json::{json, Value};
use std::{collections::BTreeMap, fs::File, io::Read, path::Path, sync::{atomic::{AtomicBool, Ordering}, Arc, Condvar, Mutex}};
#[path = "../../../m2/indexed-engine/src/sha256.rs"]
mod sha256;

#[derive(Default)]
pub(crate) struct Task {
    pub cancelled: AtomicBool,
    busy: Mutex<bool>,
    changed: Condvar,
}
pub(crate) struct Guard(Arc<Task>);
impl Task {
    pub fn start(self: &Arc<Self>) -> ApiResult<Guard> {
        let mut busy=self.busy.lock().map_err(|_| error(ApiCode::Internal,"Metadata task poisoned"))?;
        if *busy { return Err(error(ApiCode::StillRunning,"Metadata read already running")); }
        self.check()?; *busy=true; Ok(Guard(self.clone()))
    }
    pub fn busy(&self) -> bool { self.busy.lock().map(|b| *b).unwrap_or(true) }
    pub fn cancel(&self) { self.cancelled.store(true,Ordering::Release); }
    fn check(&self) -> ApiResult<()> {
        if self.cancelled.load(Ordering::Acquire) { Err(error(ApiCode::Closed,"Metadata read cancelled")) } else { Ok(()) }
    }
    pub fn wait(&self) -> ApiResult<()> {
        let mut busy=self.busy.lock().map_err(|_|error(ApiCode::Internal,"Metadata task poisoned"))?;
        while *busy { busy=self.changed.wait(busy).map_err(|_|error(ApiCode::Internal,"Metadata task poisoned"))?; }
        Ok(())
    }
}
impl Drop for Guard {
    fn drop(&mut self) { if let Ok(mut busy)=self.0.busy.lock() { *busy=false; self.0.changed.notify_all(); } }
}
fn invalid(message: impl Into<String>) -> crate::ApiError { error(ApiCode::InvalidInput,message) }
fn io(e: impl std::fmt::Display) -> crate::ApiError { invalid(format!("Metadata source: {e}")) }

pub(crate) fn read(path: &Path, expected: &str, task: &Task) -> ApiResult<Value> {
    task.check()?;
    let mut file=File::open(path).map_err(io)?;
    let meta=file.metadata().map_err(io)?;
    const CAP:u64=512*1024*1024;
    if !meta.is_file() || meta.len()>CAP { return Err(invalid("Metadata source exceeds regular-file profile")); }
    let mut prefix=[0;4]; file.read_exact(&mut prefix).map_err(io)?;
    let len=u32::from_be_bytes(prefix) as usize;
    if !(2..=65536).contains(&len) || len%2!=0 { return Err(invalid("Invalid bounded UTF-16 header")); }
    let mut bytes=vec![0;len];file.read_exact(&mut bytes).map_err(io)?;
    let mut hash=sha256::Sha256::new();hash.update(&prefix);hash.update(&bytes);
    let mut buffer=[0;65536]; let mut total=4+len as u64;
    loop {
        task.check()?;
        let n=file.read(&mut buffer).map_err(io)?;if n==0 {break;}
        total+=n as u64;if total>CAP {return Err(invalid("Metadata source grew beyond profile"));}
        hash.update(&buffer[..n]);
    }
    if sha256::hex(&hash.finish())!=expected { return Err(invalid("Source changed since reader opened; close and reopen with a matching index")); }
    task.check()?;
    let units:Vec<_>=bytes.chunks_exact(2).map(|b|u16::from_le_bytes([b[0],b[1]])).collect();
    let decoded=String::from_utf16(&units).map_err(io)?;
    let xml=decoded.trim_start_matches('\u{feff}').strip_suffix('\0').unwrap_or(decoded.trim_start_matches('\u{feff}'));
    let mut parser=quick_xml::Reader::from_str(xml);
    let mut attrs=BTreeMap::new();let mut seen=false;let mut closed=false;let mut budget=0;
    use quick_xml::events::Event;
    loop {
        let event=parser.read_event().map_err(io)?;let empty=matches!(&event,Event::Empty(_));
        match event {
            Event::Start(e)|Event::Empty(e)=>{
                if seen || !matches!(e.name().as_ref(), b"Dictionary"|b"Library_Data") {return Err(invalid("Unexpected header root"));}
                seen=true;closed=empty;
                for a in e.attributes() {
                    let a=a.map_err(io)?;let key=std::str::from_utf8(a.key.as_ref()).map_err(io)?.to_owned();
                    let val=a.decode_and_unescape_value(parser.decoder()).map_err(io)?.into_owned();
                    budget+=key.len()+val.len();
                    if attrs.len()>=256 || budget>65536 || attrs.insert(key,val).is_some() {return Err(invalid("Header attribute budget or duplicate"));}
                }
            },
            Event::End(e)=>{if !seen || closed || !matches!(e.name().as_ref(),b"Dictionary"|b"Library_Data") {return Err(invalid("Invalid header close"));}closed=true;},
            Event::Text(t) if t.as_ref().iter().all(u8::is_ascii_whitespace)=>{},
            Event::Decl(_)|Event::Comment(_)=>{},
            Event::Eof=>break,
            _=>return Err(invalid("Unsupported header XML construct")),
        }
    }
    if !seen || !closed {return Err(invalid("Incomplete header"));}
    Ok(json!({"attributes":attrs,"source_sha256":expected,"source_bytes":total}))
}
#[cfg(test)] mod tests {
    use super::*;
    #[test] fn task_cancellation_keeps_join_waiting_for_guard() {
        let task=Arc::new(Task::default());let guard=task.start().unwrap();
        task.cancel();assert!(task.busy());assert!(task.start().is_err());
        let cloned=task.clone();let (send,receive)=std::sync::mpsc::channel();
        let worker=std::thread::spawn(move || {cloned.wait().unwrap();send.send(()).unwrap();});
        assert!(receive.try_recv().is_err());drop(guard);
        receive.recv_timeout(std::time::Duration::from_secs(5)).unwrap();worker.join().unwrap();assert!(!task.busy());
    }
    #[test] fn details_are_digest_bound_bounded_and_cancellable() {
        let d=tempfile::tempdir().unwrap();let path=d.path().join("header.mdx");
        let xml="<Dictionary Title=\"字 &amp; مرحبا\" StyleSheet=\"1&#10;&lt;b&gt;&#10;&lt;/b&gt;\"/>\0";
        let raw:Vec<_>=xml.encode_utf16().flat_map(u16::to_le_bytes).collect();
        let mut file=(raw.len() as u32).to_be_bytes().to_vec();file.extend(raw);file.extend(b"records");
        std::fs::write(&path,&file).unwrap();let mut hash=sha256::Sha256::new();hash.update(&file);let digest=sha256::hex(&hash.finish());
        let task=Arc::new(Task::default());let _guard=task.start().unwrap();
        let info=read(&path,&digest,&task).unwrap();assert_eq!(info["attributes"]["Title"],"字 & مرحبا");
        assert_eq!(info["attributes"]["StyleSheet"],"1\n<b>\n</b>");
        assert!(read(&path,"wrong",&task).is_err());assert!(task.start().is_err());
        task.cancel();assert!(read(&path,&digest,&task).is_err());
        std::fs::write(&path,u32::MAX.to_be_bytes()).unwrap();assert!(read(&path,&digest,&Task::default()).is_err());
    }
}
