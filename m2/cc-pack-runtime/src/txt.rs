//! Canonical TXT publication without a whole-file buffer or second entries vec.
use crate::{Error,ErrorCode,ImportJob,Result};
use std::{fs::File,io::{BufReader,BufWriter,Read,Write},path::Path};
use studio_application::{Entry,Limits,Progress,Stage};
const CHUNK:usize=65536;
fn fail(code:ErrorCode,message:&str)->Error {Error {code,detail:"chunked_txt",message:message.into(),limit:None}}
fn check(job:&ImportJob<'_>)->Result<()> {if job.token.is_cancelled() {return Err(fail(ErrorCode::Cancelled,"TXT publication cancelled before commit"));}Ok(())}
fn progress(job:&mut ImportJob<'_>,phase:&str,completed:usize,total:usize)->Result<()> {
 check(job)?;(job.progress)(Progress {job_id:job.id.into(),stage:Stage::Publishing,phase:phase.into(),completed,total});check(job)
}
fn sum(a:usize,b:usize)->Result<usize> {a.checked_add(b).ok_or_else(||fail(ErrorCode::LimitExceeded,"TXT counter overflow"))}
fn validate(entries:&[Entry],limits:&Limits,job:&ImportJob<'_>)->Result<usize> {
 let l=&limits.dictionary;let mut bytes=0;let mut decoded=0;let mut lines=0;
 if entries.is_empty() {return Err(fail(ErrorCode::InvalidInput,"No entries to publish"));}
 if entries.len()>l.max_entries {return Err(fail(ErrorCode::LimitExceeded,"TXT entry cap exceeded"));}
 for(i,e)in entries.iter().enumerate() {
  check(job)?;
  if e.key.is_empty()||e.key=="</>"||e.key.contains(['\0','\r','\n'])||(i==0&&e.key.starts_with('\u{feff}'))||e.text.contains(['\0','\r'])||e.text.split('\n').any(|line|line=="</>") {return Err(fail(ErrorCode::UnrepresentableSource,"Unrepresentable canonical TXT record"));}
  if e.key.len()>l.max_key_bytes||e.text.len()>l.max_entry_bytes {return Err(fail(ErrorCode::LimitExceeded,"TXT per-record cap exceeded"));}
  decoded=sum(decoded,sum(e.key.len(),e.text.len())?)?;bytes=sum(bytes,sum(sum(e.key.len(),e.text.len())?,6)?)?;
  lines=sum(lines,sum(e.text.bytes().filter(|b|*b==b'\n').count(),3)?)?;
  if decoded>l.max_decoded_bytes||bytes as u64>l.max_file_bytes||lines>l.max_source_lines {return Err(fail(ErrorCode::LimitExceeded,"TXT aggregate cap exceeded"));}
 }Ok(bytes)
}
fn segments(e:&Entry)->[&str;4] {[e.key.as_str(),"\n",e.text.as_str(),"\n</>\n"]}
pub(crate) fn write_verified(entries:&[Entry],destination:&Path,limits:&Limits,job:&mut ImportJob<'_>)->Result<usize> {
 check(job)?;
 match std::fs::symlink_metadata(destination) {Ok(_)=>return Err(fail(ErrorCode::DestinationExists,"TXT destination exists")),Err(e) if e.kind()==std::io::ErrorKind::NotFound=>{},Err(e)=>return Err(e.into())}
 let file_bytes=validate(entries,limits,job)?;let parent=destination.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new("."));
 let mut temporary=tempfile::NamedTempFile::new_in(parent)?;
 {
  let mut output=BufWriter::with_capacity(CHUNK,temporary.as_file_mut());
  for(i,entry)in entries.iter().enumerate() {
   if i%256==0 {progress(job,"stream_write",i,entries.len())?;}
   for segment in segments(entry) {for chunk in segment.as_bytes().chunks(CHUNK) {check(job)?;output.write_all(chunk)?;}}
  }output.flush()?;
 }
 temporary.as_file().sync_all()?;progress(job,"stream_verify",0,entries.len())?;
 let mut actual=BufReader::with_capacity(CHUNK,File::open(temporary.path())?);let mut buffer=[0u8;CHUNK];let mut verified=0usize;
 for(i,entry)in entries.iter().enumerate() {
  if i>0&&i%256==0 {progress(job,"stream_verify",i,entries.len())?;}
  for segment in segments(entry) {for expected in segment.as_bytes().chunks(CHUNK) {
   check(job)?;actual.read_exact(&mut buffer[..expected.len()])?;
   if &buffer[..expected.len()]!=expected {return Err(fail(ErrorCode::Integrity,"TXT differs after reopen"));}verified=sum(verified,expected.len())?;
  }}
 }
 check(job)?;let mut extra=[0];if actual.read(&mut extra)?!=0||verified!=file_bytes {return Err(fail(ErrorCode::Integrity,"TXT extent differs after reopen"));}drop(actual);
 progress(job,"before_publish",entries.len(),entries.len())?;
 temporary.persist_noclobber(destination).map_err(|e|if e.error.kind()==std::io::ErrorKind::AlreadyExists {fail(ErrorCode::DestinationExists,"TXT destination appeared before commit")}else{Error::from(e.error)})?;
 // Commit succeeded: no later token check or fallible validation.
 (job.progress)(Progress {job_id:job.id.into(),stage:Stage::Publishing,phase:"published".into(),completed:entries.len(),total:entries.len()});Ok(file_bytes)
}

