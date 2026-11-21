//! Qualification only: storage encodings and metadata, using the proven v2 patch.
use mdictlib::{LegacySort, MddBuilder, MddFile, MdxBuilder, MdxFile, WriteEncoding, WriteOptions};
use serde_json::{json, Map, Value};
use std::{collections::BTreeMap, fs, path::Path};
use studio_engine_probe::{read_mdd, read_mdx, stage_directory, verify_entries, Entry, Resource, Result};

fn encoding(name: &str) -> Result<WriteEncoding> {
    match name {
        "Utf8" => Ok(WriteEncoding::Utf8), "Utf16Le" => Ok(WriteEncoding::Utf16Le),
        "Big5" => Ok(WriteEncoding::Big5), "Gbk" => Ok(WriteEncoding::Gbk),
        "Gb18030" => Ok(WriteEncoding::Gb18030), _ => Err(format!("Unknown fixture encoding: {name}").into()),
    }
}

/// Identify the candidate by its explicit wire-label change, never by lockfile.
pub fn patch_revision() -> u32 {
    if WriteEncoding::Utf16Le.label() != "UTF-16" { return 2; }
    let mut bytes=Vec::new();
    if MdxBuilder::new().finish(&mut bytes).is_ok() {
        let marker:Vec<u8>="Encrypted=\"No\"".encode_utf16().flat_map(u16::to_le_bytes).collect();
        if bytes.windows(marker.len()).any(|part|part==marker.as_slice()) {return 4;}
    }
    3
}

fn field<'a>(value: &'a Value, key: &str) -> Result<&'a str> {
    value[key].as_str().ok_or_else(||format!("Missing string: {key}").into())
}

fn metadata(header: &mdictlib::Header) -> BTreeMap<String,String> {
    header.attributes().map(|(k,v)|(k.to_string(),v.to_string())).collect()
}

fn check_metadata(header: &mdictlib::Header, expected: &BTreeMap<String,String>) -> Result<()> {
    for (key,value) in expected {
        if header.attribute(key) != Some(value.as_str()) {
            return Err(format!("Metadata mismatch {key}: expected={value:?}; actual={:?}", header.attribute(key)).into());
        }
    }
    Ok(())
}

/// Read records and metadata without transforming returned strings or bytes.
pub fn inspect(path: &Path) -> Result<Value> {
    if path.extension().and_then(|s|s.to_str()).is_some_and(|s|s.eq_ignore_ascii_case("mdd")) {
        let file=MddFile::open(path)?;
        Ok(json!({"kind":"mdd","attributes":metadata(file.header()),"resources":read_mdd(path)?}))
    } else {
        let file=MdxFile::open(path)?;
        Ok(json!({"kind":"mdx","attributes":metadata(file.header()),"entries":read_mdx(path)?}))
    }
}

fn observe(action: impl FnOnce()->Result<Value>) -> Value {
    match action() { Ok(detail)=>json!({"status":"passed","detail":detail}), Err(e)=>json!({"status":"failed","error":e.to_string()}) }
}

