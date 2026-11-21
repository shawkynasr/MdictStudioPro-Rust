//! Shared admission wraps the accepted bounded index builder unchanged.
use crate::{ApiCode,ApiResult,error,Error,ImportJob,Result};
use serde::{Deserialize,Serialize};
use std::path::PathBuf;
use studio_indexed_engine::{Dictionary,Kind,Limits,index::{Index,Policy,BuildOptions,BuildReceipt}};
#[derive(Clone,Copy,Debug,Deserialize,Serialize)]#[serde(rename_all="snake_case")]pub enum DictionaryKind {Mdx,Mdd}
#[derive(Debug,Deserialize)]#[serde(deny_unknown_fields)]pub struct Request {
 pub source:PathBuf,pub destination:PathBuf,pub kind:DictionaryKind,pub policy:Policy,
 pub run_records:Option<usize>,pub run_bytes:Option<usize>,
}
impl Request {pub(crate) fn validate(&self)->ApiResult<()> {
 if matches!(self.kind,DictionaryKind::Mdd)&&self.policy!=Policy::RawExact {return Err(error(ApiCode::InvalidInput,"MDD index requires raw_exact"));}
 if self.run_records.is_some_and(|n|n==0||n>8192)||self.run_bytes.is_some_and(|n|n==0||n>2*1024*1024) {return Err(error(ApiCode::InvalidInput,"Index sort runs may only lower the qualified ceilings"));}Ok(())
}}
fn convert(e:studio_indexed_engine::Error)->Error {Error {code:e.code,detail:e.detail,message:e.message,limit:e.limit.map(|v|studio_large_io::LimitFailure {name:v.name,value:v.value,max:v.max})}}
pub(crate) fn execute(r:&Request,job:&mut ImportJob<'_>)->Result<BuildReceipt> {
 let options=BuildOptions {run_records:r.run_records.unwrap_or(8192),run_bytes:r.run_bytes.unwrap_or(2*1024*1024)};
 let mut native=studio_indexed_engine::ImportJob::new(job.id,job.token,&mut *job.progress);
 let dictionary=Dictionary::open_v2(&r.source,match r.kind {DictionaryKind::Mdx=>Kind::Mdx,DictionaryKind::Mdd=>Kind::Mdd},&Limits::default(),&mut native).map_err(convert)?;
 let receipt=Index::build(&dictionary,&r.destination,r.policy,options,&mut native).map_err(convert)?;
 drop(native);drop(dictionary);
 // Commit succeeded. Emit a notification without a cancellation check or new
 // validation; a late cancellation cannot revoke the returned publication.
 (job.progress)(crate::Progress {job_id:job.id.into(),stage:studio_application::Stage::Publishing,phase:"index_published".into(),completed:receipt.manifest.records as usize,total:receipt.manifest.records as usize});Ok(receipt)
}
