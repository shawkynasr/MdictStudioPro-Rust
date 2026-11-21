use serde::Serialize;
use std::fmt;

#[derive(Clone,Copy,Debug,PartialEq,Eq,Serialize)]
#[serde(rename_all="snake_case")]
pub enum ErrorCode {
    InvalidInput,UnsupportedPolicy,LimitExceeded,Cancelled,DestinationExists,
    Integrity,Io,Engine,Internal,UnsafePath,PathCollision,UnsupportedPlatform,
    InvalidEncoding,MalformedSource,UnrepresentableSource,MalformedWorkbook,
    UnsupportedWorkbook,UnsupportedCell,SheetNotFound,
}
#[derive(Debug,Serialize)]
pub struct Error {pub code:ErrorCode,pub message:String}
pub type Result<T>=std::result::Result<T,Error>;
impl Error {pub fn new(code:ErrorCode,message:impl Into<String>)->Self {Self {code,message:message.into()}}}
impl fmt::Display for Error {fn fmt(&self,f:&mut fmt::Formatter<'_>)->fmt::Result {write!(f,"{:?}: {}",self.code,self.message)}}
impl std::error::Error for Error {}
impl From<std::io::Error> for Error {fn from(e:std::io::Error)->Self {
    Self::new(if e.kind()==std::io::ErrorKind::AlreadyExists {ErrorCode::DestinationExists}else{ErrorCode::Io},e.to_string())
}}
impl From<studio_core::Error> for Error {fn from(e:studio_core::Error)->Self {
    use studio_core::ErrorCode as C;
    let code=match e.code {
        C::InvalidInput=>ErrorCode::InvalidInput,C::UnsupportedPolicy=>ErrorCode::UnsupportedPolicy,
        C::LimitExceeded=>ErrorCode::LimitExceeded,C::Cancelled=>ErrorCode::Cancelled,
        C::DestinationExists=>ErrorCode::DestinationExists,C::Integrity=>ErrorCode::Integrity,
        C::Io=>ErrorCode::Io,C::Engine=>ErrorCode::Engine,C::Internal=>ErrorCode::Internal,
        C::UnsafePath=>ErrorCode::UnsafePath,C::PathCollision=>ErrorCode::PathCollision,
        C::UnsupportedPlatform=>ErrorCode::UnsupportedPlatform,C::InvalidEncoding=>ErrorCode::InvalidEncoding,
        C::MalformedSource=>ErrorCode::MalformedSource,C::UnrepresentableSource=>ErrorCode::UnrepresentableSource,
    };Self::new(code,e.message)
}}
impl From<studio_xlsx::Error> for Error {fn from(e:studio_xlsx::Error)->Self {
    let code=match e.code {
        "invalid_input"=>ErrorCode::InvalidInput,"unsupported_policy"=>ErrorCode::UnsupportedPolicy,
        "limit_exceeded"=>ErrorCode::LimitExceeded,"cancelled"=>ErrorCode::Cancelled,
        "io"=>ErrorCode::Io,"malformed_workbook"=>ErrorCode::MalformedWorkbook,
        "unsupported_workbook"=>ErrorCode::UnsupportedWorkbook,"unsupported_cell"=>ErrorCode::UnsupportedCell,
        "sheet_not_found"=>ErrorCode::SheetNotFound,"malformed_source"=>ErrorCode::MalformedSource,
        "unrepresentable_source"=>ErrorCode::UnrepresentableSource,
        _=>return Self::new(ErrorCode::Internal,format!("Unmapped workbook/converter error {}: {}",e.code,e.message)),
    };Self::new(code,e.message)
}}