#[cfg(test)]mod tests {
 use super::*;use crate::CancellationToken;
 fn rows()->Vec<Entry> {vec![Entry {key:"字".into(),text:"line\n".into()},Entry {key:"字".into(),text:String::new()},Entry {key:"مرحبا".into(),text:"body".into()}]}
 #[test]fn canonical_bytes_preserve_duplicates_empty_body_unicode_and_trailing_newline() {
  let dir=tempfile::tempdir().unwrap();let path=dir.path().join("out.txt");let token=CancellationToken::default();let mut cb=|_|{};let n=write_verified(&rows(),&path,&Limits::default(),&mut ImportJob::new("bytes",&token,&mut cb)).unwrap();let expected="字\nline\n\n</>\n字\n\n</>\nمرحبا\nbody\n</>\n";assert_eq!(std::fs::read(&path).unwrap(),expected.as_bytes());assert_eq!(n,expected.len());assert_eq!(std::fs::read_dir(dir.path()).unwrap().count(),1);
 }
 #[test]fn cancellation_at_each_precommit_checkpoint_removes_temporary_output() {
  for phase in ["stream_write","stream_verify","before_publish"] {let dir=tempfile::tempdir().unwrap();let path=dir.path().join("out.txt");let token=CancellationToken::default();let t=token.clone();let mut cb=move|p:Progress|if p.phase==phase {t.cancel();};let e=write_verified(&rows(),&path,&Limits::default(),&mut ImportJob::new("cancel",&token,&mut cb)).unwrap_err();assert_eq!(e.code,ErrorCode::Cancelled);assert!(!path.exists());assert_eq!(std::fs::read_dir(dir.path()).unwrap().count(),0);}
 }
 #[test]fn reopen_corruption_refuses_and_postcommit_cancel_keeps_success() {
  let dir=tempfile::tempdir().unwrap();let path=dir.path().join("out.txt");let token=CancellationToken::default();let mut corrupted=false;let mut cb=|p:Progress|if p.phase=="stream_verify"&&!corrupted {let tmp=std::fs::read_dir(dir.path()).unwrap().next().unwrap().unwrap().path();let mut bytes=std::fs::read(&tmp).unwrap();bytes[0]^=1;std::fs::write(tmp,bytes).unwrap();corrupted=true;};let e=write_verified(&rows(),&path,&Limits::default(),&mut ImportJob::new("bad",&token,&mut cb)).unwrap_err();assert_eq!(e.code,ErrorCode::Integrity);assert!(!path.exists());assert_eq!(std::fs::read_dir(dir.path()).unwrap().count(),0);
  let t=token.clone();let mut cb=move|p:Progress|if p.phase=="published" {t.cancel();};write_verified(&rows(),&path,&Limits::default(),&mut ImportJob::new("late",&token,&mut cb)).unwrap();assert!(token.is_cancelled()&&path.exists());
 }
 #[test]fn lower_caps_and_unrepresentable_body_refuse_before_publication() {
  let dir=tempfile::tempdir().unwrap();let path=dir.path().join("out.txt");let token=CancellationToken::default();let mut cb=|_|{};let mut limits=Limits::default();limits.dictionary.max_file_bytes=4;let e=write_verified(&rows(),&path,&limits,&mut ImportJob::new("cap",&token,&mut cb)).unwrap_err();assert_eq!(e.code,ErrorCode::LimitExceeded);
  let bad=vec![Entry {key:"word".into(),text:"one\n</>\ntwo".into()}];let e=write_verified(&bad,&path,&Limits::default(),&mut ImportJob::new("grammar",&token,&mut cb)).unwrap_err();assert_eq!(e.code,ErrorCode::UnrepresentableSource);assert!(!path.exists());assert_eq!(std::fs::read_dir(dir.path()).unwrap().count(),0);
 }
}
