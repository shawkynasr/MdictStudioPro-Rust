//! Explicit parser ceilings and complete streaming v2 validation. This first
//! sizing API retains no full definition collection or process-lifetime locator.
#[path="../../v2-import/src/header.rs"]mod header;
pub use header::{Header,Kind};
pub use studio_v2_import::{CancellationToken,ErrorCode,Progress,Stage};
use mdictlib::{MdxFile,MddFile,OpenOptions,ChecksumPolicy};
use serde::Serialize;
use std::{path::Path,fmt};

pub const PROFILE:&str="bounded-lazy-scan-v1";
#[derive(Debug,Serialize)]
pub struct LimitFailure {pub name:&'static str,pub value:u64,pub max:u64}
#[derive(Debug,Serialize)]
pub struct Error {pub code:ErrorCode,pub detail:&'static str,pub message:String,#[serde(skip_serializing_if="Option::is_none")]pub limit:Option<LimitFailure>}
pub type Result<T>=std::result::Result<T,Error>;
impl Error {fn new(code:ErrorCode,detail:&'static str,message:impl Into<String>)->Self {Self {code,detail,message:message.into(),limit:None}}}
impl fmt::Display for Error {fn fmt(&self,f:&mut fmt::Formatter<'_>)->fmt::Result {write!(f,"{}: {}",self.detail,self.message)}}
impl std::error::Error for Error {}
impl From<std::io::Error> for Error {fn from(e:std::io::Error)->Self {Self::new(ErrorCode::Io,"io",e.to_string())}}
impl From<mdictlib::Error> for Error {fn from(e:mdictlib::Error)->Self {
    let mut out=Self::new(ErrorCode::Engine,"engine",e.to_string());
    match e {
        mdictlib::Error::LimitExceeded {limit,value,max}=>{out.code=ErrorCode::LimitExceeded;out.detail="engine_limit";out.limit=Some(LimitFailure {name:limit,value,max});},
        mdictlib::Error::AllocationFailed {..}=>{out.code=ErrorCode::LimitExceeded;out.detail="allocation_failed";},
        mdictlib::Error::ChecksumMismatch {..}=>{out.code=ErrorCode::Integrity;out.detail="engine_checksum";},
        mdictlib::Error::Decode {..}=>{out.code=ErrorCode::InvalidEncoding;out.detail="engine_decode";},
        mdictlib::Error::Cancelled {..}=>{out.code=ErrorCode::Cancelled;out.detail="cancelled";},
        mdictlib::Error::Unsupported(_)=>{out.code=ErrorCode::UnsupportedPolicy;out.detail="unsupported_profile";},
        mdictlib::Error::Io(_)=>{out.code=ErrorCode::Io;out.detail="engine_io";},
        _=>{},
    }out
}}
fn invalid(detail:&'static str,message:impl Into<String>)->Error {Error::new(ErrorCode::InvalidInput,detail,message)}
fn unsupported(message:impl Into<String>)->Error {Error::new(ErrorCode::UnsupportedPolicy,"unsupported_profile",message)}
fn budget(message:&str)->Error {Error::new(ErrorCode::LimitExceeded,"limit_exceeded",message)}
fn integrity(message:&str)->Error {Error::new(ErrorCode::Integrity,"integrity",message)}
fn sum(a:usize,b:usize)->Result<usize> {a.checked_add(b).ok_or_else(||budget("Byte counter overflow"))}

#[derive(Clone,Debug)]
pub struct Limits {pub dictionary:studio_core::Limits,pub engine:mdictlib::Limits,pub max_rows:u64,pub max_scan_bytes:u64,pub max_matches:usize,pub max_result_bytes:usize}
impl Default for Limits {fn default()->Self {
    Self {dictionary:studio_core::Limits {max_file_bytes:512*1024*1024,..studio_core::Limits::default()},
        engine:mdictlib::Limits::new().with_header_xml_bytes(65536).with_header_attributes(256)
            .with_key_index_bytes(16*1024*1024).with_record_index_bytes(16*1024*1024)
            .with_compressed_block_bytes(8*1024*1024).with_decompressed_block_bytes(8*1024*1024)
            .with_block_metadata_bytes(16*1024*1024).with_key_block_entries(65536)
            .with_materialized_record_bytes(2*1024*1024).with_locator_entries(0).with_locator_bytes(0)
            .with_working_memory_bytes(64*1024*1024),
        max_rows:500000,max_scan_bytes:2*1024*1024*1024,max_matches:256,max_result_bytes:2*1024*1024}
}}
impl Limits {fn validate(&self)->Result<()> {
    let ceiling=Self::default();let a=&self.engine;let b=&ceiling.engine;
    if self.dictionary.max_file_bytes>ceiling.dictionary.max_file_bytes||self.dictionary.max_metadata_bytes>65536||self.max_rows>ceiling.max_rows||self.max_scan_bytes>ceiling.max_scan_bytes||self.max_matches>256||self.max_result_bytes>ceiling.max_result_bytes||
        a.header_xml_bytes()>b.header_xml_bytes()||a.header_attributes()>b.header_attributes()||a.key_index_bytes()>b.key_index_bytes()||a.record_index_bytes()>b.record_index_bytes()||a.compressed_block_bytes()>b.compressed_block_bytes()||a.decompressed_block_bytes()>b.decompressed_block_bytes()||a.block_metadata_bytes()>b.block_metadata_bytes()||a.key_block_entries()>b.key_block_entries()||a.materialized_record_bytes()>b.materialized_record_bytes()||a.working_memory_bytes()>b.working_memory_bytes()||a.locator_bytes()!=0||a.locator_entries()!=0 {
        return Err(invalid("limits","This first bounded profile only permits lowering its fixed ceilings; locator must stay disabled"));
    }Ok(())
}}
pub struct ImportJob<'a> {id:&'a str,token:&'a CancellationToken,progress:&'a mut dyn FnMut(Progress)}
impl<'a> ImportJob<'a> {
    pub fn new(id:&'a str,token:&'a CancellationToken,progress:&'a mut dyn FnMut(Progress))->Self {Self {id,token,progress}}
    fn check(&self)->Result<()> {
        if self.id.is_empty()||self.id.len()>256 {return Err(invalid("job_id","Require 1..256 UTF-8 bytes for job ID"));}
        if self.token.is_cancelled() {return Err(Error::new(ErrorCode::Cancelled,"cancelled","Bounded reader cancelled"));}Ok(())
    }
    fn tick(&mut self,phase:&str,completed:usize,total:usize)->Result<()> {self.check()?;(self.progress)(Progress {job_id:self.id.into(),stage:Stage::Converting,phase:phase.into(),completed,total});self.check()}
}
#[derive(Debug,Serialize)]
pub struct Usage {pub current:usize,pub peak:usize,pub locator:usize,pub metadata:usize,pub key_cache:usize,pub record_cache:usize,pub budget:usize}
#[derive(Debug,Serialize)]
pub struct Scan {pub records:u64,pub key_bytes:u64,pub payload_bytes:u64,pub framed_fnv64:String}
struct Digest(u64);
impl Digest {
    fn new()->Self {Self(0xcbf29ce484222325)}
    fn add(&mut self,data:&[u8]) {for &b in data {self.0=(self.0^u64::from(b)).wrapping_mul(0x100000001b3);}}
    fn row(&mut self,ordinal:u64,key:&str,data:&[u8]) {self.add(&ordinal.to_le_bytes());self.add(&(key.len() as u64).to_le_bytes());self.add(key.as_bytes());self.add(&(data.len() as u64).to_le_bytes());self.add(data);}
}
enum File {Mdx(MdxFile),Mdd(MddFile)}
pub struct Dictionary {_source:tempfile::NamedTempFile,file:File,header:Header,limits:Limits,scan:Scan}
#[derive(Debug,Serialize)]
pub struct Row {pub ordinal:u64,pub key:String,#[serde(skip_serializing_if="Option::is_none")]pub text:Option<String>,#[serde(skip_serializing_if="Option::is_none")]pub bytes:Option<Vec<u8>>}
impl Dictionary {
    pub fn open_v2(path:&Path,kind:Kind,limits:&Limits,job:&mut ImportJob<'_>)->Result<Self> {
        job.check()?;limits.validate()?;let(source,header)=header::snapshot(path,kind,limits,job)?;
        job.tick("engine_open",0,1)?;let options=OpenOptions::new().with_checksum_policy(ChecksumPolicy::Verify).with_limits(limits.engine.clone());
        let file=match kind {Kind::Mdx=>File::Mdx(MdxFile::open_with_options(source.path(),&options)?),Kind::Mdd=>File::Mdd(MddFile::open_with_options(source.path(),&options)?)};
        let count=match &file {File::Mdx(d)=>d.len(),File::Mdd(d)=>d.len()};if count>limits.max_rows {return Err(budget("Physical row count exceeds bounded reader cap"));}
        let mut out=Self {_source:source,file,header,limits:limits.clone(),scan:Scan {records:0,key_bytes:0,payload_bytes:0,framed_fnv64:String::new()}};
        out.scan=out.validate_all(count,job)?;out.memory_usage()?;Ok(out)
    }
    pub fn header(&self)->&Header {&self.header}
    pub fn scan(&self)->&Scan {&self.scan}
    pub fn memory_usage(&self)->Result<Usage> {
        let u=match &self.file {File::Mdx(d)=>d.memory_usage()?,File::Mdd(d)=>d.memory_usage()?};
        if u.locator_bytes()!=0||u.peak_bytes()>self.limits.engine.working_memory_bytes() {return Err(integrity("Streaming reader constructed a locator or exceeded its accounted parser budget"));}
        Ok(Usage {current:u.current_bytes(),peak:u.peak_bytes(),locator:u.locator_bytes(),metadata:u.metadata_bytes(),key_cache:u.key_cache_bytes(),record_cache:u.record_cache_bytes(),budget:self.limits.engine.working_memory_bytes()})
    }
    fn validate_all(&self,total:u64,job:&mut ImportJob<'_>)->Result<Scan> {
        let(mut count,mut key_bytes,mut payload_bytes)=(0u64,0u64,0u64);let mut digest=Digest::new();
        let mut visit=|ordinal:u64,key:&str,data:&[u8],job:&mut ImportJob<'_>|->Result<()> {
            if ordinal!=count {return Err(integrity("Physical ordinal continuity changed"));}validate_key(key)?;
            if data.len()>self.limits.engine.materialized_record_bytes() {return Err(budget("Decoded record exceeds application materialization cap"));}
            key_bytes=key_bytes.checked_add(key.len() as u64).ok_or_else(||budget("Key byte overflow"))?;
            payload_bytes=payload_bytes.checked_add(data.len() as u64).ok_or_else(||budget("Payload byte overflow"))?;
            if key_bytes.checked_add(payload_bytes).ok_or_else(||budget("Scan byte overflow"))?>self.limits.max_scan_bytes {return Err(budget("Cumulative decoded scan budget exceeded"));}
            digest.row(ordinal,key,data);count+=1;if count%256==0 {job.tick("bounded_scan",count as usize,total as usize)?;}else {job.check()?;}Ok(())
        };
        job.tick("bounded_scan",0,total as usize)?;
        match &self.file {
            File::Mdx(d)=>{let mut it=d.entries();loop {job.check()?;let Some(row)=it.next() else {break;};let row=row?;visit(row.ordinal().get(),row.key(),row.text().as_bytes(),job)?;}},
            File::Mdd(d)=>{let mut it=d.resources();loop {job.check()?;let Some(row)=it.next() else {break;};let row=row?;visit(row.ordinal().get(),row.key(),row.bytes(),job)?;}},
        }
        drop(visit);if count!=total {return Err(integrity("Incomplete physical scan"));}job.tick("bounded_scan",count as usize,total as usize)?;
        Ok(Scan {records:count,key_bytes,payload_bytes,framed_fnv64:format!("{:016x}",digest.0)})
    }
    /// Explicit raw-exact lookup by bounded traversal. No normalized fallback,
    /// redirect resolution or process-lifetime locator is selected implicitly.
    pub fn lookup_exact(&self,query:&str,job:&mut ImportJob<'_>)->Result<Vec<Row>> {
        job.check()?;validate_key(query)?;let mut rows=Vec::new();let mut bytes=0usize;
        macro_rules! push {($ordinal:expr,$key:expr,$data:expr,$row:expr)=>{{
            if rows.len()>=self.limits.max_matches {return Err(budget("Exact duplicate set exceeds result-count cap"));}
            bytes=sum(bytes,sum($key.len(),$data.len())?)?;if bytes>self.limits.max_result_bytes {return Err(budget("Complete exact result exceeds byte cap"));}
            rows.push($row);
        }}}
        match &self.file {
            File::Mdx(d)=>for (i,key) in d.keys().enumerate() {
                if i%256==0 {job.tick("bounded_lookup",i,self.scan.records as usize)?;}else{job.check()?;}let key=key?;
                if key.key()==query {let value=d.entry_at(key.ordinal())?.ok_or_else(||integrity("Missing physical MDX row"))?;push!(key.ordinal().get(),key.key(),value.text().as_bytes(),Row {ordinal:key.ordinal().get(),key:key.key().into(),text:Some(value.text().into()),bytes:None});}
            },
            File::Mdd(d)=>for (i,key) in d.keys().enumerate() {
                if i%256==0 {job.tick("bounded_lookup",i,self.scan.records as usize)?;}else{job.check()?;}let key=key?;
                if key.key()==query {let value=d.resource_at(key.ordinal())?.ok_or_else(||integrity("Missing physical MDD row"))?;push!(key.ordinal().get(),key.key(),value.bytes(),Row {ordinal:key.ordinal().get(),key:key.key().into(),text:None,bytes:Some(value.bytes().into())});}
            },
        }
        job.check()?;self.memory_usage()?;Ok(rows)
    }
}
fn validate_key(key:&str)->Result<()> {if key.is_empty()||key.contains('\0') {return Err(invalid("key","Require a nonempty NUL-free key"));}if key.len()>4096 {return Err(budget("UTF-8 key exceeds 4 KiB"));}Ok(())}
