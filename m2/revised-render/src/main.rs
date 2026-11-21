//! Standalone full-converter qualification boundary, not a GUI/job adapter.
use serde::Deserialize;
use std::{cell::Cell,collections::BTreeSet,io::Read,path::PathBuf};
use studio_revised_render::{Control,Converter,Error,Tighten};
#[derive(Deserialize)]#[serde(deny_unknown_fields)]struct Request {source:PathBuf,destination:PathBuf,converter:Converter,worksheet:Option<String>,#[serde(default)]tighten:Tighten,#[serde(default)]reader_tighten:studio_xlsx_spool::Tighten,cancel_phase:Option<String>,#[serde(default)]pre_cancel:bool}
fn run()->studio_revised_render::Result<serde_json::Value> {
 let args:Vec<_>=std::env::args_os().skip(1).collect();if args.len()!=1 {return Err(Error::new("invalid_input","One request-file argument required"));}
 let mut data=Vec::new();std::fs::File::open(&args[0])?.take(65537).read_to_end(&mut data)?;if data.len()>65536 {return Err(Error::new("invalid_input","Request exceeds 64 KiB"));}
 let req:Request=serde_json::from_slice(&data).map_err(|_|Error::new("invalid_input","Malformed rendering request"))?;
 for p in [&req.source,&req.destination] {if p.as_os_str().is_empty()||p.as_os_str().len()>16384 {return Err(Error::new("invalid_input","Paths require 1..16384 bytes"));}}
 if req.worksheet.as_ref().is_some_and(|s|s.len()>1024)||req.cancel_phase.as_deref().is_some_and(|s|!["snapshot","shared_strings","normalize_rows","verify_rows","rows_complete","index_rows","render_group","append_record","verify_output","before_publish","published"].contains(&s)) {return Err(Error::new("invalid_input","Invalid selector or cancellation checkpoint"));}
 let limits=req.tighten.limits()?;let reader_limits=req.reader_tighten.limits()?;let flag=Cell::new(req.pre_cancel);let cancelled=||flag.get();let mut phases=BTreeSet::new();
 let mut progress=|p:studio_revised_render::Progress| {phases.insert(p.phase.to_string());if req.cancel_phase.as_deref()==Some(p.phase) {flag.set(true);}};
 let control=Control::new(&cancelled,&mut progress);let receipt=studio_revised_render::render_to_txt(&req.source,&req.destination,req.converter,req.worksheet.as_deref(),&reader_limits,&limits,&control)?;drop(control);drop(progress);
 Ok(serde_json::json!({"status":"succeeded","receipt":receipt,"progress_phases":phases,"late_cancel_observed":flag.get()}))
}
fn main() {let (value,code)=match run() {Ok(value)=>(value,0),Err(error)=>(serde_json::json!({"status":"failed","error":error}),1)};println!("{}",value);std::process::exit(code)}
