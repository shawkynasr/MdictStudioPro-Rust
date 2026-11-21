use crate::{budget,malformed,normalize_number,package::{self,Cell,Package},trimmed,Error,Limits,ReadControl,Result,Table,PROFILE};
use calamine::{Data,HeaderRow,Reader,Xlsx};
use std::{collections::BTreeMap,fs,io::{Cursor,Read},path::Path};

fn scalar(cell:Option<&Cell>,data:Option<&Data>,strings:&[String],header:bool)->Result<Option<String>> {
    let Some(cell)=cell else {return Ok(None);};
    if cell.kind=="inlineStr" {return Ok(cell.inline.as_deref().map(trimmed));}
    if cell.value.is_empty() {return Ok(None);}
    let value=match cell.kind.as_str() {
        "n"=>{
            if matches!(data,Some(Data::DateTime(_)|Data::DateTimeIso(_)|Data::DurationIso(_))) {
                return Err(Error::new("unsupported_cell","Date/time/duration cells require a separate compatibility profile"));
            }
            normalize_number(&cell.value,header)?
        }
        "s"=>{
            let index=cell.value.parse::<usize>().map_err(malformed)?;
            trimmed(strings.get(index).ok_or_else(||malformed("Shared string index is out of range"))?)
        }
        "b"=>match cell.value.as_str() {"0"=>"False".into(),"1"=>"True".into(),_=>return Err(malformed("Invalid boolean cell"))},
        "str"|"e"=>trimmed(&cell.value),
        "d"=>return Err(Error::new("unsupported_cell","ISO date/time cells are outside this profile")),
        _=>return Err(Error::new("unsupported_cell",format!("Unsupported cell type {}",cell.kind))),
    };
    Ok(Some(value))
}

pub fn read_xlsx_bytes(bytes:&[u8],sheet_name:Option<&str>,limits:&Limits,control:&mut ReadControl<'_>)->Result<Table> {
    control.checkpoint("begin",0,0)?;
    let mut package=Package::new(bytes,limits,control)?;
    let (sheets,active)=package::workbook(&package.part("xl/workbook.xml")?,control)?;
    let selected=if let Some(name)=sheet_name.filter(|n|!n.is_empty()) {
        sheets.iter().find(|s|s.name==name).ok_or_else(||Error::new("sheet_not_found",format!("Worksheet not found: {name}")))?
    }else{sheets.get(active).ok_or_else(||Error::new("sheet_not_found","Active worksheet index is out of range"))?};
    let target=package::worksheet_target(&package.part("xl/_rels/workbook.xml.rels")?,&selected.relationship,control)?;
    let raw=package::cells(&package.part(&target)?,limits,control)?;
    let strings=if package.contains("xl/sharedStrings.xml") {package::shared_strings(&package.part("xl/sharedStrings.xml")?,limits,control)?}else{Vec::new()};
    control.checkpoint("calamine_range",0,raw.rows as usize)?;
    // Both readers see the exact same immutable byte snapshot. Range allocation
    // follows XML/ZIP size and coordinate checks, but is not a hard RSS bound.
    let mut workbook:Xlsx<_>=Xlsx::new(Cursor::new(bytes)).map_err(malformed)?;
    if !workbook.sheet_names().iter().any(|name|name==&selected.name) {return Err(malformed("Backend worksheet inventory differs"));}
    workbook.with_header_row(HeaderRow::Row(0));
    let range=workbook.worksheet_range(&selected.name).map_err(malformed)?;
    if range.end().is_some_and(|(r,c)|r>=raw.rows||c>=raw.columns) {return Err(malformed("Backend range exceeds declared geometry"));}
    if !raw.has_rows {
        control.checkpoint("complete",0,0)?;
        return Ok(Table {profile:PROFILE,backend:"calamine-0.31.0-with-openpyxl-scalar-sidecar",sheet_name:selected.name.clone(),
            headers:Vec::new(),rows:Vec::new(),scanned_data_rows:0,skipped_blank_rows:0});
    }
    control.checkpoint("normalization",0,raw.rows as usize)?;
    let mut headers=Vec::new();let mut decoded=0usize;
    for column in 0..raw.columns {
        let value=scalar(raw.cells.get(&(0,column)),range.get_value((0,column)),&strings,true)?;
        let header=value.unwrap_or_else(||format!("col_{column}"));
        decoded=decoded.checked_add(header.len()).ok_or_else(||budget("Header byte overflow"))?;
        if decoded>limits.max_decoded_bytes {return Err(budget("Normalized header budget exceeded"));}
        headers.push(header);
    }
    let mut rows=Vec::new();let mut skipped_blank_rows=0;
    for row in 1..raw.rows {
        control.check()?;if row%256==0 {control.checkpoint("normalization",row as usize,raw.rows as usize)?;}
        let mut values=Vec::new();let mut any_value=false;
        for column in 0..raw.columns {
            let value=scalar(raw.cells.get(&(row,column)),range.get_value((row,column)),&strings,false)?;
            any_value|=value.is_some();values.push(value.unwrap_or_default());
        }
        if !any_value {skipped_blank_rows+=1;continue;}
        let mut record=BTreeMap::new();
        for (header,value) in headers.iter().zip(values) {
            decoded=decoded.checked_add(header.len()).and_then(|n|n.checked_add(value.len())).ok_or_else(||budget("Normalized row byte overflow"))?;
            if decoded>limits.max_decoded_bytes {return Err(budget("Normalized table byte budget exceeded"));}
            record.insert(header.clone(),value);
        }
        rows.push(record);
    }
    control.checkpoint("complete",raw.rows as usize,raw.rows as usize)?;
    Ok(Table {profile:PROFILE,backend:"calamine-0.31.0-with-openpyxl-scalar-sidecar",sheet_name:selected.name.clone(),
        headers,rows,scanned_data_rows:raw.rows.saturating_sub(1) as usize,skipped_blank_rows})
}

pub fn read_xlsx(path:&Path,sheet_name:Option<&str>,limits:&Limits,control:&mut ReadControl<'_>)->Result<Table> {
    control.check()?;
    let io_error=|error:std::io::Error|Error::new("io",error.to_string());
    if !fs::metadata(path).map_err(io_error)?.is_file() {return Err(Error::new("invalid_input","Workbook must be a regular file"));}
    let mut file=fs::File::open(path).map_err(io_error)?;
    if file.metadata().map_err(io_error)?.len()>limits.max_file_bytes {return Err(budget("Workbook file byte budget exceeded"));}
    let mut bytes=Vec::new();(&mut file).take(limits.max_file_bytes.checked_add(1).ok_or_else(||budget("File budget overflow"))?).read_to_end(&mut bytes).map_err(io_error)?;
    read_xlsx_bytes(&bytes,sheet_name,limits,control)
}
