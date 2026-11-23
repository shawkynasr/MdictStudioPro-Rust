//! Explicit larger export via the M3 export-only streaming profile.
use crate::{Error,ImportJob,Result};
use serde::Deserialize;
use std::path::PathBuf;
#[derive(Clone,Copy,Debug,Deserialize)]#[serde(rename_all="snake_case")]pub enum Format {Txt,Jsonl}
#[derive(Debug,Deserialize)]#[serde(deny_unknown_fields)]pub struct Request {pub source:PathBuf,pub destination:PathBuf,pub format:Format,#[serde(default)]pub profile:studio_export_io::ExportProfile}
pub(crate) fn execute(r:&Request,job:&mut ImportJob<'_>)->Result<studio_export_io::Summary> {
 let request=match r.format {
  Format::Txt=>studio_export_io::Request::ExportTxt {source:r.source.clone(),destination:r.destination.clone()},
  Format::Jsonl=>studio_export_io::Request::ExportJsonl {source:r.source.clone(),destination:r.destination.clone()},
 };
 studio_export_io::execute_profile(&request,&studio_export_io::IoLimits::for_profile(r.profile),r.profile,&mut studio_export_io::ImportJob::new(job.id,job.token,&mut *job.progress))
  .map_err(|e|Error {code:e.code,detail:e.detail,message:e.message,limit:e.limit.map(|l|studio_large_io::LimitFailure {name:l.name,value:l.value,max:l.max})})
}

#[cfg(test)]mod tests {
 use super::*;
 #[test]fn explicit_profile_is_validated_and_old_requests_keep_96_mib() {
  let mut value=serde_json::json!({"source":"source.mdx","destination":"output.jsonl","format":"jsonl"});
  let default:Request=serde_json::from_value(value.clone()).unwrap();
  assert!(matches!(default.profile,studio_export_io::ExportProfile::Large));
  value["profile"]=serde_json::json!("extended");
  let extended:Request=serde_json::from_value(value.clone()).unwrap();
  assert!(matches!(extended.profile,studio_export_io::ExportProfile::Extended));
  value["profile"]=serde_json::json!("unlimited");assert!(serde_json::from_value::<Request>(value).is_err());
 }
}
