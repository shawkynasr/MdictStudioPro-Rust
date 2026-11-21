use studio_stream_extract::*;
use serde::Deserialize;
use std::{path::PathBuf,io::Read};
#[derive(Deserialize,Default)]#[serde(deny_unknown_fields)]struct Tighten {resources:Option<u64>,resource_bytes:Option<u64>,output_bytes:Option<u64>,plan_charge:Option<usize>,nodes:Option<usize>,file_bytes:Option<u64>,working_memory:Option<usize>,decoded_block:Option<usize>}
#[derive(Deserialize)]#[serde(deny_unknown_fields)]struct Request {source:PathBuf,destination:PathBuf,#[serde(default)]tighten:Tighten,cancel_phase:Option<String>,#[serde(default)]cancel_after:usize}
fn run()->Result<ExtractionReceipt> {
 let args=std::env::args_os().skip(1).collect::<Vec<_>>();if args.len()!=1 {return Err(Error {code:ErrorCode::InvalidInput,detail:"request",message:"Require request JSON path".into(),limit:None});}
 let f=std::fs::File::open(&args[0])?;if !f.metadata()?.is_file() {return Err(Error {code:ErrorCode::InvalidInput,detail:"request",message:"Require regular request file".into(),limit:None});}let mut bytes=Vec::new();f.take(65537).read_to_end(&mut bytes)?;
 if bytes.len()>65536 {return Err(Error {code:ErrorCode::LimitExceeded,detail:"request",message:"Request exceeds 64 KiB".into(),limit:None});}
 let req:Request=serde_json::from_slice(&bytes).map_err(|e|Error {code:ErrorCode::InvalidInput,detail:"request",message:e.to_string(),limit:None})?;let mut limits=ExtractLimits::default();let t=req.tighten;
 if let Some(n)=t.resources {limits.max_resources=n;}if let Some(n)=t.resource_bytes {limits.max_resource_bytes=n;}if let Some(n)=t.output_bytes {limits.max_output_bytes=n;}if let Some(n)=t.plan_charge {limits.max_plan_charge=n;}if let Some(n)=t.nodes {limits.max_nodes=n;}if let Some(n)=t.file_bytes {limits.reader.dictionary.max_file_bytes=n;}if let Some(n)=t.working_memory {limits.reader.engine=limits.reader.engine.with_working_memory_bytes(n);}if let Some(n)=t.decoded_block {limits.reader.engine=limits.reader.engine.with_decompressed_block_bytes(n);}
 let token=CancellationToken::default();let stop=token.clone();let mut callback=|p:Progress| {if req.cancel_phase.as_deref()==Some(&p.phase)&&p.completed>=req.cancel_after {stop.cancel();}};let mut job=ImportJob::new("extract-request",&token,&mut callback);extract_mdd(&req.source,&req.destination,&limits,&mut job)
}
fn main()->std::process::ExitCode {match run() {Ok(receipt)=>{println!("{}",serde_json::json!({"status":"published","receipt":receipt}));std::process::ExitCode::SUCCESS},Err(e)=>{eprintln!("{}",serde_json::json!({"error":e}));std::process::ExitCode::FAILURE}}}
