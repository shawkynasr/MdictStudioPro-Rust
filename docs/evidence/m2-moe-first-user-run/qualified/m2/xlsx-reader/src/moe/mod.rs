//! Captured MOE layouts. Deliberate changes: first-seen set ordering and
//! explicit refusal of non-ASCII numeric syntax / image-marker filenames.
mod text;
mod layouts;
use crate::{Error,ReadControl,Result,Table,PROFILE};
use serde::Serialize;
use std::collections::BTreeMap;
pub type Row=BTreeMap<String,String>;

#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub enum Converter {Revised,Wfg,Concise,Idioms,Mini}
impl Converter {
    pub fn parse(name:&str)->Result<Self> {match name {
        "moe_revised"=>Ok(Self::Revised),"moe_revised_wfg"=>Ok(Self::Wfg),
        "moe_concise"=>Ok(Self::Concise),"moe_idioms"=>Ok(Self::Idioms),"moe_mini"=>Ok(Self::Mini),
        _=>Err(Error::new("invalid_input","Unknown MOE converter")),
    }}
    pub fn name(self)->&'static str {match self {Self::Revised=>"moe_revised",Self::Wfg=>"moe_revised_wfg",Self::Concise=>"moe_concise",Self::Idioms=>"moe_idioms",Self::Mini=>"moe_mini"}}
}
#[derive(Debug,Serialize,PartialEq,Eq)]
pub struct Entry {pub key:String,pub text:String}
#[derive(Debug,Serialize)]
pub struct Conversion {
    pub converter:&'static str,pub profile:&'static str,pub txt_profile:&'static str,
    pub entries:Vec<Entry>,pub primary_entries:usize,pub alias_redirects:usize,pub skipped_rows:usize,
}
#[derive(Clone,Debug)]
pub struct Limits {
    pub max_rows:usize,pub max_input_bytes:usize,pub max_entries:usize,
    pub max_key_bytes:usize,pub max_entry_bytes:usize,pub max_output_bytes:usize,
}
impl Default for Limits {fn default()->Self {Self {max_rows:10_000,max_input_bytes:16*1024*1024,
    max_entries:1000,max_key_bytes:4096,max_entry_bytes:1024*1024,max_output_bytes:8*1024*1024}}}
fn budget()->Error {Error::new("limit_exceeded","MOE conversion budget exceeded")}
fn validate_record(key:&str,body:&str)->Result<()> {
    if key.is_empty()||key=="</>"||key.contains(['\n','\r','\0'])||key.starts_with('\u{feff}')||body.contains(['\r','\0'])||body.split('\n').any(|l|l=="</>") {
        return Err(Error::new("unrepresentable_source","MOE output cannot be represented by canonical TXT"));
    }Ok(())
}
fn add(entries:&mut Vec<Entry>,key:&str,body:String,bytes:&mut usize,limits:&Limits)->Result<()> {
    validate_record(key,&body)?;
    *bytes=bytes.checked_add(key.len()).and_then(|n|n.checked_add(body.len())).ok_or_else(budget)?;
    if entries.len()>=limits.max_entries||key.len()>limits.max_key_bytes||body.len()>limits.max_entry_bytes||*bytes>limits.max_output_bytes {return Err(budget());}
    entries.push(Entry {key:key.into(),text:body});Ok(())
}

/// Pure conversion; no Python, filesystem writes, dictionary sorting or HTML
/// escaping. Callers publish entries through the qualified canonical TXT API.
pub fn convert(table:&Table,kind:Converter,limits:&Limits,control:&mut ReadControl<'_>)->Result<Conversion> {
    control.check()?;
    if table.profile!=PROFILE {return Err(Error::new("unsupported_policy","Expected openpyxl-values-v1 table"));}
    if table.rows.len()>limits.max_rows {return Err(budget());}
    let head_column=match kind {Converter::Mini=>"單字",Converter::Idioms=>"成語",_=>"字詞名"};
    let mut groups:Vec<(String,Vec<&Row>)>=Vec::new();let mut index=BTreeMap::new();let mut skipped=0;let mut input_bytes=0usize;
    for row in &table.rows {
        control.check()?;
        for (key,value) in row {
            input_bytes=input_bytes.checked_add(key.len()).and_then(|n|n.checked_add(value.len())).ok_or_else(budget)?;
            if input_bytes>limits.max_input_bytes||value.len()>limits.max_entry_bytes {return Err(budget());}
            text::check_profile(key,value)?;
        }
        let head=text::get(row,head_column);
        if head.is_empty() {skipped+=1;continue;}
        if head.len()>limits.max_key_bytes {return Err(budget());}
        let slot=match index.get(head) {Some(&i)=>i,None=>{let i=groups.len();index.insert(head.to_owned(),i);groups.push((head.into(),Vec::new()));i}};
        groups[slot].1.push(row);
    }
    if groups.is_empty() {return Err(Error::new("malformed_source",format!("No valid entries under {head_column}")));}
    let primary_entries=groups.len();let mut entries=Vec::new();let mut bytes=0;let mut alias_redirects=0;
    control.checkpoint("converting",0,primary_entries)?;
    for (i,(head,rows)) in groups.iter().enumerate() {
        control.check()?;
        let body=layouts::build(kind,head,rows);
        add(&mut entries,head,body,&mut bytes,limits)?;
        if kind==Converter::Revised {
            let mut aliases=Vec::new();
            for row in rows {for alias in text::get(row,"辭條別名").split('；').map(text::trim) {
                if !alias.is_empty()&&alias!=head&&!aliases.contains(&alias) {aliases.push(alias);}
            }}
            for alias in aliases {add(&mut entries,alias,format!("@@@LINK={head}"),&mut bytes,limits)?;alias_redirects+=1;}
        }
        control.checkpoint("converting",i+1,primary_entries)?;
    }
    Ok(Conversion {converter:kind.name(),profile:"moe-legacy-layout-v1-first-seen",txt_profile:"canonical_v1",entries,primary_entries,alias_redirects,skipped_rows:skipped})
}
