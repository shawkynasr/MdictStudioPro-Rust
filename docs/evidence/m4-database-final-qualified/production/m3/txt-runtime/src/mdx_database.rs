//! MDX -> verified private JSONL -> staged SQLite, under one shared job lease.
use crate::{Error,ErrorCode,ImportJob,Progress,Result};
use serde::Deserialize;
use std::{fs,io::{BufRead,BufReader,Read},path::Path};
fn fail(code:ErrorCode,message:impl Into<String>)->Error {Error {code,detail:"mdx_to_db",message:message.into(),limit:None}}
fn tick(job:&mut ImportJob<'_>,completed:usize,total:usize)->Result<()> {
 if job.token.is_cancelled(){return Err(fail(ErrorCode::Cancelled,"MDX database import cancelled"));}
 (job.progress)(Progress {job_id:job.id.into(),stage:studio_application::Stage::Converting,phase:"mdx_to_db_decode".into(),completed,total});
 if job.token.is_cancelled(){return Err(fail(ErrorCode::Cancelled,"MDX database import cancelled"));}Ok(())
}
#[cfg(test)]mod tests {
 use super::*;use crate::CancellationToken;use std::collections::BTreeMap;
 #[test]fn mdx_to_database_preserves_decoded_header_and_duplicate_bodies_and_cancels() {
  for encoding in [studio_core::Encoding::Utf8,studio_core::Encoding::Utf16] {
   let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.jsonl");let mdx=dir.path().join("source.mdx");let db=dir.path().join("result.db");
   fs::write(&source,"{\"key\":\"字\",\"text\":\"`2`blue\\n\\n\"}\n{\"key\":\"字\",\"text\":\"second\"}\n").unwrap();let token=CancellationToken::default();
   let made=studio_large_io::execute(&studio_large_io::Request::PackMdx{source,destination:mdx.clone(),encoding,metadata:studio_large_io::Metadata{title:"字 / العربية".into(),description:"description & <b>HTML</b>".into(),stylesheet:"2\n<span style=\"color:blue\">\n</span>\n".into(),extra:BTreeMap::from([("Creator".into(),"Studio fixture".into())])}},&studio_large_io::IoLimits::default(),&mut studio_large_io::ImportJob::new("pack",&token,&mut |_|{})).unwrap();
   let before=fs::read(&mdx).unwrap();let receipt=execute(&mdx,&db,&mut ImportJob::new("db",&token,&mut |_|{})).unwrap();assert_eq!(receipt.records,2);assert_eq!(receipt.dictionary_metadata.as_ref(),Some(&made.metadata));
   let rebuilt=dir.path().join("rebuilt.mdx");let rebuilt_receipt=crate::database_mdx::execute(&db,&rebuilt,&mut ImportJob::new("rebuild",&token,&mut |_|{})).unwrap();assert_eq!(rebuilt_receipt.dictionary_metadata,made.metadata);
   let back=dir.path().join("back.db");let back_receipt=execute(&rebuilt,&back,&mut ImportJob::new("back",&token,&mut |_|{})).unwrap();assert_eq!(back_receipt.rows_sha256,receipt.rows_sha256);assert_eq!(back_receipt.dictionary_metadata,receipt.dictionary_metadata);
   let studio_database::Response::Browse(page)=studio_database::execute(&studio_database::Request::Browse{source:db.clone(),offset:0,limit:2},&mut studio_database::Job::new(&token,&mut |_|{})).unwrap()else{panic!()};assert_eq!(page.rows[0].text,"`2`blue\n\n");assert_eq!(page.rows[1].text,"second");
   let existing=fs::read(&db).unwrap();assert_eq!(execute(&mdx,&db,&mut ImportJob::new("exists",&token,&mut |_|{})).unwrap_err().code,ErrorCode::DestinationExists);assert_eq!(fs::read(&db).unwrap(),existing);
   for phase in ["mdx_to_db_decode","database_commit"] {
    let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase==phase{stop.cancel();};let dest=dir.path().join(format!("cancel-{phase}.db"));assert_eq!(execute(&mdx,&dest,&mut ImportJob::new("cancel",&token,&mut progress)).unwrap_err().code,ErrorCode::Cancelled);assert!(!dest.exists());
   }
   let invalid=dir.path().join("invalid.mdx");fs::write(&invalid,b"invalid").unwrap();let dest=dir.path().join("invalid.db");assert!(execute(&invalid,&dest,&mut ImportJob::new("bad",&token,&mut |_|{})).is_err());assert!(!dest.exists());assert_eq!(fs::read(mdx).unwrap(),before);
  }
 }
}
#[derive(Deserialize)]#[serde(deny_unknown_fields)]struct Row {key:String,text:String}
pub(crate) fn execute(source:&Path,destination:&Path,job:&mut ImportJob<'_>)->Result<studio_database::Publication> {
 match fs::symlink_metadata(destination){Ok(_)=>return Err(fail(ErrorCode::DestinationExists,"Destination exists")),Err(e) if e.kind()==std::io::ErrorKind::NotFound=>{},Err(e)=>return Err(e.into())}
 if !fs::symlink_metadata(source)?.file_type().is_file(){return Err(fail(ErrorCode::InvalidInput,"Require a regular non-symlink MDX source"));}
 let work=tempfile::tempdir()?;let jsonl=work.path().join("entries.jsonl");
 let verified=studio_large_io::execute(&studio_large_io::Request::ExportJsonl {source:source.to_owned(),destination:jsonl.clone()},&studio_large_io::IoLimits::default(),&mut studio_large_io::ImportJob::new(job.id,job.token,&mut *job.progress))?;
 let mut input=BufReader::new(fs::File::open(&jsonl)?);let mut rows=Vec::new();let(mut key_bytes,mut body_bytes)=(0u64,0u64);
 loop {
  tick(job,rows.len(),verified.records)?;let mut line=Vec::new();let cap=6*(1024*1024+4096)+128;
  let n=(&mut input).take((cap+1) as u64).read_until(b'\n',&mut line)?;if n==0{break;}
  if n>cap||line.last()!=Some(&b'\n'){return Err(fail(ErrorCode::LimitExceeded,"JSONL line exceeds bounded profile or lacks final LF"));}
  let row:Row=serde_json::from_slice(&line).map_err(|e|fail(ErrorCode::InvalidInput,e.to_string()))?;
  key_bytes+=row.key.len() as u64;body_bytes+=row.text.len() as u64;
  if rows.len()>=100000||row.key.len()>4096||row.text.len()>1024*1024||key_bytes+body_bytes>32*1024*1024{return Err(fail(ErrorCode::LimitExceeded,"MDX database profile exceeded"));}
  rows.push(studio_core::Entry {key:row.key,text:row.text});
 }
 if rows.len()!=verified.records||key_bytes!=verified.key_bytes||body_bytes!=verified.payload_bytes{return Err(fail(ErrorCode::Integrity,"Private export and decoded rows disagree"));}
 let id=job.id;let token=job.token;
 let mut progress=|p:studio_database::Progress|(job.progress)(Progress {job_id:id.into(),stage:if p.phase=="database_commit"{studio_application::Stage::Publishing}else{studio_application::Stage::Converting},phase:p.phase.into(),completed:p.completed,total:p.total});
 studio_database::import_mdx_rows(&rows,destination,&verified.source_sha256,&verified.metadata,&mut studio_database::Job::new(token,&mut progress)).map_err(crate::database::mapped)
}
