//! Streaming TXT -> private JSONL -> existing MDX packer, under one lease/job.
use crate::{Error,ErrorCode,ImportJob,Result,Progress};
use serde::{Deserialize,Serialize};
use std::{fs::File,io::{BufRead,BufReader,Write,Seek,SeekFrom},path::PathBuf};
#[path="../../../m2/indexed-engine/src/sha256.rs"]mod sha256;
const INPUT_CAP:u64=128*1024*1024;
const LINE_CAP:usize=1024*1024+3;
const LINE_COUNT:usize=8_000_000;
#[derive(Clone,Copy,Debug,Deserialize,Serialize,PartialEq,Eq)]
#[serde(rename_all="snake_case")]pub enum Profile {CanonicalV1,LegacyBodySpanV1}
#[derive(Clone,Copy,Debug,Deserialize,Serialize)]
#[serde(rename_all="snake_case")]pub enum Packing {Bounded,Block}
#[derive(Debug,Deserialize)]#[serde(deny_unknown_fields)]pub struct Request {
 pub source:PathBuf,pub destination:PathBuf,pub encoding:studio_cc_pack_io::Encoding,
 pub metadata:studio_large_io::Metadata,pub profile:Profile,pub packing:Packing,
}
#[derive(Debug,Serialize)]#[serde(tag="kind",content="receipt",rename_all="snake_case")]
pub enum Packed {Bounded(studio_large_io::Summary),Block(studio_cc_pack_io::Summary)}
#[derive(Debug,Serialize)]pub struct Receipt {
 pub source_format:&'static str,pub source_profile:Profile,pub source_sha256:String,
 pub input_bytes:u64,pub records:usize,pub packing:Packed,
}
struct Prepared {file:tempfile::NamedTempFile,digest:String,bytes:u64,records:usize}
fn fail(code:ErrorCode,line:usize,message:impl Into<String>)->Error {Error {code,detail:"txt_source",message:format!("Line {line}: {}",message.into()),limit:None}}
fn invalid(line:usize,message:&str)->Error {fail(ErrorCode::InvalidInput,line,message)}
fn limit(line:usize,message:&str)->Error {fail(ErrorCode::LimitExceeded,line,message)}
fn check(job:&ImportJob<'_>)->Result<()> {if job.token.is_cancelled() {Err(fail(ErrorCode::Cancelled,0,"TXT build cancelled before commit"))}else{Ok(())}}
fn progress(job:&mut ImportJob<'_>,phase:&str,done:usize,total:usize)->Result<()> {
 check(job)?;(job.progress)(Progress {job_id:job.id.into(),stage:studio_application::Stage::Converting,phase:phase.into(),completed:done,total});check(job)
}
// Bounded even when an input has no line breaks. Hash each byte exactly once,
// including the optional UTF-8 BOM and original CRLF separators.
fn line(reader:&mut impl BufRead,hash:&mut sha256::Sha256,bytes:&mut u64,job:&ImportJob<'_>,number:usize)->Result<Option<Vec<u8>>> {
 let mut out=Vec::new();
 loop {
  check(job)?;let buf=reader.fill_buf()?;
  if buf.is_empty() {return Ok(if out.is_empty(){None}else{Some(out)});}
  let n=buf.iter().position(|b|*b==b'\n').map_or(buf.len(),|p|p+1);
  if out.len()+n>LINE_CAP || *bytes+n as u64>INPUT_CAP {return Err(limit(number,"TXT input or line exceeds profile"));}
  out.extend_from_slice(&buf[..n]);hash.update(&buf[..n]);*bytes+=n as u64;reader.consume(n);
  if out.last()==Some(&b'\n') {return Ok(Some(out));}
 }
}
fn prepare(request:&Request,job:&mut ImportJob<'_>)->Result<Prepared> {
 check(job)?;let file=File::open(&request.source)?;let meta=file.metadata()?;
 if !meta.is_file() {return Err(invalid(0,"Expected a regular TXT source"));}
 if meta.len()>INPUT_CAP {return Err(limit(0,"TXT input exceeds 128 MiB"));}
 let (max_records,max_decoded)=match request.packing {Packing::Bounded=>(100000,32*1024*1024),Packing::Block=>(250000,96*1024*1024)};
 let mut input=BufReader::with_capacity(65536,file);let mut hash=sha256::Sha256::new();let mut bytes=0;
 let mut output=tempfile::NamedTempFile::new()?;let mut spool_bytes=0u64;
 let(mut head,mut body,mut body_lines,mut records,mut decoded,mut number)=(None::<String>,String::new(),0usize,0usize,0usize,0usize);
 progress(job,"txt_prepare",0,meta.len() as usize)?;
 while let Some(raw)=line(&mut input,&mut hash,&mut bytes,job,number+1)? {
  number+=1;if number>LINE_COUNT {return Err(limit(number,"TXT source exceeds 8 million lines"));}
  if number%256==0 {progress(job,"txt_prepare",bytes as usize,meta.len() as usize)?;}
  let decoded_line=std::str::from_utf8(&raw).map_err(|_|fail(ErrorCode::InvalidEncoding,number,"TXT source must be UTF-8 (optional UTF-8 BOM); output encoding is a separate option"))?;
  let raw_text=if number==1 {decoded_line.strip_prefix('\u{feff}').unwrap_or(decoded_line)}else{decoded_line};
  let logical=raw_text.strip_suffix("\r\n").or_else(||raw_text.strip_suffix('\n')).unwrap_or(raw_text);
  if logical.contains(['\r','\0']) {return Err(invalid(number,"Lone CR and NUL are unsupported; use LF or CRLF"));}
  if head.is_none() {
   if logical.is_empty()||logical=="</>" {return Err(invalid(number,"Expected a nonempty headword"));}
   if logical.len()>4096 {return Err(limit(number,"Headword exceeds 4 KiB"));}
   if records>=max_records {return Err(limit(number,"Record count exceeds selected packing profile"));}
   head=Some(logical.into());
  } else if logical=="</>" {
   if body_lines==0 {return Err(invalid(number,"Record needs a body line; use a blank line for an empty definition"));}
   if request.profile==Profile::CanonicalV1 {if !body.ends_with('\n'){return Err(invalid(number,"Missing body separator"));}body.pop();}
   if body.len()>1024*1024 {return Err(limit(number,"Definition exceeds 1 MiB"));}
   let key=head.take().unwrap();decoded+=key.len()+body.len();
   if decoded>max_decoded {return Err(limit(number,"Decoded entries exceed selected packing profile"));}
   let json=serde_json::to_vec(&serde_json::json!({"key":key,"text":body})).map_err(|e|invalid(number,&e.to_string()))?;
   if spool_bytes+json.len() as u64+1>INPUT_CAP {return Err(limit(number,"Prepared JSONL exceeds 128 MiB"));}
   for chunk in json.chunks(65536) {check(job)?;output.write_all(chunk)?;}output.write_all(b"\n")?;
   spool_bytes+=json.len() as u64+1;body.clear();body_lines=0;records+=1;
  } else {
   let text=if request.profile==Profile::CanonicalV1 {logical}else{raw_text};
   let extra=if request.profile==Profile::CanonicalV1&&raw_text.ends_with('\n'){1}else{0};
   if body.len()+text.len()+extra>1024*1024+1 {return Err(limit(number,"Definition exceeds 1 MiB"));}
   body.push_str(text);if extra==1 {body.push('\n');}body_lines+=1;
  }
 }
 if head.is_some() {return Err(invalid(number,"Unterminated final record: missing standalone </>"));}
 if records==0 {return Err(invalid(number,"No complete TXT records"));}
 output.flush()?;output.seek(SeekFrom::Start(0))?;
 progress(job,"txt_prepared",bytes as usize,bytes as usize)?;
 Ok(Prepared {file:output,digest:sha256::hex(&hash.finish()),bytes,records})
}
pub(crate) fn execute(r:&Request,job:&mut ImportJob<'_>)->Result<Receipt> {
 // Refuse an existing output before spending time preparing TXT. The accepted
 // packer's atomic no-clobber commit remains the final authority for races.
 match std::fs::symlink_metadata(&r.destination) {Ok(_)=>return Err(fail(ErrorCode::DestinationExists,0,"Destination exists")),Err(e) if e.kind()==std::io::ErrorKind::NotFound=>{},Err(e)=>return Err(e.into())}
 let prepared=prepare(r,job)?;check(job)?;
 let source=prepared.file.path().to_owned();
 let packing=match r.packing {
  Packing::Bounded=>{
   let request=studio_large_io::Request::PackMdx {source,destination:r.destination.clone(),encoding:r.encoding,metadata:r.metadata.clone()};
   Packed::Bounded(studio_large_io::execute(&request,&studio_large_io::IoLimits::default(),&mut studio_large_io::ImportJob::new(job.id,job.token,&mut *job.progress))?)
  },
  Packing::Block=>{
   let m=&r.metadata;let request=studio_cc_pack_io::Request::PackMdx {source,destination:r.destination.clone(),encoding:r.encoding,metadata:studio_cc_pack_io::Metadata {title:m.title.clone(),description:m.description.clone(),stylesheet:m.stylesheet.clone(),extra:m.extra.clone()}};
   Packed::Block(studio_cc_pack_io::execute(&request,&studio_cc_pack_io::IoLimits::default(),&mut studio_cc_pack_io::ImportJob::new(job.id,job.token,&mut *job.progress)).map_err(|e|Error {code:e.code,detail:e.detail,message:e.message,limit:e.limit.map(|l|studio_large_io::LimitFailure {name:l.name,value:l.value,max:l.max})})?)
  }
 };
 // Packing has committed. A late cancellation must not turn success into failure.
 Ok(Receipt {source_format:"txt_utf8",source_profile:r.profile,source_sha256:prepared.digest,input_bytes:prepared.bytes,records:prepared.records,packing})
}

pub(crate) fn validate_plugin_output(source:PathBuf,job:&mut ImportJob<'_>)->Result<(usize,String)> {
 let request=Request {source,destination:PathBuf::from("unused"),encoding:studio_cc_pack_io::Encoding::Utf8,metadata:studio_large_io::Metadata::default(),profile:Profile::CanonicalV1,packing:Packing::Block};
 let prepared=prepare(&request,job)?;Ok((prepared.records,prepared.digest))
}

#[cfg(test)]mod tests {
 use super::*;use std::path::Path;use crate::{Request as Work,Response,Runtime,AdmissionLimits,runner,CancellationToken,Budget,Operation};
 use std::{thread,time::{Duration,Instant},sync::Arc};
 fn request(dir:&Path,packing:Packing,profile:Profile)->Request {Request {source:dir.join("source.txt"),destination:dir.join("result.mdx"),encoding:studio_cc_pack_io::Encoding::Utf8,metadata:studio_large_io::Metadata {title:"TXT 字 / مرحبا".into(),description:"preserved metadata".into(),..Default::default()},profile,packing}}
 fn wait(r:&runner::Runner,id:&str)->runner::Snapshot {let start=Instant::now();loop {let s=r.snapshot(id).unwrap();if matches!(s.state,runner::State::Succeeded|runner::State::Failed|runner::State::Cancelled){return s;}assert!(start.elapsed()<Duration::from_secs(30));thread::sleep(Duration::from_millis(5));}}
 fn prepared_rows(p:&Prepared)->Vec<(String,String)> {let data=std::fs::read(p.file.path()).unwrap();std::str::from_utf8(&data).unwrap().lines().map(|s|{let v:serde_json::Value=serde_json::from_str(s).unwrap();(v["key"].as_str().unwrap().into(),v["text"].as_str().unwrap().into())}).collect()}
 #[test]fn streaming_grammar_matches_core_for_duplicates_crlf_bom_blank_bodies_and_final_delimiter() {
  let d=tempfile::tempdir().unwrap();let token=CancellationToken::default();
  for bytes in [b"\xef\xbb\xbfword\r\n<p> a </p>\r\n\r\n</>\r\nword\r\n\r\n</>".as_slice(),"字\nline\n\n\n</>\nمرحبا\nbody\n</>\n".as_bytes()] {
   std::fs::write(d.path().join("source.txt"),bytes).unwrap();
   for profile in [Profile::CanonicalV1,Profile::LegacyBodySpanV1] {
    let mut cb=|_|{};let prepared=prepare(&request(d.path(),Packing::Bounded,profile),&mut ImportJob::new("prepare",&token,&mut cb)).unwrap();
    let oracle=studio_core::parse_txt(bytes,if profile==Profile::CanonicalV1 {studio_core::TxtProfile::CanonicalV1}else{studio_core::TxtProfile::LegacyBodySpanV1},&studio_core::Limits::default(),&mut studio_core::JobContext::new(&token,&mut |_|{})).unwrap();
    assert_eq!(prepared_rows(&prepared),oracle.into_iter().map(|r|(r.key,r.text)).collect::<Vec<_>>());
    let mut hash=sha256::Sha256::new();hash.update(bytes);assert_eq!(prepared.digest,sha256::hex(&hash.finish()));assert_eq!(prepared.bytes,bytes.len() as u64);
   }
  }
 }
 #[test]fn malformed_utf8_incomplete_and_oversized_sources_leave_no_output() {
  let d=tempfile::tempdir().unwrap();let token=CancellationToken::default();
  for bytes in [b"word\nbody\n".to_vec(),b"word\n</>\n".to_vec(),b"\nbody\n</>\n".to_vec(),b"word\n\xff\n</>\n".to_vec(),b"word\rbody\n</>\n".to_vec(),b"word\n\0\n</>\n".to_vec(),b"\xff\xfea\0".to_vec(),vec![b'x';LINE_CAP+1]] {
   std::fs::write(d.path().join("source.txt"),bytes).unwrap();let r=request(d.path(),Packing::Bounded,Profile::CanonicalV1);assert!(execute(&r,&mut ImportJob::new("invalid",&token,&mut |_|{})).is_err());assert!(!r.destination.exists());
  }
 }
 #[test]fn both_packers_both_encodings_roundtrip_source_and_metadata_without_clobber() {
  for packing in [Packing::Bounded,Packing::Block] {for encoding in [studio_cc_pack_io::Encoding::Utf8,studio_cc_pack_io::Encoding::Utf16] {
   let d=tempfile::tempdir().unwrap();std::fs::write(d.path().join("source.txt"),"字\n<p>first</p>\n\n</>\n字\n\n</>\nمرحبا\nbody\n</>\n").unwrap();
   let mut r=request(d.path(),packing,Profile::CanonicalV1);r.encoding=encoding;
   let runtime=Runtime::new(AdmissionLimits::default(),runner::Config::default()).unwrap();let id=runtime.publication().submit(Work::TxtPacking(r)).unwrap();let s=wait(runtime.publication(),&id);assert_eq!(s.state,runner::State::Succeeded,"{s:?}");
   let receipt=runtime.publication().take_result(&id).unwrap().unwrap();assert!(matches!(receipt,Response::TxtPacking(Receipt {records:3,..})));assert!(runtime.publication().take_result(&id).unwrap().is_none());
   let output=d.path().join("result.mdx");let before=std::fs::read(&output).unwrap();
   let export_request=studio_large_io::Request::ExportJsonl {source:output.clone(),destination:d.path().join("roundtrip.jsonl")};let token=CancellationToken::default();
   let receipt=studio_large_io::execute(&export_request,&studio_large_io::IoLimits::default(),&mut studio_large_io::ImportJob::new("export",&token,&mut |_|{})).unwrap();assert_eq!(receipt.metadata["Title"],"TXT 字 / مرحبا");
   let rows:Vec<serde_json::Value>=std::fs::read_to_string(d.path().join("roundtrip.jsonl")).unwrap().lines().map(|s|serde_json::from_str(s).unwrap()).collect();
   let bodies:Vec<_>=rows.iter().filter(|r|r["key"]=="字").map(|r|r["text"].as_str().unwrap()).collect();assert_eq!(bodies,vec!["<p>first</p>\n",""]);
   let id=runtime.publication().submit(Work::TxtPacking(request(d.path(),packing,Profile::CanonicalV1))).unwrap();assert_eq!(wait(runtime.publication(),&id).error.unwrap().code,ErrorCode::DestinationExists);assert_eq!(before,std::fs::read(output).unwrap());runtime.join().unwrap();
  }}
 }
 #[test]fn preparation_and_pack_commit_cancel_keep_one_job_and_cleanup_lease() {
  for phase in ["txt_prepare","txt_prepared","publish_file"] {
   let d=tempfile::tempdir().unwrap();std::fs::write(d.path().join("source.txt"),"word\nbody\n</>\n").unwrap();let token=CancellationToken::default();let cancel=token.clone();
   let mut cb=|p:Progress|if p.phase==phase {cancel.cancel();};let r=request(d.path(),Packing::Block,Profile::CanonicalV1);
   assert_eq!(execute(&r,&mut ImportJob::new("cancel",&token,&mut cb)).unwrap_err().code,ErrorCode::Cancelled);assert!(!r.destination.exists());
  }
  let d=tempfile::tempdir().unwrap();std::fs::write(d.path().join("source.txt"),"word\nbody\n</>\n").unwrap();let budget=Budget::new(AdmissionLimits::default()).unwrap();
  let r=runner::Runner::with_executor(runner::Config::default(),budget.clone(),Arc::new(|request,job|{let result=crate::execute(request,job)?;job.token.cancel();Ok(result)})).unwrap();
  let id=r.submit(Work::TxtPacking(request(d.path(),Packing::Bounded,Profile::CanonicalV1))).unwrap();assert_eq!(wait(&r,&id).state,runner::State::Succeeded);assert!(d.path().join("result.mdx").exists());assert_eq!(budget.snapshot().active_operations,0);r.join().unwrap();
 }
 #[test]fn txt_prepare_and_packing_share_exclusive_admission_with_readers() {
  let d=tempfile::tempdir().unwrap();std::fs::write(d.path().join("source.txt"),"word\nbody\n</>\n").unwrap();let budget=Budget::new(AdmissionLimits::default()).unwrap();let reader=budget.reserve(Operation::Reader).unwrap();
  let r=runner::Runner::with_executor(runner::Config::default(),budget.clone(),Arc::new(crate::execute)).unwrap();
  let id=r.submit(Work::TxtPacking(request(d.path(),Packing::Bounded,Profile::CanonicalV1))).unwrap();assert_eq!(wait(&r,&id).error.unwrap().detail,"resource_admission");assert!(!d.path().join("result.mdx").exists());drop(reader);
  let id=r.submit(Work::TxtPacking(request(d.path(),Packing::Bounded,Profile::CanonicalV1))).unwrap();assert_eq!(wait(&r,&id).state,runner::State::Succeeded);assert_eq!(budget.snapshot().active_operations,0);r.join().unwrap();
 }
}
