//! Bounded qualification client for the public GUI polling API.
use std::{env,fs::File,io::Read,path::Path,process::ExitCode,time::Duration};
use studio_application::{PublishRequest,Limits};
use studio_application::runner::{Runner,Config};
fn run()->Result<serde_json::Value,Box<dyn std::error::Error>> {
    let args:Vec<_>=env::args_os().skip(1).collect();if args.len()!=1 {return Err("Usage: studio-jobs-probe BATCH.json".into());}
    let file=File::open(Path::new(&args[0]))?;if !file.metadata()?.is_file() {return Err("Batch must be a regular JSON file".into());}
    let mut bytes=Vec::new();file.take(524289).read_to_end(&mut bytes)?;if bytes.len()>524288 {return Err("Batch exceeds 512 KiB".into());}
    let requests:Vec<PublishRequest>=serde_json::from_slice(&bytes)?;if requests.is_empty()||requests.len()>32 {return Err("Batch must contain 1..32 requests".into());}
    let runner=Runner::new(Config {max_pending:32,max_retained:64})?;let mut ids=Vec::new();
    for request in requests {ids.push(runner.submit(request,Limits::default())?);}
    let mut events=runner.drain_events();let mut results=Vec::new();
    for id in &ids {results.push(runner.wait_for_terminal(id,Duration::from_secs(30))?.ok_or("Job timeout")?);events.extend(runner.drain_events());}
    runner.join()?;
    Ok(serde_json::json!({"jobs":results,"events":events,"worker_joined":true}))
}
fn main()->ExitCode {match run() {
    Ok(value)=>{println!("{value}");ExitCode::SUCCESS},
    Err(e)=>{eprintln!("{}",serde_json::json!({"status":"failed","error":e.to_string()}));ExitCode::FAILURE},
}}
