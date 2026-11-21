//! Application composition for ordinary imports. No dependency back-edge into
//! studio-application, no relaxation of its Studio-only export verification.
pub mod runner;
use crate::{Dictionary,ResourceArchive,LookupPolicy,ImportJob,Limits,Header,Entry,Resource,Resolution,Error,ErrorCode,Result};
use serde::{Deserialize,Serialize};
use std::{io::{self,Write},path::PathBuf};

pub const MAX_REPLY_BYTES:usize=2*1024*1024;
#[derive(Clone,Copy,Debug,Deserialize,Serialize)]
#[serde(tag="kind",rename_all="snake_case",deny_unknown_fields)]
pub enum Source {Mdx {policy:LookupPolicy},Mdd}
#[derive(Clone,Debug,Deserialize,Serialize)]
#[serde(tag="action",rename_all="snake_case",deny_unknown_fields)]
pub enum Action {Lookup {query:String},Resolve {query:String},Resource {query:String}}
impl Action {fn query(&self)->&str {match self {Self::Lookup {query}|Self::Resolve {query}|Self::Resource {query}=>query}}}
#[derive(Clone,Debug,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub path:PathBuf,pub source:Source,pub actions:Vec<Action>,
    #[serde(default)]pub max_results:Option<usize>,#[serde(default)]pub max_entries:Option<usize>,
    #[serde(default)]pub max_hops:Option<usize>,#[serde(default)]pub max_reply_bytes:Option<usize>,
}
impl Request {
    pub fn validate(&self)->Result<()> {
        if self.path.as_os_str().is_empty()||self.path.as_os_str().len()>8192||self.actions.len()>64 {
            return Err(crate::invalid("request","Require a source path <=8192 bytes and at most 64 actions"));
        }
        for action in &self.actions {
            if action.query().len()>4096 {return Err(crate::budget("Query metadata exceeds 4 KiB"));}
            if !matches!((&self.source,action),(Source::Mdx {..},Action::Lookup {..}|Action::Resolve {..})|(Source::Mdd,Action::Resource {..})) {
                return Err(crate::invalid("request","MDX requires lookup/resolve; MDD requires resource actions"));
            }
        }
        if self.max_results.is_some_and(|n|n>256)||self.max_entries.is_some_and(|n|n>1000)||self.max_hops.is_some_and(|n|n>16)||self.max_reply_bytes.is_some_and(|n|n>MAX_REPLY_BYTES) {
            return Err(crate::invalid("limits","Application budgets may only lower the qualified defaults"));
        }
        measured(self,65536)?;Ok(())
    }
    fn limits(&self)->Limits {
        let mut limits=Limits::default();
        if let Some(n)=self.max_results {limits.dictionary.max_result_entries=n;}
        if let Some(n)=self.max_entries {limits.dictionary.max_entries=n;}
        if let Some(n)=self.max_hops {limits.redirects.max_hops=n;}
        limits
    }
}
#[derive(Debug,Serialize)]
#[serde(tag="status",rename_all="snake_case")]
pub enum Outcome {Entries {entries:Vec<Entry>},Resolutions {results:Vec<Resolution>},Resources {resources:Vec<Resource>},Error {error:Error}}
#[derive(Debug,Serialize)]
pub struct ActionResult {pub request:Action,pub outcome:Outcome}
#[derive(Debug,Serialize)]
pub struct Response {pub header:Header,pub policy:&'static str,pub records:usize,pub results:Vec<ActionResult>}
struct Counter {bytes:usize,cap:usize}
impl Write for Counter {
    fn write(&mut self,data:&[u8])->io::Result<usize> {
        let n=self.bytes.checked_add(data.len()).ok_or_else(||io::Error::other("Reply size overflow"))?;
        if n>self.cap {return Err(io::Error::other("Reply byte cap exceeded"));}self.bytes=n;Ok(data.len())
    }
    fn flush(&mut self)->io::Result<()> {Ok(())}
}
pub(crate) fn measured<T:Serialize>(value:&T,cap:usize)->Result<usize> {
    let mut counter=Counter {bytes:0,cap};
    serde_json::to_writer(&mut counter,value).map_err(|_|crate::budget("Serialized request/reply byte cap exceeded"))?;Ok(counter.bytes)
}
fn query_outcome(value:Result<Outcome>)->Result<Outcome> {
    match value {Ok(v)=>Ok(v),Err(error) if error.code==ErrorCode::Cancelled=>Err(error),Err(error)=>Ok(Outcome::Error {error})}
}
/// Opens once, executes ordered actions and drops the dictionary before return.
/// Query errors are explicit per-action data. Open/cancel/aggregate-cap failures
/// return no partial response. Raw HTML and numeric stylesheet markers stay raw.
pub fn execute(request:&Request,job:&mut ImportJob<'_>)->Result<Response> {
    job.check()?;request.validate()?;let limits=request.limits();
    let cap=request.max_reply_bytes.unwrap_or(MAX_REPLY_BYTES);
    enum Opened {Mdx(Dictionary),Mdd(ResourceArchive)}
    let opened=match request.source {
        Source::Mdx {policy}=>Opened::Mdx(Dictionary::open_v2(&request.path,policy,&limits,job)?),
        Source::Mdd=>Opened::Mdd(ResourceArchive::open_v2(&request.path,&limits,job)?),
    };
    let mut response=match &opened {
        Opened::Mdx(d)=>Response {header:d.header().clone(),policy:d.policy().id(),records:d.entries().len(),results:Vec::new()},
        Opened::Mdd(d)=>Response {header:d.header().clone(),policy:"resource-raw-exact-v1",records:d.resources().len(),results:Vec::new()},
    };
    measured(&response,cap)?;
    for (i,action) in request.actions.iter().enumerate() {
        job.tick("import_actions",i,request.actions.len())?;
        let outcome=match (&opened,action) {
            (Opened::Mdx(d),Action::Lookup {query})=>query_outcome(d.lookup(query,job).map(|entries|Outcome::Entries {entries}))?,
            (Opened::Mdx(d),Action::Resolve {query})=>query_outcome(d.resolve(query,job).map(|results|Outcome::Resolutions {results}))?,
            (Opened::Mdd(d),Action::Resource {query})=>query_outcome(d.lookup(query,job).map(|resources|Outcome::Resources {resources}))?,
            _=>return Err(crate::invalid("request","Action/source mismatch")),
        };
        response.results.push(ActionResult {request:action.clone(),outcome});measured(&response,cap)?;
    }
    job.tick("import_actions",request.actions.len(),request.actions.len())?;Ok(response)
}
