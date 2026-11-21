//! Metadata-only rebuild: serialize a supported header, copy every data-section
//! byte, verify raw metadata and all physical records, then publish exclusively.
use crate::{Dictionary,ResourceArchive,LookupPolicy,Header,Kind,Limits,ImportJob,Error,ErrorCode,Result};
use serde::{Deserialize,Serialize};
use std::{collections::{BTreeMap,BTreeSet},fs,io::{Read,Write,Seek,SeekFrom},path::{Path,PathBuf}};
pub const PROFILE:&str="mdict-v2-metadata-v1";
#[derive(Clone,Copy,Debug,Deserialize,Serialize)]
#[serde(rename_all="snake_case")]
pub enum FileKind {Mdx,Mdd}
#[derive(Clone,Debug,Default,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
pub struct Edits {pub title:Option<String>,pub description:Option<String>,pub stylesheet:Option<String>}
#[derive(Clone,Debug,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
pub struct Request {pub source:PathBuf,pub destination:PathBuf,pub kind:FileKind,pub edits:Edits}
#[derive(Debug,Serialize)]
pub struct Summary {pub profile:&'static str,pub destination:PathBuf,pub records:usize,pub file_bytes:u64,pub stylesheet_rules:usize,pub header:Header}
fn xml_char(c:char)->bool {matches!(c,'\t'|'\n'|'\r'|'\u{20}'..='\u{d7ff}'|'\u{e000}'..='\u{fffd}'|'\u{10000}'..='\u{10ffff}')}
fn name(value:&str)->bool {let mut b=value.bytes();b.next().is_some_and(|v|v.is_ascii_alphabetic()||v==b'_')&&b.all(|v|v.is_ascii_alphanumeric()||matches!(v,b'_'|b'-'|b'.'))}
fn escape(value:&str,literal_lf:bool)->Result<String> {
    let mut out=String::new();for c in value.chars() {
        if !xml_char(c) {return Err(crate::invalid("metadata_xml","Metadata contains a character outside XML 1.0"));}
        match c {'&'=>out.push_str("&amp;"),'<'=>out.push_str("&lt;"),'>'=>out.push_str("&gt;"),'"'=>out.push_str("&quot;"),
            '\n' if !literal_lf=>out.push_str("&#10;"),'\r'=>out.push_str("&#13;"),'\t'=>out.push_str("&#9;"),_=>out.push(c)}
    }Ok(out)
}
fn rules(value:&str)->Result<BTreeSet<String>> {
    if value.is_empty() {return Ok(BTreeSet::new());}
    if value.contains('\r')||!value.ends_with('\n') {return Err(crate::unsupported("Stylesheets require LF triplets including a final LF; CR/CRLF is not silently normalized"));}
    let lines:Vec<_>=value.strip_suffix('\n').expect("Final LF").split('\n').collect();
    if lines.len()%3!=0 {return Err(crate::invalid("stylesheet_triplets","Stylesheet must contain ID/prefix/suffix triplets"));}
    let mut ids=BTreeSet::new();
    for triple in lines.chunks_exact(3) {
        if triple[0].is_empty()||triple[0].len()>32||!triple[0].bytes().all(|b|b.is_ascii_digit())||!ids.insert(triple[0].to_owned()) {
            return Err(crate::invalid("stylesheet_id","Stylesheet IDs must be unique nonempty ASCII decimal strings, <=32 bytes"));
        }
        if triple[1].contains('\t')||triple[2].contains('\t') {return Err(crate::unsupported("Stylesheet tab controls are outside the native-tested LF profile"));}
    }Ok(ids)
}
fn validate_markers(text:&str,ids:&BTreeSet<String>)->Result<()> {
    let bytes=text.as_bytes();let mut pos=0;
    while pos<bytes.len() {
        if bytes[pos]!=b'`' {pos+=1;continue;}let start=pos+1;let mut end=start;
        while end<bytes.len()&&bytes[end].is_ascii_digit() {end+=1;}
        if end>start&&end<bytes.len()&&bytes[end]==b'`' {
            if !ids.contains(&text[start..end]) {return Err(crate::invalid("stylesheet_marker","A numeric definition marker has no matching stylesheet rule"));}pos=end+1;
        }else {pos+=1;}
    }Ok(())
}
pub fn serialize(kind:FileKind,attrs:&BTreeMap<String,String>)->Result<Vec<u8>> {
    if attrs.len()>256 {return Err(crate::budget("Metadata attribute count exceeded"));}
    let style=attrs.get("StyleSheet").map(String::as_str).unwrap_or("");rules(style)?;
    let root=match kind {FileKind::Mdx=>"Dictionary",FileKind::Mdd=>"Library_Data"};let mut xml=format!("<{root}");
    for (key,value) in attrs {
        if !name(key) {return Err(crate::unsupported("Rebuild supports ASCII non-namespaced attribute names only"));}
        xml.push(' ');xml.push_str(key);xml.push_str("=\"");xml.push_str(&escape(value,key=="StyleSheet")?);xml.push('"');
        if xml.len()>65536 {return Err(crate::budget("Serialized metadata budget exceeded"));}
    }
    xml.push_str("/>\r\n\0");let bytes:Vec<_>=xml.encode_utf16().flat_map(u16::to_le_bytes).collect();
    if bytes.len()>65536 {return Err(crate::budget("UTF-16 header exceeds 64 KiB"));}Ok(bytes)
}
fn adler(data:&[u8])->u32 {let(mut a,mut b)=(1u32,0u32);for &c in data {a=(a+u32::from(c))%65521;b=(b+a)%65521;}(b<<16)|a}
enum Content {Mdx(Dictionary),Mdd(ResourceArchive)}
fn open(path:&Path,kind:FileKind,limits:&Limits,job:&mut ImportJob<'_>)->Result<Content> {
    match kind {FileKind::Mdx=>Dictionary::open_v2(path,LookupPolicy::RawExact,limits,job).map(Content::Mdx),FileKind::Mdd=>ResourceArchive::open_v2(path,limits,job).map(Content::Mdd)}
}
impl Content {
    fn header(&self)->&Header {match self {Self::Mdx(d)=>d.header(),Self::Mdd(d)=>d.header()}}
    fn len(&self)->usize {match self {Self::Mdx(d)=>d.entries().len(),Self::Mdd(d)=>d.resources().len()}}
}
/// Editing is limited to title/description/stylesheet. Structural flags, unknown
/// attributes and the key/record sections are retained; content is not repacked.
pub fn rebuild(request:&Request,job:&mut ImportJob<'_>)->Result<Summary> {
    job.check()?;
    if request.source.as_os_str().len()>8192||request.destination.as_os_str().len()>8192||request.destination.file_name().is_none() {return Err(crate::invalid("path","Expected bounded source/destination file paths"));}
    if fs::symlink_metadata(&request.destination).is_ok() {return Err(Error::new(ErrorCode::DestinationExists,"destination_exists","Destination already exists"));}
    for value in [&request.edits.title,&request.edits.description,&request.edits.stylesheet].into_iter().flatten() {
        if value.len()>65536 {return Err(crate::budget("Metadata edit exceeds 64 KiB"));}
    }
    let limits=Limits::default();let kind=match request.kind {FileKind::Mdx=>Kind::Mdx,FileKind::Mdd=>Kind::Mdd};
    let(mut source,header)=crate::header::snapshot(&request.source,kind,&limits,job)?;
    let content=open(source.path(),request.kind,&limits,job)?;let mut attrs=header.attributes.clone();
    for (name,value) in [("Title",&request.edits.title),("Description",&request.edits.description),("StyleSheet",&request.edits.stylesheet)] {if let Some(value)=value {attrs.insert(name.into(),value.clone());}}
    let style=attrs.get("StyleSheet").map(String::as_str).unwrap_or("");let ids=rules(style)?;
    match &content {
        Content::Mdx(d)=>{
            if !ids.is_empty()&&!attrs.get("Format").is_some_and(|v|v.eq_ignore_ascii_case("html")) {return Err(crate::unsupported("Numeric styles require declared HTML definitions"));}
            for (i,row) in d.entries().iter().enumerate() {job.tick("metadata_markers",i,d.entries().len())?;validate_markers(&row.text,&ids)?;}
        },
        Content::Mdd(_)=>if !ids.is_empty() {return Err(crate::unsupported("MDD resource payloads do not use numeric definition styles"));},
    }
    if !ids.is_empty() {attrs.insert("Compact".into(),"Yes".into());}
    let encoded=serialize(request.kind,&attrs)?;let offset=8u64+header.raw_utf16le.len() as u64;
    let old_size=source.as_file().metadata()?.len();let new_size=old_size.checked_sub(offset).and_then(|n|n.checked_add(8+encoded.len() as u64)).ok_or_else(||crate::budget("Rebuild size overflow"))?;
    if new_size>limits.dictionary.max_file_bytes {return Err(crate::budget("Rebuilt dictionary exceeds file budget"));}
    let parent=request.destination.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new("."));let mut stage=tempfile::NamedTempFile::new_in(parent)?;
    stage.write_all(&(encoded.len() as u32).to_be_bytes())?;stage.write_all(&encoded)?;stage.write_all(&adler(&encoded).to_le_bytes())?;
    source.seek(SeekFrom::Start(offset))?;let mut copied=0usize;let mut buffer=[0u8;65536];
    loop {job.tick("metadata_copy",copied,(old_size-offset) as usize)?;let n=source.read(&mut buffer)?;if n==0 {break;}stage.write_all(&buffer[..n])?;copied+=n;}
    stage.flush()?;stage.as_file().sync_all()?;
    let verified=open(stage.path(),request.kind,&limits,job)?;
    let same=match (&content,&verified) {(Content::Mdx(a),Content::Mdx(b))=>a.entries()==b.entries(),(Content::Mdd(a),Content::Mdd(b))=>a.resources()==b.resources(),_=>false};
    if !same||verified.header().attributes!=attrs||verified.header().raw_utf16le!=encoded||stage.as_file().metadata()?.len()!=new_size {return Err(crate::integrity("Rebuild metadata/physical records verification failed"));}
    let summary=Summary {profile:PROFILE,destination:request.destination.clone(),records:verified.len(),file_bytes:new_size,stylesheet_rules:ids.len(),header:verified.header().clone()};
    job.tick("metadata_commit",1,1)?;
    stage.persist_noclobber(&request.destination).map_err(|e|if e.error.kind()==std::io::ErrorKind::AlreadyExists {Error::new(ErrorCode::DestinationExists,"destination_exists",e.error.to_string())}else {Error::from(e.error)})?;
    // Publication has committed. A later cancellation cannot roll it back.
    Ok(summary)
}