/// Write a report even if an individual metadata/codec assertion fails.
pub fn prove(output: &Path) -> Result<Value> {
    stage_directory(output,|stage|{
        let fixture:Value=serde_json::from_str(include_str!("../../../baseline/codec-cases.json"))?;
        let expected_meta:BTreeMap<String,String>=serde_json::from_value(fixture["metadata"].clone())?;
        let mut checks=Map::new();
        for case in fixture["encodings"].as_array().ok_or("Missing encoding cases")? {
            let id=field(case,"id")?;
            let enc=encoding(field(case,"rust")?)?;
            let entries:Vec<Entry>=serde_json::from_value(case["entries"].clone())?;
            for (style,sort) in [("mdict-utils",LegacySort::MdictUtilsC),("mdxbuilder",LegacySort::MdxBuilderC)] {
                let key=format!("{id}-{style}");
                let path=stage.join(format!("{key}.mdx"));
                checks.insert(key.clone(),observe(||{
                    let options=WriteOptions::new().with_encoding(enc).with_legacy_sort(sort)
                        .with_key_block_target_bytes(40).with_record_block_target_bytes(48);
                    let mut builder=MdxBuilder::with_options(options);
                    for (name,value) in &expected_meta { builder.header_attribute(name,value)?; }
                    for entry in &entries { builder.add_entry(&entry.key,&entry.text)?; }
                    let summary=builder.finish(fs::File::create(&path)?)?;
                    let file=MdxFile::open(&path)?;
                    verify_entries(&entries,&read_mdx(&path)?)?;
                    if file.header().encoding_label()!=Some(enc.label()) {
                        return Err("Declared storage encoding differs from fixture".into());
                    }
                    if summary.key_blocks<2 { return Err("Codec fixture did not cross key-block boundaries".into()); }
                    for entry in &entries {
                        let found=file.locate(&entry.key)?.ok_or("Exact codec lookup missing")?;
                        let mut actual=Vec::new();
                        for ordinal in found.iter() { actual.push(file.entry_at(ordinal)?.ok_or("Missing codec ordinal")?.text().to_string()); }
                        let mut expected:Vec<_>=entries.iter().filter(|e|e.key==entry.key).map(|e|e.text.clone()).collect();
                        actual.sort();expected.sort();
                        if actual!=expected { return Err("Exact codec lookup lost duplicate payloads".into()); }
                    }
                    Ok(json!({"records":entries.len(),"key_blocks":summary.key_blocks,"encoding":file.header().encoding_label(),"attributes":metadata(file.header())}))
                }));
                checks.insert(format!("{key}-metadata"),observe(||{
                    let file=MdxFile::open(&path)?;
                    check_metadata(file.header(),&expected_meta)?;
                    Ok(json!({"attributes":metadata(file.header())}))
                }));
            }
        }
        for case in fixture["negative_entries"].as_array().ok_or("Missing negative cases")? {
            let id=field(case,"id")?.to_string();
            checks.insert(id,observe(||{
                let mut builder=MdxBuilder::with_options(WriteOptions::new().with_encoding(encoding(field(case,"encoding")?)?));
                match builder.add_entry(field(case,"key")?,field(case,"text")?) {
                    Err(error)=>Ok(json!({"rejected":true,"error":error.to_string()})),
                    Ok(_)=>Err("Invalid/unrepresentable fixture was accepted".into()),
                }
            }));
        }
        checks.insert("reserved-metadata".into(),observe(||{
            for name in ["Encoding","KeyCaseSensitive","StripKey","GeneratedByEngineVersion","RequiredEngineVersion","Encrypted"] {
                if MdxBuilder::new().header_attribute(name,"unexpected").is_ok() { return Err(format!("Reserved header accepted: {name}").into()); }
            }
            let mut builder=MdxBuilder::new();
            builder.header_attribute("Title","one")?;
            if builder.header_attribute("Title","two").is_ok() { return Err("Duplicate metadata accepted".into()); }
            Ok(json!({"reserved_and_duplicate_attributes_rejected":true}))
        }));
        checks.insert("mdd-unicode-resources".into(),observe(||{
            let resources:Vec<Resource>=serde_json::from_value(fixture["resources"].clone())?;
            let expected:BTreeMap<String,String>=serde_json::from_value(fixture["mdd_metadata"].clone())?;
            let path=stage.join("unicode-resources.mdd");
            let mut builder=MddBuilder::with_options(WriteOptions::new().with_key_block_target_bytes(40));
            for (name,value) in &expected {builder.header_attribute(name,value)?;}
            for resource in &resources {builder.add_resource(&resource.key,&resource.bytes)?;}
            let summary=builder.finish(fs::File::create(&path)?)?;
            let file=MddFile::open(&path)?;
            check_metadata(file.header(),&expected)?;
            let mut got:Vec<_>=read_mdd(&path)?.into_iter().map(|r|(r.key,r.bytes)).collect();
            let mut want:Vec<_>=resources.iter().map(|r|(r.key.clone(),r.bytes.clone())).collect();
            got.sort();want.sort();
            if got!=want {return Err("Unicode resource keys/binary bytes changed".into());}
            Ok(json!({"resources":resources.len(),"key_blocks":summary.key_blocks,"attributes":metadata(file.header())}))
        }));
        let passed=checks.values().all(|v|v["status"]=="passed");
        let report=json!({"status":if passed {"passed"} else {"failed"},"suite":"metadata-storage-codecs-v1","writer_patch_revision":patch_revision(),
            "checks":checks,"not_proven":["native_readers","all_codepoint_mapping_equivalence","source_file_decoding","large_files","non_C_locale"]});
        fs::write(stage.join("rust-codec-report.json"),serde_json::to_vec_pretty(&report)?)?;
        Ok(report)
    })
}
