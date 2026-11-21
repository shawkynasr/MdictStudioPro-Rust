//! M3 export-specific header policy. M2 source remains frozen.
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
fn parse(raw:&str,kind:Kind)->Result<BTreeMap<String,String>> {
    let root:&[u8]=match kind {Kind::Mdx=>b"Dictionary",Kind::Mdd=>b"Library_Data"};
    let mut reader=Reader::from_str(raw);let mut attrs=None;let(mut opened,mut closed)=(false,false);
    loop {let event=reader.read_event().map_err(xml_error)?;let empty=matches!(&event,Event::Empty(_));match event {
        Event::Empty(element)|Event::Start(element)=>{
            if opened||closed||element.name().as_ref()!=root {return Err(xml_error("Expected one format-specific root without children: Dictionary for MDX, Library_Data for MDD"));}
            let mut values=BTreeMap::new();let mut bytes=0usize;
            for attr in element.attributes() {
                let attr=attr.map_err(xml_error)?;let name=canonical(std::str::from_utf8(attr.key.as_ref()).map_err(xml_error)?);
                let value=attr.decode_and_unescape_value(reader.decoder()).map_err(xml_error)?.into_owned();
                bytes=sum(bytes,sum(name.len(),value.len())?)?;
                if values.len()>=256||bytes>65536 {return Err(budget("Header attribute budget exceeded"));}
                if values.insert(name,value).is_some() {return Err(xml_error("Duplicate/conflicting header aliases"));}
            }attrs=Some(values);opened=true;closed=empty;
        },
        Event::End(element)=>{if !opened||closed||element.name().as_ref()!=root {return Err(xml_error("Unbalanced header element"));}closed=true;},
        Event::Text(text)=>{if text.as_ref().iter().any(|b|!b.is_ascii_whitespace()) {return Err(xml_error("Unexpected header text"));}},
        Event::Decl(_)|Event::Comment(_)=>{},
        Event::Eof=>break,
        _=>return Err(xml_error("Unsupported header XML construct")),
    }}
    if !opened||!closed {return Err(xml_error("Incomplete dictionary/resource header"));}attrs.ok_or_else(||xml_error("Missing header"))
}
fn validate(kind:Kind,attrs:&BTreeMap<String,String>)->Result<(Option<bool>,Option<bool>)> {
    let legacy=matches!(kind,Kind::Mdx)&&attrs.get("GeneratedByEngineVersion").map(String::as_str)==Some("1.2")&&attrs.get("RequiredEngineVersion").map(String::as_str)==Some("1.2");
    if !legacy {for name in ["GeneratedByEngineVersion","RequiredEngineVersion"] {
        if !matches!(attrs.get(name).map(String::as_str),Some("2.0"|"2")) {return Err(unsupported(format!("Only declared v2 or the v1.2 ASCII export profile is supported ({name})")));}
    }}
    let encrypted=attrs.get("Encrypted").map(|s|s.to_ascii_lowercase());
    let supported=matches!(encrypted.as_deref(),None|Some("no"|"0"|"")) || (!legacy&&matches!(kind,Kind::Mdx)&&encrypted.as_deref()==Some("2"));
    if !supported {return Err(unsupported("Only unencrypted v2 or MDX v2 Encrypted=2 keyword-index encryption is supported; passcode modes and MDX v3 are outside this export profile"));}
    let encoding=attrs.get("Encoding").map(|s|s.to_ascii_uppercase()).unwrap_or_default();
    match kind {
        Kind::Mdx=>{
            if legacy {if encoding!="ISO8859-1" {return Err(unsupported("The v1.2 profile requires ISO8859-1-labelled ASCII content"));}}
            else if !matches!(encoding.as_str(),"UTF-8"|"UTF8"|"UTF-16"|"UTF-16LE") {return Err(unsupported("MDX v2 import supports UTF-8/UTF-16 only"));}
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
    let attrs=parse(&raw,kind)?;let(case_sensitive,strip_key)=validate(kind,&attrs)?;
    job.tick("header",1,1)?;
    Ok((temp,Header {kind,attributes:attrs,raw_xml:raw,raw_utf16le:bytes,case_sensitive,strip_key}))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn format_roots_are_selected_by_kind_and_children_are_still_refused() {
        for xml in ["<Dictionary Title=\"MDX\"/>","<Dictionary Title=\"MDX\"></Dictionary>"] {
            assert_eq!(parse(xml,Kind::Mdx).unwrap()["Title"],"MDX");assert!(parse(xml,Kind::Mdd).is_err());
        }
        for xml in ["<Library_Data Title=\"MDD\"/>","<Library_Data Title=\"MDD\"></Library_Data>"] {
            assert_eq!(parse(xml,Kind::Mdd).unwrap()["Title"],"MDD");assert!(parse(xml,Kind::Mdx).is_err());
        }
        for xml in ["<Foreign/>","<Library_Data><Child/></Library_Data>","<Library_Data/><Library_Data/>","<Library_Data Title=\"one\" title=\"two\"/>"] {assert!(parse(xml,Kind::Mdd).is_err());}
    }
}

#[cfg(test)]mod policy_tests {
 use super::*;
 #[test]fn exact_v2_index_only_flag_is_the_only_new_allowance() {
  let xml="<Dictionary GeneratedByEngineVersion=\"2.0\" RequiredEngineVersion=\"2.0\" Encoding=\"UTF-8\" Format=\"Html\" Encrypted=\"2\"/>";
  let attrs=parse(xml,Kind::Mdx).unwrap();assert!(validate(Kind::Mdx,&attrs).is_ok());assert!(validate(Kind::Mdd,&attrs).is_err());
  for flag in ["1","3","yes","4","02","-1","unknown"] {let mut a=attrs.clone();a.insert("Encrypted".into(),flag.into());assert!(validate(Kind::Mdx,&a).is_err());}
  for version in ["1.2","3.0"] {let mut a=attrs.clone();a.insert("GeneratedByEngineVersion".into(),version.into());assert!(validate(Kind::Mdx,&a).is_err());}
 }
}