#[cfg(test)]mod tests {
    use super::*;
    #[test]fn escaping_and_stylesheet_wire_are_distinct_and_lossless() {
        let mut attrs=BTreeMap::new();attrs.insert("Description".into(),"A\r\nB\t<&\"'".into());attrs.insert("StyleSheet".into(),"1\n<b>\n</b>\n".into());
        let bytes=serialize(FileKind::Mdx,&attrs).unwrap();let units:Vec<_>=bytes.chunks_exact(2).map(|b|u16::from_le_bytes([b[0],b[1]])).collect();let xml=String::from_utf16(&units).unwrap();
        assert!(xml.contains("Description=\"A&#13;&#10;B&#9;&lt;&amp;&quot;'\""));assert!(xml.contains("StyleSheet=\"1\n&lt;b&gt;\n&lt;/b&gt;\n\""));
        assert!(escape("\u{1}",false).is_err());attrs.insert("bad:name".into(),"x".into());assert!(serialize(FileKind::Mdx,&attrs).is_err());
    }
    #[test]fn triplets_and_marker_references_are_not_silently_repaired() {
        for bad in ["1\n<b>\n</b>","1\r\n<b>\r\n</b>\r\n","x\n<b>\n</b>\n","1\n<b>\n</b>\n1\n<i>\n</i>\n"] {assert!(rules(bad).is_err());}
        let ids=rules("1\n<br>\n\n").unwrap();assert!(validate_markers("`1`raw marker",&ids).is_ok());assert!(validate_markers("`2`missing",&ids).is_err());assert!(validate_markers("`1`unchanged",&BTreeSet::new()).is_err());assert!(validate_markers("`literal` text",&BTreeSet::new()).is_ok());
    }
}

pub mod publication;
