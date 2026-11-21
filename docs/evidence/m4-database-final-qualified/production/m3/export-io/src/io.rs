use crate::{Result,Error,ErrorCode,Limits,ImportJob,Kind,invalid,budget,integrity,core_error,casing::Casing,sha256::{Sha256,hex}};
use serde::{Serialize,Deserialize};
use std::{collections::{BTreeMap,BTreeSet},fs::File,io::{Read,Write,BufRead,BufReader,Seek,SeekFrom},path::{Path,PathBuf}};
use mdictlib::{MdxFile,MddFile,OpenOptions,ChecksumPolicy,WriteOptions,WriteEncoding,WriteCompression,LegacySort,MdxBuilder,MddBuilder};
use studio_v2_import::application::metadata::{serialize,FileKind};
#[derive(Clone,Debug,Default,Serialize,Deserialize)]#[serde(deny_unknown_fields)]pub struct Metadata {pub title:String,pub description:String,#[serde(default)]pub stylesheet:String,#[serde(default)]pub extra:BTreeMap<String,String>}
impl Metadata {fn attributes(&self,kind:FileKind)->Result<BTreeMap<String,String>> {
 let reserved=["GeneratedByEngineVersion","RequiredEngineVersion","Encrypted","Encoding","Format","KeyCaseSensitive","StripKey","Title","Description","StyleSheet","Compact","Compat","xmlns"];
 let mut out=self.extra.clone();for k in out.keys() {if k.to_ascii_lowercase().starts_with("studio")||reserved.iter().any(|n|k.eq_ignore_ascii_case(n)) {return Err(invalid("metadata_override","Extra metadata cannot override structural/profile attributes"));}}
 if matches!(kind,FileKind::Mdd)&&!self.stylesheet.is_empty() {return Err(invalid("stylesheet","MDD cannot carry numeric definition styles"));}
 out.insert("Title".into(),self.title.clone());out.insert("Description".into(),self.description.clone());out.insert("StyleSheet".into(),self.stylesheet.clone());serialize(kind,&out)?;Ok(out)
}}
#[derive(Debug,Deserialize)]#[serde(tag="operation",rename_all="snake_case",deny_unknown_fields)]pub enum Request {
 PackMdx {source:PathBuf,destination:PathBuf,encoding:studio_core::Encoding,metadata:Metadata},
 PackMdd {source:PathBuf,resource_root:PathBuf,destination:PathBuf,metadata:Metadata},
 ExportJsonl {source:PathBuf,destination:PathBuf},ExportTxt {source:PathBuf,destination:PathBuf},
}
impl Request {fn destination(&self)->&Path {match self {Self::PackMdx {destination,..}|Self::PackMdd {destination,..}|Self::ExportJsonl {destination,..}|Self::ExportTxt {destination,..}=>destination}}}
#[derive(Clone,Debug)]pub struct IoLimits {pub reader:Limits,pub max_records:usize,pub max_decoded_bytes:usize,pub max_entry_bytes:usize,pub max_plan_charge:usize,pub max_input_bytes:u64,pub max_output_bytes:u64}
impl Default for IoLimits {fn default()->Self {Self {reader:Limits::default(),max_records:250000,max_decoded_bytes:96*1024*1024,max_entry_bytes:1024*1024,max_plan_charge:16*1024*1024,max_input_bytes:128*1024*1024,max_output_bytes:128*1024*1024}}}
impl IoLimits {fn validate(&self)->Result<()> {self.reader.validate()?;let c=Self::default();if self.max_records>c.max_records||self.max_decoded_bytes>c.max_decoded_bytes||self.max_entry_bytes>c.max_entry_bytes||self.max_plan_charge>c.max_plan_charge||self.max_input_bytes>c.max_input_bytes||self.max_output_bytes>c.max_output_bytes {return Err(invalid("limits","Only lower IO ceilings are supported"));}Ok(())}}
#[derive(Debug,Serialize)]pub struct Summary {pub profile:&'static str,pub operation:&'static str,pub records:usize,pub key_bytes:u64,pub payload_bytes:u64,pub framed_records_sha256:String,pub file_bytes:u64,pub source_sha256:String,pub metadata:BTreeMap<String,String>}
#[derive(Default)]struct Digest {records:usize,key_bytes:u64,payload_bytes:u64,sha:Option<Sha256>}
impl Digest {
 fn row(&mut self,key:&str,bytes:&[u8]) {let mut body=Sha256::new();body.update(bytes);let sha=self.sha.get_or_insert_with(Sha256::new);sha.update(&(self.records as u64).to_le_bytes());sha.update(&(key.len() as u64).to_le_bytes());sha.update(key.as_bytes());sha.update(&(bytes.len() as u64).to_le_bytes());sha.update(&body.finish());self.records+=1;self.key_bytes+=key.len() as u64;self.payload_bytes+=bytes.len() as u64;}
 fn finish(self)->(usize,u64,u64,String) {(self.records,self.key_bytes,self.payload_bytes,hex(&self.sha.unwrap_or_else(Sha256::new).finish()))}
}
struct Descriptor {key:String,sort:String,ordinal:usize,offset:u64,length:usize}
#[derive(Deserialize)]#[serde(deny_unknown_fields)]struct InputRow {key:String,text:Option<String>,file:Option<String>}
#[derive(Serialize)]struct ExportRow<'a> {key:&'a str,text:&'a str}
fn key(value:&str)->Result<()> {if value.is_empty()||value.contains('\0') {return Err(invalid("key","Require nonempty NUL-free key"));}if value.len()>4096 {return Err(budget("Key exceeds 4 KiB"));}Ok(())}
fn markers(body:&str,ids:&BTreeSet<String>)->Result<()> {let b=body.as_bytes();let mut i=0;while i<b.len() {if b[i]==b'`' {let start=i+1;let mut end=start;while end<b.len()&&b[end].is_ascii_digit() {end+=1;}if end>start&&end<b.len()&&b[end]==b'`' {if !ids.contains(&body[start..end]) {return Err(invalid("stylesheet_marker","Numeric definition marker has no stylesheet rule"));}i=end;}}i+=1;}Ok(())}
fn rule_ids(style:&str)->BTreeSet<String> {if style.is_empty() {BTreeSet::new()}else{style.strip_suffix('\n').unwrap_or(style).split('\n').step_by(3).map(str::to_string).collect()}}
fn check_row(k:&str,payload:&[u8],count:usize,total:&mut usize,limits:&IoLimits)->Result<()> {key(k)?;if count>=limits.max_records||payload.len()>limits.max_entry_bytes {return Err(budget("Record count or payload cap exceeded"));}*total=total.checked_add(k.len()).and_then(|n|n.checked_add(payload.len())).ok_or_else(||budget("Decoded byte overflow"))?;if *total>limits.max_decoded_bytes {return Err(budget("Aggregate decoded key/payload cap exceeded"));}Ok(())}
fn read_line(input:&mut impl BufRead,cap:usize)->Result<Option<Vec<u8>>> {let mut out=Vec::new();loop {let b=input.fill_buf()?;if b.is_empty() {return if out.is_empty(){Ok(None)}else{Err(invalid("source_line","Every source record/line requires a final LF"))};}let n=b.iter().position(|b|*b==b'\n').map_or(b.len(),|p|p+1);if out.len()+n>cap {return Err(budget("Source line exceeds byte cap"));}out.extend_from_slice(&b[..n]);input.consume(n);if out.last()==Some(&b'\n') {return Ok(Some(out));}}}
fn hash_file(f:&mut File,job:&mut ImportJob<'_>)->Result<String> {f.seek(SeekFrom::Start(0))?;let mut h=Sha256::new();let mut b=[0;65536];loop {job.check()?;let n=f.read(&mut b)?;if n==0 {break;}h.update(&b[..n]);}Ok(hex(&h.finish()))}
fn snapshot(path:&Path,cap:u64,job:&mut ImportJob<'_>)->Result<tempfile::NamedTempFile> {let mut f=File::open(path)?;if !f.metadata()?.is_file() {return Err(invalid("source","Expected regular input file"));}if f.metadata()?.len()>cap {return Err(budget("Input file exceeds cap"));}let mut out=tempfile::NamedTempFile::new()?;let mut count=0u64;let mut b=[0;65536];loop {job.tick("input_snapshot",count as usize,cap as usize)?;let n=f.read(&mut b)?;if n==0 {break;}count+=n as u64;if count>cap {return Err(budget("Input grew past cap"));}out.write_all(&b[..n])?;}out.flush()?;out.seek(SeekFrom::Start(0))?;Ok(out)}
#[cfg(unix)]fn resource(root:&File,name:&str,cap:usize,job:&mut ImportJob<'_>)->Result<Vec<u8>> {
 use std::{ffi::CString,os::{fd::{AsRawFd,FromRawFd},unix::ffi::OsStrExt}};
 if name.starts_with(['/', '\\']) {return Err(invalid("resource_reference","Resource references must be relative to selected root"));}let path=studio_core::resource_relative_path(name).map_err(core_error)?;let parts=path.iter().collect::<Vec<_>>();let mut parent=root.try_clone()?;
 for (i,part) in parts.iter().enumerate() {job.check()?;let c=CString::new(part.as_bytes()).map_err(|_|invalid("resource_reference","NUL in resource reference"))?;let flags=libc::O_RDONLY|libc::O_NOFOLLOW|libc::O_CLOEXEC|if i+1<parts.len(){libc::O_DIRECTORY}else{0};
  // SAFETY: owned directory descriptor and validated single component. Neither
  // directories nor leaves may follow symlinks outside the selected root.
  let fd=unsafe {libc::openat(parent.as_raw_fd(),c.as_ptr(),flags|libc::O_NONBLOCK)};if fd<0 {return Err(std::io::Error::last_os_error().into());}parent=unsafe {File::from_raw_fd(fd)};
 }if !parent.metadata()?.is_file() {return Err(invalid("resource_reference","Resource must be a regular file"));}if parent.metadata()?.len()>cap as u64 {return Err(budget("Resource exceeds payload cap"));}let mut bytes=Vec::new();parent.take(cap as u64+1).read_to_end(&mut bytes)?;if bytes.len()>cap {return Err(budget("Resource grew past payload cap"));}job.check()?;Ok(bytes)
}
fn load(source:&Path,root:Option<&Path>,style:&str,limits:&IoLimits,job:&mut ImportJob<'_>)->Result<(tempfile::NamedTempFile,Vec<Descriptor>,String)> {
 let mut input=snapshot(source,limits.max_input_bytes,job)?;let source_sha=hash_file(input.as_file_mut(),job)?;input.seek(SeekFrom::Start(0))?;let mut reader=BufReader::new(input.as_file());let casing=Casing::pinned16().map_err(|e|invalid("casing",e.to_string()))?;let ids=rule_ids(style);let mut spool=tempfile::NamedTempFile::new()?;let(mut rows,mut total,mut charge)=(Vec::new(),0usize,0usize);
 #[cfg(unix)]let root_file=if let Some(path)=root {use std::os::unix::fs::OpenOptionsExt;Some(std::fs::OpenOptions::new().read(true).custom_flags(libc::O_DIRECTORY|libc::O_NOFOLLOW|libc::O_CLOEXEC).open(path)?)}else{None};
 #[cfg(not(unix))]if root.is_some() {return Err(crate::unsupported("Descriptor-relative resource packing requires Unix"));}
 while let Some(line)=read_line(&mut reader,8*1024*1024)? {
  job.tick("load_records",rows.len(),limits.max_records)?;std::str::from_utf8(&line).map_err(|_|Error::new(ErrorCode::InvalidEncoding,"source_utf8","JSONL must be strict UTF-8"))?;let row:InputRow=serde_json::from_slice(&line).map_err(|e|invalid("source_json",e.to_string()))?;
  let payload=if root.is_none() {if row.file.is_some() {return Err(invalid("source_json","MDX rows require key/text only"));}let body=row.text.ok_or_else(||invalid("source_json","Missing MDX text"))?;if body.contains('\0') {return Err(invalid("definition","NUL is not representable"));}markers(&body,&ids)?;body.into_bytes()}
  else {if row.text.is_some() {return Err(invalid("source_json","MDD rows require key/file only"));}let name=row.file.ok_or_else(||invalid("source_json","Missing resource reference"))?;
   #[cfg(unix)]{resource(root_file.as_ref().unwrap(),&name,limits.max_entry_bytes,job)?}
   #[cfg(not(unix))]{let _=name;return Err(invalid("platform","Resource input unsupported"));}
  };
  check_row(&row.key,&payload,rows.len(),&mut total,limits)?;let sort=casing.lower(&row.key);charge=charge.checked_add(2*std::mem::size_of::<Descriptor>()+row.key.len()+sort.len()).ok_or_else(||budget("Descriptor charge overflow"))?;if charge>limits.max_plan_charge {return Err(budget("Descriptor plan cap exceeded"));}let offset=spool.stream_position()?;spool.write_all(&payload)?;rows.push(Descriptor {key:row.key,sort,ordinal:rows.len(),offset,length:payload.len()});
 }if rows.is_empty() {return Err(invalid("source","No complete input records"));}rows.sort_by(|a,b|a.sort.cmp(&b.sort).then(a.ordinal.cmp(&b.ordinal)));spool.flush()?;Ok((spool,rows,source_sha))
}
fn payload(spool:&mut tempfile::NamedTempFile,row:&Descriptor)->Result<Vec<u8>> {spool.seek(SeekFrom::Start(row.offset))?;let mut bytes=vec![0;row.length];spool.read_exact(&mut bytes)?;Ok(bytes)}
struct Output<'a> {file:&'a mut File,bytes:u64,cap:u64,exceeded:bool}
impl Write for Output<'_> {fn write(&mut self,b:&[u8])->std::io::Result<usize> {if b.len() as u64>self.cap.saturating_sub(self.bytes) {self.exceeded=true;return Err(std::io::Error::other("Output file cap exceeded"));}let n=self.file.write(b)?;self.bytes+=n as u64;Ok(n)}fn flush(&mut self)->std::io::Result<()> {self.file.flush()}}
impl Seek for Output<'_> {fn seek(&mut self,pos:SeekFrom)->std::io::Result<u64> {let n=self.file.seek(pos)?;if n>self.cap {self.exceeded=true;return Err(std::io::Error::other("Output seek exceeds cap"));}self.bytes=n;Ok(n)}}
fn adler(data:&[u8])->u32 {let(mut a,mut b)=(1u32,0u32);for v in data {a=(a+u32::from(*v))%65521;b=(b+a)%65521;}(b<<16)|a}
fn destination(path:&Path)->Result<()> {if path.as_os_str().is_empty()||path.as_os_str().len()>16384||path.file_name().is_none() {return Err(invalid("destination","Require bounded destination file path"));}match std::fs::symlink_metadata(path) {Ok(_)=>Err(Error::new(ErrorCode::DestinationExists,"destination_exists","Destination exists")),Err(e) if e.kind()==std::io::ErrorKind::NotFound=>Ok(()),Err(e)=>Err(e.into())}}
fn stage(path:&Path)->Result<tempfile::NamedTempFile> {Ok(tempfile::NamedTempFile::new_in(path.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new(".")))?)}
fn publish(file:tempfile::NamedTempFile,path:&Path,job:&mut ImportJob<'_>)->Result<()> {job.tick("publish_file",0,1)?;file.persist_noclobber(path).map_err(|e|if e.error.kind()==std::io::ErrorKind::AlreadyExists {Error::new(ErrorCode::DestinationExists,"destination_exists","Destination exists")}else{e.error.into()})?;Ok(())}
pub fn execute(request:&Request,limits:&IoLimits,job:&mut ImportJob<'_>)->Result<Summary> {
 job.check()?;limits.validate()?;if !matches!(request,Request::ExportTxt {..}|Request::ExportJsonl {..}) {return Err(crate::unsupported("This profile accepts MDX TXT/JSONL exports only"));}destination(request.destination())?;
 match request {
  Request::PackMdx {source,destination,encoding,metadata}=>pack(source,destination,None,Some(*encoding),metadata,limits,job),
  Request::PackMdd {source,resource_root,destination,metadata}=>pack(source,destination,Some(resource_root),None,metadata,limits,job),
  Request::ExportJsonl {source,destination}=>export(source,destination,false,limits,job),Request::ExportTxt {source,destination}=>export(source,destination,true,limits,job),
 }
}
fn pack(source:&Path,destination:&Path,root:Option<&Path>,encoding:Option<studio_core::Encoding>,metadata:&Metadata,limits:&IoLimits,job:&mut ImportJob<'_>)->Result<Summary> {
 let kind=if root.is_some(){FileKind::Mdd}else{FileKind::Mdx};let edits=metadata.attributes(kind)?;let(mut spool,rows,source_sha)=load(source,root,&metadata.stylesheet,limits,job)?;let options=WriteOptions::new().with_legacy_sort(LegacySort::PreserveInput).with_compression(WriteCompression::Zlib).with_key_block_target_bytes(16*1024).with_record_block_target_bytes(64*1024);let mut raw=tempfile::NamedTempFile::new()?;let mut expected=Digest::default();
 if let Some(encoding)=encoding {
  let options=options.with_encoding(match encoding {studio_core::Encoding::Utf8=>WriteEncoding::Utf8,studio_core::Encoding::Utf16=>WriteEncoding::Utf16Le});let mut builder=MdxBuilder::with_options(options);for(k,v) in [("Format","Html"),("Compact","No"),("Compat","Yes"),("StyleSheet","")] {builder.header_attribute(k,v)?;}
  for (i,row) in rows.iter().enumerate() {job.tick("builder_entries",i,rows.len())?;let p=payload(&mut spool,row)?;builder.add_entry(&row.key,std::str::from_utf8(&p).map_err(|_|integrity("Spool UTF-8 changed"))?)?;expected.row(&row.key,&p);}
  job.tick("encode_dictionary",0,1)?;let mut out=Output {file:raw.as_file_mut(),bytes:0,cap:limits.max_output_bytes,exceeded:false};let result=builder.finish(&mut out);if out.exceeded {return Err(budget("Encoded dictionary exceeds output cap"));}result?;
 }else {
  let mut builder=MddBuilder::with_options(options);for(k,v) in [("Format",""),("Compact","No"),("Compat","No"),("StyleSheet","")] {builder.header_attribute(k,v)?;}
  for(i,row) in rows.iter().enumerate() {job.tick("builder_resources",i,rows.len())?;let p=payload(&mut spool,row)?;builder.add_resource(&row.key,&p)?;expected.row(&row.key,&p);}
  job.tick("encode_dictionary",0,1)?;let mut out=Output {file:raw.as_file_mut(),bytes:0,cap:limits.max_output_bytes,exceeded:false};let result=builder.finish(&mut out);if out.exceeded {return Err(budget("Encoded dictionary exceeds output cap"));}result?;
 }
 job.tick("encoded_dictionary",1,1)?;raw.flush()?;let filekind=if root.is_some(){Kind::Mdd}else{Kind::Mdx};let(_,header)=crate::header::snapshot(raw.path(),filekind,&limits.reader,job)?;let mut attrs=header.attributes;
 for name in ["KeyCaseSensitive","StripKey"] {if attrs.get(name).map(String::as_str)!=Some("No") {return Err(invalid("builder_policy","Expected builder-generated literal No/No flags"));}}
 attrs.extend(edits);if !metadata.stylesheet.is_empty() {attrs.insert("Compact".into(),"Yes".into());}let xml=serialize(kind,&attrs)?;if xml.len() as u64+8>limits.max_output_bytes {return Err(budget("Metadata-adjusted header exceeds output cap"));}let mut output=stage(destination)?;let mut capped=Output {file:output.as_file_mut(),bytes:0,cap:limits.max_output_bytes,exceeded:false};capped.write_all(&(xml.len() as u32).to_be_bytes())?;capped.write_all(&xml)?;capped.write_all(&adler(&xml).to_le_bytes())?;raw.seek(SeekFrom::Start(0))?;let mut size=[0;4];raw.read_exact(&mut size)?;raw.seek(SeekFrom::Start(8+u64::from(u32::from_be_bytes(size))))?;let mut b=[0;65536];loop {job.check()?;let n=raw.read(&mut b)?;if n==0 {break;}if let Err(e)=capped.write_all(&b[..n]) {if capped.exceeded {return Err(budget("Metadata-adjusted output exceeds cap"));}return Err(e.into());}}capped.flush()?;drop(capped);output.as_file().sync_all()?;
 let(verified,check_header)=crate::header::snapshot(output.path(),filekind,&limits.reader,job)?;if check_header.attributes!=attrs||check_header.raw_utf16le!=xml {return Err(integrity("Packed metadata differs"));}let options=OpenOptions::new().with_checksum_policy(ChecksumPolicy::Verify).with_limits(limits.reader.engine.clone());let mut actual=Digest::default();
 if root.is_none() {let file=MdxFile::open_with_options(verified.path(),&options)?;for(i,entry) in file.entries().enumerate() {job.tick("verify_records",i,rows.len())?;let e=entry?;let row=rows.get(i).ok_or_else(||integrity("Extra packed record"))?;let p=payload(&mut spool,row)?;if e.ordinal().get()!=i as u64||e.key()!=row.key||e.text().as_bytes()!=p {return Err(integrity("Packed MDX record differs"));}actual.row(e.key(),e.text().as_bytes());}if file.memory_usage()?.locator_bytes()!=0 {return Err(integrity("Packing verifier allocated locator"));}}
 else {let file=MddFile::open_with_options(verified.path(),&options)?;for(i,entry) in file.resources().enumerate() {job.tick("verify_records",i,rows.len())?;let e=entry?;let row=rows.get(i).ok_or_else(||integrity("Extra packed resource"))?;let p=payload(&mut spool,row)?;if e.ordinal().get()!=i as u64||e.key()!=row.key||e.bytes()!=p {return Err(integrity("Packed MDD record differs"));}actual.row(e.key(),e.bytes());}if file.memory_usage()?.locator_bytes()!=0 {return Err(integrity("Packing verifier allocated locator"));}}
 let expected=expected.finish();let found=actual.finish();if expected!=found||found.0!=rows.len() {return Err(integrity("Incomplete packed record set"));}let bytes=output.as_file().metadata()?.len();let result=Summary {profile:crate::PROFILE,operation:if root.is_some(){"pack_mdd"}else{"pack_mdx"},records:found.0,key_bytes:found.1,payload_bytes:found.2,framed_records_sha256:found.3,file_bytes:bytes,source_sha256:source_sha,metadata:attrs};publish(output,destination,job)?;Ok(result)
}
fn txt_row(key:&str,text:&str,first:bool)->Result<()> {
 if key.contains(['\r','\n'])||key=="</>"||first&&key.starts_with('\u{feff}')||text.contains('\r')||text.split('\n').any(|line|line=="</>") {return Err(Error::new(ErrorCode::UnrepresentableSource,"txt_grammar","Canonical TXT cannot represent this key/body without changing it"));}Ok(())
}
fn parse_txt(path:&Path,limits:&IoLimits,job:&mut ImportJob<'_>)->Result<Digest> {
 let mut reader=BufReader::new(File::open(path)?);let mut current=None;let mut body=String::new();let(mut result,mut total,mut lines)=(Digest::default(),0usize,0usize);
 while let Some(bytes)=read_line(&mut reader,limits.max_entry_bytes+4096+2)? {
  job.check()?;lines+=1;if lines>2_000_000 {return Err(budget("TXT line cap exceeded"));}let s=std::str::from_utf8(&bytes).map_err(|_|integrity("Staged TXT UTF-8 differs"))?;let line=s.strip_suffix('\n').unwrap();
  if current.is_none() {key(line)?;current=Some(line.to_string());}
  else if line=="</>" {if body.is_empty() {return Err(integrity("Missing TXT body line"));}body.pop();let key=current.take().unwrap();check_row(&key,body.as_bytes(),result.records,&mut total,limits)?;result.row(&key,body.as_bytes());body.clear();}
  else {if body.len()+s.len()>limits.max_entry_bytes+1 {return Err(budget("TXT definition cap exceeded"));}body.push_str(s);}
 }if current.is_some() {return Err(integrity("Unterminated staged TXT record"));}Ok(result)
}
fn export(source:&Path,destination:&Path,txt:bool,limits:&IoLimits,job:&mut ImportJob<'_>)->Result<Summary> {
 let(snapshot,header)=crate::header::snapshot(source,Kind::Mdx,&limits.reader,job)?;let mut input=File::open(snapshot.path())?;let source_sha=hash_file(&mut input,job)?;let options=OpenOptions::new().with_checksum_policy(ChecksumPolicy::Verify).with_limits(limits.reader.engine.clone());let file=MdxFile::open_with_options(snapshot.path(),&options)?;if file.len()>limits.max_records as u64 {return Err(budget("Export record count exceeds cap"));}
 let mut output=stage(destination)?;let mut cap=Output {file:output.as_file_mut(),bytes:0,cap:limits.max_output_bytes,exceeded:false};let(mut expected,mut total)=(Digest::default(),0usize);
 for entry in file.entries() {job.tick("export_records",expected.records,file.len() as usize)?;let e=entry?;if e.ordinal().get()!=expected.records as u64 {return Err(integrity("Export physical ordinals differ"));}check_row(e.key(),e.text().as_bytes(),expected.records,&mut total,limits)?;if e.text().contains('\0') {return Err(invalid("definition","NUL definition is outside this profile"));}
  let result=if txt {txt_row(e.key(),e.text(),expected.records==0)?;cap.write_all(e.key().as_bytes()).and_then(|_|cap.write_all(b"\n")).and_then(|_|cap.write_all(e.text().as_bytes())).and_then(|_|cap.write_all(b"\n</>\n"))}else {serde_json::to_writer(&mut cap,&ExportRow {key:e.key(),text:e.text()}).map_err(std::io::Error::other).and_then(|_|cap.write_all(b"\n"))};
  if let Err(e)=result {if cap.exceeded {return Err(budget("Export output cap exceeded"));}return Err(e.into());}expected.row(e.key(),e.text().as_bytes());
 }cap.flush()?;drop(cap);output.as_file().sync_all()?;if expected.records as u64!=file.len()||file.memory_usage()?.locator_bytes()!=0 {return Err(integrity("Incomplete export or locator allocated"));}let want=(expected.records,expected.key_bytes,expected.payload_bytes);let digest=expected.finish();
 let actual=if txt {parse_txt(output.path(),limits,job)?}else {let mut r=BufReader::new(File::open(output.path())?);let mut d=Digest::default();let mut total=0;while let Some(line)=read_line(&mut r,8*1024*1024)? {job.check()?;let row:InputRow=serde_json::from_slice(&line).map_err(|_|integrity("Invalid staged JSONL"))?;let text=row.text.ok_or_else(||integrity("Missing staged body"))?;if row.file.is_some() {return Err(integrity("Unexpected resource field in JSONL"));}check_row(&row.key,text.as_bytes(),d.records,&mut total,limits)?;d.row(&row.key,text.as_bytes());}d};
 let found=actual.finish();if found!=digest||want!=(found.0,found.1,found.2) {return Err(integrity("Export strict reparse differs"));}let bytes=output.as_file().metadata()?.len();let result=Summary {profile:crate::PROFILE,operation:if txt {"export_txt"}else{"export_jsonl"},records:found.0,key_bytes:found.1,payload_bytes:found.2,framed_records_sha256:found.3,file_bytes:bytes,source_sha256:source_sha,metadata:header.attributes};publish(output,destination,job)?;Ok(result)
}
