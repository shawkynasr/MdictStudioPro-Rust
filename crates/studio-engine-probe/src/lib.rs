//! Deliberately small engine qualification adapter. Not production packing code.
use mdictlib::{KeyOrdinal, MddBuilder, MddFile, MdxBuilder, MdxFile, WriteCompression, WriteEncoding, WriteOptions};
use serde::{Deserialize, Serialize};
use std::{collections::BTreeMap, fs, io, path::{Component, Path, PathBuf}};

pub type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub struct Entry {
    pub key: String,
    pub text: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Resource {
    pub key: String,
    pub bytes: Vec<u8>,
}

#[derive(Deserialize)]
pub struct Fixture {
    pub engine_entries: Vec<Entry>,
    pub engine_resources: Vec<Resource>,
}

fn require(condition: bool, message: &str) -> Result<()> {
    if condition { Ok(()) } else { Err(io::Error::other(message).into()) }
}

/// Strict UTF-8 source grammar for the probe: key, body, standalone </>.
/// CRLF is normalized. Blank body lines are retained. No inferred final record.
pub fn parse_source(text: &str) -> Result<Vec<Entry>> {
    let normalized = text.trim_start_matches('\u{feff}').replace("\r\n", "\n");
    let mut lines: Vec<&str> = Vec::new();
    let mut entries = Vec::new();
    for line in normalized.split_terminator('\n') {
        if line == "</>" {
            require(lines.len() >= 2 && !lines[0].is_empty(), "record requires nonempty key and body line")?;
            entries.push(Entry { key: lines[0].to_string(), text: lines[1..].join("\n") });
            lines.clear();
        } else {
            lines.push(line);
        }
    }
    require(lines.is_empty(), "unterminated source record")?;
    require(!entries.is_empty(), "empty source")?;
    Ok(entries)
}

pub fn source_text(entries: &[Entry]) -> Result<String> {
    let mut out = String::new();
    for e in entries {
        require(!e.key.is_empty() && !e.key.contains(['\r', '\n', '\0']) && e.key != "</>", "key cannot be represented in TXT")?;
        require(!e.text.split('\n').any(|line| line == "</>"), "body contains reserved TXT delimiter")?;
        out.push_str(&format!("{}\n{}\n</>\n", e.key, e.text));
    }
    Ok(out)
}

pub fn write_mdx(path: &Path, entries: &[Entry]) -> Result<()> {
    let mut builder = MdxBuilder::with_options(WriteOptions::new()
        .with_encoding(WriteEncoding::Utf8)
        .with_compression(WriteCompression::Zlib));
    builder.header_attribute("Title", "Mdict Studio engine qualification")?;
    builder.header_attribute("Description", "Synthetic UTF-8 round-trip fixture")?;
    for e in entries { builder.add_entry(&e.key, &e.text)?; }
    let mut output = fs::File::create(path)?;
    builder.finish(&mut output)?;
    output.sync_all()?;
    Ok(())
}

pub fn read_mdx(path: &Path) -> Result<Vec<Entry>> {
    let file = MdxFile::open(path)?;
    let mut entries = Vec::new();
    for key in file.keys() {
        let key = key?;
        let body = file.entry_at(key.ordinal())?.ok_or("missing physical entry")?;
        entries.push(Entry { key: key.key().to_string(), text: body.text().to_string() });
    }
    Ok(entries)
}

pub fn write_mdd(path: &Path, resources: &[Resource]) -> Result<()> {
    let mut builder = MddBuilder::with_options(WriteOptions::new().with_compression(WriteCompression::Zlib));
    for r in resources { builder.add_resource(&r.key, &r.bytes)?; }
    let mut output = fs::File::create(path)?;
    builder.finish(&mut output)?;
    output.sync_all()?;
    Ok(())
}

pub fn read_mdd(path: &Path) -> Result<Vec<Resource>> {
    let file = MddFile::open(path)?;
    let mut resources = Vec::new();
    for key in file.keys() {
        let key = key?;
        let resource = file.resource_at(key.ordinal())?.ok_or("missing physical resource")?;
        resources.push(Resource { key: key.key().to_string(), bytes: resource.bytes().to_vec() });
    }
    Ok(resources)
}

fn entry_counts(entries: &[Entry]) -> BTreeMap<(String, String), usize> {
    let mut counts = BTreeMap::new();
    for e in entries { *counts.entry((e.key.clone(), e.text.clone())).or_insert(0) += 1; }
    counts
}

pub fn verify_entries(expected: &[Entry], actual: &[Entry]) -> Result<()> {
    require(entry_counts(expected) == entry_counts(actual), "MDX key/body multiset mismatch (including duplicates)")
}

/// This is a resource archive path, not an OS filename supplied by the user.
pub fn safe_resource_path(key: &str) -> Result<PathBuf> {
    require(!key.starts_with("\\\\") && !key.starts_with("//"), "UNC resource path refused")?;
    let normalized = key.replace('\\', "/");
    let relative = normalized.trim_start_matches('/');
    require(!relative.is_empty() && !relative.contains([':', '\0']), "invalid resource path")?;
    require(!relative.split('/').any(|s| s == ".." || s == "." || s.is_empty()), "resource traversal or ambiguous path")?;
    let path = PathBuf::from(relative);
    require(path.components().all(|c| matches!(c, Component::Normal(_))), "non-relative resource path")?;
    Ok(path)
}

/// New directory only. Publish after success; never merge into existing directories.
pub fn stage_directory<T>(destination: &Path, action: impl FnOnce(&Path) -> Result<T>) -> Result<T> {
    require(!destination.exists(), "destination exists; choose a new directory")?;
    let parent = destination.parent().filter(|p| !p.as_os_str().is_empty()).unwrap_or(Path::new("."));
    require(parent.is_dir(), "destination parent must exist")?;
    let stage = tempfile::Builder::new().prefix(".studio-probe-").tempdir_in(parent)?;
    let value = action(stage.path())?;
    // Single-user qualification CLI. Production needs platform-specific no-replace publication.
    require(!destination.exists(), "destination appeared during operation")?;
    fs::rename(stage.path(), destination)?;
    Ok(value)
}

pub fn extract_mdd(source: &Path, destination: &Path) -> Result<()> {
    stage_directory(destination, |stage| {
        for r in read_mdd(source)? {
            let path = stage.join(safe_resource_path(&r.key)?);
            if let Some(parent) = path.parent() { fs::create_dir_all(parent)?; }
            let mut file = fs::OpenOptions::new().create_new(true).write(true).open(path)?;
            use std::io::Write;
            file.write_all(&r.bytes)?;
        }
        Ok(())
    })
}

pub fn prove(fixture: &Fixture, stage: &Path) -> Result<serde_json::Value> {
    let mdx = stage.join("qualification.mdx");
    let mdd = stage.join("qualification.mdd");
    write_mdx(&mdx, &fixture.engine_entries)?;
    verify_entries(&fixture.engine_entries, &read_mdx(&mdx)?)?;
    let file = MdxFile::open(&mdx)?;
    require(file.header().title() == Some("Mdict Studio engine qualification"), "title mismatch")?;
    // Exact queries and duplicate payloads, not merely a positive lookup.
    for e in &fixture.engine_entries {
        let matches = file.locate(&e.key)?.ok_or("exact key missing")?;
        let mut actual = Vec::new();
        for ordinal in matches.iter() {
            let found = file.entry_at(ordinal)?.ok_or("lookup ordinal missing")?;
            actual.push(found.text().to_string());
        }
        let mut expected: Vec<String> = fixture.engine_entries.iter().filter(|v| v.key == e.key).map(|v| v.text.clone()).collect();
        expected.sort(); actual.sort();
        require(expected == actual, "exact lookup returned wrong duplicate bodies or normalization collision")?;
    }
    require(file.entry_at(KeyOrdinal::new(u64::MAX))?.is_none(), "out-of-range ordinal accepted")?;
    write_mdd(&mdd, &fixture.engine_resources)?;
    let mut actual: Vec<_> = read_mdd(&mdd)?.into_iter().map(|v| (v.key, v.bytes)).collect();
    let mut expected: Vec<_> = fixture.engine_resources.iter().map(|v| (v.key.clone(), v.bytes.clone())).collect();
    actual.sort(); expected.sort();
    require(expected == actual, "MDD resource keys or binary bytes changed")?;
    let mdd_file = MddFile::open(&mdd)?;
    for r in &fixture.engine_resources {
        let found = mdd_file.lookup(&r.key)?.ok_or("resource lookup failed")?;
        require(found.bytes() == r.bytes.as_slice(), "resource lookup bytes mismatch")?;
    }
    let recovered = read_mdx(&mdx)?;
    let txt = source_text(&recovered)?;
    verify_entries(&fixture.engine_entries, &parse_source(&txt)?)?;
    fs::write(stage.join("qualification.txt"), txt)?;
    extract_mdd(&mdd, &stage.join("resources"))?;
    for r in &fixture.engine_resources {
        require(fs::read(stage.join("resources").join(safe_resource_path(&r.key)?))? == r.bytes, "extracted resource differs")?;
    }
    fs::write(stage.join("invalid.mdx"), b"not an mdx")?;
    require(MdxFile::open(stage.join("invalid.mdx")) .is_err(), "invalid MDX accepted")?;
    fs::write(stage.join("truncated.mdd"), &fs::read(&mdd)?[..8])?;
    require(MddFile::open(stage.join("truncated.mdd")).is_err(), "truncated MDD accepted")?;
    let all_cases: serde_json::Value = serde_json::from_str(include_str!("../../../baseline/cases.json"))?;
    let sort_keys: Vec<String> = serde_json::from_value(all_cases["sort_keys"].clone())?;
    let legacy_sorts: serde_json::Value = serde_json::from_str(include_str!("../../../baseline/expected/sort-C-locale.json"))?;
    let sort_entries: Vec<Entry> = sort_keys.iter().map(|key| Entry { key: key.clone(), text: "sort fixture".into() }).collect();
    let sort_resources: Vec<Resource> = sort_keys.iter().map(|key| Resource { key: key.clone(), bytes: vec![0, 255] }).collect();
    write_mdx(&stage.join("sort.mdx"), &sort_entries)?;
    write_mdd(&stage.join("sort.mdd"), &sort_resources)?;
    let mdx_order: Vec<String> = read_mdx(&stage.join("sort.mdx"))?.into_iter().map(|v| v.key).collect();
    let mdd_order: Vec<String> = read_mdd(&stage.join("sort.mdd"))?.into_iter().map(|v| v.key).collect();
    let mut sort_matches = serde_json::Map::new();
    for style in ["mdxbuilder", "mdict-utils"] {
        for (kind, order) in [("mdx", &mdx_order), ("mdd", &mdd_order)] {
            let key = format!("{style}:{kind}");
            sort_matches.insert(key.clone(), serde_json::json!(legacy_sorts[&key] == serde_json::json!(order)));
        }
    }
    let report = serde_json::json!({
        "engine": "mdictlib", "version": "0.2.8", "status": "synthetic_subset_passed",
        "entries": recovered.len(), "resources": actual.len(),
        "checks": ["utf8_zlib_mdx_roundtrip", "exact_duplicate_lookup", "title", "unicode", "redirect_body_preserved", "utf8_txt_roundtrip", "mdd_binary_roundtrip", "mdd_lookup", "resource_extraction", "invalid_mdx", "truncated_mdd"],
        "not_proven": ["reader_app_compatibility", "legacy_python_interop", "both_legacy_sort_profiles", "description_and_stylesheet_preservation", "legacy_encodings", "lzo_input", "encryption", "large_files", "multiblock_boundaries", "redirect_resolution", "production_resource_limits"],
        "decision": "candidate_only"
    });
    let mut report = report;
    report["sort_probe"] = serde_json::json!({"mdx_physical_order":mdx_order, "mdd_physical_order":mdd_order, "matches_legacy_C_locale":sort_matches, "note":"This compares the engine default against both oracles; it does not implement selectable sort profiles. A false result is a migration blocker, not waived."});
    fs::write(stage.join("report.json"), serde_json::to_vec_pretty(&report)?)?;
    Ok(report)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn source_grammar_preserves_duplicates_and_blank_body_lines() {
        let entries = parse_source("\u{feff}a\r\none\r\n\r\ntwo\r\n</>\r\na\r\n@@@LINK=和\r\n</>\r\n").unwrap();
        assert_eq!(entries[0].text, "one\n\ntwo");
        assert_eq!(entries[1].key, "a");
        assert_eq!(parse_source(&source_text(&entries).unwrap()).unwrap(), entries);
    }

    #[test]
    fn source_grammar_rejects_incomplete_or_unrepresentable_records() {
        for text in ["", "a\nbody", "a\n</>\n", "\nbody\n</>\n"] { assert!(parse_source(text).is_err()); }
        assert!(source_text(&[Entry { key: "a\nb".into(), text: "body".into() }]).is_err());
        assert!(source_text(&[Entry { key: "a".into(), text: "x\n</>\ny".into() }]).is_err());
    }

    #[test]
    fn resource_paths_reject_escape_and_aliases() {
        for key in ["../x", "\\..\\x", "C:\\x", "//server/x", "\\\\server\\x", "a/./b", "a//b", "a/../b", "", "/"] {
            assert!(safe_resource_path(key).is_err(), "{key}");
        }
        assert_eq!(safe_resource_path("\\images\\字.png").unwrap(), PathBuf::from("images/字.png"));
    }

    #[test]
    fn failed_stage_leaves_no_destination_and_refuses_overwrite() {
        let dir = tempfile::tempdir().unwrap();
        let dest = dir.path().join("out");
        assert!(stage_directory(&dest, |p| -> Result<()> { fs::write(p.join("partial"), b"x")?; Err("cancelled".into()) }).is_err());
        assert!(!dest.exists());
        fs::create_dir(&dest).unwrap();
        assert!(stage_directory(&dest, |_| Ok(())).is_err());
    }

    #[test]
    fn synthetic_engine_qualification() {
        let fixture: Fixture = serde_json::from_str(include_str!("../../../baseline/cases.json")).unwrap();
        let dir = tempfile::tempdir().unwrap();
        prove(&fixture, dir.path()).unwrap();
    }
}
