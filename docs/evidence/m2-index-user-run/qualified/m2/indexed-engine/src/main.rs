use studio_indexed_engine::{Dictionary,Kind,Limits,ImportJob,CancellationToken,Progress,Error,ErrorCode,index::{Index,Policy,BuildOptions,REVISION}};
use serde::{Deserialize,Serialize};
use std::{path::PathBuf,io::{Read,Write},fs::File,process::ExitCode,time::Instant};
#[derive(Deserialize)]#[serde(deny_unknown_fields)]struct Query {query:String,offset:u64,limit:usize}
#[derive(Deserialize)]#[serde(deny_unknown_fields)]struct Request {path:PathBuf,kind:String,artifact:PathBuf,policy:Policy,action:String,#[serde(default)]queries:Vec<Query>,cancel_phase:Option<String>,run_records:Option<usize>,run_bytes:Option<usize>,page_bytes:Option<usize>}
fn invalid(message:&str)->Error {Error {code:ErrorCode::InvalidInput,detail:"request",message:message.into(),limit:None}}
struct Counter(usize);
impl Write for Counter {fn write(&mut self,b:&[u8])->std::io::Result<usize> {self.0=self.0.checked_add(b.len()).ok_or_else(||std::io::Error::other("Reply size overflow"))?;if self.0>2*1024*1024 {return Err(std::io::Error::other("Reply exceeds 2 MiB"));}Ok(b.len())}fn flush(&mut self)->std::io::Result<()> {Ok(())}}
fn check_json<T:Serialize>(v:&T)->Result<(),Error> {serde_json::to_writer(&mut Counter(0),v).map_err(|_|Error {code:ErrorCode::LimitExceeded,detail:"reply_limit",message:"Reply exceeds 2 MiB".into(),limit:None})}
fn run()->Result<serde_json::Value,Box<dyn std::error::Error>> {
 let args:Vec<_>=std::env::args_os().skip(1).collect();if args.len()!=1 {return Err(invalid("Require one request JSON path").into());}
 let f=File::open(&args[0])?;if !f.metadata()?.is_file() {return Err(invalid("Require regular request file").into());}let mut bytes=Vec::new();f.take(65537).read_to_end(&mut bytes)?;if bytes.len()>65536 {return Err(invalid("Request exceeds 64 KiB").into());}
 let req:Request=serde_json::from_slice(&bytes)?;if req.queries.len()>16||!matches!(req.action.as_str(),"build"|"query") {return Err(invalid("Require build/query action and at most 16 page queries").into());}
 // A publishing build returns only a thin receipt. Query/materialization errors
 // must never make an already committed publication look like a failed build.
 if req.action=="build"&&!req.queries.is_empty() {return Err(invalid("Build cannot include queries; reopen in a separate request").into());}
 let kind=match req.kind.as_str() {"mdx"=>Kind::Mdx,"mdd"=>Kind::Mdd,_=>return Err(invalid("Require mdx or mdd kind").into())};
 let token=CancellationToken::default();let stop=token.clone();let mut phases=Vec::new();let mut callback=|p:Progress| {if phases.last()!=Some(&p.phase) {phases.push(p.phase.clone());}if req.cancel_phase.as_deref()==Some(&p.phase) {stop.cancel();}};
 let mut job=ImportJob::new("indexed-request",&token,&mut callback);let mut limits=Limits::default();if let Some(n)=req.page_bytes {if n>limits.max_result_bytes {return Err(invalid("Page bytes may only lower the default").into());}limits.max_result_bytes=n;}
 let started=Instant::now();let dictionary=Dictionary::open_v2(&req.path,kind,&limits,&mut job)?;let open_us=started.elapsed().as_micros();
 if req.action=="build" {
  let mut options=BuildOptions::default();if let Some(n)=req.run_records {options.run_records=n;}if let Some(n)=req.run_bytes {options.run_bytes=n;}
  let receipt=Index::build(&dictionary,&req.artifact,req.policy,options,&mut job)?;
  return Ok(serde_json::json!({"status":"published","revision":REVISION,"receipt":receipt}));
 }
 let started=Instant::now();let mut index=Index::open(&dictionary,&req.artifact,req.policy,&mut job)?;let attach_us=started.elapsed().as_micros();let mut results=Vec::new();
 for q in req.queries {
  let started=Instant::now();let page=index.page(&q.query,q.offset,q.limit,&mut job)?;results.push(serde_json::json!({"query":q.query,"page":page,"lookup_us":started.elapsed().as_micros()}));check_json(&results)?;
 }
 let manifest=index.manifest().clone();drop(index);let memory=dictionary.memory_usage()?;drop(job);drop(callback);
 let reply=serde_json::json!({"status":"queried","revision":REVISION,"manifest":manifest,"results":results,"memory":memory,"scan":dictionary.scan(),"timing_us":{"validated_open":open_us,"verified_attach":attach_us},"phases":phases});check_json(&reply)?;Ok(reply)
}
fn main()->ExitCode {match run() {Ok(v)=>{println!("{v}");ExitCode::SUCCESS},Err(e)=>{let value=if let Some(e)=e.downcast_ref::<Error>() {serde_json::json!({"error":e})}else{serde_json::json!({"error":{"code":"invalid_input","detail":"request","message":e.to_string()}})};eprintln!("{value}");ExitCode::FAILURE}}}
