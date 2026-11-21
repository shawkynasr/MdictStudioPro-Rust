//! Explicit exclusive block-spooled MDX packing profile.
use crate::{ApiCode,ApiResult,error,Error,ImportJob,Result};
use serde::Deserialize;
use std::path::PathBuf;
#[derive(Debug,Deserialize)]#[serde(deny_unknown_fields)]pub struct Request {
 pub source:PathBuf,pub destination:PathBuf,pub encoding:studio_cc_pack_io::Encoding,pub metadata:studio_cc_pack_io::Metadata,
 #[serde(default)]pub tighten:studio_cc_pack_io::Tighten,
}
impl Request {pub(crate) fn metadata_bytes(&self)->ApiResult<usize> {
 if self.metadata.extra.len()>256 {return Err(error(ApiCode::InvalidInput,"At most 256 extra attributes"));}
 let mut n=self.metadata.title.len().saturating_add(self.metadata.description.len()).saturating_add(self.metadata.stylesheet.len());for(k,v)in &self.metadata.extra {n=n.saturating_add(k.len()).saturating_add(v.len());}
 if n>65536 {return Err(error(ApiCode::InvalidInput,"CC metadata exceeds 64 KiB"));}Ok(n)
}}
fn convert(e:studio_cc_pack_io::Error)->Error {Error {code:e.code,detail:e.detail,message:e.message,limit:e.limit.map(|v|studio_large_io::LimitFailure {name:v.name,value:v.value,max:v.max})}}
pub(crate) fn execute(r:&Request,job:&mut ImportJob<'_>)->Result<studio_cc_pack_io::Summary> {
 let limits=r.tighten.limits().map_err(convert)?;let request=studio_cc_pack_io::Request::PackMdx {source:r.source.clone(),destination:r.destination.clone(),encoding:r.encoding,metadata:r.metadata.clone()};
 let receipt=studio_cc_pack_io::execute(&request,&limits,&mut studio_cc_pack_io::ImportJob::new(job.id,job.token,&mut *job.progress)).map_err(convert)?;
 // Native operation committed; no new checks or cancellation after success.
 (job.progress)(crate::Progress {job_id:job.id.into(),stage:studio_application::Stage::Publishing,phase:"cc_pack_published".into(),completed:receipt.records,total:receipt.records});Ok(receipt)
}
