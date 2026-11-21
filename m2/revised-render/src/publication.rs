use crate::{budget,sum,Control,Error,Limits,Result,sha256::{Sha256,hex}};
use std::{fs::File,io::{BufRead,BufReader,BufWriter,Read,Write},path::Path};
#[derive(Debug,PartialEq,Eq)]pub(crate) struct Summary {pub entries:usize,pub key_bytes:usize,pub body_bytes:usize,pub file_bytes:u64,pub file_sha256:String,pub framed_records_sha256:String}
struct State {entries:usize,keys:usize,bodies:usize,bytes:u64,lines:usize,txt:Sha256,framed:Sha256}
impl State {
 fn new()->Self {Self {entries:0,keys:0,bodies:0,bytes:0,lines:0,txt:Sha256::new(),framed:Sha256::new()}}
 fn add(&mut self,key:&str,body:&str,limits:&Limits)->Result<()> {
  if key.is_empty()||key=="</>"||key.starts_with('\u{feff}')||key.contains(['\0','\r','\n'])||body.contains(['\0','\r'])||body.split('\n').any(|s|s=="</>") {return Err(Error::new("unrepresentable_source","Invalid canonical TXT record"));}
  if key.len()>4096||body.len()>1024*1024||self.entries>=limits.entries {return Err(budget("Output record cap exceeded"));}
  self.keys=sum(self.keys,key.len())?;self.bodies=sum(self.bodies,body.len())?;self.bytes=self.bytes.checked_add((key.len()+body.len()+6) as u64).ok_or_else(||budget("TXT byte counter overflow"))?;self.lines=sum(self.lines,body.bytes().filter(|c|*c==b'\n').count()+3)?;
  if sum(self.keys,self.bodies)?>limits.decoded_bytes||self.bytes>limits.output_bytes||self.lines>4_000_000 {return Err(budget("Global TXT output cap exceeded"));}
  self.framed.update(&(self.entries as u64).to_le_bytes());self.framed.update(&(key.len() as u64).to_le_bytes());self.framed.update(key.as_bytes());self.framed.update(&(body.len() as u64).to_le_bytes());let mut h=Sha256::new();h.update(body.as_bytes());self.framed.update(&h.finish());
  for segment in [key,"\n",body,"\n</>\n"] {self.txt.update(segment.as_bytes());}self.entries+=1;Ok(())
 }
 fn finish(self)->Summary {Summary {entries:self.entries,key_bytes:self.keys,body_bytes:self.bodies,file_bytes:self.bytes,file_sha256:hex(&self.txt.finish()),framed_records_sha256:hex(&self.framed.finish())}}
}
pub(crate) struct Sink {temporary:tempfile::NamedTempFile,writer:Option<BufWriter<File>>,state:State,verified:bool}
impl Sink {
 pub fn new(destination:&Path)->Result<Self> {let parent=destination.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new("."));let temporary=tempfile::NamedTempFile::new_in(parent)?;let writer=BufWriter::with_capacity(65536,temporary.reopen()?);Ok(Self {temporary,writer:Some(writer),state:State::new(),verified:false})}
 pub fn append(&mut self,key:&str,body:&str,limits:&Limits,control:&Control<'_>)->Result<()> {
  control.check()?;if self.state.entries%256==0 {control.step("append_record",self.state.entries,limits.entries)?;}self.state.add(key,body,limits)?;
  let writer=self.writer.as_mut().ok_or_else(||Error::new("integrity","Output already sealed"))?;
  for segment in [key,"\n",body,"\n</>\n"] {for chunk in segment.as_bytes().chunks(65536) {control.check()?;writer.write_all(chunk)?;}}Ok(())
 }
 pub fn verify(&mut self,limits:&Limits,control:&Control<'_>)->Result<Summary> {
  let mut writer=self.writer.take().ok_or_else(||Error::new("integrity","Output already sealed"))?;writer.flush()?;drop(writer);self.temporary.as_file().sync_all()?;
  control.step("verify_output",0,limits.entries)?;let expected=std::mem::replace(&mut self.state,State::new()).finish();let actual=read_summary(self.temporary.path(),limits,control)?;
  if expected!=actual {return Err(Error::new("integrity","TXT differs after strict reopen"));}self.verified=true;Ok(expected)
 }
 pub fn commit(self,destination:&Path,control:&Control<'_>,entries:usize)->Result<()> {
  if !self.verified {return Err(Error::new("integrity","TXT not verified"));}control.step("before_publish",entries,entries)?;
  self.temporary.persist_noclobber(destination).map_err(|e|if e.error.kind()==std::io::ErrorKind::AlreadyExists {Error::new("destination_exists","TXT destination appeared before commit")}else{Error::from(e.error)})?;
  control.emit("published",entries,entries);Ok(())
 }
}
fn line(input:&mut BufReader<File>,buffer:&mut Vec<u8>,cap:usize)->Result<usize> {buffer.clear();let n=(&mut *input).take(cap as u64+1).read_until(b'\n',buffer)?;if n>cap||(n!=0&&!buffer.ends_with(b"\n")) {return Err(Error::new("malformed_source","TXT line exceeds cap or lacks LF"));}Ok(n)}
fn read_summary(path:&Path,limits:&Limits,control:&Control<'_>)->Result<Summary> {
 let mut input=BufReader::with_capacity(65536,File::open(path)?);let mut key=Vec::new();let mut raw=Vec::new();let mut body=Vec::new();let mut state=State::new();let mut bytes=0u64;let mut raw_hash=Sha256::new();
 loop {control.check()?;let n=line(&mut input,&mut key,4097)?;if n==0 {break;}bytes+=n as u64;raw_hash.update(&key);let key=std::str::from_utf8(&key[..n-1]).map_err(|_|Error::new("invalid_encoding","Invalid TXT key UTF-8"))?;body.clear();
  loop {control.check()?;let n=line(&mut input,&mut raw,1024*1024+1)?;if n==0 {return Err(Error::new("malformed_source","Missing TXT delimiter"));}bytes+=n as u64;if bytes>limits.output_bytes {return Err(budget("Reopened TXT file exceeds cap"));}raw_hash.update(&raw);
   if raw.as_slice()==b"</>\n" {if body.last()!=Some(&b'\n') {return Err(Error::new("malformed_source","Missing body separator"));}body.pop();break;}
   if sum(body.len(),raw.len())?>1024*1024+1 {return Err(budget("Reopened body cap exceeded"));}body.extend_from_slice(&raw);
  }
  let text=std::str::from_utf8(&body).map_err(|_|Error::new("invalid_encoding","Invalid TXT body UTF-8"))?;state.add(key,text,limits)?;if state.entries%256==0 {control.step("verify_output",state.entries,limits.entries)?;}
 }
 let result=state.finish();if result.entries==0||result.file_bytes!=bytes||result.file_sha256!=hex(&raw_hash.finish()) {return Err(Error::new("integrity","Reopened TXT extent or framing differs"));}Ok(result)
}
