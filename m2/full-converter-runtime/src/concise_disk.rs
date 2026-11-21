//! Verified disk rows -> first-seen headword groups -> bounded canonical TXT.
#[path="concise_publication.rs"]mod publication;
#[path="concise_text.rs"]mod text;
#[path="../../indexed-engine/src/sha256.rs"]mod sha256;
use serde::{Deserialize,Serialize};
use std::{cell::RefCell,collections::BTreeMap,fs::File,io::{BufRead,BufReader,Read,Seek,SeekFrom},path::Path};
pub use studio_xlsx::moe::Row;
pub const PROFILE:&str="moe-concise-disk-groups-txt-v1";
#[derive(Debug,Serialize)]pub struct Error {pub code:&'static str,pub message:String}
impl Error {pub fn new(code:&'static str,message:impl Into<String>)->Self {Self {code,message:message.into()}}}
impl std::fmt::Display for Error {fn fmt(&self,f:&mut std::fmt::Formatter<'_>)->std::fmt::Result {write!(f,"{}: {}",self.code,self.message)}}
impl std::error::Error for Error {}
pub type Result<T>=std::result::Result<T,Error>;
impl From<std::io::Error> for Error {fn from(e:std::io::Error)->Self {Self::new("io",e.to_string())}}
impl From<studio_xlsx_spool::Error> for Error {fn from(e:studio_xlsx_spool::Error)->Self {Self::new(e.code,e.message)}}
impl From<studio_xlsx::Error> for Error {fn from(e:studio_xlsx::Error)->Self {Self::new(e.code,e.message)}}
fn malformed(e:impl std::fmt::Display)->Error {Error::new("malformed_source",e.to_string())}
fn budget(s:&str)->Error {Error::new("limit_exceeded",s)}
fn sum(a:usize,b:usize)->Result<usize> {a.checked_add(b).ok_or_else(||budget("Counter overflow"))}
fn py_space(c:char)->bool {matches!(c,'\t'..='\r'|'\u{1c}'..='\u{20}'|'\u{85}'|'\u{a0}'|'\u{1680}'|'\u{2000}'..='\u{200a}'|'\u{2028}'|'\u{2029}'|'\u{202f}'|'\u{205f}'|'\u{3000}')}
#[derive(Clone,Copy,Debug,Deserialize,Serialize)]pub enum Converter {#[serde(rename="moe_concise")]Concise}
impl Converter {fn native(self)->studio_xlsx::moe::Converter {studio_xlsx::moe::Converter::Concise}}
#[derive(Clone,Debug)]pub struct Limits {pub groups:usize,pub group_rows:usize,pub group_input_bytes:usize,pub group_output_bytes:usize,pub index_charge_bytes:usize,pub entries:usize,pub decoded_bytes:usize,pub output_bytes:u64}
impl Default for Limits {fn default()->Self {Self {groups:100000,group_rows:4096,group_input_bytes:16*1024*1024,group_output_bytes:8*1024*1024,index_charge_bytes:32*1024*1024,entries:100000,decoded_bytes:32*1024*1024,output_bytes:64*1024*1024}}}
impl Limits {fn validate(&self)->Result<()> {let cap=Self::default();macro_rules! bound {($n:ident)=>{if self.$n>cap.$n {return Err(Error::new("invalid_input","Profile limits may only be lowered"));}};}bound!(groups);bound!(group_rows);bound!(group_input_bytes);bound!(group_output_bytes);bound!(index_charge_bytes);bound!(entries);bound!(decoded_bytes);bound!(output_bytes);Ok(())}}
#[derive(Default,Debug,Deserialize)]#[serde(deny_unknown_fields)]pub struct Tighten {pub groups:Option<usize>,pub group_rows:Option<usize>,pub group_input_bytes:Option<usize>,pub group_output_bytes:Option<usize>,pub index_charge_bytes:Option<usize>,pub entries:Option<usize>,pub decoded_bytes:Option<usize>,pub output_bytes:Option<u64>}
impl Tighten {pub fn limits(&self)->Result<Limits> {let mut l=Limits::default();macro_rules! lower {($n:ident)=>{if let Some(n)=self.$n {if n>l.$n {return Err(Error::new("invalid_input","Profile limits may only be lowered"));}l.$n=n;}};}lower!(groups);lower!(group_rows);lower!(group_input_bytes);lower!(group_output_bytes);lower!(index_charge_bytes);lower!(entries);lower!(decoded_bytes);lower!(output_bytes);Ok(l)}}
#[derive(Debug)]pub struct Progress {pub phase:&'static str,pub completed:usize,pub total:usize}
pub struct Control<'a> {cancelled:&'a dyn Fn()->bool,progress:RefCell<&'a mut dyn FnMut(Progress)>}
impl<'a> Control<'a> {
 pub fn new(cancelled:&'a dyn Fn()->bool,progress:&'a mut dyn FnMut(Progress))->Self {Self {cancelled,progress:RefCell::new(progress)}}
 fn check(&self)->Result<()> {if (self.cancelled)() {Err(Error::new("cancelled","Conversion cancelled before publication"))}else{Ok(())}}
 fn emit(&self,phase:&'static str,completed:usize,total:usize) {(self.progress.borrow_mut())(Progress {phase,completed,total});}
 fn step(&self,phase:&'static str,completed:usize,total:usize)->Result<()> {self.check()?;self.emit(phase,completed,total);self.check()}
}
#[derive(Clone,Copy)]struct Location {offset:u64,len:usize}
struct Group {head:String,rows:Vec<Location>}
fn index_rows(path:&Path,limits:&Limits,control:&Control<'_>)->Result<(Vec<Group>,usize,usize)> {
 let mut file=BufReader::new(File::open(path)?);let mut groups:Vec<Group>=Vec::new();let mut index=BTreeMap::new();let mut charge=65536usize;let mut offset=0u64;let mut line=Vec::new();let mut skipped=0;
 control.step("index_rows",0,200000)?;
 loop {control.check()?;line.clear();let n=(&mut file).take(8*1024*1024+2).read_until(b'\n',&mut line)?;if n==0 {break;}if n>8*1024*1024+1||!line.ends_with(b"\n") {return Err(budget("Invalid or oversized row frame"));}
  let row:Row=serde_json::from_slice(&line[..n-1]).map_err(malformed)?;
  for(k,v)in &row {if v.len()>1024*1024 {return Err(budget("Source field cap exceeded"));}text::check_profile(k,v)?;}
  let head=text::get(&row,"字詞名");
  if head.is_empty() {skipped+=1;}else {
   if head.len()>4096 {return Err(budget("Headword cap exceeded"));}
   let slot=if let Some(&slot)=index.get(head) {slot}else {if groups.len()>=limits.groups {return Err(budget("Headword group cap exceeded"));}charge=sum(charge,sum(256,head.len()*2)?)?;if charge>limits.index_charge_bytes {return Err(budget("Group index plan charge exceeded"));}let slot=groups.len();index.insert(head.to_owned(),slot);groups.push(Group {head:head.into(),rows:Vec::new()});slot};
   charge=sum(charge,64)?;if charge>limits.index_charge_bytes||groups[slot].rows.len()>=limits.group_rows {return Err(budget("Group index or per-group row cap exceeded"));}
   groups[slot].rows.push(Location {offset,len:n});
  }offset+=n as u64;
 }
 if groups.is_empty() {return Err(Error::new("malformed_source","No valid headwords under 字詞名"));}Ok((groups,skipped,charge))
}
#[derive(Debug,Serialize)]pub struct Receipt {
 pub profile:&'static str,pub converter:Converter,pub source_sha256:String,pub worksheet:String,pub input_rows:u64,pub groups:usize,pub skipped_rows:usize,
 pub entries:usize,pub primary_entries:usize,pub alias_redirects:usize,pub file_bytes:u64,pub decoded_bytes:usize,pub file_sha256:String,pub framed_records_sha256:String,
 pub key_bytes:usize,pub body_bytes:usize,pub index_charge_bytes:usize,pub largest_group_rows:usize,pub largest_group_input_bytes:usize,pub temporary_file_peak_bytes:u64,
 pub row_source:studio_xlsx_spool::Receipt,
}
pub fn render_to_txt(source:&Path,destination:&Path,converter:Converter,worksheet:Option<&str>,reader_limits:&studio_xlsx_spool::Limits,limits:&Limits,control:&Control<'_>)->Result<Receipt> {
 control.check()?;limits.validate()?;
 match std::fs::symlink_metadata(destination) {Ok(_)=>return Err(Error::new("destination_exists","TXT destination exists")),Err(e) if e.kind()==std::io::ErrorKind::NotFound=>{},Err(e)=>return Err(e.into())}
 let spool={let cancelled=||(control.cancelled)();let mut progress=|p:studio_xlsx_spool::Progress|control.emit(if p.phase=="complete" {"rows_complete"}else{p.phase},p.completed,p.total);studio_xlsx_spool::read_to_spool(source,worksheet,reader_limits,&studio_xlsx_spool::ReadControl::new(&cancelled,&mut progress))?};
 let (groups,skipped,charge)=index_rows(spool.rows_path(),limits,control)?;let group_count=groups.len();let indexed:usize=groups.iter().map(|g|g.rows.len()).sum();if indexed+skipped!=spool.receipt.row_digest.rows as usize {return Err(Error::new("integrity","Indexed row count differs"));}let mut source_rows=File::open(spool.rows_path())?;let mut position=0u64;let mut line=Vec::new();let mut output=publication::Sink::new(destination)?;
 let mut largest_rows=0;let mut largest_input=0;let mut primary=0;let mut aliases=0;
 for(i,group)in groups.iter().enumerate() {
  control.step("render_group",i,group_count)?;let mut rows=Vec::new();let mut input_bytes=0;
  for location in &group.rows {control.check()?;if position!=location.offset {source_rows.seek(SeekFrom::Start(location.offset))?;}line.resize(location.len,0);source_rows.read_exact(&mut line)?;position=location.offset+location.len as u64;
   if !line.ends_with(b"\n") {return Err(Error::new("integrity","Row frame changed"));}let row:Row=serde_json::from_slice(&line[..line.len()-1]).map_err(malformed)?;
   if text::get(&row,"字詞名")!=group.head {return Err(Error::new("integrity","Headword group changed"));}
   for(k,v)in &row {input_bytes=sum(input_bytes,sum(k.len(),v.len())?)?;}if input_bytes>limits.group_input_bytes {return Err(budget("Headword group input cap exceeded"));}rows.push(row);
  }
  largest_rows=largest_rows.max(rows.len());largest_input=largest_input.max(input_bytes);
  let table=studio_xlsx::Table {profile:studio_xlsx::PROFILE,backend:"verified-disk-group",sheet_name:spool.receipt.worksheet.clone(),headers:spool.receipt.headers.clone(),scanned_data_rows:rows.len(),skipped_blank_rows:0,rows};
  let ml=studio_xlsx::moe::Limits {max_rows:limits.group_rows,max_input_bytes:limits.group_input_bytes,max_entries:16384,max_key_bytes:4096,max_entry_bytes:1024*1024,max_output_bytes:limits.group_output_bytes};
  let cancelled=||(control.cancelled)();let mut progress=|_:studio_xlsx::Progress|{};
  let converted=studio_xlsx::moe::convert(&table,converter.native(),&ml,&mut studio_xlsx::ReadControl::new(&cancelled,&mut progress))?;
  if converted.primary_entries!=1||converted.skipped_rows!=0 {return Err(Error::new("integrity","Invalid group conversion counts"));}primary+=1;aliases+=converted.alias_redirects;
  for entry in converted.entries {output.append(&entry.key,&entry.text,limits,control)?;}
 }
 drop(source_rows);drop(groups);drop(line);
 let row_receipt=spool.receipt.clone();let private=spool.private_path().to_owned();drop(spool);if private.exists() {return Err(Error::new("io","Private source spool cleanup failed"));}
 let prepared=output.verify(limits,control)?;
 if prepared.entries!=primary+aliases {return Err(Error::new("integrity","Global conversion counts differ"));}
 let temporary=row_receipt.temporary_bytes+prepared.file_bytes;if temporary>512*1024*1024 {return Err(budget("Combined private-file cap exceeded"));}
 let receipt=Receipt {profile:PROFILE,converter,source_sha256:row_receipt.source_sha256.clone(),worksheet:row_receipt.worksheet.clone(),input_rows:row_receipt.row_digest.rows,groups:group_count,skipped_rows:skipped,entries:prepared.entries,primary_entries:primary,alias_redirects:aliases,file_bytes:prepared.file_bytes,decoded_bytes:prepared.key_bytes+prepared.body_bytes,file_sha256:prepared.file_sha256,framed_records_sha256:prepared.framed_records_sha256,key_bytes:prepared.key_bytes,body_bytes:prepared.body_bytes,index_charge_bytes:charge,largest_group_rows:largest_rows,largest_group_input_bytes:largest_input,temporary_file_peak_bytes:temporary,row_source:row_receipt};
 output.commit(destination,control,receipt.entries)?;Ok(receipt)
}