/// A bounded decoder-only view, retaining the v1.2 wire grammar. Original
/// source bytes, source digest and exported metadata always use the snapshot.
/// UTF-8 is used solely as an ASCII validator; every decoded row is also
/// required to be ASCII before any destination is published.
pub(crate) fn legacy_ascii_view(snapshot:&tempfile::NamedTempFile,header:&Header,job:&mut ImportJob<'_>)->Result<Option<tempfile::NamedTempFile>> {
    if header.attributes.get("GeneratedByEngineVersion").map(String::as_str)!=Some("1.2"){return Ok(None);}
    if snapshot.as_file().metadata()?.len()>128*1024*1024{return Err(budget("v1.2 ASCII source exceeds 128 MiB"));}
    let mut xml=String::from("<Dictionary");
    for (name,value) in &header.attributes {
        let value=if name=="Encoding"{"UTF-8"}else{value.as_str()};
        xml.push_str(&format!(" {}=\"{}\"",name,quick_xml::escape::escape(value)));
    }
    xml.push_str("/>\r\n\0");let bytes:Vec<u8>=xml.encode_utf16().flat_map(u16::to_le_bytes).collect();
    if bytes.len()>65536{return Err(budget("v1.2 decoder header exceeds 64 KiB"));}
    let mut out=tempfile::NamedTempFile::new()?;out.write_all(&(bytes.len() as u32).to_be_bytes())?;out.write_all(&bytes)?;out.write_all(&adler(&bytes).to_le_bytes())?;
    let mut source=File::open(snapshot.path())?;source.seek(SeekFrom::Start(8+header.raw_utf16le.len() as u64))?;let mut buf=[0u8;65536];let mut copied=0;
    loop {job.tick("legacy_v1_snapshot",copied,128*1024*1024)?;let n=source.read(&mut buf)?;if n==0{break;}copied+=n;if copied>128*1024*1024{return Err(budget("v1.2 decoder copy exceeded cap"));}out.write_all(&buf[..n])?;}
    out.flush()?;Ok(Some(out))
}

#[cfg(test)]mod legacy_policy_tests {
 use super::*;
 #[test]fn only_exact_unencrypted_v1_2_ISO_label_is_admitted_to_ASCII_validation() {
  let xml="<Dictionary GeneratedByEngineVersion=\"1.2\" RequiredEngineVersion=\"1.2\" Encoding=\"ISO8859-1\" Format=\"Html\" Encrypted=\"No\"/>";
  let attrs=parse(xml,Kind::Mdx).unwrap();assert!(validate(Kind::Mdx,&attrs).is_ok());assert!(validate(Kind::Mdd,&attrs).is_err());
  for (name,value) in [("RequiredEngineVersion","2.0"),("GeneratedByEngineVersion","3.0"),("Encoding","UTF-8"),("Encoding","windows-1252"),("Encrypted","1"),("Encrypted","2"),("Encrypted","3")] {let mut a=attrs.clone();a.insert(name.into(),value.into());assert!(validate(Kind::Mdx,&a).is_err());}
 }
}
