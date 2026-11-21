use std::{env,fs::File,io::Read,process::ExitCode,path::Path};
use studio_v2_import::{CancellationToken,ImportJob,Progress,application::metadata::{self,Request}};
fn seed(args:&[std::ffi::OsString])->Result<serde_json::Value,Box<dyn std::error::Error>> {
    if args.len()!=2 {return Err("Usage: studio-metadata-rebuild seed PACK_REQUEST.json OUTPUT.mdx".into());}
    let file=File::open(&args[0])?;if !file.metadata()?.is_file() {return Err("Expected regular seed JSON".into());}
    let mut bytes=Vec::new();file.take(65537).read_to_end(&mut bytes)?;if bytes.len()>65536 {return Err("Seed exceeds 64 KiB".into());}
    let request:studio_core::PackRequest=serde_json::from_slice(&bytes)?;
    let token=CancellationToken::default();let summary=studio_core::pack_mdx(&request,Path::new(&args[1]),&studio_core::Limits::default(),&mut studio_core::JobContext::new(&token,&mut |_|{}))?;
    Ok(serde_json::to_value(summary)?)
}
fn main()->ExitCode {
    let args:Vec<_>=env::args_os().skip(1).collect();let mut phases=Vec::<String>::new();
    if args.first().is_some_and(|s|s.to_str()==Some("seed")) {return match seed(&args[1..]) {Ok(value)=>{println!("{value}");ExitCode::SUCCESS},Err(e)=>{eprintln!("{e}");ExitCode::FAILURE}};}
    let result=(||->Result<metadata::Summary,Box<dyn std::error::Error>> {
        if args.is_empty()||args.len()>2 {return Err("Usage: studio-metadata-rebuild REQUEST.json [CANCEL_PHASE]".into());}
        let file=File::open(&args[0])?;if !file.metadata()?.is_file() {return Err("Expected regular request JSON".into());}
        let mut data=Vec::new();file.take(262145).read_to_end(&mut data)?;if data.len()>262144 {return Err("Request exceeds 256 KiB".into());}
        let request:Request=serde_json::from_slice(&data)?;let token=CancellationToken::default();let stop=token.clone();
        let cancel=args.get(1).map(|s|s.to_string_lossy().into_owned());
        let mut progress=|p:Progress| {if !phases.contains(&p.phase) {phases.push(p.phase.clone());}if cancel.as_deref()==Some(p.phase.as_str()) {stop.cancel();}};
        Ok(metadata::rebuild(&request,&mut ImportJob::new("metadata-rebuild",&token,&mut progress))?)
    })();
    match result {Ok(summary)=>{println!("{}",serde_json::json!({"summary":summary,"progress_phases":phases}));ExitCode::SUCCESS},Err(e)=>{
        let error=if let Some(e)=e.downcast_ref::<studio_v2_import::Error>() {serde_json::to_value(e).expect("Typed error JSON")}else{serde_json::json!({"code":"invalid_input","detail":"request","message":e.to_string()})};
        eprintln!("{}",serde_json::json!({"status":"failed","error":error,"progress_phases":phases}));ExitCode::FAILURE
    }}
}
