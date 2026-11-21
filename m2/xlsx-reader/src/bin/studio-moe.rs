//! JSON conversion boundary. File publication remains in studio-core.
use std::{env,path::Path,process::ExitCode};
use studio_xlsx::{Error,Limits,ReadControl,read_xlsx,moe};
fn run()->studio_xlsx::Result<moe::Conversion> {
    let args:Vec<_>=env::args_os().skip(1).collect();
    if !(args.len()==2||args.len()==3) {return Err(Error {code:"invalid_input",message:"Usage: studio-moe CONVERTER INPUT.xlsx [SHEET]".into()});}
    let kind=moe::Converter::parse(args[0].to_str().ok_or_else(||Error {code:"invalid_input",message:"Invalid converter name".into()})?)?;
    let sheet=match args.get(2) {Some(s)=>Some(s.to_str().ok_or_else(||Error {code:"invalid_input",message:"Invalid sheet name".into()})?),None=>None};
    let cancelled=||false;let mut progress=|p|eprintln!("{}",serde_json::to_string(&p).expect("Progress JSON"));
    let mut control=ReadControl::new(&cancelled,&mut progress);
    let table=read_xlsx(Path::new(&args[1]),sheet,&Limits::default(),&mut control)?;
    moe::convert(&table,kind,&moe::Limits::default(),&mut control)
}
fn main()->ExitCode {match run() {
    Ok(value)=>{println!("{}",serde_json::to_string(&value).expect("Conversion JSON"));ExitCode::SUCCESS},
    Err(error)=>{eprintln!("{}",serde_json::json!({"status":"failed","error":error}));ExitCode::FAILURE},
}}
