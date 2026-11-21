//! Qualification rebuild of unencrypted v2 UTF-8 MDX / UTF-16-key MDD.
//! Preserve source XML bytes and physical order; no new sort/metadata policy.
mod stress;
use mdictlib::{LegacySort,MdxBuilder,MddBuilder,MdxFile,MddFile,WriteOptions,WriteEncoding};
use studio_engine_probe::{Result,stage_directory};
use std::{env,fs::{self,File,OpenOptions},io::{self,Read,Write,Seek,SeekFrom},path::Path};

fn attributes(header:&mdictlib::Header)->std::collections::BTreeMap<String,String> {
    header.attributes().map(|(k,v)|(k.to_owned(),v.to_owned())).collect()
}

fn prefix(file:&mut File)->Result<Vec<u8>> {
    file.seek(SeekFrom::Start(0))?;
    let mut length=[0u8;4]; file.read_exact(&mut length)?;
    let size=u32::from_be_bytes(length) as usize;
    if !(2..=1024*1024).contains(&size) || size%2!=0 { return Err("Invalid bounded v2 header".into()); }
    let mut bytes=vec![0u8;size+8];bytes[..4].copy_from_slice(&length);
    file.read_exact(&mut bytes[4..])?;Ok(bytes)
}

fn budget(count:u64,bytes:&mut u64,key:&str,size:usize)->Result<()> {
    let amount=key.len().checked_add(size).ok_or("Decoded size overflow")?;
    *bytes=bytes.checked_add(amount as u64).ok_or("Decoded size overflow")?;
    if count>500_000 || *bytes>256*1024*1024 { return Err("Qualification budget exceeded: 500k records / 256 MiB decoded key+payload bytes".into()); }
    Ok(())
}

