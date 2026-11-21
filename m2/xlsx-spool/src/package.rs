use crate::{budget,malformed,xml::{self,Kind},Error,Limits,ReadControl,Result};
use std::{collections::{BTreeSet},fs::File,io::Read};
use zip::{ZipArchive,CompressionMethod};
pub(crate) struct Package {archive:ZipArchive<File>,max_part:u64,pub parts:usize,pub expanded:u64,pub largest:u64}
impl Package {
 pub fn new(file:File,limits:&Limits,control:&ReadControl<'_>)->Result<Self> {
  let mut archive=ZipArchive::new(file).map_err(malformed)?;let parts=archive.len();if parts>limits.parts {return Err(budget("ZIP member count exceeded"));}
  let mut expanded=0u64;let mut largest=0;let mut names=BTreeSet::new();
  for i in 0..parts {control.check()?;let f=archive.by_index(i).map_err(malformed)?;
   if !names.insert(f.name().to_owned()) {return Err(malformed("Duplicate ZIP member"));}
   if f.size()>limits.part_bytes {return Err(budget("ZIP part byte cap exceeded"));}largest=largest.max(f.size());expanded=expanded.checked_add(f.size()).ok_or_else(||budget("ZIP sum overflow"))?;
   if expanded>limits.expanded_bytes {return Err(budget("ZIP expansion cap exceeded"));}
   if !matches!(f.compression(),CompressionMethod::Stored|CompressionMethod::Deflated) {return Err(Error::new("unsupported_workbook","Only stored/deflate ZIP parts supported"));}
  }
  control.checkpoint("package_preflight",parts,parts)?;Ok(Self {archive,max_part:limits.part_bytes,parts,expanded,largest})
 }
 pub fn contains(&self,name:&str)->bool {self.archive.file_names().any(|n|n==name)}
 pub fn part(&mut self,name:&str,control:&ReadControl<'_>)->Result<String> {
  let mut file=self.archive.by_name(name).map_err(malformed)?;let mut data=Vec::new();let mut buffer=[0u8;65536];
  loop {control.check()?;let n=file.read(&mut buffer).map_err(malformed)?;if n==0 {break;}
   if data.len() as u64+n as u64>self.max_part {return Err(budget("Actual ZIP part byte cap exceeded"));}data.extend_from_slice(&buffer[..n]);
  }String::from_utf8(data).map_err(|_|Error::new("unsupported_workbook","Only UTF-8 XML supported"))
 }
}
#[derive(Debug)]
pub(crate) struct Sheet {pub name:String,pub relationship:String}
pub(crate) fn workbook(source:&str,control:&ReadControl<'_>)->Result<(Vec<Sheet>,usize)> {
    let mut sheets=Vec::new();let mut active=None;
    xml::visit(source,control,|path,kind,attrs,_|{
        if kind!=Kind::Start {return Ok(());}
        match path.last().map(String::as_str) {
            Some("workbookView") if active.is_none()&&path.len()==3&&path[0]=="workbook"&&path[1]=="bookViews"=>{active=Some(attrs.get("activeTab").map(|s|s.parse::<usize>()).transpose().map_err(malformed)?.unwrap_or(0));}
            Some("sheet") if path.len()==3&&path[0]=="workbook"&&path[1]=="sheets"=>{
                if sheets.len()>=256 {return Err(budget("Workbook sheet-count budget exceeded"));}
                sheets.push(Sheet {name:attrs.get("name").ok_or_else(||malformed("Missing sheet name"))?.clone(),
                    relationship:attrs.get("r:id").ok_or_else(||malformed("Missing worksheet relationship"))?.clone()});
            }
            _=>{},
        }
        Ok(())
    })?;
    if sheets.is_empty() {return Err(Error::new("unsupported_workbook","No workbook sheets"));}
    Ok((sheets,active.unwrap_or(0)))
}

pub(crate) fn worksheet_target(source:&str,id:&str,control:&ReadControl<'_>)->Result<String> {
    let mut target=None;
    xml::visit(source,control,|path,kind,attrs,_|{
        if kind==Kind::Start&&path.len()==2&&path[0]=="Relationships"&&path[1]=="Relationship"&&attrs.get("Id").map(String::as_str)==Some(id) {
            if target.is_some() {return Err(malformed("Duplicate sheet relationship"));}
            if attrs.get("TargetMode").map(String::as_str)==Some("External")||!attrs.get("Type").is_some_and(|t|t.ends_with("/worksheet")) {
                return Err(Error::new("unsupported_workbook","Selected sheet must be an internal worksheet"));
            }
            target=Some(attrs.get("Target").ok_or_else(||malformed("Missing sheet target"))?.clone());
        }
        Ok(())
    })?;
    let target=target.ok_or_else(||malformed("Worksheet relationship not found"))?;
    if target.contains(['\\','\0',':','?','#']) {return Err(Error::new("unsupported_workbook","Unsupported worksheet target URI"));}
    let rooted=target.starts_with('/');let mut parts=if rooted {Vec::new()}else{vec!["xl"]};
    for part in target.trim_start_matches('/').split('/') {
        match part {""|"."=>{},".."=>{parts.pop().ok_or_else(||malformed("Relationship escapes package root"))?;},_=>parts.push(part)}
    }
    Ok(parts.join("/"))
}

pub(crate) fn rich_text(path:&[String],root:&str)->bool {
    let n=path.len();n>=2&&path[n-1]=="t"&&(path[n-2]==root||(n>=3&&path[n-2]=="r"&&path[n-3]==root))
}
pub(crate) fn coordinate(value:&str)->Result<(u32,u32)> {
    let split=value.find(|c:char|c.is_ascii_digit()).ok_or_else(||malformed("Invalid cell coordinate"))?;
    let (letters,digits)=value.split_at(split);
    if letters.is_empty()||digits.is_empty()||!letters.bytes().all(|b|b.is_ascii_uppercase())||!digits.bytes().all(|b|b.is_ascii_digit()) {return Err(malformed("Invalid A1 coordinate"));}
    let mut column=0u32;
    for b in letters.bytes() {column=column.checked_mul(26).and_then(|n|n.checked_add((b-b'A'+1) as u32)).ok_or_else(||budget("Column coordinate overflow"))?;}
    let row=digits.parse::<u32>().map_err(malformed)?;
    if row==0||column==0 {return Err(malformed("Zero cell coordinate"));}
    Ok((row-1,column-1))
}
