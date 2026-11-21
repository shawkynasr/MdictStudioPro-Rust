use crate::{Error,ErrorCode,Limits,ImportJob,Result,budget,integrity,invalid,unsupported,sum};
use quick_xml::{Reader,events::Event};
use serde::Serialize;
use std::{collections::BTreeMap,fs::File,io::{Read,Write,Seek,SeekFrom},path::Path};

#[derive(Clone,Copy,Debug,Serialize)]
#[serde(rename_all="snake_case")]
pub enum Kind {Mdx,Mdd}
#[derive(Clone,Debug,Serialize)]
pub struct Header {
    pub kind:Kind,pub attributes:BTreeMap<String,String>,pub raw_xml:String,
    pub raw_utf16le:Vec<u8>,pub case_sensitive:Option<bool>,pub strip_key:Option<bool>,
}
fn adler(data:&[u8])->u32 {let(mut a,mut b)=(1u32,0u32);for &c in data {a=(a+u32::from(c))%65521;b=(b+a)%65521;}(b<<16)|a}
fn canonical(name:&str)->String {
    for known in ["GeneratedByEngineVersion","RequiredEngineVersion","Encrypted","Encoding","Format","KeyCaseSensitive","StripKey","Title","Description","StyleSheet","Compact","Compat"] {
        if name.eq_ignore_ascii_case(known) {return known.into();}
    }name.into()
}
fn flag(attrs:&BTreeMap<String,String>,name:&str)->Result<Option<bool>> {
    match attrs.get(name) {None=>Ok(None),Some(value)=>match value.to_ascii_lowercase().as_str() {"yes"|"1"=>Ok(Some(true)),"no"|"0"=>Ok(Some(false)),_=>Err(unsupported(format!("Unsupported {name} flag")))}}
}
fn xml_error(e:impl std::fmt::Display)->Error {invalid("header_xml",e.to_string())}
fn parse(raw:&str)->Result<BTreeMap<String,String>> {
    let mut reader=Reader::from_str(raw);let mut attrs=None;let(mut opened,mut closed)=(false,false);
    loop {let event=reader.read_event().map_err(xml_error)?;let empty=matches!(&event,Event::Empty(_));match event {
        Event::Empty(element)|Event::Start(element)=>{
            if opened||closed||element.name().as_ref()!=b"Dictionary" {return Err(xml_error("Expected one Dictionary element without children"));}
            let mut values=BTreeMap::new();let mut bytes=0usize;
            for attr in element.attributes() {
                let attr=attr.map_err(xml_error)?;let name=canonical(std::str::from_utf8(attr.key.as_ref()).map_err(xml_error)?);
                let value=attr.decode_and_unescape_value(reader.decoder()).map_err(xml_error)?.into_owned();
                bytes=sum(bytes,sum(name.len(),value.len())?)?;
                if values.len()>=256||bytes>65536 {return Err(budget("Header attribute budget exceeded"));}
                if values.insert(name,value).is_some() {return Err(xml_error("Duplicate/conflicting header aliases"));}
            }attrs=Some(values);opened=true;closed=empty;
        },
        Event::End(element)=>{if !opened||closed||element.name().as_ref()!=b"Dictionary" {return Err(xml_error("Unbalanced header element"));}closed=true;},
        Event::Text(text)=>{if text.as_ref().iter().any(|b|!b.is_ascii_whitespace()) {return Err(xml_error("Unexpected header text"));}},
        Event::Decl(_)|Event::Comment(_)=>{},
        Event::Eof=>break,
        _=>return Err(xml_error("Unsupported header XML construct")),
    }}
    if !opened||!closed {return Err(xml_error("Incomplete Dictionary header"));}attrs.ok_or_else(||xml_error("Missing header"))
}
fn validate(kind:Kind,attrs:&BTreeMap<String,String>)->Result<(Option<bool>,Option<bool>)> {
    for name in ["GeneratedByEngineVersion","RequiredEngineVersion"] {
        if !matches!(attrs.get(name).map(String::as_str),Some("2.0"|"2")) {return Err(unsupported(format!("Only declared v2 is supported ({name})")));}
    }
    if !matches!(attrs.get("Encrypted").map(|s|s.to_ascii_lowercase()).as_deref(),None|Some("no"|"0"|"")) {return Err(unsupported("Encrypted dictionaries are outside this import profile"));}
    let encoding=attrs.get("Encoding").map(|s|s.to_ascii_uppercase()).unwrap_or_default();
    match kind {
        Kind::Mdx=>{
            if !matches!(encoding.as_str(),"UTF-8"|"UTF8"|"UTF-16"|"UTF-16LE") {return Err(unsupported("MDX import supports UTF-8/UTF-16 only"));}
            if !matches!(attrs.get("Format").map(|s|s.to_ascii_lowercase()).as_deref(),Some("html"|"text")) {return Err(unsupported("MDX import supports declared HTML/Text content"));}
        },
        // MDD uses the engine's typed resource/key grammar; this declaration
        // never decodes resource payloads as text. Legacy writers also emit
        // UTF-8 here while resource keys follow the MDD UTF-16 grammar.
        Kind::Mdd=>if !matches!(encoding.as_str(),""|"UTF-8"|"UTF8"|"UTF-16"|"UTF-16LE") {return Err(unsupported("Unsupported MDD encoding declaration"));},
    }
    Ok((flag(attrs,"KeyCaseSensitive")?,flag(attrs,"StripKey")?))
}
/// Copy through a fixed buffer into a private capped snapshot. Version and
/// encryption checks and engine decoding then read the same private bytes.
pub(crate) fn snapshot(path:&Path,kind:Kind,limits:&Limits,job:&mut ImportJob<'_>)->Result<(tempfile::NamedTempFile,Header)> {
    job.check()?;let mut source=File::open(path)?;let meta=source.metadata()?;
    if !meta.is_file() {return Err(invalid("source","Expected a regular dictionary file"));}
    let cap=limits.dictionary.max_file_bytes;
    if meta.len()>cap {return Err(budget("Dictionary file budget exceeded"));}
    let mut temp=tempfile::NamedTempFile::new()?;let mut copied=0u64;let mut buffer=[0u8;65536];
    loop {
        job.tick("snapshot",usize::try_from(copied).map_err(|_|budget("File size overflow"))?,usize::try_from(meta.len().max(copied)).map_err(|_|budget("File size overflow"))?)?;
        let n=source.read(&mut buffer)?;if n==0 {break;}
        copied=copied.checked_add(n as u64).ok_or_else(||budget("File size overflow"))?;
        if copied>cap {return Err(budget("Dictionary grew beyond file budget"));}temp.write_all(&buffer[..n])?;
    }
    temp.flush()?;temp.seek(SeekFrom::Start(0))?;
    let mut size=[0u8;4];temp.read_exact(&mut size)?;let size=u32::from_be_bytes(size) as usize;
    if size<2||size%2!=0||size>limits.dictionary.max_metadata_bytes.min(65536) {return Err(budget("Invalid or oversized UTF-16 header"));}
    let mut bytes=vec![0u8;size];temp.read_exact(&mut bytes)?;let mut checksum=[0u8;4];temp.read_exact(&mut checksum)?;
    if u32::from_le_bytes(checksum)!=adler(&bytes) {return Err(integrity("Header checksum mismatch"));}
    let units:Vec<_>=bytes.chunks_exact(2).map(|b|u16::from_le_bytes([b[0],b[1]])).collect();
    let decoded=String::from_utf16(&units).map_err(|_|Error::new(ErrorCode::InvalidEncoding,"header_encoding","Invalid UTF-16LE header"))?;
    let raw=decoded.strip_prefix('\u{feff}').unwrap_or(&decoded);
    let raw=raw.strip_suffix('\0').unwrap_or(raw).to_owned();
    if raw.contains('\0') {return Err(xml_error("Interior NUL in header"));}
    let attrs=parse(&raw)?;let(case_sensitive,strip_key)=validate(kind,&attrs)?;
    job.tick("header",1,1)?;
    Ok((temp,Header {kind,attributes:attrs,raw_xml:raw,raw_utf16le:bytes,case_sensitive,strip_key}))
}
