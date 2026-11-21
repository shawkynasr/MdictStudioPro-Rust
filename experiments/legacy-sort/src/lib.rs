//! Isolated qualification of a local engine patch. Not a production engine choice.
pub mod codec;
pub mod readers;
use mdictlib::{LegacySort, MddBuilder, MddFile, MdxBuilder, MdxFile, WriteOptions};
use serde_json::{json, Value};
use std::{collections::BTreeMap, fs, path::Path};
use studio_engine_probe::{stage_directory, Result};

const CASES: &str = include_str!("../../../baseline/cases.json");
const ORACLE: &str = include_str!("../../../baseline/expected/sort-C-locale.json");

fn options(profile: Option<LegacySort>) -> WriteOptions {
    let value = WriteOptions::new().with_key_block_target_bytes(48).with_record_block_target_bytes(32);
    match profile { Some(profile) => value.with_legacy_sort(profile), None => value }
}

fn check(condition: bool, message: &str) -> Result<()> {
    if condition { Ok(()) } else { Err(message.to_string().into()) }
}

fn check_header_framing(path: &Path) -> Result<()> {
    let data = fs::read(path)?;
    let prefix: [u8; 4] = data.get(..4).ok_or("missing header length")?.try_into()?;
    let length = u32::from_be_bytes(prefix) as usize;
    let header = data.get(4..4+length).ok_or("truncated XML header")?;
    check(header.len() >= 2 && header.len() % 2 == 0 && header.ends_with(&[0,0]), "UTF-16LE header lacks terminator")?;
    let stored = u32::from_le_bytes(data.get(4+length..8+length).ok_or("missing header checksum")?.try_into()?);
    // Independent ADLER32 calculation verifies the terminator is included.
    let (mut a, mut b) = (1u32, 0u32);
    for &byte in header { a = (a + u32::from(byte)) % 65521; b = (b+a) % 65521; }
    check(stored == ((b << 16) | a), "Header length/checksum does not include the correct payload")
}

/// Write one dictionary using tiny blocks, assert physical order and exact bodies.
fn mdx_case(path: &Path, keys: &[String], profile: Option<LegacySort>) -> Result<(Vec<String>, u64)> {
    let mut builder = MdxBuilder::with_options(options(profile));
    builder.header_attribute("Title", "Experimental sort qualification")?;
    for (i, key) in keys.iter().enumerate() {
        builder.add_entry(key, &format!("<p>record-{i}: {key}</p>"))?;
    }
    let summary = builder.finish(fs::File::create(path)?)?;
    check_header_framing(path)?;
    check(summary.key_blocks > 1 && summary.record_blocks > 1, "MDX fixture did not cross block boundaries")?;
    let file = MdxFile::open(path)?;
    check(!file.header().key_case_sensitive() && !file.header().strip_key(), "Patch changed header semantics")?;
    let mut order = Vec::new();
    for key in file.keys() { order.push(key?.key().to_string()); }
    for key in keys {
        let matches = file.locate(key)?.ok_or("exact MDX lookup missing")?;
        let mut got = Vec::new();
        for ordinal in matches.iter() {
            got.push(file.entry_at(ordinal)?.ok_or("missing MDX ordinal")?.text().to_string());
        }
        let expected: Vec<String> = keys.iter().enumerate().filter(|(_, k)| *k == key).map(|(i, k)| format!("<p>record-{i}: {k}</p>")).collect();
        check(got == expected, "Exact MDX lookup lost duplicate payloads or stable tie order")?;
    }
    Ok((order, summary.key_blocks))
}

fn mdd_case(path: &Path, keys: &[String], profile: Option<LegacySort>) -> Result<(Vec<String>, u64)> {
    let mut builder = MddBuilder::with_options(options(profile));
    for (i, key) in keys.iter().enumerate() {
        let body = [vec![0, 255, 128, i as u8], vec![42; 40]].concat();
        builder.add_resource(key, &body)?;
    }
    let summary = builder.finish(fs::File::create(path)?)?;
    check_header_framing(path)?;
    check(summary.key_blocks > 1 && summary.record_blocks > 1, "MDD fixture did not cross block boundaries")?;
    let file = MddFile::open(path)?;
    let mut order = Vec::new();
    for key in file.keys() { order.push(key?.key().to_string()); }
    for key in keys {
        let matches = file.locate(key)?.ok_or("exact MDD lookup missing")?;
        let mut got = Vec::new();
        for ordinal in matches.iter() {
            got.push(file.resource_at(ordinal)?.ok_or("missing MDD ordinal")?.bytes().to_vec());
        }
        let expected: Vec<Vec<u8>> = keys.iter().enumerate().filter(|(_, k)| *k == key).map(|(i, _)| [vec![0, 255, 128, i as u8], vec![42; 40]].concat()).collect();
        check(got == expected, "Exact MDD lookup lost binary payloads or duplicates")?;
    }
    Ok((order, summary.key_blocks))
}

