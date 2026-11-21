//! Studio disk index v1. Indexes contain keys/ordinals only, never definitions.
use crate::{Dictionary,File,Row,Kind,ImportJob,Result,Error,ErrorCode,invalid,budget,integrity,sum,casing::Casing,sha256::{Sha256,hex}};
use std::{fs::File as FsFile,io::{Read,Write,Seek,SeekFrom,BufReader,BufWriter},path::{Path,PathBuf}};
use serde::{Serialize,Deserialize};
const HEAD:u64=4096;const MAX_ARTIFACT:u64=128*1024*1024;const MAX_TOKEN:usize=12288;const MAX_RUNS:usize=8192;
pub const REVISION:&str="studio-disk-index-v1-frozen16";
const CASING:&str="f69d2e55d6b8c8d5fe33f764cc47b829bccc6d73aaff1791e1216328a1c24071";
#[derive(Clone,Copy,Debug,PartialEq,Eq,Serialize,Deserialize)]#[serde(rename_all="snake_case")]
pub enum Policy {RawExact,HeaderAsciiV1}
#[derive(Clone,Debug,PartialEq,Eq,Serialize,Deserialize)]#[serde(deny_unknown_fields)]
pub struct Manifest {pub revision:String,pub engine_revision:String,pub casing_sha256:String,pub source_sha256:String,pub records:u64,pub kind:String,pub policy:Policy,pub case_sensitive:Option<bool>,pub strip_key:Option<bool>}
#[derive(Clone,Copy)]pub struct BuildOptions {pub run_bytes:usize,pub run_records:usize}
impl Default for BuildOptions {fn default()->Self {Self {run_bytes:2*1024*1024,run_records:8192}}}
impl BuildOptions {fn validate(self)->Result<()> {if self.run_bytes==0||self.run_bytes>2*1024*1024||self.run_records==0||self.run_records>8192 {return Err(invalid("index_limits","Require 1..2 MiB run bytes and 1..8192 run records"));}Ok(())}}
#[derive(Debug,Serialize)]pub struct BuildReceipt {pub manifest:Manifest,pub bytes:u64,pub initial_runs:usize}
#[derive(Debug,Serialize)]pub struct Page {pub basis:String,pub total:u64,pub offset:u64,pub next_offset:Option<u64>,pub rows:Vec<Row>}
pub struct Index<'a> {dictionary:&'a Dictionary,artifact:tempfile::NamedTempFile,manifest:Manifest,casing:Casing,end:u64}
type Item=(String,u64);
fn casing()->Result<Casing> {Casing::pinned16().map_err(|e|invalid("casing",e.to_string()))}
fn normalize(dictionary:&Dictionary,casing:&Casing,s:&str,policy:Policy)->String {
 if policy==Policy::RawExact {return s.into();}
 let value=if dictionary.header.case_sensitive==Some(false) {casing.lower(s)}else{s.into()};
 if dictionary.header.strip_key==Some(true) {value.chars().filter(|c|!c.is_ascii_punctuation()&&!matches!(c,'\t'..='\r'|' ')).collect()}else{value}
}
fn key(dictionary:&Dictionary,n:u64)->Result<String> {
 let ordinal=mdictlib::KeyOrdinal::new(n);
 let value=match &dictionary.file {File::Mdx(d)=>d.key_at(ordinal)?,File::Mdd(d)=>d.key_at(ordinal)?}.ok_or_else(||integrity("Index ordinal has no source key"))?;
 Ok(value.key().into())
}
fn hash(file:&mut FsFile,length:u64,job:&mut ImportJob<'_>)->Result<[u8;32]> {
 file.seek(SeekFrom::Start(0))?;let mut h=Sha256::new();let mut left=length;let mut b=[0;65536];
 while left>0 {job.check()?;let n=file.read(&mut b[..left.min(65536) as usize])?;if n==0 {return Err(integrity("Truncated file while hashing"));}h.update(&b[..n]);left-=n as u64;}
 Ok(h.finish())
}
fn manifest(dictionary:&Dictionary,policy:Policy,job:&mut ImportJob<'_>)->Result<Manifest> {
 if policy==Policy::HeaderAsciiV1 {
  if !matches!(dictionary.header.kind,Kind::Mdx) {return Err(invalid("index_policy","MDD requires raw_exact"));}
  if dictionary.header.case_sensitive.is_none()||dictionary.header.strip_key.is_none() {return Err(invalid("index_policy","Header lookup requires explicit case/strip flags"));}
 }
 job.tick("index_fingerprint",0,1)?;let mut f=FsFile::open(dictionary._source.path())?;let n=f.metadata()?.len();let digest=hex(&hash(&mut f,n,job)?);
 Ok(Manifest {revision:REVISION.into(),engine_revision:"mdictlib-0.2.8-studio-sort-v6".into(),casing_sha256:CASING.into(),source_sha256:digest,records:dictionary.scan.records,kind:if matches!(dictionary.header.kind,Kind::Mdx){"mdx"}else{"mdd"}.into(),policy,case_sensitive:dictionary.header.case_sensitive,strip_key:dictionary.header.strip_key})
}
fn write_item(out:&mut impl Write,item:&Item)->Result<()> {out.write_all(&(item.0.len() as u32).to_le_bytes())?;out.write_all(&item.1.to_le_bytes())?;out.write_all(item.0.as_bytes())?;Ok(())}
fn read_item(input:&mut impl Read)->Result<Option<Item>> {
 let mut len=[0;4];match input.read(&mut len[..1])? {0=>return Ok(None),_=>input.read_exact(&mut len[1..])?};let n=u32::from_le_bytes(len) as usize;
 if n>MAX_TOKEN {return Err(budget("Index sort token exceeds 12 KiB"));}let mut ord=[0;8];input.read_exact(&mut ord)?;let mut bytes=vec![0;n];input.read_exact(&mut bytes)?;
 Ok(Some((String::from_utf8(bytes).map_err(|_|integrity("Invalid UTF-8 sort token"))?,u64::from_le_bytes(ord))))
}
fn flush_run(items:&mut Vec<Item>,dir:&Path,serial:&mut usize)->Result<PathBuf> {
 items.sort_unstable();let p=dir.join(format!("run-{}",*serial));*serial+=1;let mut out=BufWriter::new(FsFile::create(&p)?);for item in items.iter() {write_item(&mut out,item)?;}out.flush()?;items.clear();Ok(p)
}
fn sorted(dictionary:&Dictionary,casing:&Casing,normal:bool,policy:Policy,dir:&Path,options:BuildOptions,job:&mut ImportJob<'_>)->Result<(PathBuf,usize)> {
 let(mut paths,mut items,mut bytes,mut serial,mut total_bytes)=(Vec::new(),Vec::with_capacity(options.run_records),0usize,0usize,0u64);
 for n in 0..dictionary.scan.records {
  if n%128==0 {job.tick("index_runs",n as usize,dictionary.scan.records as usize)?;}else{job.check()?;}
  let raw=key(dictionary,n)?;let token=if normal {normalize(dictionary,casing,&raw,policy)}else{raw};
  if token.len()>MAX_TOKEN {return Err(budget("Normalized key exceeds 12 KiB"));}
  // Bound serialized runs separately from allocator overhead; at most 8192
  // tuples are retained, and sort_unstable needs no auxiliary row vector.
  let added=sum(token.len(),12)?;if !items.is_empty()&&(sum(bytes,added)?>options.run_bytes||items.len()>=options.run_records) {
   paths.push(flush_run(&mut items,dir,&mut serial)?);bytes=0;
   if paths.len()>=MAX_RUNS {return Err(budget("External sort run-count cap exceeded"));}
  }
  if added>options.run_bytes {return Err(budget("One sort key exceeds run-byte budget"));}bytes=sum(bytes,added)?;total_bytes+=added as u64;if total_bytes>MAX_ARTIFACT/2 {return Err(budget("One index sort section exceeds 64 MiB"));}items.push((token,n));
 }
 if !items.is_empty()||paths.is_empty() {paths.push(flush_run(&mut items,dir,&mut serial)?);}let initial=paths.len();
 while paths.len()>1 {
  let mut next=Vec::new();
  for group in paths.chunks(8) {
   job.tick("index_merge",next.len(),paths.len().div_ceil(8))?;
   let mut readers=group.iter().map(|p|FsFile::open(p).map(BufReader::new)).collect::<std::io::Result<Vec<_>>>()?;
   let mut heads=readers.iter_mut().map(read_item).collect::<Result<Vec<_>>>()?;
   let p=dir.join(format!("run-{serial}"));serial+=1;let mut out=BufWriter::new(FsFile::create(&p)?);
   loop {job.check()?;let selected=heads.iter().enumerate().filter_map(|(i,h)|h.as_ref().map(|h|(i,h))).min_by(|(_,a),(_,b)|a.cmp(b)).map(|(i,_)|i);let Some(i)=selected else {break;};write_item(&mut out,heads[i].as_ref().unwrap())?;heads[i]=read_item(&mut readers[i])?;}
   out.flush()?;drop(out);drop(readers);for p in group {std::fs::remove_file(p)?;}next.push(p);
  }paths=next;
 }Ok((paths.remove(0),initial))
}
fn slot(file:&mut FsFile,count:u64,section:u64,n:u64,end:u64)->Result<(String,u64,u64)> {
 if n>=count||section>1 {return Err(integrity("Index slot out of range"));}
 file.seek(SeekFrom::Start(HEAD+(section*count+n)*16))?;let mut b=[0;16];file.read_exact(&mut b)?;
 let offset=u64::from_le_bytes(b[..8].try_into().unwrap());let length=u32::from_le_bytes(b[8..12].try_into().unwrap()) as usize;let ordinal=u32::from_le_bytes(b[12..].try_into().unwrap()) as u64;
 if ordinal>=count||length>MAX_TOKEN||offset<HEAD+32*count||offset.checked_add(length as u64).is_none_or(|v|v>end) {return Err(integrity("Invalid index key extent or ordinal"));}
 file.seek(SeekFrom::Start(offset))?;let mut data=vec![0;length];file.read_exact(&mut data)?;
 Ok((String::from_utf8(data).map_err(|_|integrity("Invalid index UTF-8"))?,ordinal,offset))
}
impl<'a> Index<'a> {
 /// Cache publication is exclusive and never deletes or replaces an existing
 /// artifact. On success, cancellation arriving after commit cannot revoke it.
 pub fn build(dictionary:&'a Dictionary,path:&Path,policy:Policy,options:BuildOptions,job:&mut ImportJob<'_>)->Result<BuildReceipt> {
  job.check()?;options.validate()?;if path.try_exists()? {return Err(Error::new(ErrorCode::DestinationExists,"destination_exists","Index destination exists"));}
  let m=manifest(dictionary,policy,job)?;let c=casing()?;let parent=path.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new("."));
  let scratch=tempfile::tempdir_in(parent)?;let mut artifact=tempfile::NamedTempFile::new_in(parent)?;let n=m.records;let mut end=HEAD+32*n;artifact.as_file_mut().set_len(end)?;let mut runs=0;
  for section in 0..2u64 {
   let dir=tempfile::tempdir_in(scratch.path())?;let(p,initial)=sorted(dictionary,&c,section==1,policy,dir.path(),options,job)?;runs+=initial;let mut input=BufReader::new(FsFile::open(p)?);
   for i in 0..n {
    job.check()?;let(token,ordinal)=read_item(&mut input)?.ok_or_else(||integrity("Incomplete sorted run"))?;
    if end+token.len() as u64+32>MAX_ARTIFACT {return Err(budget("Index artifact exceeds 128 MiB"));}
    let file=artifact.as_file_mut();file.seek(SeekFrom::Start(HEAD+(section*n+i)*16))?;file.write_all(&end.to_le_bytes())?;file.write_all(&(token.len() as u32).to_le_bytes())?;file.write_all(&(ordinal as u32).to_le_bytes())?;
    file.seek(SeekFrom::Start(end))?;file.write_all(token.as_bytes())?;end+=token.len() as u64;
   }if read_item(&mut input)?.is_some() {return Err(integrity("Extra sorted keys"));}
  }
  let bytes=serde_json::to_vec(&m).map_err(|e|invalid("manifest",e.to_string()))?;if bytes.len()>HEAD as usize-12 {return Err(budget("Index manifest exceeds fixed header"));}
  let f=artifact.as_file_mut();f.seek(SeekFrom::Start(0))?;f.write_all(b"STIDX001")?;f.write_all(&(bytes.len() as u32).to_le_bytes())?;f.write_all(&bytes)?;f.flush()?;
  let digest=hash(f,end,job)?;f.seek(SeekFrom::Start(end))?;f.write_all(&digest)?;f.flush()?;f.sync_all()?;
  // Prove completeness, order and frozen normalization before publication.
  {let _verified=Self::open(dictionary,artifact.path(),policy,job)?;}
  drop(scratch);let receipt=BuildReceipt {manifest:m,bytes:end+32,initial_runs:runs};job.tick("index_publish",0,1)?;
  artifact.persist_noclobber(path).map_err(|e|if e.error.kind()==std::io::ErrorKind::AlreadyExists {Error::new(ErrorCode::DestinationExists,"destination_exists","Index destination exists")}else{Error::from(e.error)})?;
  Ok(receipt)
 }
 pub fn open(dictionary:&'a Dictionary,path:&Path,policy:Policy,job:&mut ImportJob<'_>)->Result<Self> {
  let expected=manifest(dictionary,policy,job)?;job.tick("index_snapshot",0,1)?;let mut source=FsFile::open(path)?;let metadata=source.metadata()?;
  if !metadata.is_file()||metadata.len()<HEAD+32||metadata.len()>MAX_ARTIFACT {return Err(integrity("Invalid or oversized cache artifact"));}
  let mut artifact=tempfile::NamedTempFile::new()?;let mut buffer=[0;65536];let mut copied=0u64;
  loop {job.check()?;let n=source.read(&mut buffer)?;if n==0 {break;}copied+=n as u64;if copied>MAX_ARTIFACT {return Err(budget("Cache grew past cap"));}artifact.write_all(&buffer[..n])?;}
  if copied!=metadata.len() {return Err(integrity("Cache changed size during snapshot"));}let end=copied-32;let file=artifact.as_file_mut();let digest=hash(file,end,job)?;let mut want=[0;32];file.read_exact(&mut want)?;if want!=digest {return Err(integrity("Cache SHA-256 mismatch"));}
  file.seek(SeekFrom::Start(0))?;let mut header=[0;4096];file.read_exact(&mut header)?;if &header[..8]!=b"STIDX001" {return Err(integrity("Unknown cache format"));}let size=u32::from_le_bytes(header[8..12].try_into().unwrap()) as usize;
  if size>4084||header[12+size..].iter().any(|b|*b!=0) {return Err(integrity("Invalid cache header extent/padding"));}
  let m:Manifest=serde_json::from_slice(&header[12..12+size]).map_err(|_|integrity("Invalid cache manifest"))?;
  if m!=expected||HEAD+32*m.records>end {return Err(integrity("Stale cache or wrong source/policy/revision"));}
  let mut out=Self {dictionary,artifact,manifest:m,casing:casing()?,end};out.verify(job)?;dictionary.memory_usage()?;Ok(out)
 }
 fn verify(&mut self,job:&mut ImportJob<'_>)->Result<()> {
  let n=self.manifest.records;let mut position=HEAD+32*n;
  for section in 0..2 {
   let mut seen=vec![0u8;n.div_ceil(8) as usize];let mut previous:Option<Item>=None;
   for i in 0..n {
    if i%128==0 {job.tick("index_verify",(section*n+i) as usize,(2*n) as usize)?;}else{job.check()?;}
    let(token,ordinal,offset)=slot(self.artifact.as_file_mut(),n,section,i,self.end)?;
    if offset!=position {return Err(integrity("Noncanonical cache blob extent"));}position+=token.len() as u64;
    let mask=1u8<<(ordinal%8);let byte=&mut seen[(ordinal/8) as usize];if *byte&mask!=0 {return Err(integrity("Duplicate cache ordinal"));}*byte|=mask;
    let raw=key(self.dictionary,ordinal)?;let expected=if section==1 {normalize(self.dictionary,&self.casing,&raw,self.manifest.policy)}else{raw};
    if token!=expected||previous.as_ref().is_some_and(|p|p>=&(token.clone(),ordinal)) {return Err(integrity("Cache token/order differs from complete source key space"));}previous=Some((token,ordinal));
   }
  }if position!=self.end {return Err(integrity("Unreferenced cache payload"));}job.check()
 }
 fn bound(&mut self,section:u64,query:&str,upper:bool,job:&mut ImportJob<'_>)->Result<u64> {
  let(mut lo,mut hi)=(0,self.manifest.records);while lo<hi {job.check()?;let mid=lo+(hi-lo)/2;let(value,_,_)=slot(self.artifact.as_file_mut(),self.manifest.records,section,mid,self.end)?;if value.as_str()<query||(upper&&value==query) {lo=mid+1;}else{hi=mid;}}Ok(lo)
 }
 pub fn page(&mut self,query:&str,offset:u64,limit:usize,job:&mut ImportJob<'_>)->Result<Page> {
  job.tick("index_lookup",0,1)?;crate::validate_key(query)?;if limit>128 {return Err(budget("Index page exceeds 128 rows"));}
  let mut section=0;let mut token=query.to_string();let(mut lo,mut hi)=(self.bound(0,&token,false,job)?,self.bound(0,&token,true,job)?);let mut basis="exact";
  if lo==hi&&self.manifest.policy==Policy::HeaderAsciiV1 {section=1;token=normalize(self.dictionary,&self.casing,query,self.manifest.policy);if token.is_empty() {return Err(invalid("empty_normalized_query","Query becomes empty under header_ascii_v1"));}lo=self.bound(1,&token,false,job)?;hi=self.bound(1,&token,true,job)?;basis="normalized";}
  let total=hi-lo;let start=lo+offset.min(total);let stop=hi.min(start+limit as u64);let(mut rows,mut bytes)=(Vec::new(),0usize);
  for i in start..stop {
   job.check()?;let(_,ordinal,_)=slot(self.artifact.as_file_mut(),self.manifest.records,section,i,self.end)?;let ord=mdictlib::KeyOrdinal::new(ordinal);
   let row=match &self.dictionary.file {
    File::Mdx(d)=>{let r=d.entry_at(ord)?.ok_or_else(||integrity("Missing indexed row"))?;Row {ordinal,key:r.key().into(),text:Some(r.text().into()),bytes:None}},
    File::Mdd(d)=>{let r=d.resource_at(ord)?.ok_or_else(||integrity("Missing indexed resource"))?;Row {ordinal,key:r.key().into(),text:None,bytes:Some(r.bytes().into())}},
   };
   let payload=row.text.as_ref().map_or_else(||row.bytes.as_ref().map_or(0,Vec::len),String::len);bytes=sum(bytes,sum(row.key.len(),payload)?)?;
   if payload>self.dictionary.limits.engine.materialized_record_bytes()||bytes>self.dictionary.limits.max_result_bytes {return Err(budget("Complete page exceeds payload byte cap"));}rows.push(row);
  }
  job.check()?;self.dictionary.memory_usage()?;let next=offset.min(total)+rows.len() as u64;
  Ok(Page {basis:if total==0 {"none"}else{basis}.into(),total,offset,next_offset:if next<total&&limit>0 {Some(next)}else{None},rows})
 }
 pub fn manifest(&self)->&Manifest {&self.manifest}
}
