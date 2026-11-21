//! Fresh UTF-8/LF TXT packing. XLSX conversion is still the Python oracle.
use mdictlib::{LegacySort,MdxBuilder,MddBuilder,MdxFile,MddFile,WriteOptions};
use serde_json::{json,Value};
use std::{fs,path::Path};
use studio_engine_probe::{Entry,Resource,Result,stage_directory};

/// Legacy LF fixture contract: keep the line ending before the delimiter.
/// Bounded deliberately; no guessed records, BOM or CR normalization.
fn parse(text:&str)->Result<Vec<Entry>> {
    if text.contains(['\r','\0']) || text.starts_with('\u{feff}') {return Err("This fresh-source preset requires UTF-8 without BOM and LF line endings".into());}
    let mut entries=Vec::new();let mut key:Option<String>=None;let mut body=String::new();
    for raw in text.split_inclusive('\n') {
        let line=raw.strip_suffix('\n').unwrap_or(raw);
        if let Some(head)=key.as_ref() {
            if line=="</>" {
                if body.is_empty() {return Err("Empty source body".into());}
                entries.push(Entry{key:head.clone(),text:std::mem::take(&mut body)});key=None;
            } else {body.push_str(raw);}
        } else {
            if line.is_empty() || line=="</>" {return Err("Invalid source key".into());}
            key=Some(line.to_owned());
        }
    }
    if key.is_some() || entries.is_empty() {return Err("Empty or incomplete source".into());}
    Ok(entries)
}

pub fn build(spec:&Path,out:&Path)->Result<Value> {
    if fs::metadata(spec)?.len()>1024*1024 {return Err("Fresh spec limit is 1 MiB".into());}
    let spec:Value=serde_json::from_slice(&fs::read(spec)?)?;
    let source=Path::new(spec["source"].as_str().ok_or("Missing source")?);
    if fs::metadata(source)?.len()>8*1024*1024 {return Err("Fresh TXT limit is 8 MiB".into());}
    let entries=parse(&fs::read_to_string(source)?)?;
    let resources:Vec<Resource>=serde_json::from_value(spec["resources"].clone())?;
    let sort=match spec["profile"].as_str() {Some("mdict-utils")=>LegacySort::MdictUtilsC,Some("mdxbuilder")=>LegacySort::MdxBuilderC,_=>return Err("Unsupported profile".into())};
    let title=spec["title"].as_str().ok_or("Missing title")?;
    let description=spec["description"].as_str().ok_or("Missing description")?;
    let mut bytes=0;for (i,e) in entries.iter().enumerate(){super::budget((i+1) as u64,&mut bytes,&e.key,e.text.len())?;}
    for (i,r) in resources.iter().enumerate(){super::budget((i+1) as u64,&mut bytes,&r.key,r.bytes.len())?;}
    stage_directory(out,|stage|{
        let options=WriteOptions::new().with_legacy_sort(sort).with_key_block_target_bytes(64).with_record_block_target_bytes(128);
        let mut builder=MdxBuilder::with_options(options);
        builder.header_attribute("Title",title)?;builder.header_attribute("Description",description)?;
        for e in &entries {builder.add_entry(&e.key,&e.text)?;}
        let path=stage.join("fresh.mdx");builder.finish(fs::File::create(&path)?)?;super::strict::validate(&path)?;
        let file=MdxFile::open_with_options(&path,&super::strict::options())?;let mut rows=Vec::new();
        for key in file.keys(){let key=key?;let e=file.entry_at(key.ordinal())?.ok_or("Missing entry")?;rows.push(json!({"key":key.key(),"text":e.text()}));}
        let mut result=json!({"status":"fresh_built_strictly_validated_not_qualified","rows":rows,"attributes":super::attributes(file.header()),"source_contract":"UTF8 LF; final body LF retained","profile":spec["profile"]});
        if !resources.is_empty(){
            let mut builder=MddBuilder::with_options(WriteOptions::new().with_legacy_sort(sort).with_key_block_target_bytes(64).with_record_block_target_bytes(128));
            builder.header_attribute("Title",title)?;builder.header_attribute("Description",description)?;
            for r in &resources{builder.add_resource(&r.key,&r.bytes)?;}
            let path=stage.join("fresh.mdd");builder.finish(fs::File::create(&path)?)?;super::strict::validate(&path)?;
            let file=MddFile::open_with_options(&path,&super::strict::options())?;let mut rows=Vec::new();
            for key in file.keys(){let key=key?;let r=file.resource_at(key.ordinal())?.ok_or("Missing resource")?;rows.push(json!({"key":key.key(),"bytes":r.bytes()}));}
            result["mdd"]=json!({"rows":rows,"attributes":super::attributes(file.header())});
        }
        Ok(result)
    })
}

/// Exact reverse-direction rows, with Verify on every lazy key/payload access.
pub fn inspect(path:&Path)->Result<Value>{
    if fs::metadata(path)?.len()>16*1024*1024{return Err("Fresh inspection limit is 16 MiB".into());}
    let mut rows=Vec::new();
    let attrs=if path.extension().and_then(|x|x.to_str())==Some("mdd"){
        let file=MddFile::open_with_options(path,&super::strict::options())?;
        for key in file.keys(){let key=key?;let r=file.resource_at(key.ordinal())?.ok_or("Missing inspected resource")?;rows.push(json!({"key":key.key(),"bytes":r.bytes()}));}
        super::attributes(file.header())
    }else{
        let file=MdxFile::open_with_options(path,&super::strict::options())?;
        for key in file.keys(){let key=key?;let e=file.entry_at(key.ordinal())?.ok_or("Missing inspected entry")?;rows.push(json!({"key":key.key(),"text":e.text()}));}
        super::attributes(file.header())
    };
    Ok(json!({"rows":rows,"attributes":attrs,"checksum_policy":"Verify"}))
}

#[cfg(test)]
mod tests{
    use super::*;
    #[test]
    fn legacy_body_lf_duplicates_and_incomplete_source(){
        let e=parse("a\none\n\ntwo\n</>\na\n@@@LINK=和\n</>\n").unwrap();
        assert_eq!(e[0].text,"one\n\ntwo\n");assert_eq!(e[0].key,e[1].key);assert_eq!(e[1].text,"@@@LINK=和\n");
        for bad in ["","a\nbody","a\n</>\n","a\r\nbody\r\n</>\r\n","\u{feff}a\nb\n</>\n"] {assert!(parse(bad).is_err());}
    }
}
