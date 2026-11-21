use crate::{Result,Error,ErrorCode,Limits,ImportJob,Kind,invalid,budget,integrity,casing::Casing,sha256::{Sha256,hex}};
use mdictlib::{MddFile,OpenOptions,ChecksumPolicy,KeyOrdinal};
use serde::Serialize;
use std::{collections::BTreeMap,fs::File,io::{Read,Write,Seek,SeekFrom},path::{Path,PathBuf}};
#[derive(Clone,Debug)]pub struct ExtractLimits {pub reader:Limits,pub max_resources:u64,pub max_resource_bytes:u64,pub max_output_bytes:u64,pub max_plan_charge:usize,pub max_nodes:usize}
impl Default for ExtractLimits {fn default()->Self {let mut reader=Limits::default();reader.engine=reader.engine.with_materialized_record_bytes(0);Self {reader,max_resources:100000,max_resource_bytes:256*1024*1024,max_output_bytes:2*1024*1024*1024,max_plan_charge:16*1024*1024,max_nodes:200000}}}
impl ExtractLimits {fn validate(&self)->Result<()> {self.reader.validate()?;let c=Self::default();if self.max_resources>c.max_resources||self.max_resource_bytes>c.max_resource_bytes||self.max_output_bytes>c.max_output_bytes||self.max_plan_charge>c.max_plan_charge||self.max_nodes>c.max_nodes||self.reader.engine.materialized_record_bytes()!=0 {return Err(invalid("extract_limits","Only lower extraction ceilings are supported; materialization stays disabled"));}Ok(())}}
#[derive(Debug,Serialize)]pub struct ExtractionReceipt {pub profile:&'static str,pub source_sha256:String,pub resources:u64,pub payload_bytes:u64,pub largest_resource_bytes:u64,pub framed_resources_sha256:String,pub plan_charge:usize,pub planned_nodes:usize,pub parser_peak_bytes:usize,pub parser_budget_bytes:usize,pub locator_bytes:usize,pub materialized_record_limit:usize}
struct Planned {ordinal:u64,key:String,path:PathBuf,bytes:u64}
fn core_error(e:studio_core::Error)->Error {
 use studio_core::ErrorCode as C;
 let code=match e.code {
  C::InvalidInput=>ErrorCode::InvalidInput,C::UnsupportedPolicy=>ErrorCode::UnsupportedPolicy,
  C::LimitExceeded=>ErrorCode::LimitExceeded,C::Cancelled=>ErrorCode::Cancelled,
  C::DestinationExists=>ErrorCode::DestinationExists,C::Integrity=>ErrorCode::Integrity,
  C::Io=>ErrorCode::Io,C::Engine=>ErrorCode::Engine,C::Internal=>ErrorCode::Internal,
  C::UnsafePath=>ErrorCode::UnsafePath,C::PathCollision=>ErrorCode::PathCollision,
  C::UnsupportedPlatform=>ErrorCode::UnsupportedPlatform,C::InvalidEncoding=>ErrorCode::InvalidEncoding,
  C::MalformedSource=>ErrorCode::MalformedSource,C::UnrepresentableSource=>ErrorCode::UnrepresentableSource,
 };Error::new(code,"resource_path",e.message)
}
fn add_charge(charge:&mut usize,n:usize,cap:usize)->Result<()> {*charge=charge.checked_add(n).ok_or_else(||budget("Path plan charge overflow"))?;if *charge>cap {return Err(budget("Path plan charge exceeds cap"));}Ok(())}
fn plan(file:&MddFile,limits:&ExtractLimits,job:&mut ImportJob<'_>)->Result<(Vec<Planned>,u64,u64,usize,usize)> {
 let total=file.len();if total>limits.max_resources {return Err(budget("Resource count cap exceeded"));}
 let casing=Casing::pinned16().map_err(|e|invalid("casing",e.to_string()))?;let mut nodes:BTreeMap<String,(String,bool)>=BTreeMap::new();let(mut rows,mut bytes,mut largest,mut charge)=(Vec::new(),0u64,0u64,0usize);
 for (i,physical) in file.keys().enumerate() {
  job.tick("plan_paths",i,total as usize)?;let key=physical?;if key.ordinal().get()!=i as u64 {return Err(integrity("Noncontiguous resource ordinal"));}
  let path=studio_core::resource_relative_path(key.key()).map_err(core_error)?;let mut raw=String::new();let mut folded=String::new();let parts=path.iter().collect::<Vec<_>>();
  add_charge(&mut charge,2*std::mem::size_of::<Planned>()+key.key().len()+path.as_os_str().len(),limits.max_plan_charge)?;
  for (index,part) in parts.iter().enumerate() {
   let part=part.to_str().ok_or_else(||invalid("resource_path","Resource component is not UTF-8"))?;if index!=0 {raw.push('/');folded.push('/');}raw.push_str(part);folded.push_str(&casing.lower(part));let leaf=index+1==parts.len();
   if let Some((old,old_leaf))=nodes.get(&folded) {if old!=&raw||*old_leaf||leaf {return Err(Error::new(ErrorCode::PathCollision,"path_collision","Archive paths alias or conflict as files/directories"));}}
   else {if nodes.len()>=limits.max_nodes {return Err(budget("Path-node cap exceeded"));}add_charge(&mut charge,256+folded.len()+2*raw.len(),limits.max_plan_charge)?;nodes.insert(folded.clone(),(raw.clone(),leaf));}
  }
  drop(parts);let span=file.span_at(key.ordinal())?.ok_or_else(||integrity("Missing resource span"))?;if span.key_entry().key()!=key.key() {return Err(integrity("Resource span key differs from planned physical row"));}let size=span.len();
  if size>limits.max_resource_bytes {return Err(budget("Individual resource exceeds extraction cap"));}bytes=bytes.checked_add(size).ok_or_else(||budget("Output size overflow"))?;if bytes>limits.max_output_bytes {return Err(budget("Total extracted payload exceeds cap"));}largest=largest.max(size);rows.push(Planned {ordinal:key.ordinal().get(),key:key.key().into(),path,bytes:size});
 }
 if rows.len() as u64!=total {return Err(integrity("Incomplete resource key plan"));}job.tick("plan_paths",rows.len(),rows.len())?;Ok((rows,bytes,largest,charge,nodes.len()))
}
fn file_hash(file:&mut File,length:u64,phase:&str,job:&mut ImportJob<'_>)->Result<[u8;32]> {
 file.seek(SeekFrom::Start(0))?;let mut h=Sha256::new();let mut left=length;let mut buffer=[0;65536];
 while left>0 {job.tick(phase,(length-left) as usize,length as usize)?;let n=file.read(&mut buffer[..left.min(65536) as usize])?;if n==0 {return Err(integrity("Truncated file during verification"));}h.update(&buffer[..n]);left-=n as u64;}
 job.check()?;Ok(h.finish())
}
struct Sink<'a,'b> {file:&'a mut File,job:&'a mut ImportJob<'b>,digest:Sha256,count:u64,total:u64,failed:Option<Error>}
impl Sink<'_,'_> {fn fail(&mut self,e:Error)->std::io::Error {self.failed=Some(e);std::io::Error::other("Extraction sink stopped")}}
impl Write for Sink<'_,'_> {
 fn write(&mut self,bytes:&[u8])->std::io::Result<usize> {
  if let Err(e)=self.job.tick("copy_resource",self.count as usize,self.total as usize) {return Err(self.fail(e));}
  if bytes.len() as u64>self.total-self.count {return Err(self.fail(integrity("Span emitted more bytes than declared")));}
  let n=bytes.len().min(65536);let n=self.file.write(&bytes[..n])?;self.digest.update(&bytes[..n]);self.count+=n as u64;Ok(n)
 }
 fn flush(&mut self)->std::io::Result<()> {self.file.flush()}
}
fn copy(file:&MddFile,row:&Planned,out:&mut File,job:&mut ImportJob<'_>)->Result<[u8;32]> {
 job.tick("copy_resource",0,row.bytes as usize)?;let span=file.span_at(KeyOrdinal::new(row.ordinal))?.ok_or_else(||integrity("Missing extraction span"))?;
 if span.len()!=row.bytes||span.key_entry().key()!=row.key {return Err(integrity("Span changed after preflight"));}
 let mut sink=Sink {file:out,job,digest:Sha256::new(),count:0,total:row.bytes,failed:None};let result=span.copy_to(&mut sink);let failed=sink.failed.take();let count=sink.count;let digest=std::mem::replace(&mut sink.digest,Sha256::new()).finish();drop(sink);
 if let Some(e)=failed {return Err(e);}let copied=result?;if copied!=row.bytes||count!=row.bytes {return Err(integrity("Incomplete resource copy"));}job.check()?;out.flush()?;out.sync_all()?;
 if out.metadata()?.len()!=row.bytes||file_hash(out,row.bytes,"verify_file",job)?!=digest {return Err(integrity("Staged resource bytes differ from source span"));}Ok(digest)
}
#[cfg(unix)]mod platform {
 use super::*;
 use std::{collections::BTreeSet,ffi::CString,fs::OpenOptions as FsOptions,os::{fd::{AsRawFd,FromRawFd},unix::{fs::OpenOptionsExt,ffi::OsStrExt}}};
 fn component(s:&[u8])->Result<CString> {CString::new(s).map_err(|_|invalid("resource_path","NUL in path"))}
 fn fs_error(e:std::io::Error)->Error {if e.kind()==std::io::ErrorKind::AlreadyExists {Error::new(ErrorCode::PathCollision,"path_collision","Target filesystem aliases planned names")}else{e.into()}}
 pub(super) fn write(root:&Path,rows:&[Planned],file:&MddFile,job:&mut ImportJob<'_>)->Result<String> {
  let root=FsOptions::new().read(true).custom_flags(libc::O_DIRECTORY|libc::O_NOFOLLOW|libc::O_CLOEXEC).open(root)?;let mut created=BTreeSet::new();let mut framed=Sha256::new();
  for (i,row) in rows.iter().enumerate() {
   job.tick("write_resources",i,rows.len())?;let parts=row.path.iter().collect::<Vec<_>>();let mut parent=root.try_clone()?;let mut prefix=PathBuf::new();
   for part in &parts[..parts.len()-1] {
    prefix.push(part);let name=component(part.as_bytes())?;
    // SAFETY: owned directory fd and validated single, NUL-free component.
    if created.insert(prefix.clone())&&unsafe {libc::mkdirat(parent.as_raw_fd(),name.as_ptr(),0o700)}!=0 {return Err(fs_error(std::io::Error::last_os_error()));}
    // SAFETY: anchor each traversal to the owned parent and refuse symlinks.
    let fd=unsafe {libc::openat(parent.as_raw_fd(),name.as_ptr(),libc::O_RDONLY|libc::O_DIRECTORY|libc::O_NOFOLLOW|libc::O_CLOEXEC)};if fd<0 {return Err(std::io::Error::last_os_error().into());}parent=unsafe {File::from_raw_fd(fd)};
   }
   let leaf=component(parts.last().ok_or_else(||invalid("resource_path","Missing leaf"))?.as_bytes())?;
   // SAFETY: create one new leaf relative to an owned directory, never replace
   // a file or follow a symlink. Read permission enables staged-byte verification.
   let fd=unsafe {libc::openat(parent.as_raw_fd(),leaf.as_ptr(),libc::O_RDWR|libc::O_CREAT|libc::O_EXCL|libc::O_NOFOLLOW|libc::O_CLOEXEC,0o600 as libc::c_int)};if fd<0 {return Err(fs_error(std::io::Error::last_os_error()));}let mut out=unsafe {File::from_raw_fd(fd)};let digest=copy(file,row,&mut out,job)?;
   framed.update(&row.ordinal.to_le_bytes());framed.update(&(row.key.len() as u64).to_le_bytes());framed.update(row.key.as_bytes());framed.update(&row.bytes.to_le_bytes());framed.update(&digest);
  }job.tick("write_resources",rows.len(),rows.len())?;Ok(hex(&framed.finish()))
 }
 pub(super) fn publish(source:&Path,destination:&Path)->Result<()> {
  let src=component(source.as_os_str().as_bytes())?;let dst=component(destination.as_os_str().as_bytes())?;
  #[cfg(target_os="macos")]
  // SAFETY: live C strings and the same exclusive primitive as qualified core.
  let result=unsafe {libc::renamex_np(src.as_ptr(),dst.as_ptr(),libc::RENAME_EXCL)} as libc::c_long;
  #[cfg(target_os="linux")]
  // SAFETY: correct renameat2 syscall signature; replacement is forbidden.
  let result=unsafe {libc::syscall(libc::SYS_renameat2,libc::AT_FDCWD,src.as_ptr(),libc::AT_FDCWD,dst.as_ptr(),libc::RENAME_NOREPLACE)};
  #[cfg(not(any(target_os="macos",target_os="linux")))]
  return Err(Error::new(ErrorCode::UnsupportedPlatform,"platform","Exclusive directory publication unavailable"));
  #[cfg(any(target_os="macos",target_os="linux"))]
  if result==0 {Ok(())}else {let e=std::io::Error::last_os_error();if e.kind()==std::io::ErrorKind::AlreadyExists||e.raw_os_error()==Some(libc::ENOTEMPTY) {Err(Error::new(ErrorCode::DestinationExists,"destination_exists","Extraction destination exists"))}else{Err(e.into())}}
 }
 #[cfg(test)]pub(super) fn refuses_symlink(root:&Path,file:&MddFile,job:&mut ImportJob<'_>)->Result<String> {write(root,&[Planned {ordinal:0,key:"assets/file.bin".into(),path:"assets/file.bin".into(),bytes:3}],file,job)}
}
pub fn extract_mdd(source:&Path,destination:&Path,limits:&ExtractLimits,job:&mut ImportJob<'_>)->Result<ExtractionReceipt> {
 job.check()?;limits.validate()?;
 if !cfg!(any(target_os="macos",target_os="linux")) {return Err(Error::new(ErrorCode::UnsupportedPlatform,"platform","Streaming directory extraction requires macOS/Linux"));}
 match std::fs::symlink_metadata(destination) {Ok(_)=>return Err(Error::new(ErrorCode::DestinationExists,"destination_exists","Extraction destination exists")),Err(e) if e.kind()==std::io::ErrorKind::NotFound=>{},Err(e)=>return Err(e.into())}
 let (snapshot,_header)=crate::header::snapshot(source,Kind::Mdd,&limits.reader,job)?;let mut input=File::open(snapshot.path())?;let input_size=input.metadata()?.len();let source_sha256=hex(&file_hash(&mut input,input_size,"source_hash",job)?);
 let options=OpenOptions::new().with_checksum_policy(ChecksumPolicy::Verify).with_limits(limits.reader.engine.clone());let file=MddFile::open_with_options(snapshot.path(),&options)?;
 let (rows,bytes,largest,charge,nodes)=plan(&file,limits,job)?;let parent=destination.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new("."));let stage=tempfile::Builder::new().prefix(".studio-stream-extract-").tempdir_in(parent)?;
 #[cfg(unix)]let digest=platform::write(stage.path(),&rows,&file,job)?;
 #[cfg(not(unix))]let digest=String::new();
 let usage=file.memory_usage()?;if usage.locator_bytes()!=0||usage.peak_bytes()>limits.reader.engine.working_memory_bytes() {return Err(integrity("Extraction allocated a locator or exceeded engine accounting"));}
 let receipt=ExtractionReceipt {profile:"mdd-stream-extract-v1",source_sha256,resources:rows.len() as u64,payload_bytes:bytes,largest_resource_bytes:largest,framed_resources_sha256:digest,plan_charge:charge,planned_nodes:nodes,parser_peak_bytes:usage.peak_bytes(),parser_budget_bytes:limits.reader.engine.working_memory_bytes(),locator_bytes:usage.locator_bytes(),materialized_record_limit:limits.reader.engine.materialized_record_bytes()};
 job.tick("publish_directory",0,1)?;
 #[cfg(unix)]platform::publish(stage.path(),destination)?;
 let _=stage.keep();Ok(receipt)
}
#[cfg(all(test,unix))]mod safety_tests {
 use super::*;
 #[test]fn core_path_adapter_preserves_serialized_codes_and_messages() {
  use studio_core::ErrorCode as C;
  for code in [C::InvalidInput,C::UnsupportedPolicy,C::LimitExceeded,C::Cancelled,C::DestinationExists,C::Integrity,C::Io,C::Engine,C::Internal,C::UnsafePath,C::PathCollision,C::UnsupportedPlatform,C::InvalidEncoding,C::MalformedSource,C::UnrepresentableSource] {
   let expected=serde_json::to_value(code).unwrap();let e=core_error(studio_core::Error {code,message:"path diagnostic".into()});assert_eq!(serde_json::to_value(e.code).unwrap(),expected);assert_eq!(e.detail,"resource_path");assert_eq!(e.message,"path diagnostic");
  }
  let e=core_error(studio_core::resource_relative_path("../escape").unwrap_err());assert_eq!(e.code,ErrorCode::UnsafePath);
 }
 #[test]fn staged_symlink_is_not_followed() {
  let root=tempfile::tempdir().unwrap();let outside=tempfile::tempdir().unwrap();let input=tempfile::NamedTempFile::new().unwrap();let mut b=mdictlib::MddBuilder::new();b.add_resource("assets/file.bin",&[1,2,3]).unwrap();b.finish(input.as_file()).unwrap();let options=OpenOptions::new().with_checksum_policy(ChecksumPolicy::Verify);let file=MddFile::open_with_options(input.path(),&options).unwrap();
  std::os::unix::fs::symlink(outside.path(),root.path().join("assets")).unwrap();let token=crate::CancellationToken::default();let mut cb=|_|{};assert!(platform::refuses_symlink(root.path(),&file,&mut ImportJob::new("symlink",&token,&mut cb)).is_err());assert_eq!(std::fs::read_dir(outside.path()).unwrap().count(),0);
 }
}
