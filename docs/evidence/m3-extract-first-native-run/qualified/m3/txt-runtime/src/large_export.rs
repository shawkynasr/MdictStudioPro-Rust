//! Explicit larger MDX export using the accepted CC I/O profile, not raised caps.
use crate::{Error,ImportJob,Result};
use serde::Deserialize;
use std::path::PathBuf;
#[derive(Clone,Copy,Debug,Deserialize)]#[serde(rename_all="snake_case")]pub enum Format {Txt,Jsonl}
#[derive(Debug,Deserialize)]#[serde(deny_unknown_fields)]pub struct Request {pub source:PathBuf,pub destination:PathBuf,pub format:Format}
pub(crate) fn execute(r:&Request,job:&mut ImportJob<'_>)->Result<studio_cc_pack_io::Summary> {
 let request=match r.format {
  Format::Txt=>studio_cc_pack_io::Request::ExportTxt {source:r.source.clone(),destination:r.destination.clone()},
  Format::Jsonl=>studio_cc_pack_io::Request::ExportJsonl {source:r.source.clone(),destination:r.destination.clone()},
 };
 studio_cc_pack_io::execute(&request,&studio_cc_pack_io::IoLimits::default(),&mut studio_cc_pack_io::ImportJob::new(job.id,job.token,&mut *job.progress))
  .map_err(|e|Error {code:e.code,detail:e.detail,message:e.message,limit:e.limit.map(|l|studio_large_io::LimitFailure {name:l.name,value:l.value,max:l.max})})
}
