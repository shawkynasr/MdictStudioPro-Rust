//! Native-reader fixtures and read-only streaming corpus inspection.
use mdictlib::{LegacySort,MdxBuilder,MddBuilder,MdxFile,MddFile,WriteOptions,WriteEncoding};
use serde_json::{json,Value};
use std::{fs,io::{self,Write},path::Path};
use studio_engine_probe::{Entry,Resource,Result,stage_directory,read_mdx,verify_entries};

fn attributes(header:&mdictlib::Header)->Value {
    serde_json::to_value(header.attributes().map(|(k,v)|(k.to_owned(),v.to_owned())).collect::<std::collections::BTreeMap<_,_>>()).unwrap()
}

pub fn fixtures(spec:&Path,output:&Path)->Result<Value> {
    let spec:Value=serde_json::from_slice(&fs::read(spec)?)?;
    let entries:Vec<Entry>=serde_json::from_value(spec["entries"].clone())?;
    let resources:Vec<Resource>=serde_json::from_value(spec["resources"].clone())?;
    stage_directory(output,|stage|{
        let mut files=Vec::new();
        for (enc_label,enc) in [("utf8",WriteEncoding::Utf8),("utf16",WriteEncoding::Utf16Le)] {
            for (profile,sort) in [("mdict-utils",LegacySort::MdictUtilsC),("mdxbuilder",LegacySort::MdxBuilderC)] {
                let name=format!("reader-{enc_label}-{profile}");
                let path=stage.join(format!("{name}.mdx"));
                let options=WriteOptions::new().with_encoding(enc).with_legacy_sort(sort)
                    .with_key_block_target_bytes(64).with_record_block_target_bytes(128);
                let mut builder=MdxBuilder::with_options(options);
                builder.header_attribute("Title",&name)?;
                builder.header_attribute("Description","Synthetic native-reader stylesheet qualification")?;
                for (k,v) in spec["metadata"].as_object().ok_or("Missing fixture metadata")? {
                    builder.header_attribute(k,v.as_str().ok_or("Non-string metadata")?)?;
                }
                for entry in &entries {builder.add_entry(&entry.key,&entry.text)?;}
                builder.finish(fs::File::create(&path)?)?;
                verify_entries(&entries,&read_mdx(&path)?)?;
                let mut builder=MddBuilder::with_options(WriteOptions::new().with_legacy_sort(sort));
                if crate::codec::patch_revision()>=4 {
                    builder.header_attribute("Title",&name)?;
                    for (key,value) in [("Description","Synthetic native-reader resources"),("Format",""),("Compact","No"),("Compat","No"),("CreationDate","2026-10-28"),("RegisterBy",""),("StyleSheet","")] {
                        builder.header_attribute(key,value)?;
                    }
                }
                for resource in &resources {builder.add_resource(&resource.key,&resource.bytes)?;}
                builder.finish(fs::File::create(stage.join(format!("{name}.mdd")))?)?;
                files.push(name);
            }
        }
        Ok(json!({"status":"fixtures_written_not_native_verified","files":files,"writer_patch_revision":crate::codec::patch_revision()}))
    })
}

fn emit(out:&mut impl Write,value:Value)->Result<()> {
    serde_json::to_writer(&mut *out,&value)?;out.write_all(b"\n")?;Ok(())
}

/// One JSON record at a time; never collect a real dictionary into a Vec.
pub fn rows(path:&Path)->Result<()> {
    let mut out=io::BufWriter::new(io::stdout().lock());
    let mut count=0u64;
    if path.extension().and_then(|s|s.to_str()).is_some_and(|s|s.eq_ignore_ascii_case("mdd")) {
        let file=MddFile::open(path)?;
        emit(&mut out,json!({"type":"header","kind":"mdd","attributes":attributes(file.header())}))?;
        for key in file.keys() {
            let key=key?;
            let value=file.resource_at(key.ordinal())?.ok_or("Missing resource ordinal")?;
            emit(&mut out,json!({"type":"row","key":key.key(),"bytes":value.bytes()}))?;
            count+=1;
        }
    } else {
        let file=MdxFile::open(path)?;
        emit(&mut out,json!({"type":"header","kind":"mdx","attributes":attributes(file.header())}))?;
        for key in file.keys() {
            let key=key?;
            let value=file.entry_at(key.ordinal())?.ok_or("Missing entry ordinal")?;
            emit(&mut out,json!({"type":"row","key":key.key(),"text":value.text()}))?;
            count+=1;
        }
    }
    emit(&mut out,json!({"type":"end","records":count}))?;
    out.flush()?;Ok(())
}

pub fn lookup(path:&Path,key:&str)->Result<Value> {
    let mut rows=Vec::new();
    if path.extension().and_then(|s|s.to_str()).is_some_and(|s|s.eq_ignore_ascii_case("mdd")) {
        let file=MddFile::open(path)?;
        if let Some(found)=file.locate(key)? {
            for n in found.iter() {let v=file.resource_at(n)?.ok_or("Missing lookup resource")?;rows.push(json!({"key":key,"bytes":v.bytes()}));}
        }
    } else {
        let file=MdxFile::open(path)?;
        if let Some(found)=file.locate(key)? {
            for n in found.iter() {let v=file.entry_at(n)?.ok_or("Missing lookup entry")?;rows.push(json!({"key":key,"text":v.text()}));}
        }
    }
    Ok(json!({"rows":rows}))
}
