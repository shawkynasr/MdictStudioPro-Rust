//! Qualification CLI; all blocking waits are confined to this process.
use std::{env,fs::File,io::Read,process::ExitCode,time::Duration};
use serde::Deserialize;
use studio_v2_import::{CancellationToken,ImportJob,Progress,application::metadata::publication::{self,Request,runner::{Runner,Config}}};
#[derive(Deserialize)]#[serde(deny_unknown_fields)]struct Batch {requests:Vec<Request>}
fn run()->Result<serde_json::Value,Box<dyn std::error::Error>> {
    let args:Vec<_>=env::args_os().skip(1).collect();if args.len()!=2 {return Err("Usage: studio-metadata-jobs sync|background BATCH.json".into());}
    let background=match args[0].to_str() {Some("background")=>true,Some("sync")=>false,_=>return Err("Expected sync or background".into())};
    let file=File::open(&args[1])?;if !file.metadata()?.is_file() {return Err("Expected regular batch JSON".into());}
    let mut data=Vec::new();file.take(publication::MAX_REQUEST_BYTES as u64+1).read_to_end(&mut data)?;if data.len()>publication::MAX_REQUEST_BYTES {return Err("Batch exceeds 16 MiB".into());}
    let batch:Batch=serde_json::from_slice(&data)?;if batch.requests.is_empty()||batch.requests.len()>64 {return Err("Require 1..64 batch jobs".into());}
    let runner=if background {Some(Runner::new(Config::default())?)}else{None};let mut jobs=Vec::new();
    for (index,request) in batch.requests.into_iter().enumerate() {
        if let Err(error)=request.validate() {jobs.push(serde_json::json!({"index":index,"state":"rejected","error":error,"publication_uncertain":false,"response":null}));continue;}
        if let Some(runner)=&runner {
            let id=runner.submit(request)?;let terminal=runner.wait_for_terminal(&id,Duration::from_secs(60))?.ok_or("Publication timed out; inspect destination before retrying")?;
            let events=runner.drain_events();let response=runner.take_result(&id)?;let once=runner.take_result(&id)?.is_none();let collected=runner.snapshot(&id)?;let late_cancel=runner.cancel(&id)?;runner.forget(&id)?;let forgotten=runner.snapshot(&id).is_err();
            jobs.push(serde_json::json!({"index":index,"state":terminal.state,"error":terminal.error.clone(),"response":response,"terminal":terminal,"collected":collected,"events":events,"taken_once":once,"forgotten":forgotten,"late_cancel":late_cancel}));
        }else {
            let id=format!("publication-sync-{index}");let token=CancellationToken::default();let mut latest=None;let mut progress=|p:Progress|latest=Some(p);
            let result=publication::execute(&request,&mut ImportJob::new(&id,&token,&mut progress));
            jobs.push(match result {Ok(response)=>serde_json::json!({"index":index,"state":"succeeded","response":response,"error":null,"latest_progress":latest}),Err(error)=>serde_json::json!({"index":index,"state":"failed","response":null,"error":error,"publication_uncertain":false,"latest_progress":latest})});
        }
    }
    if let Some(runner)=runner {runner.join()?;}Ok(serde_json::json!({"mode":if background {"background"}else{"sync"},"jobs":jobs}))
}
fn main()->ExitCode {match run() {Ok(value)=>{println!("{value}");ExitCode::SUCCESS},Err(e)=>{eprintln!("{}",serde_json::json!({"status":"failed","error":e.to_string()}));ExitCode::FAILURE}}}
