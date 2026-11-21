//! Explicit qualified profiles composed into the unchanged serial publisher.
use crate::{ApiCode,ApiResult,Error,ErrorCode,ImportJob,Result,error};
use serde::{Deserialize,Serialize};
use std::path::{Path,PathBuf};
use studio_application::{ConverterId,Progress,Stage};
#[path="../../cc-runtime/src/converters.rs"]mod cc;
#[path="../../concise-runtime/src/converters.rs"]mod concise;
#[path="../../converter-runtime/src/converters.rs"]mod small;
pub use cc::Request as CcRequest;
pub use concise::Request as ConciseRequest;
pub use small::Request as SmallMoeRequest;
#[derive(Debug,Deserialize)]#[serde(deny_unknown_fields)]pub struct GroupedRequest {
 pub converter:studio_revised_render::Converter,pub input:PathBuf,pub destination:PathBuf,pub worksheet:Option<String>,
 #[serde(default)]pub tighten:studio_revised_render::Tighten,#[serde(default)]pub reader_tighten:studio_xlsx_spool::Tighten,
}
#[derive(Debug,Deserialize)]#[serde(tag="profile",content="request",rename_all="snake_case",deny_unknown_fields)]pub enum Request {Cc(CcRequest),Concise(ConciseRequest),SmallMoe(SmallMoeRequest),GroupedMoe(GroupedRequest)}
impl Request {
 pub fn input(&self)->&Path {match self {Self::Cc(r)=>&r.input,Self::Concise(r)=>&r.input,Self::SmallMoe(r)=>&r.input,Self::GroupedMoe(r)=>&r.input}}
 pub fn destination(&self)->&Path {match self {Self::Cc(r)=>&r.destination,Self::Concise(r)=>&r.destination,Self::SmallMoe(r)=>&r.destination,Self::GroupedMoe(r)=>&r.destination}}
 pub(crate) fn validate(&self)->ApiResult<()> {match self {
  Self::Cc(r)=>r.validate(),Self::Concise(r)=>r.validate(),
  Self::SmallMoe(r)=>{if !matches!(r.converter,ConverterId::MoeMini|ConverterId::MoeIdioms) {return Err(error(ApiCode::InvalidInput,"small_moe accepts Mini/Idioms only"));}r.validate()},
  Self::GroupedMoe(r)=>{if r.worksheet.as_ref().is_some_and(|s|s.len()>1024) {return Err(error(ApiCode::InvalidInput,"Worksheet selector exceeds 1 KiB"));}Ok(())},
 }}
}
#[derive(Debug,Serialize)]pub struct GroupedReceipt {
 pub pipeline_profile:&'static str,pub converter:studio_revised_render::Converter,pub source_sha256:String,
 pub input_rows:u64,pub groups:usize,pub skipped_rows:usize,pub entries:usize,pub primary_entries:usize,pub alias_redirects:usize,
 pub file_bytes:u64,pub decoded_bytes:usize,pub file_sha256:String,pub framed_records_sha256:String,pub key_bytes:usize,pub body_bytes:usize,
 pub index_charge_bytes:usize,pub largest_group_rows:usize,pub largest_group_input_bytes:usize,pub temporary_file_peak_bytes:u64,
 pub row_digest:studio_xlsx_spool::RowDigest,pub row_spool_bytes:u64,
}
impl From<studio_revised_render::Receipt> for GroupedReceipt {fn from(r:studio_revised_render::Receipt)->Self {Self {
 pipeline_profile:r.profile,converter:r.converter,source_sha256:r.source_sha256,input_rows:r.input_rows,groups:r.groups,skipped_rows:r.skipped_rows,
 entries:r.entries,primary_entries:r.primary_entries,alias_redirects:r.alias_redirects,file_bytes:r.file_bytes,decoded_bytes:r.decoded_bytes,file_sha256:r.file_sha256,
 framed_records_sha256:r.framed_records_sha256,key_bytes:r.key_bytes,body_bytes:r.body_bytes,index_charge_bytes:r.index_charge_bytes,
 largest_group_rows:r.largest_group_rows,largest_group_input_bytes:r.largest_group_input_bytes,temporary_file_peak_bytes:r.temporary_file_peak_bytes,
 row_digest:r.row_source.row_digest,row_spool_bytes:r.row_source.row_spool_bytes,
}}}
#[derive(Debug,Serialize)]#[serde(tag="profile",content="receipt",rename_all="snake_case")]pub enum Receipt {Cc(cc::Receipt),Concise(concise::Receipt),SmallMoe(small::Receipt),GroupedMoe(GroupedReceipt)}
fn grouped_error(e:studio_revised_render::Error)->Error {
 let code=match e.code {"invalid_input"=>ErrorCode::InvalidInput,"unsupported_policy"=>ErrorCode::UnsupportedPolicy,"limit_exceeded"=>ErrorCode::LimitExceeded,
 "cancelled"=>ErrorCode::Cancelled,"destination_exists"=>ErrorCode::DestinationExists,"integrity"=>ErrorCode::Integrity,"io"=>ErrorCode::Io,
 "invalid_encoding"=>ErrorCode::InvalidEncoding,"malformed_source"=>ErrorCode::MalformedSource,"unrepresentable_source"=>ErrorCode::UnrepresentableSource,
 "malformed_workbook"=>ErrorCode::MalformedWorkbook,"unsupported_workbook"=>ErrorCode::UnsupportedWorkbook,"unsupported_cell"=>ErrorCode::UnsupportedCell,
 "sheet_not_found"=>ErrorCode::SheetNotFound,_=>ErrorCode::Internal};Error {code,detail:"grouped_converter",message:e.message,limit:None}
}
pub(crate) fn execute(request:&Request,job:&mut ImportJob<'_>)->Result<Receipt> {
 match request {
  Request::Cc(r)=>cc::execute(r,job).map(Receipt::Cc),Request::Concise(r)=>concise::execute(r,job).map(Receipt::Concise),Request::SmallMoe(r)=>small::execute(r,job).map(Receipt::SmallMoe),
  Request::GroupedMoe(r)=>{
   let limits=r.tighten.limits().map_err(grouped_error)?;
   let reader_limits=r.reader_tighten.limits().map_err(|e|grouped_error(studio_revised_render::Error::new(e.code,e.message)))?;
   let token=job.token.clone();let cancelled=||token.is_cancelled();let id=job.id.to_owned();let sink=&mut *job.progress;
   let mut progress=|p:studio_revised_render::Progress| {let stage=match p.phase {"begin"|"snapshot"|"package_preflight"|"shared_strings"|"normalize_rows"|"verify_rows"|"rows_complete"=>Stage::ReadingWorkbook,"index_rows"|"render_group"=>Stage::Converting,_=>Stage::Publishing};sink(Progress {job_id:id.clone(),stage,phase:p.phase.into(),completed:p.completed,total:p.total});};
   let native=studio_revised_render::render_to_txt(&r.input,&r.destination,r.converter,r.worksheet.as_deref(),&reader_limits,&limits,&studio_revised_render::Control::new(&cancelled,&mut progress)).map_err(grouped_error)?;
   // The renderer committed. Move scalar/fixed-digest metadata only: no new
   // source/header validation, token check, hashing or fallible serialization.
   Ok(Receipt::GroupedMoe(native.into()))
  }
 }
}
