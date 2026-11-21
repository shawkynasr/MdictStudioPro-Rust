//! Isolated XLSX compatibility boundary. Raw OOXML scalar lexemes preserve the
//! original openpyxl normalization; calamine validates/reads the selected range.
mod xml;
mod numbers;
mod package;
mod reader;
pub mod moe;

pub use numbers::normalize_number;
pub use reader::{read_xlsx,read_xlsx_bytes};
use serde::Serialize;
use std::{collections::BTreeMap,fmt};

pub const PROFILE:&str="openpyxl-values-v1";

#[derive(Debug,Serialize)]
pub struct Error {pub code:&'static str,pub message:String}
impl Error {pub(crate) fn new(code:&'static str,message:impl Into<String>)->Self {Self {code,message:message.into()}}}
impl fmt::Display for Error {fn fmt(&self,f:&mut fmt::Formatter<'_>)->fmt::Result {write!(f,"{}: {}",self.code,self.message)}}
impl std::error::Error for Error {}
pub type Result<T>=std::result::Result<T,Error>;
pub(crate) fn malformed(error:impl fmt::Display)->Error {Error::new("malformed_workbook",error.to_string())}
pub(crate) fn budget(message:&str)->Error {Error::new("limit_exceeded",message)}

#[derive(Clone,Debug)]
pub struct Limits {
    pub max_file_bytes:u64,pub max_uncompressed_bytes:u64,pub max_part_bytes:u64,
    pub max_parts:usize,pub max_rows:u32,pub max_columns:u32,pub max_cells:u64,
    pub max_value_bytes:usize,pub max_decoded_bytes:usize,
}
impl Default for Limits {
    fn default()->Self {Self {max_file_bytes:16*1024*1024,max_uncompressed_bytes:64*1024*1024,
        max_part_bytes:16*1024*1024,max_parts:2048,max_rows:10_000,max_columns:256,
        max_cells:1_000_000,max_value_bytes:1024*1024,max_decoded_bytes:16*1024*1024}}
}

#[derive(Debug,Serialize)]
pub struct Progress {pub phase:&'static str,pub completed:usize,pub total:usize}
pub struct ReadControl<'a> {cancelled:&'a dyn Fn()->bool,progress:&'a mut dyn FnMut(Progress)}
impl<'a> ReadControl<'a> {
    pub fn new(cancelled:&'a dyn Fn()->bool,progress:&'a mut dyn FnMut(Progress))->Self {Self {cancelled,progress}}
    pub(crate) fn check(&self)->Result<()> {
        if (self.cancelled)() {Err(Error::new("cancelled","Workbook read cancelled"))}else{Ok(())}
    }
    pub(crate) fn checkpoint(&mut self,phase:&'static str,completed:usize,total:usize)->Result<()> {
        self.check()?;(self.progress)(Progress {phase,completed,total});self.check()
    }
}

#[derive(Debug,Serialize)]
pub struct Table {
    pub profile:&'static str,pub backend:&'static str,pub sheet_name:String,
    pub headers:Vec<String>,pub rows:Vec<BTreeMap<String,String>>,
    pub scanned_data_rows:usize,pub skipped_blank_rows:usize,
}

pub(crate) fn py_space(c:char)->bool {
    matches!(c,'\t'..='\r'|'\u{1c}'..='\u{20}'|'\u{85}'|'\u{a0}'|'\u{1680}'|
        '\u{2000}'..='\u{200a}'|'\u{2028}'|'\u{2029}'|'\u{202f}'|'\u{205f}'|'\u{3000}')
}
pub(crate) fn trimmed(text:&str)->String {text.trim_matches(py_space).to_owned()}
