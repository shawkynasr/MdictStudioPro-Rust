//! Metadata-aware packing and file-publication composition. Every result is
//! verified before the existing exclusive metadata publisher commits it.
pub mod runner;
use crate::{Entry,Resource,Limits,ImportJob,Dictionary,ResourceArchive,LookupPolicy,Error,ErrorCode,Result};
use serde::{Deserialize,Serialize};
use std::{collections::BTreeMap,fs,io::{Read,Write,Seek,SeekFrom},path::{Path,PathBuf}};
pub const MAX_REQUEST_BYTES:usize=16*1024*1024;
#[derive(Clone,Debug,Default,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
pub struct Metadata {
    pub title:String,pub description:String,#[serde(default)]pub stylesheet:String,
    #[serde(default)]pub extra:BTreeMap<String,String>,
}
impl Metadata {
    fn attributes(&self)->Result<BTreeMap<String,String>> {
        let reserved=["GeneratedByEngineVersion","RequiredEngineVersion","Encrypted","Encoding","Format","KeyCaseSensitive","StripKey","Title","Description","StyleSheet","Compact","Compat","xmlns"];
        let mut bytes=crate::sum(self.title.len(),crate::sum(self.description.len(),self.stylesheet.len())?)?;
        for key in self.extra.keys() {
            if key.to_ascii_lowercase().starts_with("studio")||reserved.iter().any(|n|key.eq_ignore_ascii_case(n)) {return Err(crate::invalid("metadata_override","Extra metadata cannot override structural/profile attributes"));}
        }
        for (key,value) in &self.extra {bytes=crate::sum(bytes,crate::sum(key.len(),value.len())?)?;}
        if bytes>65536 {return Err(crate::budget("Packing metadata exceeds 64 KiB"));}
        let mut attrs=self.extra.clone();attrs.insert("Title".into(),self.title.clone());attrs.insert("Description".into(),self.description.clone());attrs.insert("StyleSheet".into(),self.stylesheet.clone());
        super::serialize(super::FileKind::Mdx,&attrs)?;Ok(attrs)
    }
}
#[derive(Clone,Debug,Deserialize,Serialize)]
#[serde(tag="operation",rename_all="snake_case",deny_unknown_fields)]
pub enum Request {
    PackMdx {destination:PathBuf,encoding:studio_core::Encoding,metadata:Metadata,entries:Vec<Entry>},
    PackMdd {destination:PathBuf,metadata:Metadata,resources:Vec<Resource>},
    Rebuild {request:super::Request},
}
impl Request {
    pub fn destination(&self)->&Path {match self {Self::PackMdx {destination,..}|Self::PackMdd {destination,..}=>destination,Self::Rebuild {request}=>&request.destination}}
    pub fn operation(&self)->&'static str {match self {Self::PackMdx {..}=>"pack_metadata_mdx",Self::PackMdd {..}=>"pack_metadata_mdd",Self::Rebuild {..}=>"rebuild_metadata"}}
    pub fn validate(&self)->Result<()> {
        fn path(path:&Path)->Result<()> {if path.as_os_str().is_empty()||path.as_os_str().len()>8192||path.to_str().is_none() {return Err(crate::invalid("path","Require nonempty UTF-8 paths <=8192 bytes"));}Ok(())}
        path(self.destination())?;if self.destination().file_name().is_none() {return Err(crate::invalid("path","Destination must name a file"));}
        let limits=Limits::default();let mut decoded=0usize;
        match self {
            Self::PackMdx {metadata,entries,..}=>{
                metadata.attributes()?;let ids=super::rules(&metadata.stylesheet)?;
                if entries.is_empty()||entries.len()>limits.dictionary.max_entries {return Err(crate::budget("Packing requires 1..1000 entries"));}
                for row in entries {
                    crate::key(&row.key,&limits)?;
                    if row.text.contains('\0') {return Err(crate::invalid("definition","NUL inside a definition is not representable"));}
                    if row.text.len()>limits.dictionary.max_entry_bytes {return Err(crate::budget("Definition exceeds byte cap"));}
                    super::validate_markers(&row.text,&ids)?;decoded=crate::sum(decoded,crate::sum(row.key.len(),row.text.len())?)?;
                }
            },
            Self::PackMdd {metadata,resources,..}=>{
                metadata.attributes()?;if !metadata.stylesheet.is_empty() {return Err(crate::unsupported("MDD resources cannot carry numeric definition styles"));}
                if resources.is_empty()||resources.len()>limits.dictionary.max_entries {return Err(crate::budget("Packing requires 1..1000 resources"));}
                for row in resources {crate::key(&row.key,&limits)?;if row.bytes.len()>limits.dictionary.max_entry_bytes {return Err(crate::budget("Resource exceeds byte cap"));}decoded=crate::sum(decoded,crate::sum(row.key.len(),row.bytes.len())?)?;}
            },
            Self::Rebuild {request}=>{
                path(&request.source)?;let mut attrs=BTreeMap::new();
                for (key,value) in [("Title",&request.edits.title),("Description",&request.edits.description),("StyleSheet",&request.edits.stylesheet)] {if let Some(v)=value {attrs.insert(key.into(),v.clone());}}
                super::serialize(request.kind,&attrs)?;
            },
        }
        if decoded>limits.dictionary.max_decoded_bytes {return Err(crate::budget("Packing decoded-input cap exceeded"));}
        crate::application::measured(self,MAX_REQUEST_BYTES)?;Ok(())
    }
}
#[derive(Clone,Debug,Serialize)]
pub struct Output {pub destination:PathBuf,pub operation:&'static str,pub records:usize,pub file_bytes:u64,pub profile:&'static str}
fn order(keys:impl Iterator<Item=String>)->Result<Vec<usize>> {
    let casing=crate::casing::Casing::pinned16().map_err(|e|Error::new(ErrorCode::Internal,"casing",e.to_string()))?;
    let mut rows:Vec<_>=keys.enumerate().map(|(i,k)|(casing.lower(&k),i)).collect();rows.sort_by(|a,b|a.0.cmp(&b.0));Ok(rows.into_iter().map(|(_,i)|i).collect())
}
fn header_copy(source:&mut tempfile::NamedTempFile,attrs:&BTreeMap<String,String>,kind:super::FileKind,job:&mut ImportJob<'_>)->Result<tempfile::NamedTempFile> {
    let encoded=super::serialize(kind,attrs)?;let mut output=tempfile::NamedTempFile::new()?;
    output.write_all(&(encoded.len() as u32).to_be_bytes())?;output.write_all(&encoded)?;output.write_all(&super::adler(&encoded).to_le_bytes())?;
    source.seek(SeekFrom::Start(0))?;let mut size=[0u8;4];source.read_exact(&mut size)?;let offset=8+u64::from(u32::from_be_bytes(size));source.seek(SeekFrom::Start(offset))?;
    let total=source.as_file().metadata()?.len().checked_sub(offset).ok_or_else(||crate::integrity("Packed header extent exceeds file"))?;let mut copied=0usize;let mut buffer=[0u8;65536];
    loop {job.tick("packing_header_copy",copied,total as usize)?;let n=source.read(&mut buffer)?;if n==0 {break;}output.write_all(&buffer[..n])?;copied=crate::sum(copied,n)?;}
    output.flush()?;if output.as_file().metadata()?.len()>Limits::default().dictionary.max_file_bytes {return Err(crate::budget("Metadata-packed file exceeds byte cap"));}Ok(output)
}
/// Completion means publication committed. Never check cancellation or perform
/// fallible work after the nested publisher returns success.
pub fn execute(request:&Request,job:&mut ImportJob<'_>)->Result<Output> {
    job.check()?;request.validate()?;
    if fs::symlink_metadata(request.destination()).is_ok() {return Err(Error::new(ErrorCode::DestinationExists,"destination_exists","Destination already exists"));}
    let (summary,operation)=match request {
        Request::Rebuild {request:inner}=>(super::rebuild(inner,job)?,request.operation()),
        Request::PackMdx {destination,encoding,metadata,entries}=>{
            let indices=order(entries.iter().map(|r|r.key.clone()))?;
            let encoding=match encoding {studio_core::Encoding::Utf8=>mdictlib::WriteEncoding::Utf8,studio_core::Encoding::Utf16=>mdictlib::WriteEncoding::Utf16Le};
            let options=mdictlib::WriteOptions::new().with_encoding(encoding).with_compression(mdictlib::WriteCompression::Zlib).with_legacy_sort(mdictlib::LegacySort::PreserveInput).with_key_block_target_bytes(16*1024).with_record_block_target_bytes(64*1024);
            let mut builder=mdictlib::MdxBuilder::with_options(options);
            for (k,v) in [("Title","Metadata staging"),("Description","Metadata staging"),("Format","Html"),("KeyCaseSensitive","No"),("StripKey","No"),("Compact","No"),("Compat","Yes"),("StyleSheet","")] {builder.header_attribute(k,v)?;}
            for (i,&index) in indices.iter().enumerate() {job.tick("packing_entries",i,indices.len())?;builder.add_entry(&entries[index].key,&entries[index].text)?;}
            let mut raw=tempfile::NamedTempFile::new()?;builder.finish(raw.as_file_mut())?;raw.flush()?;job.tick("packing_encoded",1,1)?;
            let mut attrs={let d=Dictionary::open_v2(raw.path(),LookupPolicy::RawExact,&Limits::default(),job)?;
                if d.entries().len()!=indices.len()||d.entries().iter().zip(&indices).any(|(row,&i)|row!=&entries[i]) {return Err(crate::integrity("Packed MDX differs from input physical rows"));}d.header().attributes.clone()};
            attrs.extend(metadata.attributes()?);if !metadata.stylesheet.is_empty() {attrs.insert("Compact".into(),"Yes".into());}
            let source=header_copy(&mut raw,&attrs,super::FileKind::Mdx,job)?;
            {let d=Dictionary::open_v2(source.path(),LookupPolicy::RawExact,&Limits::default(),job)?;if d.header().attributes!=attrs {return Err(crate::integrity("Packed metadata differs from requested values"));}}
            let inner=super::Request {source:source.path().to_owned(),destination:destination.clone(),kind:super::FileKind::Mdx,edits:super::Edits::default()};
            (super::rebuild(&inner,job)?,request.operation())
        },
        Request::PackMdd {destination,metadata,resources}=>{
            let indices=order(resources.iter().map(|r|r.key.clone()))?;
            let options=mdictlib::WriteOptions::new().with_compression(mdictlib::WriteCompression::Zlib).with_legacy_sort(mdictlib::LegacySort::PreserveInput).with_key_block_target_bytes(16*1024).with_record_block_target_bytes(64*1024);
            let mut builder=mdictlib::MddBuilder::with_options(options);
            for (k,v) in [("Title","Metadata staging"),("Description","Metadata staging"),("Format",""),("KeyCaseSensitive","No"),("StripKey","No"),("Compact","No"),("Compat","No"),("StyleSheet","")] {builder.header_attribute(k,v)?;}
            for (i,&index) in indices.iter().enumerate() {job.tick("packing_resources",i,indices.len())?;builder.add_resource(&resources[index].key,&resources[index].bytes)?;}
            let mut raw=tempfile::NamedTempFile::new()?;builder.finish(raw.as_file_mut())?;raw.flush()?;job.tick("packing_encoded",1,1)?;
            let mut attrs={let d=ResourceArchive::open_v2(raw.path(),&Limits::default(),job)?;
                if d.resources().len()!=indices.len()||d.resources().iter().zip(&indices).any(|(row,&i)|row!=&resources[i]) {return Err(crate::integrity("Packed MDD differs from input physical resources"));}d.header().attributes.clone()};
            attrs.extend(metadata.attributes()?);let source=header_copy(&mut raw,&attrs,super::FileKind::Mdd,job)?;
            {let d=ResourceArchive::open_v2(source.path(),&Limits::default(),job)?;if d.header().attributes!=attrs {return Err(crate::integrity("Packed metadata differs from requested values"));}}
            let inner=super::Request {source:source.path().to_owned(),destination:destination.clone(),kind:super::FileKind::Mdd,edits:super::Edits::default()};
            (super::rebuild(&inner,job)?,request.operation())
        },
    };
    Ok(Output {destination:summary.destination,operation,records:summary.records,file_bytes:summary.file_bytes,profile:summary.profile})
}
