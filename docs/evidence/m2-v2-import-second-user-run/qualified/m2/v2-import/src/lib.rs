//! Bounded unencrypted v2 import. This does not relax Studio export verification.
mod header;
mod mdx;
mod mdd;
#[path="../../studio-core/src/casing.rs"]
mod casing;
pub use header::{Header,Kind};
pub use mdx::{Dictionary,LookupPolicy,Resolution,RedirectHop};
pub use mdd::ResourceArchive;
pub use studio_application::{CancellationToken,ErrorCode,Progress,Stage};
pub use studio_core::{Entry,Resource};
use serde::Serialize;

#[derive(Debug,Serialize)]
pub struct Error {pub code:ErrorCode,pub detail:&'static str,pub message:String}
pub type Result<T>=std::result::Result<T,Error>;
impl Error {fn new(code:ErrorCode,detail:&'static str,message:impl Into<String>)->Self {Self {code,detail,message:message.into()}}}
impl std::fmt::Display for Error {fn fmt(&self,f:&mut std::fmt::Formatter<'_>)->std::fmt::Result {write!(f,"{}: {}",self.detail,self.message)}}
impl std::error::Error for Error {}
impl From<std::io::Error> for Error {fn from(e:std::io::Error)->Self {Self::new(ErrorCode::Io,"io",e.to_string())}}
impl From<mdictlib::Error> for Error {fn from(e:mdictlib::Error)->Self {
    let code=if matches!(&e,mdictlib::Error::ChecksumMismatch {..}) {ErrorCode::Integrity}else{ErrorCode::Engine};
    Self::new(code,"engine",e.to_string())
}}
fn invalid(detail:&'static str,message:impl Into<String>)->Error {Error::new(ErrorCode::InvalidInput,detail,message)}
fn unsupported(message:impl Into<String>)->Error {Error::new(ErrorCode::UnsupportedPolicy,"unsupported_profile",message)}
fn budget(message:&str)->Error {Error::new(ErrorCode::LimitExceeded,"limit_exceeded",message)}
fn integrity(message:&str)->Error {Error::new(ErrorCode::Integrity,"integrity",message)}
fn sum(a:usize,b:usize)->Result<usize> {a.checked_add(b).ok_or_else(||budget("Byte counter overflow"))}

#[derive(Clone,Debug,Default)]
pub struct Limits {pub dictionary:studio_core::Limits,pub redirects:RedirectLimits}
#[derive(Clone,Debug)]
pub struct RedirectLimits {pub max_hops:usize,pub max_visits:usize}
impl Default for RedirectLimits {fn default()->Self {Self {max_hops:16,max_visits:4096}}}
/// Uses the existing application token and serialized progress shape. This
/// separate facade has no background queue/Tauri routing in this first slice.
pub struct ImportJob<'a> {id:&'a str,token:&'a CancellationToken,progress:&'a mut dyn FnMut(Progress)}
impl<'a> ImportJob<'a> {
    pub fn new(id:&'a str,token:&'a CancellationToken,progress:&'a mut dyn FnMut(Progress))->Self {Self {id,token,progress}}
    fn check(&self)->Result<()> {
        if self.id.is_empty()||self.id.len()>256 {return Err(invalid("job_id","Job ID must contain 1..256 UTF-8 bytes"));}
        if self.token.is_cancelled() {Err(Error::new(ErrorCode::Cancelled,"cancelled","Import job cancelled"))}else{Ok(())}
    }
    fn tick(&mut self,phase:&str,completed:usize,total:usize)->Result<()> {
        self.check()?;(self.progress)(Progress {job_id:self.id.into(),stage:Stage::Converting,phase:phase.into(),completed,total});self.check()
    }
}
fn key(value:&str,limits:&Limits)->Result<()> {
    if value.is_empty()||value.contains('\0') {return Err(invalid("key","Expected a nonempty key without NUL"));}
    if value.len()>limits.dictionary.max_key_bytes {return Err(budget("Key byte budget exceeded"));}Ok(())
}
