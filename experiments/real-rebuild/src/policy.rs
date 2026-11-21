//! Header/lookup qualification. Existing writer profiles remain unchanged.
use mdictlib::{LegacySort,MdxBuilder,MdxFile,WriteEncoding,WriteOptions};
use serde_json::{json,Value};
use std::{fs,path::Path};
use studio_engine_probe::{Entry,Result,stage_directory};

fn spec(path:&Path)->Result<Value>{
    if fs::metadata(path)?.len()>1024*1024{return Err("Policy spec limit is 1 MiB".into());}
    Ok(serde_json::from_slice(&fs::read(path)?)?)
}

fn boolean(attrs:&std::collections::BTreeMap<String,String>,name:&str)->Result<bool>{
    let mut resolved=None;
    for (key,value) in attrs {
        if key.eq_ignore_ascii_case(name){
            let value=match value.to_ascii_lowercase().as_str(){"yes"|"1"=>true,"no"|"0"=>false,_=>return Err(format!("Invalid {name} boolean").into())};
            if resolved.is_some_and(|previous|previous!=value){return Err(format!("Conflicting {name} aliases").into());}
            resolved=Some(value);
        }
    }
    resolved.ok_or_else(||format!("Missing explicit {name} in policy fixture").into())
}

fn adler(bytes:&[u8])->u32{
    let (mut a,mut b)=(1u32,0u32);
    for byte in bytes {a=(a+u32::from(*byte))%65521;b=(b+a)%65521;}
    (b<<16)|a
}

/// Diagnostic legacy flag overlay, not a general production header serializer.
/// Blocks and their relative offsets are unchanged. Prefix CRC is regenerated.
fn enable_strip(path:&Path)->Result<()> {
    let data=fs::read(path)?;let length=u32::from_be_bytes(data[..4].try_into()?) as usize;
    let words:Vec<u16>=data[4..4+length].chunks_exact(2).map(|p|u16::from_le_bytes([p[0],p[1]])).collect();
    let xml=String::from_utf16(&words)?;
    let anchor=" StripKey=\"No\"";
    if xml.matches(anchor).count()!=1{return Err("Ambiguous generated StripKey flag".into());}
    let xml=xml.replacen(anchor," StripKey=\"Yes\"",1);
    let xml:Vec<u8>=xml.encode_utf16().flat_map(u16::to_le_bytes).collect();
    let mut output=Vec::new();output.extend_from_slice(&(xml.len() as u32).to_be_bytes());output.extend_from_slice(&xml);
    output.extend_from_slice(&adler(&xml).to_le_bytes());output.extend_from_slice(&data[length+8..]);fs::write(path,output)?;Ok(())
}

pub fn inspect(spec_path:&Path,path:&Path)->Result<Value>{
    let spec=spec(spec_path)?;
    if fs::metadata(path)?.len()>16*1024*1024{return Err("Policy file limit is 16 MiB".into());}
    let file=MdxFile::open_with_options(path,&super::strict::options())?;
    let attrs=super::attributes(file.header());
    // Reject conflicting aliases before exposing rows or triggering lookups.
    let strip=boolean(&attrs,"StripKey")?;let sensitive=boolean(&attrs,"KeyCaseSensitive")?;
    let mut rows=Vec::new();
    for key in file.keys(){let key=key?;let e=file.entry_at(key.ordinal())?.ok_or("Missing policy row")?;rows.push(json!({"key":key.key(),"text":e.text()}));}
    if rows.len() as u64!=file.len() as u64{return Err("Incomplete policy scan".into());}
    let queries=spec["queries"].as_array().ok_or("Missing policy queries")?;
    if queries.len()>512{return Err("Policy query limit is 512".into());}
    let mut lookups=Vec::new();
    for query in queries {
        let query=query.as_str().ok_or("Invalid query")?;let mut matches=Vec::new();
        if let Some(found)=file.locate(query)?{for ordinal in found.iter(){let e=file.entry_at(ordinal)?.ok_or("Missing policy lookup")?;matches.push(json!({"key":e.key(),"text":e.text()}));}}
        lookups.push(json!({"query":query,"rows":matches}));
    }
    Ok(json!({"attributes":attrs,"resolved_strip":strip,"resolved_case_sensitive":sensitive,"rows":rows,"lookups":lookups,"checksum_policy":"Verify"}))
}

