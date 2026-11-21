//! Qualification-only CLI. Blocking waits are confined to this CLI.
use std::{env,fs::File,io::Read,process::ExitCode,time::Duration};
use studio_v2_import::application::{Request,execute,runner::{Runner,Config}};
use studio_v2_import::{CancellationToken,ImportJob};
fn run()->Result<serde_json::Value,Box<dyn std::error::Error>> {
    let args:Vec<_>=env::args_os().skip(1).collect();if args.len()!=2 {return Err("Usage: studio-import-jobs sync|background REQUEST.json".into());}
    let file=File::open(&args[1])?;if !file.metadata()?.is_file() {return Err("Expected regular request JSON".into());}
    let mut data=Vec::new();file.take(65537).read_to_end(&mut data)?;if data.len()>65536 {return Err("Request exceeds 64 KiB".into());}
    let request:Request=serde_json::from_slice(&data)?;
    if args[0]=="sync" {
        let token=CancellationToken::default();let mut progress=|_|{};let mut job=ImportJob::new("sync-import",&token,&mut progress);
        return Ok(match execute(&request,&mut job) {Ok(response)=>serde_json::json!({"state":"succeeded","response":response}),Err(error)=>serde_json::json!({"state":"failed","error":error})});
    }
    if args[0]!="background" {return Err("Expected sync or background".into());}
    let runner=Runner::new(Config::default())?;let id=runner.submit(request)?;
    let terminal=runner.wait_for_terminal(&id,Duration::from_secs(60))?.ok_or("Import timed out")?;
    let events=runner.drain_events();let response=runner.take_result(&id)?;let taken_again=runner.take_result(&id)?.is_none();let collected=runner.snapshot(&id)?;
    let late_cancel=runner.cancel(&id)?;runner.forget(&id)?;let forgotten=runner.snapshot(&id).is_err();runner.join()?;
    Ok(serde_json::json!({"state":terminal.state,"error":terminal.error.clone(),"response":response,"terminal":terminal,"collected":collected,"events":events,"taken_once":taken_again,"forgotten":forgotten,"late_cancel":late_cancel}))
}
fn main()->ExitCode {match run() {Ok(value)=>{println!("{value}");ExitCode::SUCCESS},Err(e)=>{eprintln!("{}",serde_json::json!({"status":"failed","error":e.to_string()}));ExitCode::FAILURE}}}
