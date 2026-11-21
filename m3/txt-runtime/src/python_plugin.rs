//! Trusted local converter subprocess, under the existing serial publication job.
//! The child is not sandboxed. Its protocol never travels over stdout/stderr.
use crate::{Error,ErrorCode,ImportJob,Progress,Result};
use serde::{Deserialize,Serialize};
use serde_json::json;
use std::{fs::{self,File,OpenOptions},io::{Read,Write,Seek,SeekFrom},net::{TcpListener,TcpStream},path::{Path,PathBuf},process::{Child,Command,Stdio},time::{Duration,Instant}};
#[path="../../../m2/indexed-engine/src/sha256.rs"]mod sha256;
const INPUT:u64=64*1024*1024;
const PLUGIN:u64=1024*1024;
const FILE_BYTES:u64=64*1024*1024;
const TOTAL_BYTES:u64=128*1024*1024;
const RAW_LOG:u64=16*1024*1024;
const DEADLINE:Duration=Duration::from_secs(300);
#[derive(Debug,Deserialize)]#[serde(deny_unknown_fields)]pub struct Request {
 pub python:PathBuf,pub plugin:PathBuf,pub class_name:String,pub source:PathBuf,pub destination:PathBuf,pub trusted:bool,
 #[serde(default)]pub expected_plugin_sha256:Option<String>,
 #[serde(default)]pub options:std::collections::BTreeMap<String,serde_json::Value>,
}
fn valid_options(options:&std::collections::BTreeMap<String,serde_json::Value>)->bool {
 options.len()<=64 && serde_json::to_vec(options).map_or(false,|v|v.len()<=8192) && options.iter().all(|(key,value)| {
  !key.is_empty() && key.len()<=64 && key.bytes().enumerate().all(|(i,b)|b.is_ascii_alphabetic()||b==b'_'||(i>0&&b.is_ascii_digit())) && match value {
   serde_json::Value::String(s)=>s.len()<=2048,
   serde_json::Value::Bool(_)=>true,
   serde_json::Value::Number(n)=>n.as_f64().map_or(false,|v|v.is_finite()&&v.abs()<=9007199254740991.0),
   _=>false,
  }
 })
}
impl Request {pub(crate) fn validate(&self)->crate::ApiResult<()> {
 if self.expected_plugin_sha256.as_ref().map_or(false,|s|s.len()!=64||!s.bytes().all(|b|b.is_ascii_hexdigit())){return Err(crate::ApiError {code:crate::ApiCode::InvalidInput,message:"Expected plugin SHA-256 must be 64 hexadecimal characters".into()});}
 if !valid_options(&self.options){return Err(crate::ApiError {code:crate::ApiCode::InvalidInput,message:"Plugin options require <=64 scalar fields, ASCII identifiers <=64 bytes, strings <=2048 UTF-8 bytes, finite numbers within the safe range, and <=8 KiB JSON".into()});}
 if !self.trusted||self.class_name.is_empty()||self.class_name.len()>128||!self.class_name.bytes().enumerate().all(|(i,b)|b.is_ascii_alphabetic()||b==b'_'||(i>0&&b.is_ascii_digit())) {
  return Err(crate::ApiError {code:crate::ApiCode::InvalidInput,message:"Confirm trusted local Python code and select one ASCII class identifier <=128 bytes".into()});
 }Ok(())
}}
#[derive(Debug,Serialize)]pub struct Receipt {
 pub profile:&'static str,pub destination:PathBuf,pub plugin_sha256:String,pub input_sha256:String,pub output_sha256:String,
 pub options_sha256:String,pub option_fields:usize,
 pub records:usize,pub paths:usize,pub bytes:u64,pub summary:String,pub callback_logs:Vec<String>,pub stdout_tail:String,pub stderr_tail:String,
}
fn fail(code:ErrorCode,message:impl Into<String>)->Error {Error {code,detail:"python_plugin",message:message.into(),limit:None}}
fn invalid(message:impl Into<String>)->Error {fail(ErrorCode::InvalidInput,message)}
fn limit(message:impl Into<String>)->Error {fail(ErrorCode::LimitExceeded,message)}
fn check(job:&ImportJob<'_>)->Result<()> {if job.token.is_cancelled(){Err(fail(ErrorCode::Cancelled,"Python converter cancelled before publication"))}else{Ok(())}}
fn event(job:&mut ImportJob<'_>,phase:&str,value:usize)->Result<()> {
 check(job)?;(job.progress)(Progress {job_id:job.id.into(),stage:studio_application::Stage::Converting,phase:phase.into(),completed:value,total:100});check(job)
}
fn copy(source:&Path,target:&Path,cap:u64,job:&ImportJob<'_>)->Result<String> {
 if !fs::symlink_metadata(source)?.file_type().is_file(){return Err(invalid("Expected a regular file, without a symlink"));}
 let mut input=File::open(source)?;let mut output=OpenOptions::new().write(true).create_new(true).open(target)?;
 let mut count=0;let mut buffer=[0u8;65536];let mut hash=sha256::Sha256::new();
 loop {check(job)?;let n=input.read(&mut buffer)?;if n==0{break;}count+=n as u64;if count>cap{return Err(limit("Snapshot/file byte limit exceeded"));}hash.update(&buffer[..n]);output.write_all(&buffer[..n])?;}
 output.sync_all()?;Ok(sha256::hex(&hash.finish()))
}
fn tail(path:&Path)->String {
 let Ok(mut file)=File::open(path) else{return String::new();};let len=file.metadata().map_or(0,|m|m.len());let _=file.seek(SeekFrom::Start(len.saturating_sub(4096)));let mut data=Vec::new();let _=file.take(4096).read_to_end(&mut data);String::from_utf8_lossy(&data).into_owned()
}
// Private files are polled rather than pipe-read threads. A descendant holding
// inherited stdout cannot block cancellation or job cleanup waiting for pipe EOF.
struct ChildGuard {child:Child,stopped:bool}
impl ChildGuard {fn stop(&mut self) {
 if self.stopped{return;}self.stopped=true;
 #[cfg(unix)]unsafe {libc::kill(-(self.child.id() as i32),libc::SIGKILL);}
 let _=self.child.kill();let _=self.child.wait();
}}
impl Drop for ChildGuard {fn drop(&mut self){self.stop();}}
#[derive(Deserialize)]#[serde(tag="type",rename_all="snake_case",deny_unknown_fields)]enum Message {
 Hello {token:String,version:u32},Progress {value:u8},Log {message:String},Done {message:String},Error {message:String},
}
fn messages(buffer:&mut Vec<u8>,hello:&mut bool,done:&mut Option<String>,logs:&mut Vec<String>,token:&str,job:&mut ImportJob<'_>)->Result<()> {
 while let Some(end)=buffer.iter().position(|b|*b==b'\n') {
  if end>8192{return Err(limit("Protocol frame exceeds 8 KiB"));}
  let message:Message=serde_json::from_slice(&buffer[..end]).map_err(|e|invalid(format!("Invalid plugin protocol: {e}")))?;buffer.drain(..=end);
  if done.is_some(){return Err(invalid("Protocol message after completion"));}
  match message {
   Message::Hello {token:provided,version} if !*hello&&provided==token&&version==1=>*hello=true,
   Message::Progress {value} if *hello&&value<=100=>event(job,"python_convert",value as usize)?,
   Message::Log {message} if *hello&&logs.len()<64&&message.len()<=3072=>logs.push(message),
   Message::Done {message} if *hello&&message.len()<=3072=>*done=Some(message),
   Message::Error {message} if *hello=>return Err(fail(ErrorCode::Engine,message)),
   _=>return Err(invalid("Unexpected/unauthenticated plugin protocol message")),
  }
 }if buffer.len()>8192{return Err(limit("Unterminated protocol frame exceeds 8 KiB"));}Ok(())
}
fn conversation(listener:TcpListener,child:&mut ChildGuard,stdout:&Path,stderr:&Path,stage:&Path,token:&str,job:&mut ImportJob<'_>,timeout:Duration)->Result<(String,Vec<String>)> {
 let start=Instant::now();let mut socket:Option<TcpStream>=None;let mut buffer=Vec::new();let mut hello=false;let mut done=None;let mut logs=Vec::new();let mut wire=0usize;let mut eof=false;
 loop {
  check(job)?;if start.elapsed()>timeout{return Err(limit("Python process exceeded its time budget"));}
  for path in [stdout,stderr]{if fs::metadata(path)?.len()>RAW_LOG{return Err(limit("Python stdout/stderr exceeds 16 MiB per stream"));}}
  inventory(stage)?;
  if socket.is_none(){match listener.accept(){Ok((s,peer)) if peer.ip().is_loopback()=>{s.set_nonblocking(true)?;socket=Some(s);},Err(e) if e.kind()==std::io::ErrorKind::WouldBlock=>{},Err(e)=>return Err(e.into()),_=>return Err(invalid("Non-loopback protocol peer"))}}
  if let Some(s)=&mut socket {
   let mut data=[0u8;4096];
   // Bound each polling pass so a busy child cannot starve cancellation/limits.
   for _ in 0..16 {match s.read(&mut data){Ok(0)=>{eof=true;break;},Ok(n)=>{wire+=n;if wire>4*1024*1024{return Err(limit("Plugin protocol exceeds 4 MiB"));}buffer.extend_from_slice(&data[..n]);messages(&mut buffer,&mut hello,&mut done,&mut logs,token,job)?;},Err(e) if e.kind()==std::io::ErrorKind::WouldBlock=>break,Err(e)=>return Err(e.into())}}
  }
  let status=child.child.try_wait()?;
  if let Some(status)=status {
   if !status.success(){return Err(fail(ErrorCode::Engine,format!("Python exited with {status}; {}",tail(stderr))));}
   if eof {if !buffer.is_empty()||!hello{return Err(invalid("Incomplete plugin protocol"));}return done.map(|d|(d,logs)).ok_or_else(||invalid("Python exited without a completion message"));}
  }
  if !hello&&start.elapsed()>Duration::from_secs(10){return Err(limit("Python protocol startup exceeded 10 seconds"));}
  // A child that exits with inherited sockets still open is bounded too.
  if eof&&status.is_none()&&done.is_none(){return Err(invalid("Plugin protocol closed before completion"));}
  std::thread::sleep(Duration::from_millis(20));
 }
}
fn inventory(root:&Path)->Result<(usize,u64)> {
 fn walk(root:&Path,depth:usize,count:&mut usize,total:&mut u64)->Result<()> {
  if depth>8{return Err(limit("Plugin output nesting exceeds 8"));}
  let mut names=std::collections::BTreeSet::new();
  for entry in fs::read_dir(root)? {
   let entry=entry?;*count+=1;if *count>256{return Err(limit("Plugin workspace exceeds 256 paths"));}
   let name=entry.file_name();let name=name.to_str().ok_or_else(||invalid("Plugin filenames must be ASCII"))?;
   if name.len()>128||name.is_empty()||!name.bytes().all(|b|b.is_ascii_alphanumeric()||b"._-".contains(&b)){return Err(invalid("Plugin filenames must use ASCII letters/digits, dot, underscore or hyphen"));}
   studio_core::resource_relative_path(name).map_err(|e|invalid(e.to_string()))?;
   if !names.insert(name.to_ascii_lowercase()){return Err(invalid("Case-aliasing output names are unsupported"));}
   let m=fs::symlink_metadata(entry.path())?;
   if m.is_dir(){walk(&entry.path(),depth+1,count,total)?;}else if m.is_file(){if m.len()>FILE_BYTES{return Err(limit("Plugin workspace file exceeds 64 MiB"));}*total=total.saturating_add(m.len());if *total>TOTAL_BYTES{return Err(limit("Plugin workspace exceeds 128 MiB"));}}else{return Err(invalid("Symlinks and special files are not supported in plugin output"));}
  }Ok(())
 }
 let(mut count,mut total)=(0,0);walk(root,0,&mut count,&mut total)?;Ok((count,total))
}
#[cfg(unix)]fn publish(source:&Path,destination:&Path)->Result<()> {
 use std::{ffi::CString,os::unix::ffi::OsStrExt};
 let src=CString::new(source.as_os_str().as_bytes()).map_err(|_|invalid("NUL in path"))?;let dst=CString::new(destination.as_os_str().as_bytes()).map_err(|_|invalid("NUL in path"))?;
 #[cfg(target_os="macos")]let result=unsafe{libc::renamex_np(src.as_ptr(),dst.as_ptr(),libc::RENAME_EXCL)} as libc::c_long;
 #[cfg(target_os="linux")]let result=unsafe{libc::syscall(libc::SYS_renameat2,libc::AT_FDCWD,src.as_ptr(),libc::AT_FDCWD,dst.as_ptr(),libc::RENAME_NOREPLACE)};
 #[cfg(not(any(target_os="macos",target_os="linux")))]return Err(fail(ErrorCode::UnsupportedPlatform,"Plugin publication requires macOS/Linux"));
 #[cfg(any(target_os="macos",target_os="linux"))]if result==0{Ok(())}else{let e=std::io::Error::last_os_error();if e.kind()==std::io::ErrorKind::AlreadyExists||e.raw_os_error()==Some(libc::ENOTEMPTY){Err(fail(ErrorCode::DestinationExists,"Destination folder exists"))}else{Err(e.into())}}
}
fn run_child(python:&Path,wrapper:&Path,root_path:&Path,result:&Path,stdout:&Path,stderr:&Path,listener:TcpListener,token:&str,config:&serde_json::Value,job:&mut ImportJob<'_>,timeout:Duration)->Result<(String,Vec<String>)> {
 // The wrapper owns only this random private stage; publication moves result
 // out of it. Parent-death cleanup must never receive the destination path.
 let mut config=config.clone();
 config["parent_watch"]=json!({"pid":std::process::id(),"stage":root_path});
 fs::write(root_path.join(".studio-parent-watch"),token.as_bytes())?;
 let mut command=Command::new(python);command.arg("-u").arg(&wrapper).current_dir(&result).stdin(Stdio::piped()).stdout(Stdio::from(File::create(&stdout)?)).stderr(Stdio::from(File::create(&stderr)?));
 command.env("PYTHONDONTWRITEBYTECODE","1").env("PYTHONIOENCODING","utf-8");
 #[cfg(unix)]{use std::os::unix::process::CommandExt;command.process_group(0);}
 let mut child=ChildGuard {child:command.spawn()?,stopped:false};
 {let mut stdin=child.child.stdin.take().ok_or_else(||invalid("Missing child stdin"))?;let data=serde_json::to_vec(&config).map_err(|e|invalid(e.to_string()))?;if data.len()>65536{return Err(limit("Child configuration exceeds 64 KiB"));}stdin.write_all(&data)?;stdin.write_all(b"\n")?;}
 let conversation=conversation(listener,&mut child,stdout,stderr,root_path,token,job,timeout);child.stop();
 conversation.map_err(|mut e|{let trace=tail(&stderr);if !trace.is_empty(){e.message=format!("{}\n{}",e.message,trace);}e})
}