pub fn build(spec_path:&Path,out:&Path)->Result<Value>{
    let spec=spec(spec_path)?;
    let entries:Vec<Entry>=serde_json::from_value(spec["entries"].clone())?;
    if entries.is_empty()||entries.len()>1000{return Err("Policy fixture requires 1..1000 entries".into());}
    let profile=spec["profile"].as_str().ok_or("Missing profile")?;
    let (sort,strip)=match profile{"literal"=>(LegacySort::HeaderLiteralC,false),"mdict-utils"=>(LegacySort::MdictUtilsC,true),"mdxbuilder"=>(LegacySort::MdxBuilderC,true),_=>return Err("Unknown policy profile".into())};
    let encoding=match spec["encoding"].as_str(){Some("utf8")=>WriteEncoding::Utf8,Some("utf16")=>WriteEncoding::Utf16Le,_=>return Err("Unknown policy encoding".into())};
    let title=spec["title"].as_str().ok_or("Missing title")?;
    stage_directory(out,|stage|{
        let options=WriteOptions::new().with_encoding(encoding).with_legacy_sort(sort).with_key_block_target_bytes(32).with_record_block_target_bytes(96);
        let mut builder=MdxBuilder::with_options(options);
        for (key,value) in [("Title",title),("Description","Explicit header and lookup qualification"),("Format","Html"),("Compact","No"),("Compat","Yes"),("StyleSheet",""),("CreationDate","2026-10-29"),("RegisterBy",""),("DataSourceFormat","106"),("Left2Right","Yes")]{builder.header_attribute(key,value)?;}
        for e in &entries{builder.add_entry(&e.key,&e.text)?;}
        let path=stage.join("policy.mdx");let summary=builder.finish(fs::File::create(&path)?)?;
        if strip{enable_strip(&path)?;}
        super::strict::validate(&path)?;
        let mut observed=inspect(spec_path,&path)?;
        observed["key_blocks"]=json!(summary.key_blocks);observed["record_blocks"]=json!(summary.record_blocks);
        observed["profile"]=json!(profile);observed["diagnostic_header_overlay"]=json!(strip);
        Ok(observed)
    })
}

#[cfg(test)]
mod tests{
    use super::*;
    #[test]
    fn aliases_require_consistent_booleans(){
        let mut a=std::collections::BTreeMap::new();a.insert("Stripkey".into(),"Yes".into());assert!(boolean(&a,"StripKey").unwrap());
        a.insert("StripKey".into(),"No".into());assert!(boolean(&a,"StripKey").is_err());
        a.remove("StripKey");a.insert("Stripkey".into(),"maybe".into());assert!(boolean(&a,"StripKey").is_err());
        assert!(boolean(&a,"KeyCaseSensitive").is_err());
        assert_eq!(adler(b"Wikipedia"),0x11e60398);
    }
    #[test]
    fn diagnostic_overlay_keeps_every_key_and_record_byte(){
        let temp=tempfile::tempdir().unwrap();let path=temp.path().join("overlay.mdx");
        let mut builder=MdxBuilder::new();builder.add_entry("word","payload").unwrap();
        builder.finish(fs::File::create(&path).unwrap()).unwrap();let before=fs::read(&path).unwrap();
        enable_strip(&path).unwrap();let after=fs::read(&path).unwrap();
        let start=|b:&[u8]|u32::from_be_bytes(b[..4].try_into().unwrap()) as usize+8;
        assert_eq!(&before[start(&before)..],&after[start(&after)..]);
        assert!(super::super::strict::validate(&path).is_ok());
    }
}
