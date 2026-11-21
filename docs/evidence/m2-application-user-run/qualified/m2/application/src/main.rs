use std::{env,fs::File,io::Read,path::Path,process::ExitCode};
use studio_application::{CancellationToken,Error,ErrorCode,JobContext,Limits};
fn request<T:serde::de::DeserializeOwned>(path:&Path)->studio_application::Result<T> {
    let file=File::open(path)?;
    if !file.metadata()?.is_file() {return Err(Error::new(ErrorCode::InvalidInput,"Expected regular request JSON file"));}
    let mut bytes=Vec::new();file.take(32769).read_to_end(&mut bytes)?;
    if bytes.len()>32768 {return Err(Error::new(ErrorCode::LimitExceeded,"Request JSON exceeds 32 KiB"));}
    serde_json::from_slice(&bytes).map_err(|e|Error::new(ErrorCode::InvalidInput,e.to_string()))
}
fn run()->studio_application::Result<serde_json::Value> {
    let args:Vec<_>=env::args_os().skip(1).collect();let token=CancellationToken::default();
    let mut sink=|p|eprintln!("{}",serde_json::to_string(&p).expect("Progress JSON"));
    let mut job=JobContext::new("cli-conversion",&token,&mut sink);let limits=Limits::default();
    let value=match args.first().and_then(|a|a.to_str()) {
        Some("convert") if args.len()==2=>serde_json::to_value(studio_application::convert(&request(Path::new(&args[1]))?,&limits,&mut job)?),
        Some("publish") if args.len()==2=>serde_json::to_value(studio_application::convert_to_txt(&request(Path::new(&args[1]))?,&limits,&mut job)?),
        Some("read-workbook") if args.len()==2||args.len()==3=>{
            let sheet=match args.get(2) {Some(s)=>Some(s.to_str().ok_or_else(||Error::new(ErrorCode::InvalidInput,"Worksheet must be UTF-8"))?),None=>None};
            serde_json::to_value(studio_application::read_workbook(Path::new(&args[1]),sheet,&limits,&mut job)?)
        },
        _=>return Err(Error::new(ErrorCode::InvalidInput,"Usage: studio-application convert REQUEST.json | publish REQUEST.json | read-workbook INPUT.xlsx [SHEET]")),
    };value.map_err(|e|Error::new(ErrorCode::Internal,e.to_string()))
}
fn main()->ExitCode {match run() {
    Ok(value)=>{println!("{value}");ExitCode::SUCCESS},
    Err(error)=>{eprintln!("{}",serde_json::json!({"status":"failed","error":error}));ExitCode::FAILURE},
}}