pub(crate) fn execute(r:&Request,job:&mut ImportJob<'_>)->Result<Receipt> {
 #[cfg(not(any(target_os="macos",target_os="linux")))]return Err(fail(ErrorCode::UnsupportedPlatform,"Python plugin jobs currently support macOS/Linux only"));
 check(job)?;
 if !valid_options(&r.options){return Err(invalid("Invalid plugin options scalar-map-v1"));}
 if !r.trusted{return Err(invalid("Local Python code must be explicitly trusted"));}
 match fs::symlink_metadata(&r.destination){Ok(_)=>return Err(fail(ErrorCode::DestinationExists,"Destination folder exists")),Err(e) if e.kind()==std::io::ErrorKind::NotFound=>{},Err(e)=>return Err(e.into())}
 let python=if r.python.is_absolute(){r.python.clone()}else{std::env::current_dir()?.join(&r.python)};let original=fs::canonicalize(&r.plugin)?;
 if !python.is_file(){return Err(invalid("Choose an existing Python interpreter executable"));}
 let parent=r.destination.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new("."));let root=tempfile::tempdir_in(parent)?;
 let root_path=fs::canonicalize(root.path())?;
 let work=root_path.join("input");let result=root_path.join("result");fs::create_dir(&work)?;fs::create_dir(&result)?;
 let extension=r.source.extension().and_then(|s|s.to_str()).filter(|s|s.len()<=12&&s.bytes().all(|b|b.is_ascii_alphanumeric())).unwrap_or("data");
 let input=work.join(format!("input.{extension}"));let snapshot=root_path.join("plugin.py");
 event(job,"python_snapshot",0)?;let input_sha256=copy(&r.source,&input,INPUT,job)?;let plugin_sha256=copy(&r.plugin,&snapshot,PLUGIN,job)?;
 if r.expected_plugin_sha256.as_ref().map_or(false,|s|s!=&plugin_sha256){return Err(invalid("Plugin source changed since inspection; inspect it again or clear the inspected selection"));}
 let wrapper=root_path.join("bridge.py");let base=root_path.join("base_plugin.py");fs::write(&wrapper,include_bytes!("plugin_wrapper.py"))?;fs::write(&base,include_bytes!("base_plugin.py"))?;
 let stdout=root_path.join("stdout.log");let stderr=root_path.join("stderr.log");let output=result.join("output.txt");
 let listener=TcpListener::bind((std::net::Ipv4Addr::LOCALHOST,0))?;listener.set_nonblocking(true)?;
 let mut random=[0u8;32];getrandom::fill(&mut random).map_err(|e|fail(ErrorCode::Internal,e.to_string()))?;let token=sha256::hex(&random);
 let config=json!({"port":listener.local_addr()?.port(),"token":token,"snapshot":snapshot,"original_plugin":original,"base":base,"class_name":r.class_name,"options":r.options,"input":input,"output":output});
 let(summary,callback_logs)=run_child(&python,&wrapper,&root_path,&result,&stdout,&stderr,listener,&token,&config,job,DEADLINE)?;
 check(job)?;let stdout_tail=tail(&stdout);let stderr_tail=tail(&stderr);
 // Preserve ordinary adjacent-input logs without ever passing the original
 // input path to the plugin. Only regular top-level sidecars are supported.
 for entry in fs::read_dir(&work)? {let entry=entry?;if entry.path()==input{continue;}if !entry.file_type()?.is_file(){return Err(invalid("Only regular adjacent-input sidecars are supported"));}let logs=result.join("input-sidecars");fs::create_dir_all(&logs)?;copy(&entry.path(),&logs.join(entry.file_name()),FILE_BYTES,job)?;}
 copy(&stdout,&result.join("bridge-stdout.log"),RAW_LOG,job)?;copy(&stderr,&result.join("bridge-stderr.log"),RAW_LOG,job)?;
 let(paths,bytes)=inventory(&result)?;
 File::open(&output)?.sync_all()?;
 event(job,"python_validate_txt",100)?;let(records,output_sha256)=crate::txt_packing::validate_plugin_output(output,job)?;
 let mut options_hash=sha256::Sha256::new();options_hash.update(&serde_json::to_vec(&r.options).map_err(|e|invalid(e.to_string()))?);
 let receipt=Receipt {options_sha256:sha256::hex(&options_hash.finish()),option_fields:r.options.len(),profile:"trusted-python-converter-v1",destination:r.destination.clone(),plugin_sha256,input_sha256,output_sha256,records,paths,bytes,summary,callback_logs,stdout_tail,stderr_tail};
 event(job,"python_commit",100)?;
 #[cfg(unix)]publish(&result,&r.destination)?;
 // Publication has committed. Later cancellation must remain success.
 Ok(receipt)
}

#[path="plugin_inspection.rs"]pub mod inspection;
#[path="plugin_folder.rs"]pub mod folder;
#[path="plugin_probe.rs"]pub mod probe;

#[cfg(test)]#[path="python_plugin_tests.rs"]mod tests;