fn rebuild(source:&Path,output:&Path)->Result<serde_json::Value> {
    let is_mdd=source.extension().and_then(|x|x.to_str()).is_some_and(|x|x.eq_ignore_ascii_case("mdd"));
    if !is_mdd && !source.extension().and_then(|x|x.to_str()).is_some_and(|x|x.eq_ignore_ascii_case("mdx")) {
        return Err("Expected MDX or MDD".into());
    }
    if fs::metadata(source)?.len()>32*1024*1024 { return Err("Qualification input limit is 32 MiB per file".into()); }
    let original_header=prefix(&mut File::open(source)?)?;
    // Source order avoids inventing a comparator for case-variant header names.
    let options=WriteOptions::new().with_encoding(WriteEncoding::Utf8).with_legacy_sort(LegacySort::PreserveInput);
    stage_directory(output,|stage|{
        let mut encoded=tempfile::tempfile()?;let mut count=0u64;let mut decoded_bytes=0u64;
        let attrs=if is_mdd {
            let file=MddFile::open(source)?;
            attributes(file.header())
        } else {
            let file=MdxFile::open(source)?;
            attributes(file.header())
        };
        if attrs.get("GeneratedByEngineVersion").map(String::as_str)!=Some("2.0") { return Err("Only version 2 qualification inputs are supported".into()); }
        if !["No","no","0", ""].contains(&attrs.get("Encrypted").map(String::as_str).unwrap_or("No")) {
            return Err("Encrypted rebuild inputs are outside this qualification preset".into());
        }
        if !is_mdd && !attrs.get("Encoding").is_some_and(|x|x.eq_ignore_ascii_case("UTF-8")) {
            return Err("This preset rebuilds UTF-8 MDX only; metadata must match encoded bodies".into());
        }
        if is_mdd {
            let file=MddFile::open(source)?;let mut builder=MddBuilder::with_options(options);
            for key in file.keys() {
                let key=key?;let resource=file.resource_at(key.ordinal())?.ok_or("Missing source resource")?;
                count+=1;budget(count,&mut decoded_bytes,key.key(),resource.bytes().len())?;
                builder.add_resource(key.key(),resource.bytes())?;
            }
            builder.finish(&mut encoded)?;
        } else {
            let file=MdxFile::open(source)?;let mut builder=MdxBuilder::with_options(options);
            for key in file.keys() {
                let key=key?;let entry=file.entry_at(key.ordinal())?.ok_or("Missing source entry")?;
                count+=1;budget(count,&mut decoded_bytes,key.key(),entry.text().len())?;
                builder.add_entry(key.key(),entry.text())?;
            }
            builder.finish(&mut encoded)?;
        }
        // Reuse the complete source header prefix, not a reserialized attribute map.
        // This is valid only for the gated same-version/encoding/unencrypted preset.
        let new_header=prefix(&mut encoded)?;
        encoded.seek(SeekFrom::Start(new_header.len() as u64))?;
        let result_name=if is_mdd {"rebuilt.mdd"} else {"rebuilt.mdx"};
        let mut destination=OpenOptions::new().write(true).create_new(true).open(stage.join(result_name))?;
        destination.write_all(&original_header)?;io::copy(&mut encoded,&mut destination)?;destination.sync_all()?;
        Ok(serde_json::json!({"status":"rebuilt_not_qualified","file":result_name,"records":count,"decoded_bytes":decoded_bytes,
            "metadata_policy":"source_header_prefix_reused_exactly","ordering":"source_physical_order_preserved",
            "limits":"32 MiB input; 500000 records; 256 MiB decoded key+payload; in-memory builder remains a limitation"}))
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn qualification_budget_boundaries_are_explicit() {
        let mut bytes=256*1024*1024-1;assert!(budget(500_000,&mut bytes,"",1).is_ok());
        assert!(budget(500_000,&mut bytes,"",1).is_err());
        assert!(budget(500_001,&mut 0,"",0).is_err());
        assert!(budget(1,&mut 0,"x",usize::MAX).is_err());
    }
    #[test]
    fn preserve_input_and_header_across_a_real_rebuild() {
        let temp=tempfile::tempdir().unwrap();let source=temp.path().join("source.mdx");
        let mut builder=MdxBuilder::with_options(WriteOptions::new().with_legacy_sort(LegacySort::PreserveInput));
        builder.header_attribute("Title","Keep this exact").unwrap();
        builder.header_attribute("FixtureTag","Exact metadata").unwrap();
        for (key,text) in [("z","z\n"),("a-b","dash"),("ab","plain"),("a-b","second duplicate")] { builder.add_entry(key,text).unwrap(); }
        builder.finish(File::create(&source).unwrap()).unwrap();
        let output=temp.path().join("result");rebuild(&source,&output).unwrap();
        let rebuilt=output.join("rebuilt.mdx");
        assert_eq!(prefix(&mut File::open(&source).unwrap()).unwrap(),prefix(&mut File::open(&rebuilt).unwrap()).unwrap());
        let file=MdxFile::open(rebuilt).unwrap();let mut rows=Vec::new();
        for key in file.keys() { let key=key.unwrap();rows.push((key.key().to_owned(),file.entry_at(key.ordinal()).unwrap().unwrap().text().to_owned())); }
        let expected:Vec<(String,String)>=[("z","z\n"),("a-b","dash"),("ab","plain"),("a-b","second duplicate")]
            .into_iter().map(|(key,text)|(key.to_owned(),text.to_owned())).collect();
        assert_eq!(rows,expected);
        assert!(rebuild(&source,&output).is_err());
    }
}

fn main() {
    let args:Vec<String>=env::args().skip(1).collect();
    let result=match args.iter().map(String::as_str).collect::<Vec<_>>().as_slice() {
        ["stress-build",spec,out]=>stress::build(Path::new(spec),Path::new(out)),
        ["stress-verify",spec,out]=>stress::verify(Path::new(spec),Path::new(out)),
        ["stress-inspect",path]=>stress::inspect(Path::new(path)),
        ["stress-fail-write",out]=>stress::fail_write(Path::new(out)),
        ["stress-hold",out,ready]=>stress::hold(Path::new(out),Path::new(ready)),
        [source,output]=>rebuild(Path::new(source),Path::new(output)),
        _=>Err("Usage: studio-real-rebuild SOURCE NEW_OUTPUT_DIRECTORY | stress-build SPEC NEW_OUT | stress-verify SPEC OUT | stress-inspect MDX | stress-fail-write NEW_OUT | stress-hold NEW_OUT READY".into()) };
    match result { Ok(value)=>println!("{}",serde_json::to_string_pretty(&value).unwrap()), Err(e)=>{eprintln!("ERROR: {e}");std::process::exit(1);} }
}