/// Execute four independent physical-order comparisons plus lookup invariants.
pub fn prove(output: &Path) -> Result<Value> {
    stage_directory(output, |stage| {
        let cases: Value = serde_json::from_str(CASES)?;
        let oracle: BTreeMap<String, Vec<String>> = serde_json::from_str(ORACLE)?;
        let keys: Vec<String> = serde_json::from_value(cases["sort_keys"].clone())?;
        let original: Value = serde_json::from_str(include_str!("../../../docs/evidence/macos-user-run/report.json"))?;
        let mut checks = BTreeMap::new();
        // Verify that the optional patch leaves upstream defaults byte-order
        // compatible with the user's prior report (not byte-identical files).
        let (order, _) = mdx_case(&stage.join("default.mdx"), &keys, None)?;
        check(json!(order) == original["sort_probe"]["mdx_physical_order"], "Upstream default MDX ordering changed")?;
        let (order, _) = mdd_case(&stage.join("default.mdd"), &keys, None)?;
        check(json!(order) == original["sort_probe"]["mdd_physical_order"], "Upstream default MDD ordering changed")?;
        for (label, profile) in [("mdict-utils", LegacySort::MdictUtilsC), ("mdxbuilder", LegacySort::MdxBuilderC)] {
            let (mdx_order, mdx_blocks) = mdx_case(&stage.join(format!("{label}.mdx")), &keys, Some(profile))?;
            let (mdd_order, mdd_blocks) = mdd_case(&stage.join(format!("{label}.mdd")), &keys, Some(profile))?;
            for (kind, order, blocks) in [("mdx", mdx_order, mdx_blocks), ("mdd", mdd_order, mdd_blocks)] {
                let name = format!("{label}:{kind}");
                check(order == oracle[&name], &format!("{name}: physical order differs from Python oracle"))?;
                checks.insert(name, json!({"physical_order_matches":true, "exact_lookups_pass":true, "key_blocks":blocks, "physical_order":order}));
            }
            let duplicates: Vec<String> = ["Apple", "apple", "APPLE", "apple", "a-b", "ab", "a b"].iter().map(|s| s.to_string()).collect();
            let file = stage.join(format!("{label}-duplicates.mdx"));
            mdx_case(&file, &duplicates, Some(profile))?;
            mdd_case(&stage.join(format!("{label}-duplicates.mdd")), &duplicates, Some(profile))?;
            let opened = MdxFile::open(file)?;
            // Physical compatibility must not silently change the reader's
            // Unicode fallback. Header StripKey=No remains authoritative.
            let variants = opened.locate("aPpLe")?.ok_or("case fallback missing")?;
            let mut got = Vec::new();
            for ordinal in variants.iter() { got.push(opened.entry_at(ordinal)?.ok_or("missing fallback ordinal")?.text().to_string()); }
            check(got == vec!["<p>record-0: Apple</p>", "<p>record-1: apple</p>", "<p>record-2: APPLE</p>", "<p>record-3: apple</p>"], "Case fallback did not retain all distinct spellings/duplicates")?;
            check(opened.locate("a?b")?.is_none(), "Physical sort leaked into StripKey=No lookup policy")?;
        }
        let report = json!({
            "engine":"mdictlib", "version":"0.2.8", "patch":format!("studio-legacy-sort-header-experiment-v{}", codec::patch_revision()),
            "writer_patch_revision":codec::patch_revision(),
            "status":"experimental_sort_subset_passed", "decision":"candidate_only",
            "profiles":checks, "upstream_default_order_unchanged":true,
            "duplicate_ties_and_multiblock_exact_lookups":true,
            "header_and_reader_normalization_unchanged":true,
            "utf16le_header_terminator_length_and_checksum_checked":true,
            "not_proven":["non_C_locale", "all_Unicode_lowercase_equivalence", "external_readers", "legacy_python_binary_interop", "all_key_summary_invariants", "large_files", "production_performance"]
        });
        fs::write(stage.join("sort-report.json"), serde_json::to_vec_pretty(&report)?)?;
        Ok(report)
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn all_four_profiles_match_legacy_oracles_across_blocks() {
        let root = tempfile::tempdir().unwrap();
        prove(&root.path().join("proof")).unwrap();
    }

    #[test]
    fn optional_patch_keeps_original_synthetic_proof_passing() {
        let fixture: studio_engine_probe::Fixture = serde_json::from_str(CASES).unwrap();
        let root = tempfile::tempdir().unwrap();
        studio_engine_probe::prove(&fixture, root.path()).unwrap();
    }
}
