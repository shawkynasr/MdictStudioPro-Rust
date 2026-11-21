use std::{env,fs::File,io::{Read,Write},path::PathBuf,process::ExitCode};
use serde::{Deserialize,Serialize};
use studio_bounded_engine::{Dictionary,Limits,Kind,ImportJob,CancellationToken,Progress,Error,ErrorCode,PROFILE};
#[derive(Default,Deserialize)]#[serde(deny_unknown_fields)]struct Tighten {
    max_rows:Option<u64>,file_bytes:Option<u64>,scan_bytes:Option<u64>,compressed_block:Option<usize>,decoded_block:Option<usize>,key_index:Option<usize>,record_index:Option<usize>,block_metadata:Option<usize>,key_block_entries:Option<u64>,materialized_record:Option<usize>,working_memory:Option<usize>,max_matches:Option<usize>,result_bytes:Option<usize>,
}
#[derive(Deserialize)]#[serde(deny_unknown_fields)]struct Request {path:PathBuf,kind:String,#[serde(default)]queries:Vec<String>,#[serde(default)]tighten:Tighten,cancel_phase:Option<String>}
fn error(message:&str)->Error {Error {code:ErrorCode::InvalidInput,detail:"request",message:message.into(),limit:None}}
struct Count {n:usize}
impl Write for Count {
    fn write(&mut self,b:&[u8])->std::io::Result<usize> {self.n=self.n.checked_add(b.len()).ok_or_else(||std::io::Error::other("JSON byte overflow"))?;if self.n>2*1024*1024 {return Err(std::io::Error::other("Aggregate JSON reply exceeds 2 MiB"));}Ok(b.len())}
    fn flush(&mut self)->std::io::Result<()> {Ok(())}
}
fn bounded_json<T:Serialize>(value:&T)->Result<(),Error> {serde_json::to_writer(&mut Count {n:0},value).map_err(|_|Error {code:ErrorCode::LimitExceeded,detail:"reply_limit",message:"Aggregate JSON reply exceeds 2 MiB".into(),limit:None})}
fn run()->Result<serde_json::Value,Box<dyn std::error::Error>> {
    let args:Vec<_>=env::args_os().skip(1).collect();if args.len()!=1 {return Err(error("Usage: studio-bounded-engine REQUEST.json").into());}
    let file=File::open(&args[0])?;if !file.metadata()?.is_file() {return Err(error("Expected a regular request JSON file").into());}
    let mut bytes=Vec::new();file.take(65537).read_to_end(&mut bytes)?;if bytes.len()>65536 {return Err(error("Request exceeds 64 KiB").into());}
    let req:Request=serde_json::from_slice(&bytes)?;if req.queries.len()>8 {return Err(error("At most eight exact queries").into());}
    let kind=match req.kind.as_str() {"mdx"=>Kind::Mdx,"mdd"=>Kind::Mdd,_=>return Err(error("Expected mdx or mdd kind").into())};let mut limits=Limits::default();let t=req.tighten;
    if let Some(n)=t.max_rows {limits.max_rows=n;}if let Some(n)=t.file_bytes {limits.dictionary.max_file_bytes=n;}if let Some(n)=t.scan_bytes {limits.max_scan_bytes=n;}if let Some(n)=t.max_matches {limits.max_matches=n;}if let Some(n)=t.result_bytes {limits.max_result_bytes=n;}
    macro_rules! tighten {($field:ident,$method:ident)=>{if let Some(n)=t.$field {limits.engine=limits.engine.$method(n);}};}
    tighten!(compressed_block,with_compressed_block_bytes);tighten!(decoded_block,with_decompressed_block_bytes);tighten!(key_index,with_key_index_bytes);tighten!(record_index,with_record_index_bytes);tighten!(block_metadata,with_block_metadata_bytes);tighten!(key_block_entries,with_key_block_entries);tighten!(materialized_record,with_materialized_record_bytes);tighten!(working_memory,with_working_memory_bytes);
    let token=CancellationToken::default();let stop=token.clone();let mut phases=Vec::new();let mut progress=|p:Progress| {if !phases.contains(&p.phase) {phases.push(p.phase.clone());}if req.cancel_phase.as_deref()==Some(p.phase.as_str()) {stop.cancel();}};
    let mut job=ImportJob::new("bounded-reader",&token,&mut progress);let dictionary=Dictionary::open_v2(&req.path,kind,&limits,&mut job)?;
    let mut queries=Vec::new();
    for query in req.queries {
        let value=match dictionary.lookup_exact(&query,&mut job) {Ok(rows)=>serde_json::json!({"query":query,"rows":rows}),Err(e) if e.code==ErrorCode::Cancelled=>return Err(e.into()),Err(e)=>serde_json::json!({"query":query,"error":e})};
        queries.push(value);bounded_json(&queries)?;
    }
    drop(job);drop(progress);
    let reply=serde_json::json!({"profile":PROFILE,"lookup_policy":"raw-exact-bounded-scan-v1","scan":dictionary.scan(),"memory":dictionary.memory_usage()?,"queries":queries,"phases":phases});bounded_json(&reply)?;Ok(reply)
}
fn main()->ExitCode {match run() {Ok(value)=>{println!("{value}");ExitCode::SUCCESS},Err(e)=>{
    let value=if let Some(e)=e.downcast_ref::<Error>() {serde_json::json!({"status":"failed","error":e})}else {serde_json::json!({"status":"failed","error":{"code":"invalid_input","detail":"request","message":e.to_string()}})};
    eprintln!("{value}");ExitCode::FAILURE
}}}
