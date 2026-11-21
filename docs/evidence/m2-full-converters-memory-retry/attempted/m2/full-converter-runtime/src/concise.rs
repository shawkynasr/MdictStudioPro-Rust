//! Explicit full Concise owned profile; qualified converter sources stay unchanged.
use crate::{Error,ErrorCode,ImportJob,Result,ApiResult,ApiCode,error};
use serde::{Deserialize,Serialize};
use std::{fs::File,io::{Read,Write,Seek,SeekFrom},path::PathBuf};
use studio_application::{ConverterId,Progress,Stage};
#[path="../../indexed-engine/src/sha256.rs"]mod sha256;
use sha256::{Sha256,hex};
pub const PROFILE:&str="moe-concise-owned-v1";
#[derive(Debug,Default,Deserialize)]#[serde(deny_unknown_fields)]pub struct Tighten {pub input_bytes:Option<u64>,pub entries:Option<usize>,pub decoded_bytes:Option<usize>,pub output_bytes:Option<u64>,pub workbook_rows:Option<u32>,pub workbook_cells:Option<u64>,pub workbook_decoded_bytes:Option<usize>}
#[derive(Debug,Deserialize)]#[serde(deny_unknown_fields)]pub struct Request {pub converter:ConverterId,pub input:PathBuf,pub destination:PathBuf,pub worksheet:Option<String>,#[serde(default)]pub tighten:Tighten}
impl Request {pub(crate) fn validate(&self)->ApiResult<()> {if self.converter!=ConverterId::MoeConcise {return Err(error(ApiCode::InvalidInput,"This profile accepts only moe_concise"));}if self.worksheet.as_ref().is_some_and(|s|s.len()>1024) {return Err(error(ApiCode::InvalidInput,"Worksheet selector exceeds 1 KiB"));}Ok(())}}
#[derive(Debug,Serialize)]pub struct Receipt {pub profile:&'static str,pub converter:ConverterId,pub txt_profile:studio_application::TxtProfile,pub entries:usize,pub file_bytes:usize,pub metrics:studio_application::Metrics,pub comments_count:usize,pub source_sha256:String}
fn fail(code:ErrorCode,message:impl Into<String>)->Error {Error {code,detail:"converter",message:message.into(),limit:None}}
fn limits(t:&Tighten)->Result<(studio_application::Limits,u64)> {
 let mut l=studio_application::Limits::default();let mut input=32*1024*1024;
 l.dictionary.max_entries=100000;l.dictionary.max_decoded_bytes=32*1024*1024;l.dictionary.max_file_bytes=64*1024*1024;l.dictionary.max_source_lines=4_000_000;
 l.workbook.max_file_bytes=input;l.workbook.max_uncompressed_bytes=128*1024*1024;l.workbook.max_part_bytes=32*1024*1024;l.workbook.max_rows=50000;l.workbook.max_columns=64;l.workbook.max_cells=750000;l.workbook.max_decoded_bytes=32*1024*1024;
 l.moe.max_rows=50000;l.moe.max_input_bytes=48*1024*1024;l.moe.max_entries=100000;l.moe.max_output_bytes=32*1024*1024;
 macro_rules! lower {($v:expr,$field:expr)=>{if let Some(n)=$v {if n>$field {return Err(fail(ErrorCode::InvalidInput,"Converter ceilings may only be lowered"));}$field=n;}};}
 lower!(t.input_bytes,input);lower!(t.entries,l.dictionary.max_entries);lower!(t.decoded_bytes,l.dictionary.max_decoded_bytes);lower!(t.output_bytes,l.dictionary.max_file_bytes);lower!(t.workbook_rows,l.workbook.max_rows);lower!(t.workbook_cells,l.workbook.max_cells);lower!(t.workbook_decoded_bytes,l.workbook.max_decoded_bytes);
 l.workbook.max_file_bytes=input;Ok((l,input))
}
fn check(job:&ImportJob<'_>)->Result<()> {if job.token.is_cancelled() {return Err(fail(ErrorCode::Cancelled,"Converter cancelled before commit"));}Ok(())}
fn app_error(e:studio_application::Error)->Error {fail(e.code,e.message)}
pub(crate) fn execute(request:&Request,job:&mut ImportJob<'_>)->Result<Receipt> {
 check(job)?;if request.converter!=ConverterId::MoeConcise {return Err(fail(ErrorCode::InvalidInput,"This profile accepts only moe_concise"));}let(l,input_cap)=limits(&request.tighten)?;
 match std::fs::symlink_metadata(&request.destination) {Ok(_)=>return Err(fail(ErrorCode::DestinationExists,"Text destination exists")),Err(e) if e.kind()==std::io::ErrorKind::NotFound=>{},Err(e)=>return Err(e.into())}
 let mut input=File::open(&request.input)?;if !input.metadata()?.is_file() {return Err(fail(ErrorCode::InvalidInput,"Expected regular converter input"));}if input.metadata()?.len()>input_cap {return Err(fail(ErrorCode::LimitExceeded,"Converter input snapshot exceeds cap"));}
 let suffix=if request.converter==ConverterId::CcCedict {".txt"}else{".xlsx"};let mut snapshot=tempfile::Builder::new().prefix("studio-converter-").suffix(suffix).tempfile()?;let mut hash=Sha256::new();let mut bytes=0u64;let mut buf=[0;65536];
 loop {check(job)?;(job.progress)(Progress {job_id:job.id.into(),stage:if request.converter==ConverterId::CcCedict {Stage::Converting}else{Stage::ReadingWorkbook},phase:"input_snapshot".into(),completed:bytes as usize,total:input_cap as usize});check(job)?;let n=input.read(&mut buf)?;if n==0 {break;}bytes+=n as u64;if bytes>input_cap {return Err(fail(ErrorCode::LimitExceeded,"Converter input grew beyond snapshot cap"));}snapshot.write_all(&buf[..n])?;hash.update(&buf[..n]);}
 snapshot.flush()?;snapshot.seek(SeekFrom::Start(0))?;let source_sha256=hex(&hash.finish());let native=studio_application::ConversionRequest {converter:request.converter,input:snapshot.path().into(),worksheet:request.worksheet.clone()};
 let result=studio_application::convert(&native,&l,&mut studio_application::JobContext::new(job.id,job.token,&mut *job.progress)).map_err(app_error)?;
 let entries=result.entries.len();let comments_count=result.comments.len();
 let file_bytes=crate::txt::write_verified(&result.entries,&request.destination,&l,job)?;
 // Commit succeeded. Move prepared metadata; no later cancellation or validation.
 Ok(Receipt {profile:PROFILE,converter:result.converter,txt_profile:result.txt_profile,entries,file_bytes,metrics:result.metrics,comments_count,source_sha256})
}

#[cfg(test)]mod tests {
 use super::*;
 #[test]fn measured_concise_shape_fits_without_output_ceiling_changes() {
  let (l,input)=limits(&Tighten::default()).unwrap();
  assert_eq!(l.workbook.max_rows,50000);assert_eq!(l.moe.max_rows,50000);assert_eq!(l.workbook.max_cells,750000);
  assert!(45179<=l.workbook.max_rows&&677685<=l.workbook.max_cells);
  assert_eq!(input,32*1024*1024);assert_eq!(l.dictionary.max_entries,100000);
  assert_eq!(l.dictionary.max_decoded_bytes,32*1024*1024);assert_eq!(l.dictionary.max_file_bytes,64*1024*1024);
  assert_eq!(l.workbook.max_part_bytes,32*1024*1024);assert_eq!(l.workbook.max_decoded_bytes,32*1024*1024);
 }
 #[test]fn ceilings_only_lower_and_do_not_grow_through_options() {
  for t in [Tighten {workbook_rows:Some(50001),..Default::default()},Tighten {workbook_cells:Some(750001),..Default::default()},Tighten {entries:Some(100001),..Default::default()}] {assert!(matches!(limits(&t),Err(e) if e.code==ErrorCode::InvalidInput));}
  let (l,_)=limits(&Tighten {workbook_rows:Some(10),workbook_cells:Some(100),..Default::default()}).unwrap();assert_eq!(l.workbook.max_rows,10);assert_eq!(l.workbook.max_cells,100);
 }
 #[test]fn other_converters_cannot_select_this_profile() {
  for converter in ["cc_cedict","moe_mini","moe_idioms","moe_revised","moe_revised_wfg"] {
   let r:Request=serde_json::from_value(serde_json::json!({"converter":converter,"input":"input.xlsx","destination":"output.txt"})).unwrap();assert_eq!(r.validate().unwrap_err().code,ApiCode::InvalidInput);
  }
 }
}

// The reference writer test must use the same bounded profile as this adapter.
#[cfg(test)]pub(crate) fn reference_limits()->studio_application::Limits {limits(&Tighten::default()).unwrap().0}
