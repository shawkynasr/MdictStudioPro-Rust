//! Publish the exact decoded stylesheet from an admitted reader's cached header.
//! This request is constructed by the native adapter, not deserialized from IPC.
use crate::{Error,ErrorCode,ImportJob,Progress,Result};
use serde::Serialize;
use std::{io::{Read,Write},path::PathBuf};
#[path="../../../m2/indexed-engine/src/sha256.rs"]mod sha256;
#[derive(Debug)]pub struct Request {pub destination:PathBuf,pub stylesheet:String,pub source_sha256:String}
impl Request {pub(crate) fn validate(&self)->crate::ApiResult<()> {
 if self.stylesheet.is_empty()||self.stylesheet.len()>65536||self.source_sha256.len()!=64||!self.source_sha256.bytes().all(|b|b.is_ascii_digit()||(b'a'..=b'f').contains(&b)) {
  return Err(crate::ApiError {code:crate::ApiCode::InvalidInput,message:"Require a nonempty stylesheet <=64 KiB and verified snapshot SHA-256".into()});
 }Ok(())
}}
#[derive(Debug,Serialize)]pub struct Receipt {pub profile:&'static str,pub destination:PathBuf,pub snapshot_source_sha256:String,pub stylesheet_sha256:String,pub bytes:usize,pub encoding:&'static str}
fn fail(code:ErrorCode,message:&str)->Error {Error {code,detail:"stylesheet_export",message:message.into(),limit:None}}
fn tick(job:&mut ImportJob<'_>,phase:&str)->Result<()> {
 if job.token.is_cancelled(){return Err(fail(ErrorCode::Cancelled,"Stylesheet export cancelled before publication"));}
 (job.progress)(Progress {job_id:job.id.into(),stage:studio_application::Stage::Publishing,phase:phase.into(),completed:1,total:1});
 if job.token.is_cancelled(){return Err(fail(ErrorCode::Cancelled,"Stylesheet export cancelled before publication"));}Ok(())
}
pub(crate) fn execute(r:&Request,job:&mut ImportJob<'_>)->Result<Receipt> {
 r.validate().map_err(|e|fail(ErrorCode::InvalidInput,&e.message))?;tick(job,"stylesheet_stage")?;
 match std::fs::symlink_metadata(&r.destination){Ok(_)=>return Err(fail(ErrorCode::DestinationExists,"Destination exists")),Err(e) if e.kind()==std::io::ErrorKind::NotFound=>{},Err(e)=>return Err(e.into())}
 let parent=r.destination.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(std::path::Path::new("."));
 let mut stage=tempfile::NamedTempFile::new_in(parent)?;stage.write_all(r.stylesheet.as_bytes())?;stage.flush()?;stage.as_file().sync_all()?;
 let mut actual=Vec::new();stage.reopen()?.take(65537).read_to_end(&mut actual)?;
 if actual!=r.stylesheet.as_bytes(){return Err(fail(ErrorCode::Integrity,"Staged stylesheet differs from the cached header"));}
 let mut hash=sha256::Sha256::new();hash.update(&actual);
 let receipt=Receipt {profile:"reader-stylesheet-utf8-v1",destination:r.destination.clone(),snapshot_source_sha256:r.source_sha256.clone(),stylesheet_sha256:sha256::hex(&hash.finish()),bytes:actual.len(),encoding:"utf-8"};
 tick(job,"stylesheet_commit")?;
 stage.persist_noclobber(&r.destination).map_err(|e|if e.error.kind()==std::io::ErrorKind::AlreadyExists{fail(ErrorCode::DestinationExists,"Destination exists")}else{Error::from(e.error)})?;
 Ok(receipt)
}
#[cfg(test)]mod tests {
 use super::*;use crate::CancellationToken;
 fn request(destination:PathBuf)->Request {Request {destination,stylesheet:"1\n<span title=\"字 & العربية\">\r\n</span>\n\n".into(),source_sha256:"a".repeat(64)}}
 #[test]fn exact_bytes_no_bom_no_added_newline_and_no_clobber() {
  let dir=tempfile::tempdir().unwrap();let r=request(dir.path().join("style.txt"));let token=CancellationToken::default();
  let receipt=execute(&r,&mut ImportJob::new("style",&token,&mut |_|{})).unwrap();assert_eq!(std::fs::read(&r.destination).unwrap(),r.stylesheet.as_bytes());assert_eq!(receipt.bytes,r.stylesheet.len());
  assert_eq!(execute(&r,&mut ImportJob::new("exists",&token,&mut |_|{})).unwrap_err().code,ErrorCode::DestinationExists);assert_eq!(std::fs::read(&r.destination).unwrap(),r.stylesheet.as_bytes());
 }
 #[test]fn cancellation_and_destination_races_never_replace_files() {
  for phase in ["stylesheet_stage","stylesheet_commit"] {
   let dir=tempfile::tempdir().unwrap();let r=request(dir.path().join("style.txt"));let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase==phase{stop.cancel();};
   assert_eq!(execute(&r,&mut ImportJob::new("cancel",&token,&mut progress)).unwrap_err().code,ErrorCode::Cancelled);assert!(!r.destination.exists());assert_eq!(std::fs::read_dir(dir.path()).unwrap().count(),0);
  }
  let dir=tempfile::tempdir().unwrap();let r=request(dir.path().join("style.txt"));let token=CancellationToken::default();let mut progress=|p:Progress|if p.phase=="stylesheet_commit"{std::fs::write(&r.destination,b"sentinel").unwrap();};
  assert_eq!(execute(&r,&mut ImportJob::new("race",&token,&mut progress)).unwrap_err().code,ErrorCode::DestinationExists);assert_eq!(std::fs::read(&r.destination).unwrap(),b"sentinel");
 }
}
