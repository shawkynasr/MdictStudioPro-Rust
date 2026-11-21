use std::{env,fs::File,io::Read,process::ExitCode};
use serde::Deserialize;
use studio_large_io::{Request,IoLimits,ImportJob,CancellationToken,Progress,Error,ErrorCode,execute};
#[derive(Default,Deserialize)]#[serde(deny_unknown_fields)]struct Tighten {records:Option<usize>,decoded_bytes:Option<usize>,entry_bytes:Option<usize>,plan_charge:Option<usize>,input_bytes:Option<u64>,output_bytes:Option<u64>}
#[derive(Deserialize)]#[serde(deny_unknown_fields)]struct Envelope {request:Request,#[serde(default)]tighten:Tighten,cancel_phase:Option<String>,#[serde(default)]cancel_after:usize}
fn run()->Result<serde_json::Value,Box<dyn std::error::Error>> {
 let args:Vec<_>=env::args_os().skip(1).collect();if args.len()!=1 {return Err("Usage: studio-large-io REQUEST.json".into());}
 let f=File::open(&args[0])?;if !f.metadata()?.is_file() {return Err("Expected regular request JSON file".into());}let mut bytes=Vec::new();f.take(65537).read_to_end(&mut bytes)?;if bytes.len()>65536 {return Err("Request exceeds 64 KiB".into());}let req:Envelope=serde_json::from_slice(&bytes)?;
 let mut limits=IoLimits::default();let t=req.tighten;
 if let Some(n)=t.records {limits.max_records=n;}if let Some(n)=t.decoded_bytes {limits.max_decoded_bytes=n;}if let Some(n)=t.entry_bytes {limits.max_entry_bytes=n;}if let Some(n)=t.plan_charge {limits.max_plan_charge=n;}if let Some(n)=t.input_bytes {limits.max_input_bytes=n;}if let Some(n)=t.output_bytes {limits.max_output_bytes=n;}
 let token=CancellationToken::default();let stop=token.clone();let mut phases=Vec::new();let mut progress=|p:Progress| {if !phases.contains(&p.phase) {phases.push(p.phase.clone());}if req.cancel_phase.as_deref()==Some(p.phase.as_str())&&p.completed>=req.cancel_after {stop.cancel();}};
 let mut job=ImportJob::new("large-io",&token,&mut progress);let summary=execute(&req.request,&limits,&mut job)?;drop(job);drop(progress);Ok(serde_json::json!({"status":"succeeded","summary":summary,"phases":phases}))
}
fn main()->ExitCode {match run() {Ok(v)=>{println!("{v}");ExitCode::SUCCESS},Err(e)=>{let v=if let Some(e)=e.downcast_ref::<Error>() {serde_json::json!({"status":"failed","error":e})}else {serde_json::json!({"status":"failed","error":{"code":ErrorCode::InvalidInput,"detail":"request","message":e.to_string()}})};eprintln!("{v}");ExitCode::FAILURE}}}
