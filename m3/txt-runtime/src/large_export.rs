//! Explicit larger export via the M3 export-only streaming profile.
use crate::{Error,ImportJob,Result};
use serde::Deserialize;
use std::path::PathBuf;
#[derive(Clone,Copy,Debug,Deserialize)]#[serde(rename_all="snake_case")]pub enum Format {Txt,Jsonl}
#[derive(Debug,Deserialize)]#[serde(deny_unknown_fields)]pub struct Request {pub source:PathBuf,pub destination:PathBuf,pub format:Format}
pub(crate) fn execute(r:&Request,job:&mut ImportJob<'_>)->Result<studio_export_io::Summary> {
 let request=match r.format {
  Format::Txt=>studio_export_io::Request::ExportTxt {source:r.source.clone(),destination:r.destination.clone()},
  Format::Jsonl=>studio_export_io::Request::ExportJsonl {source:r.source.clone(),destination:r.destination.clone()},
 };
 studio_export_io::execute(&request,&studio_export_io::IoLimits::default(),&mut studio_export_io::ImportJob::new(job.id,job.token,&mut *job.progress))
  .map_err(|e|Error {code:e.code,detail:e.detail,message:e.message,limit:e.limit.map(|l|studio_large_io::LimitFailure {name:l.name,value:l.value,max:l.max})})
}
