use crate::{budget,malformed,xml::{self,Kind},Error,Limits,ReadControl,Result};
use std::{collections::{BTreeMap,BTreeSet},io::{Cursor,Read}};
use zip::{ZipArchive,CompressionMethod};

pub(crate) struct Package<'a> {archive:ZipArchive<Cursor<&'a [u8]>>,max_part:u64}
impl<'a> Package<'a> {
    pub fn new(bytes:&'a [u8],limits:&Limits,control:&mut ReadControl<'_>)->Result<Self> {
        if bytes.len() as u64>limits.max_file_bytes {return Err(budget("XLSX file byte budget exceeded"));}
        let mut archive=ZipArchive::new(Cursor::new(bytes)).map_err(malformed)?;
        if archive.len()>limits.max_parts {return Err(budget("ZIP member-count budget exceeded"));}
        let mut total=0u64;let mut names=BTreeSet::new();
        for index in 0..archive.len() {
            control.check()?;
            let file=archive.by_index(index).map_err(malformed)?;
            if !names.insert(file.name().to_owned()) {return Err(malformed("Duplicate ZIP member"));}
            if file.size()>limits.max_part_bytes {return Err(budget("ZIP member byte budget exceeded"));}
            total=total.checked_add(file.size()).ok_or_else(||budget("ZIP size overflow"))?;
            if total>limits.max_uncompressed_bytes {return Err(budget("ZIP uncompressed-byte budget exceeded"));}
            if !matches!(file.compression(),CompressionMethod::Stored|CompressionMethod::Deflated) {
                return Err(Error::new("unsupported_workbook","Only stored/deflate XLSX members are supported"));
            }
        }
        control.checkpoint("package_preflight",archive.len(),archive.len())?;
        Ok(Self {archive,max_part:limits.max_part_bytes})
    }
    pub fn contains(&self,name:&str)->bool {self.archive.file_names().any(|n|n==name)}
    pub fn part(&mut self,name:&str)->Result<String> {
        let file=self.archive.by_name(name).map_err(malformed)?;
        let mut bytes=Vec::new();file.take(self.max_part.checked_add(1).ok_or_else(||budget("Part budget overflow"))?).read_to_end(&mut bytes).map_err(malformed)?;
        if bytes.len() as u64>self.max_part {return Err(budget("Actual ZIP member exceeds byte budget"));}
        String::from_utf8(bytes).map_err(|_|Error::new("unsupported_workbook","OOXML part is not UTF-8"))
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
pub(crate) fn shared_strings(source:&str,limits:&Limits,control:&ReadControl<'_>)->Result<Vec<String>> {
    let mut result=Vec::new();let mut current=None;let mut total=0usize;
    xml::visit(source,control,|path,kind,_,text|{
        let name=path.last().map(String::as_str);
        if kind==Kind::Start&&name==Some("si")&&path.len()==2&&path[0]=="sst" {current=Some(String::new());}
        if kind==Kind::Text&&rich_text(path,"si") {
            xml::append(current.as_mut().ok_or_else(||malformed("Shared string outside item"))?,text,limits.max_value_bytes)?;
        }
        if kind==Kind::End&&name==Some("si")&&path.len()==2&&path[0]=="sst" {
            let value=current.take().ok_or_else(||malformed("Missing shared string item"))?.replace("x005F_","");
            total=total.checked_add(value.len()).ok_or_else(||budget("Shared-string byte overflow"))?;
            if total>limits.max_decoded_bytes||result.len() as u64>=limits.max_cells {return Err(budget("Shared-string table budget exceeded"));}
            result.push(value);
        }
        Ok(())
    })?;Ok(result)
}

#[derive(Debug)]
pub(crate) struct Cell {pub kind:String,pub value:String,pub inline:Option<String>}
pub(crate) struct Cells {pub rows:u32,pub columns:u32,pub has_rows:bool,pub cells:BTreeMap<(u32,u32),Cell>}
fn coordinate(value:&str)->Result<(u32,u32)> {
    let split=value.find(|c:char|c.is_ascii_digit()).ok_or_else(||malformed("Invalid cell coordinate"))?;
    let (letters,digits)=value.split_at(split);
    if letters.is_empty()||digits.is_empty()||!letters.bytes().all(|b|b.is_ascii_uppercase())||!digits.bytes().all(|b|b.is_ascii_digit()) {return Err(malformed("Invalid A1 coordinate"));}
    let mut column=0u32;
    for b in letters.bytes() {column=column.checked_mul(26).and_then(|n|n.checked_add((b-b'A'+1) as u32)).ok_or_else(||budget("Column coordinate overflow"))?;}
    let row=digits.parse::<u32>().map_err(malformed)?;
    if row==0||column==0 {return Err(malformed("Zero cell coordinate"));}
    Ok((row-1,column-1))
}
pub(crate) fn cells(source:&str,limits:&Limits,control:&ReadControl<'_>)->Result<Cells> {
    let mut dimensions=None;let mut current:Option<((u32,u32),Cell)>=None;let mut result=BTreeMap::new();let mut total=0usize;let mut has_rows=false;
    xml::visit(source,control,|path,kind,attrs,text|{
        let name=path.last().map(String::as_str);
        if kind==Kind::Start {
            match name {
                Some("dimension") if path.len()==2&&path[0]=="worksheet"=>{
                    let reference=attrs.get("ref").ok_or_else(||malformed("Missing worksheet dimension"))?;
                    let coordinates:Vec<_>=reference.split(':').collect();
                    if coordinates.is_empty()||coordinates.len()>2||dimensions.is_some() {return Err(malformed("Invalid or repeated worksheet dimension"));}
                    let first=coordinate(coordinates[0])?;
                    let last=coordinates[coordinates.len()-1];
                    let (row,col)=coordinate(last)?;let rows=row.checked_add(1).ok_or_else(||budget("Row overflow"))?;
                    if first.0>row||first.1>col {return Err(malformed("Reversed worksheet dimension"));}
                    let columns=col.checked_add(1).ok_or_else(||budget("Column overflow"))?;
                    if rows>limits.max_rows||columns>limits.max_columns||u64::from(rows)*u64::from(columns)>limits.max_cells {return Err(budget("Worksheet rectangle budget exceeded before calamine load"));}
                    dimensions=Some((rows,columns));
                }
                Some("row") if path.len()==3&&path[0]=="worksheet"&&path[1]=="sheetData"=>{has_rows=true;}
                Some("c") if path.len()==4&&path[0]=="worksheet"&&path[1]=="sheetData"&&path[2]=="row"=>{
                    if current.is_some() {return Err(malformed("Nested worksheet cell"));}
                    let address=coordinate(attrs.get("r").ok_or_else(||Error::new("unsupported_workbook","Explicit A1 cell coordinates are required"))?)?;
                    if address.0>=limits.max_rows||address.1>=limits.max_columns {return Err(budget("Cell coordinate budget exceeded"));}
                    current=Some((address,Cell {kind:attrs.get("t").cloned().unwrap_or_else(||"n".into()),value:String::new(),inline:None}));
                }
                Some("is") if path.len()==5&&path[3]=="c"=>{if let Some((_,cell))=&mut current {cell.inline=Some(String::new());}}
                _=>{},
            }
        }
        if kind==Kind::Text {
            if let Some((_,cell))=&mut current {
                if name==Some("v")&&path.len()==5&&path[3]=="c" {xml::append(&mut cell.value,text,limits.max_value_bytes)?;}
                if rich_text(path,"is") {xml::append(cell.inline.as_mut().ok_or_else(||malformed("Inline string outside is"))?,text,limits.max_value_bytes)?;}
            }
        }
        if kind==Kind::End&&name==Some("c")&&path.len()==4&&path[0]=="worksheet"&&path[1]=="sheetData"&&path[2]=="row" {
            let (address,cell)=current.take().ok_or_else(||malformed("Missing current worksheet cell"))?;
            total=total.checked_add(cell.value.len()).and_then(|v|v.checked_add(cell.inline.as_ref().map_or(0,String::len))).ok_or_else(||budget("Raw cell byte overflow"))?;
            if total>limits.max_decoded_bytes||result.len() as u64>=limits.max_cells {return Err(budget("Raw worksheet cell budget exceeded"));}
            if result.insert(address,cell).is_some() {return Err(malformed("Duplicate worksheet coordinate"));}
        }
        Ok(())
    })?;
    let (rows,columns)=dimensions.ok_or_else(||Error::new("unsupported_workbook","An explicit worksheet dimension is required"))?;
    if result.keys().any(|(r,c)|*r>=rows||*c>=columns) {return Err(Error::new("unsupported_workbook","Cells outside declared worksheet dimension are refused"));}
    Ok(Cells {rows,columns,has_rows,cells:result})
}
