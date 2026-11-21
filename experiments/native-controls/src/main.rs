//! Offline minimal controls; no native applications are opened.
use mdictlib::{LegacySort, MdxBuilder, MdxFile, MddBuilder, MddFile, WriteEncoding, WriteOptions};
use serde_json::{json, Value};
use std::{env, fs, path::Path};
use studio_engine_probe::{stage_directory, Entry, Resource, Result};

/// Experimental compact-style wire serialization. Definition text is untouched.
fn stylesheet_wire(value: &str) -> Result<String> {
    let mut value = value.replace("\r\n", "\n");
    if value.contains('\r') { return Err("Bare CR in diagnostic stylesheet".into()); }
    if !value.is_empty() && !value.ends_with('\n') { value.push('\n'); }
    Ok(value)
}

fn build(spec: &Path, output: &Path) -> Result<Value> {
    let spec: Value = serde_json::from_slice(&fs::read(spec)?)?;
    stage_directory(output, |stage| {
        let mut cases = Vec::new();
        for case in spec["cases"].as_array().ok_or("Missing cases")? {
            let name = case["name"].as_str().ok_or("Missing case name")?;
            if !["01-plain", "02-punctuation", "03-multilingual", "04-stylesheet", "05-stylesheet-wire", "06-mdd-resources"].contains(&name) {
                return Err("Unexpected control name".into());
            }
            let entries: Vec<Entry> = serde_json::from_value(case["entries"].clone())?;
            let resources: Vec<Resource> = if case.get("resources").is_some() {
                serde_json::from_value(case["resources"].clone())?
            } else { Vec::new() };
            if !resources.is_empty() && name != "06-mdd-resources" {
                return Err("Resources are only allowed in the MDD control".into());
            }
            if name == "06-mdd-resources" && resources.is_empty() {
                return Err("MDD control has no resources".into());
            }
            let supplied_style = case["stylesheet"].as_str().unwrap_or("");
            let stylesheet = if name == "05-stylesheet-wire" {
                stylesheet_wire(supplied_style)?
            } else { supplied_style.to_owned() };
            if !["04-stylesheet", "05-stylesheet-wire"].contains(&name) && !stylesheet.is_empty() {
                return Err("Stylesheet is only allowed in the isolated stylesheet control".into());
            }
            for (label, encoding) in [("utf8", WriteEncoding::Utf8), ("utf16", WriteEncoding::Utf16Le)] {
                let path = stage.join(format!("{name}-{label}.mdx"));
                // Small targets force lookup and boundary checks across blocks.
                let options = WriteOptions::new().with_encoding(encoding)
                    .with_legacy_sort(LegacySort::HeaderLiteralC)
                    .with_key_block_target_bytes(32).with_record_block_target_bytes(64);
                let mut builder = MdxBuilder::with_options(options);
                for (key, value) in [("Title", name), ("Description", "Isolated plain-text lookup control"),
                    ("Format", "Html"), ("Compact", if stylesheet.is_empty() { "No" } else { "Yes" }), ("Compat", "Yes"),
                    ("CreationDate", "2026-10-28"), ("DataSourceFormat", "106"),
                    ("RegisterBy", ""), ("StyleSheet", stylesheet.as_str())] {
                    builder.header_attribute(key, value)?;
                }
                for entry in &entries { builder.add_entry(&entry.key, &entry.text)?; }
                let summary = builder.finish(fs::File::create(&path)?)?;
                let file = MdxFile::open(&path)?;
                let mut rows = Vec::new();
                for key in file.keys() {
                    let key = key?;
                    let entry = file.entry_at(key.ordinal())?.ok_or("Missing physical record")?;
                    rows.push(json!({"key": key.key(), "text": entry.text()}));
                }
                let mut lookups = Vec::new();
                for query in case["queries"].as_array().ok_or("Missing queries")? {
                    let query = query.as_str().ok_or("Invalid query")?;
                    let mut found = Vec::new();
                    if let Some(matches) = file.locate(query)? {
                        for ordinal in matches.iter() {
                            let entry = file.entry_at(ordinal)?.ok_or("Missing lookup record")?;
                            found.push(json!({"key": entry.key(), "text": entry.text()}));
                        }
                    }
                    lookups.push(json!({"query": query, "rows": found}));
                }
                let mut observation = json!({"file": path.file_name().unwrap().to_str().unwrap(),
                    "rows": rows, "lookups": lookups, "key_blocks": summary.key_blocks});
                if !resources.is_empty() {
                    let mdd_path = path.with_extension("mdd");
                    let options = WriteOptions::new().with_legacy_sort(LegacySort::HeaderLiteralC)
                        .with_key_block_target_bytes(64).with_record_block_target_bytes(128);
                    let mut builder = MddBuilder::with_options(options);
                    for (key,value) in [("Title",name),("Description","Synthetic CSS image font and binary resources"),
                        ("Format",""),("Compact","No"),("Compat","No"),("CreationDate","2026-10-28"),
                        ("RegisterBy",""),("StyleSheet","")] { builder.header_attribute(key,value)?; }
                    for resource in &resources { builder.add_resource(&resource.key, &resource.bytes)?; }
                    let summary = builder.finish(fs::File::create(&mdd_path)?)?;
                    let file = MddFile::open(&mdd_path)?;
                    let mut rows = Vec::new();
                    for key in file.keys() {
                        let key = key?;
                        let resource = file.resource_at(key.ordinal())?.ok_or("Missing physical resource")?;
                        rows.push(json!({"key":key.key(),"bytes":resource.bytes()}));
                    }
                    let mut lookups = Vec::new();
                    let mut queries: Vec<String> = resources.iter().map(|r|r.key.clone()).collect();
                    queries.push("\\missing-resource.bin".to_owned());
                    for query in queries {
                        let mut rows = Vec::new();
                        if let Some(matches) = file.locate(&query)? {
                            for ordinal in matches.iter() {
                                let resource = file.resource_at(ordinal)?.ok_or("Missing lookup resource")?;
                                rows.push(json!({"key":query,"bytes":resource.bytes()}));
                            }
                        }
                        lookups.push(json!({"query":query,"rows":rows}));
                    }
                    observation["mdd"] = json!({"file":mdd_path.file_name().unwrap().to_str().unwrap(),
                        "rows":rows,"lookups":lookups,"key_blocks":summary.key_blocks,"record_blocks":summary.record_blocks});
                }
                cases.push(observation);
            }
        }
        Ok(json!({"status": "controls_built_native_untested", "profile": "HeaderLiteralC", "cases": cases}))
    })
}

#[cfg(test)]
mod tests {
    use super::stylesheet_wire;
    #[test]
    fn compact_style_matches_reference_wire_line_endings() {
        assert_eq!(stylesheet_wire("1\r\n<span>\r\n</span>").unwrap(), "1\n<span>\n</span>\n");
        assert_eq!(stylesheet_wire("1\n<span>\n</span>\n").unwrap(), "1\n<span>\n</span>\n");
        assert_eq!(stylesheet_wire("").unwrap(), "");
        assert_eq!(stylesheet_wire("1\n<br>\n\n").unwrap(), "1\n<br>\n\n");
        assert!(stylesheet_wire("1\r<span>\r</span>").is_err());
    }
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let result = match args.as_slice() {
        [spec, output] => build(Path::new(spec), Path::new(output)),
        _ => Err("Usage: studio-native-controls SPEC.json NEW_OUTPUT_DIRECTORY".into()),
    };
    match result {
        Ok(report) => println!("{}", serde_json::to_string_pretty(&report).unwrap()),
        Err(error) => { eprintln!("ERROR: {error}"); std::process::exit(1); }
    }
}
