//! Disk-backed normalized MOE rows. One bounded XML part, one row and an SST
//! offset index are resident; no calamine range or whole normalized table.
mod package;
#[path="../../xlsx-reader/src/xml.rs"]mod xml;
#[path="../../xlsx-reader/src/numbers.rs"]mod numbers;
#[path="../../indexed-engine/src/sha256.rs"]mod sha256;
mod rows;
use serde::{Deserialize,Serialize};
use std::{cell::RefCell,collections::BTreeMap,fs::File,io::{Read,Write},path::{Path,PathBuf}};
use sha256::{Sha256,hex};
pub const PROFILE:&str="moe-disk-rows-general-numeric-v1";
#[derive(Debug,Serialize)]pub struct Error {pub code:&'static str,pub message:String}
impl Error {pub fn new(code:&'static str,message:impl Into<String>)->Self {Self {code,message:message.into()}}}
impl std::fmt::Display for Error {fn fmt(&self,f:&mut std::fmt::Formatter<'_>)->std::fmt::Result {write!(f,"{}: {}",self.code,self.message)}}
impl std::error::Error for Error {}
pub type Result<T>=std::result::Result<T,Error>;
impl From<std::io::Error> for Error {fn from(e:std::io::Error)->Self {Self::new("io",e.to_string())}}
fn malformed(e:impl std::fmt::Display)->Error {Error::new("malformed_workbook",e.to_string())}
fn budget(s:&str)->Error {Error::new("limit_exceeded",s)}
pub(crate) fn py_space(c:char)->bool {matches!(c,'\t'..='\r'|'\u{1c}'..='\u{20}'|'\u{85}'|'\u{a0}'|'\u{1680}'|'\u{2000}'..='\u{200a}'|'\u{2028}'|'\u{2029}'|'\u{202f}'|'\u{205f}'|'\u{3000}')}
pub(crate) fn trimmed(s:&str)->String {s.trim_matches(py_space).to_owned()}
#[derive(Clone,Debug,Serialize)]pub struct Limits {
 pub input_bytes:u64,pub part_bytes:u64,pub expanded_bytes:u64,pub parts:usize,
 pub rows:u32,pub columns:u32,pub cells:u64,pub shared_strings:usize,
 pub shared_bytes:u64,pub value_bytes:usize,pub row_bytes:usize,pub normalized_bytes:usize,pub spool_bytes:u64,
}
impl Default for Limits {fn default()->Self {Self {input_bytes:32*1024*1024,part_bytes:96*1024*1024,expanded_bytes:128*1024*1024,parts:2048,rows:200000,columns:64,cells:3200000,shared_strings:1000000,shared_bytes:96*1024*1024,value_bytes:1024*1024,row_bytes:8*1024*1024,normalized_bytes:128*1024*1024,spool_bytes:192*1024*1024}}}
impl Limits {fn validate(&self)->Result<()> {let cap=Self::default();macro_rules! bound {($field:ident)=>{if self.$field>cap.$field {return Err(Error::new("invalid_input","Row profile ceilings may only be lowered"));}};}bound!(input_bytes);bound!(part_bytes);bound!(expanded_bytes);bound!(parts);bound!(rows);bound!(columns);bound!(cells);bound!(shared_strings);bound!(shared_bytes);bound!(value_bytes);bound!(row_bytes);bound!(normalized_bytes);bound!(spool_bytes);Ok(())}}
#[derive(Debug,Default,Deserialize)]#[serde(deny_unknown_fields)]pub struct Tighten {pub rows:Option<u32>,pub cells:Option<u64>,pub part_bytes:Option<u64>,pub value_bytes:Option<usize>,pub row_bytes:Option<usize>,pub shared_bytes:Option<u64>,pub shared_strings:Option<usize>,pub normalized_bytes:Option<usize>,pub spool_bytes:Option<u64>}
impl Tighten {pub fn limits(&self)->Result<Limits> {let mut l=Limits::default();macro_rules! lower {($field:ident)=>{if let Some(n)=self.$field {if n>l.$field {return Err(Error::new("invalid_input","Limits may only be lowered"));}l.$field=n;}};}lower!(rows);lower!(cells);lower!(part_bytes);lower!(value_bytes);lower!(row_bytes);lower!(shared_bytes);lower!(shared_strings);lower!(normalized_bytes);lower!(spool_bytes);Ok(l)}}
#[derive(Debug)]pub struct Progress {pub phase:&'static str,pub completed:usize,pub total:usize}
pub struct ReadControl<'a> {cancelled:&'a dyn Fn()->bool,progress:RefCell<&'a mut dyn FnMut(Progress)>}
impl<'a> ReadControl<'a> {
 pub fn new(cancelled:&'a dyn Fn()->bool,progress:&'a mut dyn FnMut(Progress))->Self {Self {cancelled,progress:RefCell::new(progress)}}
 pub(crate) fn check(&self)->Result<()> {if (self.cancelled)() {Err(Error::new("cancelled","Row read cancelled"))}else{Ok(())}}
 pub(crate) fn checkpoint(&self,phase:&'static str,completed:usize,total:usize)->Result<()> {self.check()?;(self.progress.borrow_mut())(Progress {phase,completed,total});self.check()}
}
#[derive(Clone,Debug,Serialize,PartialEq,Eq)]pub struct RowDigest {pub rows:u64,pub pairs:u64,pub key_bytes:u64,pub value_bytes:u64,pub framed_rows_sha256:String}
pub(crate) struct Digest {hash:Sha256,rows:u64,pairs:u64,keys:u64,values:u64}
impl Digest {
 fn new()->Self {Self {hash:Sha256::new(),rows:0,pairs:0,keys:0,values:0}}
 fn add(&mut self,row:&BTreeMap<String,String>) {self.hash.update(&self.rows.to_le_bytes());self.hash.update(&(row.len() as u64).to_le_bytes());for(k,v)in row {self.hash.update(&(k.len() as u64).to_le_bytes());self.hash.update(k.as_bytes());self.hash.update(&(v.len() as u64).to_le_bytes());self.hash.update(v.as_bytes());self.keys+=k.len() as u64;self.values+=v.len() as u64;}self.rows+=1;self.pairs+=row.len() as u64;}
 fn finish(self)->RowDigest {RowDigest {rows:self.rows,pairs:self.pairs,key_bytes:self.keys,value_bytes:self.values,framed_rows_sha256:hex(&self.hash.finish())}}
}
#[derive(Clone,Debug,Serialize)]pub struct Receipt {
 pub profile:&'static str,pub source_sha256:String,pub worksheet:String,pub headers:Vec<String>,
 pub declared_rows:u32,pub declared_columns:u32,pub stored_cells:u64,pub scanned_data_rows:u32,pub skipped_blank_rows:u32,
 pub shared_strings:usize,pub shared_string_bytes:u64,pub shared_index_bytes:usize,pub shared_index_reserved_bytes:usize,pub normalized_charge_bytes:usize,
 pub row_spool_bytes:u64,pub temporary_bytes:u64,pub row_digest:RowDigest,pub parts:usize,pub advertised_expansion_bytes:u64,pub largest_advertised_part_bytes:u64,
}
pub struct Spool {private:tempfile::TempDir,rows:PathBuf,pub receipt:Receipt}
impl Spool {pub fn rows_path(&self)->&Path {&self.rows}pub fn private_path(&self)->&Path {self.private.path()}}
pub fn read_to_spool(source:&Path,worksheet:Option<&str>,limits:&Limits,control:&ReadControl<'_>)->Result<Spool> {
 control.checkpoint("begin",0,0)?;limits.validate()?;let private=tempfile::tempdir()?;let snapshot=private.path().join("source.xlsx");let mut src=File::open(source)?;
 if !src.metadata()?.is_file() {return Err(Error::new("invalid_input","Expected regular workbook source"));}
 if src.metadata()?.len()>limits.input_bytes {return Err(budget("Source snapshot cap exceeded"));}
 let mut copy=File::create(&snapshot)?;let mut source_hash=Sha256::new();let mut bytes=0u64;let mut buffer=[0u8;65536];
 loop {control.checkpoint("snapshot",bytes as usize,limits.input_bytes as usize)?;let n=src.read(&mut buffer)?;if n==0 {break;}bytes+=n as u64;if bytes>limits.input_bytes {return Err(budget("Source grew beyond snapshot cap"));}copy.write_all(&buffer[..n])?;source_hash.update(&buffer[..n]);}copy.flush()?;drop(copy);drop(src);
 let mut package=package::Package::new(File::open(&snapshot)?,limits,control)?;
 let (sheets,active)=package::workbook(&package.part("xl/workbook.xml",control)?,control)?;
 let selected=if let Some(name)=worksheet.filter(|s|!s.is_empty()) {sheets.iter().find(|s|s.name==name)}else{sheets.get(active)}.ok_or_else(||Error::new("sheet_not_found","Selected worksheet not found"))?;
 let target=package::worksheet_target(&package.part("xl/_rels/workbook.xml.rels",control)?,&selected.relationship,control)?;
 let styles=if package.contains("xl/styles.xml") {rows::styles(&package.part("xl/styles.xml",control)?,control)?}else{vec![true]};
 let mut strings=rows::Strings::new(private.path().join("strings.bin"))?;
 control.checkpoint("shared_strings",0,0)?;
 if package.contains("xl/sharedStrings.xml") {strings.load(&package.part("xl/sharedStrings.xml",control)?,limits,control)?;}
 let rows_path=private.path().join("rows.jsonl");
 let summary=rows::normalize(&package.part(&target,control)?,&mut strings,&styles,&rows_path,limits,control)?;
 let verified=rows::verify(&rows_path,limits,control)?;
 if verified!=summary.digest {return Err(Error::new("integrity","Row spool differs after reopen"));}
 control.checkpoint("complete",verified.rows as usize,verified.rows as usize)?;
 let receipt=Receipt {profile:PROFILE,source_sha256:hex(&source_hash.finish()),worksheet:selected.name.clone(),headers:summary.headers,declared_rows:summary.rows,declared_columns:summary.columns,stored_cells:summary.cells,scanned_data_rows:summary.rows.saturating_sub(1),skipped_blank_rows:summary.rows.saturating_sub(1).saturating_sub(verified.rows as u32),shared_strings:strings.index.len(),shared_string_bytes:strings.bytes,shared_index_bytes:strings.index.len()*16,shared_index_reserved_bytes:strings.index.capacity()*16,normalized_charge_bytes:summary.normalized,row_spool_bytes:summary.spool_bytes,temporary_bytes:bytes+strings.bytes+summary.spool_bytes,row_digest:verified,parts:package.parts,advertised_expansion_bytes:package.expanded,largest_advertised_part_bytes:package.largest};
 Ok(Spool {private,rows:rows_path,receipt})
}
