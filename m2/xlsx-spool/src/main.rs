//! Diagnostic row-spool gate. No dictionary rendering or publication.
use serde::Deserialize;
use std::{cell::Cell,collections::BTreeSet,io::Read,path::PathBuf};
use studio_xlsx_spool::{Error,ReadControl,Tighten};
#[derive(Deserialize)]#[serde(deny_unknown_fields)]struct Request {source:PathBuf,worksheet:Option<String>,#[serde(default)]tighten:Tighten,cancel_phase:Option<String>,#[serde(default)]pre_cancel:bool}
fn run()->studio_xlsx_spool::Result<serde_json::Value> {
 let mut input=Vec::new();let args:Vec<_>=std::env::args_os().skip(1).collect();
 if args.len()>1 {return Err(Error::new("invalid_input","At most one request-file argument"));}
 if let Some(path)=args.first() {std::fs::File::open(path)?.take(65537).read_to_end(&mut input)?;}else{std::io::stdin().take(65537).read_to_end(&mut input)?;}
 if input.len()>65536 {return Err(Error::new("invalid_input","Request exceeds 64 KiB"));}
 let request:Request=serde_json::from_slice(&input).map_err(|_|Error::new("invalid_input","Malformed row-spool request"))?;
 if request.cancel_phase.as_ref().is_some_and(|s|!["begin","snapshot","package_preflight","shared_strings","normalize_rows","verify_rows","complete"].contains(&s.as_str())) {return Err(Error::new("invalid_input","Unknown cancellation checkpoint"));}
 let limits=request.tighten.limits()?;let flag=Cell::new(request.pre_cancel);let cancelled=||flag.get();let mut phases=BTreeSet::new();
 let mut progress=|p:studio_xlsx_spool::Progress| {phases.insert(p.phase.to_string());if request.cancel_phase.as_deref()==Some(p.phase) {flag.set(true);}};
 let control=ReadControl::new(&cancelled,&mut progress);
 let spool=studio_xlsx_spool::read_to_spool(&request.source,request.worksheet.as_deref(),&limits,&control)?;
 let receipt=spool.receipt.clone();let private=spool.private_path().to_path_buf();drop(spool);
 if private.exists() {return Err(Error::new("io","Private row-spool cleanup failed"));}
 drop(control);drop(progress);
 Ok(serde_json::json!({"status":"succeeded","receipt":receipt,"progress_phases":phases,"private_cleanup":true}))
}
fn main() {
 let (value,code)=match run() {Ok(v)=>(v,0),Err(e)=>(serde_json::json!({"status":"failed","error":e}),1)};
 println!("{}",value);std::process::exit(code)
}
