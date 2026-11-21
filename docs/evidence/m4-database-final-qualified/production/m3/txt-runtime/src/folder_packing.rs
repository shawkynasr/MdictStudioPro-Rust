//! Folder -> private resource manifest -> accepted MDD packer, under one job.
use crate::{Error,ErrorCode,ImportJob,Progress,Result};
use serde::{Deserialize,Serialize};
use std::{collections::BTreeMap,ffi::OsString,fs,io::Write,path::{Path,PathBuf}};
#[path="../../../m2/studio-core/src/casing.rs"]mod casing;
#[derive(Debug,Deserialize)]#[serde(deny_unknown_fields)]pub struct Request {
 pub resource_root:PathBuf,pub destination:PathBuf,pub metadata:studio_large_io::Metadata,
}
#[derive(Debug,Serialize)]pub struct Receipt {
 pub source_format:&'static str,pub key_policy:&'static str,pub files:usize,
 pub directories:usize,pub skipped_metadata:usize,pub scanned_file_bytes:u64,
 pub packing:studio_large_io::Summary,
}
#[derive(Clone,Copy)]struct ScanLimits {entries:usize,plan_bytes:usize,manifest_bytes:usize,file_bytes:u64,decoded_bytes:u64}
impl Default for ScanLimits {fn default()->Self {Self {entries:100000,plan_bytes:32*1024*1024,manifest_bytes:16*1024*1024,file_bytes:1024*1024,decoded_bytes:32*1024*1024}}}
#[derive(Default)]struct Scan {entries:usize,plan_bytes:usize,manifest_bytes:usize,files:usize,directories:usize,skipped:usize,payload:u64,decoded:u64,nodes:BTreeMap<String,String>}
fn fail(code:ErrorCode,message:impl Into<String>)->Error {Error {code,detail:"resource_folder",message:message.into(),limit:None}}
fn invalid(message:impl Into<String>)->Error {fail(ErrorCode::InvalidInput,message)}
fn limit(message:impl Into<String>)->Error {fail(ErrorCode::LimitExceeded,message)}
fn check(job:&ImportJob<'_>)->Result<()> {if job.token.is_cancelled() {Err(fail(ErrorCode::Cancelled,"Resource folder build cancelled before commit"))}else{Ok(())}}
fn progress(job:&mut ImportJob<'_>,phase:&str,done:usize,total:usize)->Result<()> {
 check(job)?;(job.progress)(Progress {job_id:job.id.into(),stage:studio_application::Stage::Converting,phase:phase.into(),completed:done,total});check(job)
}
fn walk(root:&Path,relative:&str,folded:&str,output:&mut tempfile::NamedTempFile,scan:&mut Scan,casing:&casing::Casing,limits:ScanLimits,job:&mut ImportJob<'_>)->Result<()> {
 check(job)?;let path=if relative.is_empty(){root.to_owned()}else{root.join(relative)};
 let info=fs::symlink_metadata(&path)?;
 if info.file_type().is_symlink() {return Err(fail(ErrorCode::UnsafePath,format!("Symlink directory is unsupported: {relative}")));}
 if !info.is_dir() {return Err(invalid(format!("Expected a resource folder: {}",path.display())));}
 scan.directories+=1;
 let mut names:Vec<OsString>=Vec::new();
 // Bound names before collecting/sorting, including ignored metadata names.
 for entry in fs::read_dir(&path)? {
  check(job)?;let name=entry?.file_name();scan.entries+=1;
  if scan.entries>limits.entries {return Err(limit("Folder exceeds 100,000 scanned entries"));}
  scan.plan_bytes=scan.plan_bytes.saturating_add(256+name.len()*2);
  if scan.plan_bytes>limits.plan_bytes {return Err(limit("Resource folder path plan exceeds 32 MiB"));}
  names.push(name);
 }
 names.sort();
 for name in names {
  check(job)?;
  let name=name.to_str().ok_or_else(||fail(ErrorCode::InvalidEncoding,"Resource filenames must be valid UTF-8"))?;
  if name==".DS_Store" || name==".localized" || name.starts_with("._") {scan.skipped+=1;continue;}
  if name.contains('\\') {return Err(fail(ErrorCode::UnsafePath,format!("Backslash is ambiguous in a resource filename: {name}")));}
  let child=if relative.is_empty(){name.to_owned()}else{format!("{relative}/{name}")};
  studio_core::resource_relative_path(&child).map_err(|e|fail(ErrorCode::UnsafePath,format!("{child}: {e}")))?;
  let folded_name=casing.lower(name);let folded_child=if folded.is_empty(){folded_name}else{format!("{folded}/{folded_name}")};
  scan.plan_bytes=scan.plan_bytes.saturating_add(child.len()*2+folded_child.len());
  if scan.plan_bytes>limits.plan_bytes {return Err(limit("Resource folder path plan exceeds 32 MiB"));}
  if scan.nodes.insert(folded_child.clone(),child.clone()).is_some() {return Err(fail(ErrorCode::PathCollision,format!("Case-aliased resource path: {child}")));}
  let metadata=fs::symlink_metadata(root.join(&child))?;
  if metadata.file_type().is_symlink() {return Err(fail(ErrorCode::UnsafePath,format!("Symlink resources are unsupported: {child}")));}
  if metadata.is_dir() {walk(root,&child,&folded_child,output,scan,casing,limits,job)?;continue;}
  if !metadata.is_file() {return Err(fail(ErrorCode::UnsafePath,format!("Expected a regular resource file: {child}")));}
  if metadata.len()>limits.file_bytes {return Err(limit(format!("Resource exceeds 1 MiB: {child}")));}
  let key=format!("\\{}",child.replace('/',"\\"));
  if key.len()>4096 {return Err(limit(format!("Resource key exceeds 4 KiB: {child}")));}
  scan.decoded=scan.decoded.saturating_add(metadata.len()).saturating_add(key.len() as u64);
  if scan.decoded>limits.decoded_bytes {return Err(limit("Resource folder exceeds 32 MiB of decoded keys and payloads"));}
  let row=serde_json::to_vec(&serde_json::json!({"key":key,"file":child})).map_err(|e|invalid(e.to_string()))?;
  scan.manifest_bytes=scan.manifest_bytes.saturating_add(row.len()+1);
  if scan.manifest_bytes>limits.manifest_bytes {return Err(limit("Generated resource manifest exceeds 16 MiB"));}
  check(job)?;output.write_all(&row)?;output.write_all(b"\n")?;
  scan.files+=1;scan.payload+=metadata.len();
  if scan.files%64==0 {progress(job,"folder_scan",scan.files,0)?;}
 }
 Ok(())
}
fn prepare(r:&Request,job:&mut ImportJob<'_>,limits:ScanLimits)->Result<(tempfile::NamedTempFile,Scan)> {
 if !r.metadata.stylesheet.is_empty() {return Err(invalid("Numeric stylesheets belong to MDX, not MDD resources"));}
 progress(job,"folder_scan",0,0)?;
 let casing=casing::Casing::pinned16().map_err(|e|invalid(e.to_string()))?;
 let mut file=tempfile::NamedTempFile::new()?;let mut scan=Scan::default();
 walk(&r.resource_root,"","",&mut file,&mut scan,&casing,limits,job)?;
 if scan.files==0 {return Err(invalid("Resource folder contains no regular files after excluding macOS metadata"));}
 file.flush()?;progress(job,"folder_prepared",scan.files,scan.files)?;
 Ok((file,scan))
}
pub(crate) fn execute(r:&Request,job:&mut ImportJob<'_>)->Result<Receipt> {
 #[cfg(not(unix))]return Err(fail(ErrorCode::UnsupportedPolicy,"Folder MDD packing currently requires the qualified Unix resource packer"));
 check(job)?;
 match fs::symlink_metadata(&r.destination) {Ok(_)=>return Err(fail(ErrorCode::DestinationExists,"Destination exists")),Err(e) if e.kind()==std::io::ErrorKind::NotFound=>{},Err(e)=>return Err(e.into())}
 let (manifest,scan)=prepare(r,job,ScanLimits::default())?;
 let request=studio_large_io::Request::PackMdd {source:manifest.path().to_owned(),resource_root:r.resource_root.clone(),destination:r.destination.clone(),metadata:r.metadata.clone()};
 // The accepted packer opens payloads relative to its root descriptor and refuses
 // symlink components. Scan-time checks are not a replacement for those checks.
 let packing=studio_large_io::execute(&request,&studio_large_io::IoLimits::default(),&mut studio_large_io::ImportJob::new(job.id,job.token,&mut *job.progress))?;
 // Commit succeeded: do not introduce a fallible check or cancellation here.
 Ok(Receipt {source_format:"resource_folder",key_policy:"backslash-root-relative-v1",files:packing.records,directories:scan.directories,skipped_metadata:scan.skipped,scanned_file_bytes:scan.payload,packing})
}

#[cfg(all(test,unix))]mod tests {
 use super::*;use crate::{CancellationToken,Runtime,AdmissionLimits,Request as Work,runner,Budget,Operation};
 use std::{sync::Arc,thread,time::{Instant,Duration}};
 fn fixture(root:&Path) {
  fs::create_dir(root).unwrap();fs::create_dir(root.join("css")).unwrap();fs::create_dir(root.join("images")).unwrap();fs::create_dir(root.join("fonts")).unwrap();fs::create_dir(root.join("空目录")).unwrap();
  for (name,bytes) in [("css/main.css",b"body{color:blue}".as_slice()),("images/字.png",&[0,255,1,128]),("fonts/amiri-regular.ttf",&[0,1,0,0,255]),("sound.wav",b"RIFF\0WAVE".as_slice()),("empty.bin",b"".as_slice())] {fs::write(root.join(name),bytes).unwrap();}
  fs::write(root.join(".DS_Store"),b"ignored").unwrap();fs::write(root.join("images/._字.png"),b"ignored").unwrap();
 }
 fn request(dir:&Path)->Request {Request {resource_root:dir.join("assets"),destination:dir.join("out.mdd"),metadata:studio_large_io::Metadata {title:"Folder 字".into(),description:"binary resources".into(),..Default::default()}}}
 fn wait(r:&runner::Runner,id:&str)->runner::Snapshot {let start=Instant::now();loop {let s=r.snapshot(id).unwrap();if matches!(s.state,runner::State::Succeeded|runner::State::Failed|runner::State::Cancelled) {return s;}assert!(start.elapsed()<Duration::from_secs(30));thread::sleep(Duration::from_millis(5));}}
 #[test]fn manifest_is_deterministic_relative_and_ignores_only_metadata() {
  let d=tempfile::tempdir().unwrap();let r=request(d.path());fixture(&r.resource_root);let token=CancellationToken::default();
  let (a,s)=prepare(&r,&mut ImportJob::new("scan",&token,&mut |_|{}),ScanLimits::default()).unwrap();
  let (b,_)=prepare(&r,&mut ImportJob::new("scan",&token,&mut |_|{}),ScanLimits::default()).unwrap();
  let data=fs::read(a.path()).unwrap();assert_eq!(data,fs::read(b.path()).unwrap());assert_eq!((s.files,s.skipped,s.directories),(5,2,5));
  let rows:Vec<serde_json::Value>=std::str::from_utf8(&data).unwrap().lines().map(|l|serde_json::from_str(l).unwrap()).collect();
  assert!(rows.iter().any(|v|v["key"]=="\\fonts\\amiri-regular.ttf" && v["file"]=="fonts/amiri-regular.ttf"));
  assert!(rows.iter().any(|v|v["key"]=="\\images\\字.png"));assert!(!r.destination.exists());
 }
 #[test]fn folder_mdd_roundtrip_preserves_nested_unicode_empty_and_binary_resources_without_clobber() {
  let d=tempfile::tempdir().unwrap();let r=request(d.path());fixture(&r.resource_root);let token=CancellationToken::default();
  let receipt=execute(&r,&mut ImportJob::new("pack",&token,&mut |_|{})).unwrap();assert_eq!((receipt.files,receipt.skipped_metadata),(5,2));assert_eq!(receipt.packing.metadata["Title"],"Folder 字");
  let before=fs::read(&r.destination).unwrap();let extracted=d.path().join("extracted");
  studio_stream_extract::extract_mdd(&r.destination,&extracted,&studio_stream_extract::ExtractLimits::default(),&mut studio_stream_extract::ImportJob::new("extract",&token,&mut |_|{})).unwrap();
  for name in ["css/main.css","images/字.png","fonts/amiri-regular.ttf","sound.wav","empty.bin"] {assert_eq!(fs::read(extracted.join(name)).unwrap(),fs::read(r.resource_root.join(name)).unwrap());}
  assert!(!extracted.join(".DS_Store").exists());
  assert_eq!(execute(&r,&mut ImportJob::new("again",&token,&mut |_|{})).unwrap_err().code,ErrorCode::DestinationExists);assert_eq!(before,fs::read(&r.destination).unwrap());
 }
 #[test]fn symlinks_ambiguous_names_empty_folders_and_lowered_budgets_refuse_publication() {
  use std::os::unix::fs::symlink;
  for link_directory in [false,true] {
   let d=tempfile::tempdir().unwrap();let r=request(d.path());fs::create_dir(&r.resource_root).unwrap();let outside=d.path().join("outside");
   if link_directory {fs::create_dir(&outside).unwrap();fs::write(outside.join("secret"),b"private").unwrap();}else{fs::write(&outside,b"private").unwrap();}
   symlink(outside,r.resource_root.join("link")).unwrap();let token=CancellationToken::default();assert_eq!(execute(&r,&mut ImportJob::new("link",&token,&mut |_|{})).unwrap_err().code,ErrorCode::UnsafePath);assert!(!r.destination.exists());
  }
  let d=tempfile::tempdir().unwrap();let r=request(d.path());fs::create_dir(&r.resource_root).unwrap();let token=CancellationToken::default();
  assert!(execute(&r,&mut ImportJob::new("empty",&token,&mut |_|{})).is_err());
  fs::write(r.resource_root.join("bad\\name"),b"x").unwrap();assert_eq!(execute(&r,&mut ImportJob::new("name",&token,&mut |_|{})).unwrap_err().code,ErrorCode::UnsafePath);fs::remove_file(r.resource_root.join("bad\\name")).unwrap();
  fs::write(r.resource_root.join("a.bin"),b"data").unwrap();
  for limits in [ScanLimits {entries:0,..ScanLimits::default()},ScanLimits {plan_bytes:0,..ScanLimits::default()},ScanLimits {manifest_bytes:0,..ScanLimits::default()},ScanLimits {file_bytes:0,..ScanLimits::default()},ScanLimits {decoded_bytes:0,..ScanLimits::default()}] {
   match prepare(&r,&mut ImportJob::new("limit",&token,&mut |_|{}),limits) {Err(e)=>assert_eq!(e.code,ErrorCode::LimitExceeded),Ok(_)=>panic!("Expected scan budget refusal")}
   assert!(!r.destination.exists());
  }
 }
 #[test]fn case_aliases_are_refused_on_case_sensitive_filesystems() {
  let d=tempfile::tempdir().unwrap();let r=request(d.path());fs::create_dir(&r.resource_root).unwrap();fs::write(r.resource_root.join("A.png"),b"a").unwrap();fs::write(r.resource_root.join("a.png"),b"b").unwrap();
  // A case-insensitive native filesystem cannot create this fixture at all.
  if fs::read_dir(&r.resource_root).unwrap().count()<2 {return;}
  let token=CancellationToken::default();assert_eq!(execute(&r,&mut ImportJob::new("alias",&token,&mut |_|{})).unwrap_err().code,ErrorCode::PathCollision);assert!(!r.destination.exists());
 }
 #[test]fn folder_preparation_and_packing_cancel_under_one_exclusive_lease() {
  for phase in ["folder_scan","folder_prepared","publish_file"] {
   let d=tempfile::tempdir().unwrap();let r=request(d.path());fixture(&r.resource_root);let token=CancellationToken::default();let cancel=token.clone();let mut cb=|p:Progress|if p.phase==phase {cancel.cancel();};
   assert_eq!(execute(&r,&mut ImportJob::new("cancel",&token,&mut cb)).unwrap_err().code,ErrorCode::Cancelled);assert!(!r.destination.exists());
  }
  let d=tempfile::tempdir().unwrap();let r=request(d.path());fixture(&r.resource_root);let budget=Budget::new(AdmissionLimits::default()).unwrap();let reader=budget.reserve(Operation::Reader).unwrap();
  let runner=runner::Runner::with_executor(runner::Config::default(),budget.clone(),Arc::new(|r,j| {let result=crate::execute(r,j)?;j.token.cancel();Ok(result)})).unwrap();
  let id=runner.submit(Work::FolderPacking(request(d.path()))).unwrap();assert_eq!(wait(&runner,&id).error.unwrap().detail,"resource_admission");assert!(!r.destination.exists());drop(reader);
  let id=runner.submit(Work::FolderPacking(request(d.path()))).unwrap();assert_eq!(wait(&runner,&id).state,runner::State::Succeeded);assert!(r.destination.exists());assert!(runner.take_result(&id).unwrap().is_some());assert!(runner.take_result(&id).unwrap().is_none());assert_eq!(budget.snapshot().active_operations,0);runner.join().unwrap();
 }
}
