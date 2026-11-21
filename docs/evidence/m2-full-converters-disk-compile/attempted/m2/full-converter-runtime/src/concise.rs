//! Disk-backed Concise profile; accepted standalone sources stay unchanged.
use crate::{Error,ErrorCode,ImportJob,Result,ApiResult,ApiCode,error};
use serde::{Deserialize,Serialize};
use std::path::PathBuf;
use studio_application::{ConverterId,Progress,Stage};
pub const PROFILE:&str="moe-concise-disk-groups-txt-v1";
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
fn disk_error(e:crate::concise_disk::Error)->Error {fail(match e.code {
 "cancelled"=>ErrorCode::Cancelled,"limit_exceeded"=>ErrorCode::LimitExceeded,"invalid_input"=>ErrorCode::InvalidInput,"destination_exists"=>ErrorCode::DestinationExists,"integrity"=>ErrorCode::Integrity,"io"=>ErrorCode::Io,"malformed_workbook"=>ErrorCode::MalformedWorkbook,"unsupported_workbook"=>ErrorCode::UnsupportedWorkbook,"unsupported_cell"=>ErrorCode::UnsupportedCell,"sheet_not_found"=>ErrorCode::SheetNotFound,"malformed_source"=>ErrorCode::MalformedSource,"invalid_encoding"=>ErrorCode::InvalidEncoding,"unrepresentable_source"=>ErrorCode::UnrepresentableSource,"unsupported_policy"=>ErrorCode::UnsupportedPolicy,_=>ErrorCode::Internal},e.message)}
pub(crate) fn execute(request:&Request,job:&mut ImportJob<'_>)->Result<Receipt> {
 check(job)?;request.validate().map_err(|e|fail(ErrorCode::InvalidInput,e.message))?;let(l,input_cap)=limits(&request.tighten)?;
 let reader=studio_xlsx_spool::Limits {input_bytes:input_cap,part_bytes:l.workbook.max_part_bytes as u64,expanded_bytes:l.workbook.max_uncompressed_bytes as u64,rows:l.workbook.max_rows,columns:l.workbook.max_columns,cells:l.workbook.max_cells,normalized_bytes:l.moe.max_input_bytes.min(l.workbook.max_decoded_bytes),..Default::default()};
 let renderer=crate::concise_disk::Limits {entries:l.dictionary.max_entries,groups:l.dictionary.max_entries,decoded_bytes:l.dictionary.max_decoded_bytes,output_bytes:l.dictionary.max_file_bytes,..Default::default()};
 let token=job.token.clone();let cancelled=||token.is_cancelled();let id=job.id.to_owned();let sink=&mut *job.progress;
 let mut progress=|p:crate::concise_disk::Progress| {let stage=match p.phase {"index_rows"|"render_group"=>Stage::Converting,"append_record"|"verify_output"|"before_publish"|"published"=>Stage::Publishing,_=>Stage::ReadingWorkbook};sink(Progress {job_id:id.clone(),stage,phase:p.phase.into(),completed:p.completed,total:p.total});};
 let result=crate::concise_disk::render_to_txt(&request.input,&request.destination,crate::concise_disk::Converter::Concise,request.worksheet.as_deref(),&reader,&renderer,&crate::concise_disk::Control::new(&cancelled,&mut progress)).map_err(disk_error)?;
 // The disk renderer committed; move prepared thin metadata without new checks.
 Ok(Receipt {profile:PROFILE,converter:request.converter,txt_profile:studio_application::TxtProfile::CanonicalV1,entries:result.entries,file_bytes:result.file_bytes as usize,metrics:studio_application::Metrics {primary_entries:result.primary_entries,alias_redirects:result.alias_redirects,traditional_entries:0,skipped_rows_or_lines:result.skipped_rows},comments_count:0,source_sha256:result.source_sha256})
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
