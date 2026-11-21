use crate::{budget,malformed,trimmed,xml::{self,Kind},Digest,Error,Limits,ReadControl,Result,RowDigest};
use std::{collections::BTreeMap,fs::{File,OpenOptions},io::{BufRead,BufReader,BufWriter,Read,Seek,SeekFrom,Write},path::{Path,PathBuf}};
pub(crate) struct Strings {pub index:Vec<(u64,usize)>,pub bytes:u64,file:File}
impl Strings {
 pub fn new(path:PathBuf)->Result<Self> {Ok(Self {index:Vec::new(),bytes:0,file:OpenOptions::new().read(true).write(true).create_new(true).open(path)?})}
 pub fn load(&mut self,source:&str,limits:&Limits,control:&ReadControl<'_>)->Result<()> {
  let mut output=BufWriter::new(self.file.try_clone()?);let mut current=None;
  xml::visit(source,control,|path,kind,_,text| {
   let name=path.last().map(String::as_str);
   if kind==Kind::Start&&path.len()==2&&path[0]=="sst"&&name==Some("si") {if current.is_some() {return Err(malformed("Nested shared string"));}current=Some(String::new());}
   if kind==Kind::Text&&crate::package::rich_text(path,"si") {xml::append(current.as_mut().ok_or_else(||malformed("Text outside shared item"))?,text,limits.value_bytes)?;}
   if kind==Kind::End&&path.len()==2&&path[0]=="sst"&&name==Some("si") {
    let value=current.take().ok_or_else(||malformed("Missing shared item"))?.replace("x005F_","");
    if self.index.len()>=limits.shared_strings||self.bytes+value.len() as u64>limits.shared_bytes {return Err(budget("Shared string spool cap exceeded"));}
    self.index.push((self.bytes,value.len()));output.write_all(value.as_bytes())?;self.bytes+=value.len() as u64;
    if self.index.len()%4096==0 {control.checkpoint("shared_strings",self.index.len(),limits.shared_strings)?;}
   }Ok(())
  })?;output.flush()?;Ok(())
 }
 fn get(&mut self,index:usize,limits:&Limits)->Result<String> {
  let &(offset,len)=self.index.get(index).ok_or_else(||malformed("Shared string index out of range"))?;
  if len>limits.value_bytes {return Err(budget("Shared value exceeds cap"));}
  self.file.seek(SeekFrom::Start(offset))?;let mut bytes=vec![0;len];self.file.read_exact(&mut bytes)?;String::from_utf8(bytes).map_err(malformed)
 }
}
pub(crate) fn styles(source:&str,control:&ReadControl<'_>)->Result<Vec<bool>> {
 let mut result=Vec::new();xml::visit(source,control,|path,kind,attrs,_| {
  if kind==Kind::Start&&path.len()==3&&path[0]=="styleSheet"&&path[1]=="cellXfs"&&path[2]=="xf" {
   if result.len()>=4096 {return Err(budget("Style count cap exceeded"));}
   let format=attrs.get("numFmtId").map(|s|s.parse::<u32>()).transpose().map_err(malformed)?.unwrap_or(0);result.push(format==0);
  }Ok(())
 })?;if result.is_empty() {return Err(Error::new("unsupported_workbook","Missing cell styles"));}Ok(result)
}
struct Cell {column:u32,kind:String,style:usize,value:String,inline:Option<String>}
fn scalar(cell:Cell,strings:&mut Strings,styles:&[bool],header:bool,limits:&Limits)->Result<Option<String>> {
 if cell.kind=="inlineStr" {return Ok(cell.inline.as_deref().map(trimmed));}
 if cell.value.is_empty() {return Ok(None);}
 let result=match cell.kind.as_str() {
  "s"=>trimmed(&strings.get(cell.value.parse::<usize>().map_err(malformed)?,limits)?),
  "n"=>{if !styles.get(cell.style).copied().unwrap_or(false) {return Err(Error::new("unsupported_cell","Numeric styles other than General require separate compatibility"));}crate::numbers::normalize_number(&cell.value,header)?},
  "b"=>match cell.value.as_str() {"0"=>"False".into(),"1"=>"True".into(),_=>return Err(malformed("Invalid boolean cell"))},
  "str"|"e"=>trimmed(&cell.value),
  _=>return Err(Error::new("unsupported_cell","Unsupported scalar cell type")),
 };Ok(Some(result))
}
pub(crate) struct Summary {pub headers:Vec<String>,pub rows:u32,pub columns:u32,pub cells:u64,pub normalized:usize,pub spool_bytes:u64,pub digest:RowDigest}
pub(crate) fn normalize(source:&str,strings:&mut Strings,styles:&[bool],destination:&Path,limits:&Limits,control:&ReadControl<'_>)->Result<Summary> {
 let mut output=BufWriter::new(File::create(destination)?);let mut dimensions=None;let mut row_number=None;let mut last_row=None;let mut last_column=None;let mut values=Vec::new();let mut current:Option<Cell>=None;
 let mut headers:Vec<String>=Vec::new();let mut any_rows=false;let mut cell_count=0u64;let mut raw_bytes=0usize;let mut row_bytes=0usize;let mut normalized=0usize;let mut spool_bytes=0u64;let mut digest=Digest::new();
 control.checkpoint("normalize_rows",0,limits.rows as usize)?;
 xml::visit(source,control,|path,kind,attrs,text| {
  let name=path.last().map(String::as_str);
  if kind==Kind::Start {
   if path.len()==2&&path[0]=="worksheet"&&name==Some("dimension") {
    if dimensions.is_some()||any_rows {return Err(malformed("Repeated or late worksheet dimension"));}
    let coords:Vec<_>=attrs.get("ref").ok_or_else(||malformed("Missing dimension"))?.split(':').collect();
    if coords.is_empty()||coords.len()>2 {return Err(malformed("Invalid dimension"));}
    let first=crate::package::coordinate(coords[0])?;let last=crate::package::coordinate(coords[coords.len()-1])?;
    let rows=last.0.checked_add(1).ok_or_else(||budget("Row overflow"))?;let columns=last.1.checked_add(1).ok_or_else(||budget("Column overflow"))?;
    if first.0>last.0||first.1>last.1 {return Err(malformed("Reversed dimension"));}
    if rows>limits.rows||columns>limits.columns||rows as u64*columns as u64>limits.cells {return Err(budget("Worksheet coordinate or rectangle cap exceeded"));}dimensions=Some((rows,columns));
   }
   if path.len()==3&&path[0]=="worksheet"&&path[1]=="sheetData"&&name==Some("row") {
    let (rows,columns)=dimensions.ok_or_else(||Error::new("unsupported_workbook","An early explicit dimension is required"))?;
    let number=attrs.get("r").ok_or_else(||malformed("Explicit row coordinate required"))?.parse::<u32>().map_err(malformed)?;
    if number==0||number>rows||last_row.is_some_and(|previous|number<=previous)||row_number.is_some() {return Err(Error::new("unsupported_workbook","Rows must be strictly ordered within dimension"));}
    row_number=Some(number-1);last_row=Some(number);last_column=None;values=vec![None;columns as usize];row_bytes=0;any_rows=true;
    if number%256==0 {control.checkpoint("normalize_rows",number as usize,rows as usize)?;}
   }
   if path.len()==4&&path[0]=="worksheet"&&path[1]=="sheetData"&&path[2]=="row"&&name==Some("c") {
    let address=crate::package::coordinate(attrs.get("r").ok_or_else(||malformed("Explicit cell coordinate required"))?)?;
    if current.is_some()||row_number!=Some(address.0)||address.1>=values.len() as u32||last_column.is_some_and(|c|address.1<=c) {return Err(Error::new("unsupported_workbook","Cell coordinates must be unique and ordered within their row"));}
    last_column=Some(address.1);current=Some(Cell {column:address.1,kind:attrs.get("t").cloned().unwrap_or_else(||"n".into()),style:attrs.get("s").map(|s|s.parse::<usize>()).transpose().map_err(malformed)?.unwrap_or(0),value:String::new(),inline:None});
   }
   if path.len()==5&&path[3]=="c"&&name==Some("is") {if let Some(cell)=&mut current {cell.inline=Some(String::new());}}
  }
  if kind==Kind::Text {if let Some(cell)=&mut current {
   if path.len()==5&&path[3]=="c"&&name==Some("v") {xml::append(&mut cell.value,text,limits.value_bytes)?;}
   if crate::package::rich_text(path,"is") {xml::append(cell.inline.as_mut().ok_or_else(||malformed("Text outside inline string"))?,text,limits.value_bytes)?;}
  }}
  if kind==Kind::End&&path.len()==4&&path[0]=="worksheet"&&path[1]=="sheetData"&&path[2]=="row"&&name==Some("c") {
   let cell=current.take().ok_or_else(||malformed("Missing current cell"))?;let column=cell.column as usize;cell_count+=1;
   raw_bytes=raw_bytes.checked_add(cell.value.len()).and_then(|n|n.checked_add(cell.inline.as_ref().map_or(0,String::len))).ok_or_else(||budget("Raw cell counter overflow"))?;
   if cell_count>limits.cells||raw_bytes>limits.normalized_bytes {return Err(budget("Raw cell aggregate cap exceeded"));}
   let value=scalar(cell,strings,styles,row_number==Some(0),limits)?;
   row_bytes=row_bytes.checked_add(value.as_ref().map_or(0,String::len)).ok_or_else(||budget("Row byte overflow"))?;
   if row_bytes>limits.row_bytes {return Err(budget("Per-row normalized byte cap exceeded"));}values[column]=value;
  }
  if kind==Kind::End&&path.len()==3&&path[0]=="worksheet"&&path[1]=="sheetData"&&name==Some("row") {
   let number=row_number.take().ok_or_else(||malformed("Missing current row"))?;
   if current.is_some() {return Err(malformed("Unterminated cell"));}
   if number==0 {
    headers=values.iter_mut().enumerate().map(|(i,v)|v.take().unwrap_or_else(||format!("col_{i}"))).collect();normalized=headers.iter().map(String::len).sum();
   }else {
    if headers.is_empty() {headers=(0..values.len()).map(|i|format!("col_{i}")).collect();normalized=headers.iter().map(String::len).sum();}
    if values.iter().any(Option::is_some) {
     let mut record=BTreeMap::new();
     for(header,value)in headers.iter().zip(values.iter_mut()) {let value=value.take().unwrap_or_default();normalized=normalized.checked_add(header.len()).and_then(|n|n.checked_add(value.len())).ok_or_else(||budget("Normalized byte counter overflow"))?;if normalized>limits.normalized_bytes {return Err(budget("Normalized aggregate cap exceeded"));}record.insert(header.clone(),value);}
     let data=serde_json::to_vec(&record).map_err(malformed)?;
     if data.len()>limits.row_bytes||spool_bytes+data.len() as u64+1>limits.spool_bytes {return Err(budget("Row spool cap exceeded"));}
     output.write_all(&data)?;output.write_all(b"\n")?;spool_bytes+=data.len() as u64+1;digest.add(&record);
    }
   }
   if normalized>limits.normalized_bytes {return Err(budget("Header byte cap exceeded"));}
  }Ok(())
 })?;
 let (rows,columns)=dimensions.ok_or_else(||Error::new("unsupported_workbook","Explicit worksheet dimension required"))?;
 if row_number.is_some()||current.is_some() {return Err(malformed("Truncated row"));}
 if any_rows&&headers.is_empty() {headers=(0..columns).map(|i|format!("col_{i}")).collect();normalized=headers.iter().map(String::len).sum();if normalized>limits.normalized_bytes {return Err(budget("Header cap exceeded"));}}
 output.flush()?;Ok(Summary {headers,rows,columns,cells:cell_count,normalized,spool_bytes,digest:digest.finish()})
}
pub(crate) fn verify(path:&Path,limits:&Limits,control:&ReadControl<'_>)->Result<RowDigest> {
 let mut input=BufReader::new(File::open(path)?);let mut line=Vec::new();let mut digest=Digest::new();let mut bytes=0;
 control.checkpoint("verify_rows",0,limits.rows as usize)?;
 loop {
  control.check()?;line.clear();let n=(&mut input).take(limits.row_bytes as u64+2).read_until(b'\n',&mut line)?;if n==0 {break;}
  bytes+=n as u64;if n>limits.row_bytes+1||!line.ends_with(b"\n")||bytes>limits.spool_bytes||digest.rows>=limits.rows as u64 {return Err(budget("Reopened row spool exceeds limits"));}
  let row:BTreeMap<String,String>=serde_json::from_slice(&line[..n-1]).map_err(malformed)?;digest.add(&row);
  if digest.rows%256==0 {control.checkpoint("verify_rows",digest.rows as usize,limits.rows as usize)?;}
 }Ok(digest.finish())
}
