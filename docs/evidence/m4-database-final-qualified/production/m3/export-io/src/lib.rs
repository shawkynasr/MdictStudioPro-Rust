//! M3 export-only profile derived from accepted M2 streaming I/O.
//! This new 96 MiB profile requires its own native qualification.
#[path="../../../m2/v2-import/src/header.rs"]mod header;
pub use header::{Header,Kind};
pub use studio_v2_import::{CancellationToken,ErrorCode,Progress,Stage};
use serde::Serialize;
use std::fmt;

pub const PROFILE:&str="studio-m3-stream-export-96-v1";
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
            .with_materialized_record_bytes(4*1024*1024).with_locator_entries(0).with_locator_bytes(0)
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

impl From<studio_v2_import::Error> for Error {fn from(e:studio_v2_import::Error)->Self {Self::new(e.code,e.detail,e.message)}}
fn core_error(e:studio_core::Error)->Error {let e:studio_application::Error=e.into();Error::new(e.code,"resource_path",e.message)}
#[path="../../../m2/studio-core/src/casing.rs"]mod casing;
#[path="../../../m2/indexed-engine/src/sha256.rs"]mod sha256;
mod io;
pub use io::{Request,Metadata,IoLimits,Summary,execute};
#[cfg(test)]mod tests;
