//! Observation harness. It records incompatibility rather than silently fixing
//! input or redefining the success criteria to match the candidate.
use mdx::builder::{BuilderConfig, DataLoader, SourceType, ZDBBuilder};
use mdx::builder::mdict_source_loader::MDictSourceLoader;
use mdx::readers::zdb_reader::ZdbReader;
use serde_json::{json, Value};
use std::{env, fs::{self, File}, io::BufReader, path::Path, process};
use studio_engine_probe::{Entry, Fixture, Result, stage_directory, verify_entries};

fn observe(action: impl FnOnce() -> Result<Value>) -> Value {
    // These are tiny synthetic inputs. This does not make upstream parsing safe
    // for arbitrary files; it only keeps an unwinding panic visible in a report.
    match std::panic::catch_unwind(std::panic::AssertUnwindSafe(action)) {
        Ok(Ok(result)) => json!({"execution":"completed", "result":result}),
        Ok(Err(error)) => json!({"execution":"error", "error":error.to_string()}),
        Err(_) => json!({"execution":"panic", "error":"upstream unwound on synthetic input"}),
    }
}

fn classic_mdx_read(path: &Path, fixture: &Fixture) -> Result<Value> {
    let mut file = ZdbReader::<BufReader<File>>::from_file(path, "", "")?;
    let mut entries = Vec::new();
    for n in 0..file.get_entry_count() {
        let key = file.get_index(i64::try_from(n)?)?;
        let bytes = file.get_data(&key, false)?;
        entries.push(Entry { key:key.key, text:String::from_utf8(bytes)? });
    }
    verify_entries(&fixture.engine_entries, &entries)?;
    Ok(json!({"passed":true, "records":entries.len(), "duplicate_payloads_preserved":true}))
}

fn classic_mdx_lookup(path: &Path, fixture: &Fixture) -> Result<Value> {
    let mut file = ZdbReader::<BufReader<File>>::from_file(path, "", "")?;
    let mut failures = Vec::new();
    for entry in &fixture.engine_entries {
        match file.find_first_match(&entry.key, false, false, true)? {
            Some(found) if found.key == entry.key => {
                let body = String::from_utf8(file.get_data(&found, false)?)?;
                if !fixture.engine_entries.iter().any(|e| e.key == found.key && e.text == body) {
                    failures.push(json!({"key":entry.key,"reason":"wrong payload"}));
                }
            }
            Some(found) => failures.push(json!({"key":entry.key,"reason":"different spelling returned","found":found.key})),
            None => failures.push(json!({"key":entry.key,"reason":"not found"})),
        }
    }
    Ok(json!({"passed":failures.is_empty(),"failures":failures,"scope":"one exact spelling/payload per query; not global duplicate lookup equivalence"}))
}

fn classic_mdd_read(path: &Path, fixture: &Fixture) -> Result<Value> {
    let mut file = ZdbReader::<BufReader<File>>::from_file(path, "", "")?;
    let mut got = Vec::new();
    for n in 0..file.get_entry_count() {
        let key = file.get_index(i64::try_from(n)?)?;
        got.push((key.key.clone(), file.get_data(&key, false)?));
    }
    let mut expected: Vec<_> = fixture.engine_resources.iter().map(|r| (r.key.clone(),r.bytes.clone())).collect();
    got.sort(); expected.sort();
    Ok(json!({"passed":got==expected, "resources":got.len()}))
}

fn main() {
    if let Err(error) = run() { eprintln!("ERROR: {error}"); process::exit(1); }
}

fn run() -> Result<()> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.len()!=1 { return Err("Usage: studio-safari-probe NEW_OUTPUT_DIRECTORY".into()); }
    let report = stage_directory(Path::new(&args[0]), |stage| {
        let fixture: Fixture = serde_json::from_str(include_str!("../../../baseline/cases.json"))?;
        let classic = stage.join("classic-v2");
        fs::create_dir(&classic)?;
        studio_engine_probe::prove(&fixture, &classic)?;
        let mdx = classic.join("qualification.mdx");
        let mdd = classic.join("qualification.mdd");
        let mut results = serde_json::Map::new();
        results.insert("read_classic_v2_mdx".into(), observe(|| classic_mdx_read(&mdx,&fixture)));
        results.insert("lookup_classic_v2_mdx".into(), observe(|| classic_mdx_lookup(&mdx,&fixture)));
        results.insert("read_classic_v2_mdd".into(), observe(|| classic_mdd_read(&mdd,&fixture)));
        results.insert("published_writer_header".into(), observe(|| {
            let config = BuilderConfig::default();
            let mut builder = ZDBBuilder::new(&config);
            let mut bytes = Vec::new();
            builder.build_db_header(&mut bytes)?;
            if bytes.len()<8 { return Err("header unexpectedly short".into()); }
            let length=u32::from_be_bytes(bytes[..4].try_into()?) as usize;
            let payload=bytes.get(4..4+length).ok_or("truncated written header")?;
            let xml=String::from_utf8(payload.to_vec())?;
            Ok(json!({"generated_version":builder.db_header.generated_by_engine_version,
                "required_version":builder.db_header.required_engine_version,
                "declares_v2":builder.db_header.required_engine_version=="2.0","encoding":"UTF-8 header payload", "raw_header":xml}))
        }));
        results.insert("mb_sort_key_valid_big5_pair".into(), observe(|| {
            let input=vec![0xa4,0x40]; // valid Big5 pair
            let got=mdx::utils::sort_key::mb_get_sort_key(&input,false,false,"big5")?;
            Ok(json!({"identity_when_no_transforms":got==input,"input":input,"actual":got}))
        }));
        results.insert("source_delimiter_payload".into(), observe(|| {
            let input=stage.join("single.txt");
            fs::write(&input,"word\n<p>body</p>\n</>\n")?;
            let (mut loader,records)=MDictSourceLoader::new(input.to_str().ok_or("non-UTF8 path")?,None)?;
            let record=records.first().ok_or("loader produced no entry")?;
            let payload=String::from_utf8(loader.load_data(record)?)?;
            Ok(json!({"records":records.len(),"payload":payload,"delimiter_removed":!payload.contains("</>")}))
        }));
        results.insert("source_blank_line_semantics".into(), observe(|| {
            let input=stage.join("blank-lines.txt");
            fs::write(&input,"word\nline1\n\nline2\n</>\n")?;
            let (mut loader,records)=MDictSourceLoader::new(input.to_str().ok_or("non-UTF8 path")?,None)?;
            let keys:Vec<_>=records.iter().map(|r|r.key.clone()).collect();
            let payload=records.first().map(|r|loader.load_data(r)).transpose()?;
            Ok(json!({"keys":keys,"preserves_one_entry_with_blank_body_line":records.len()==1 && payload.as_deref()==Some(b"line1\n\nline2\n".as_slice())}))
        }));
        results.insert("full_builder_container".into(), observe(|| {
            let input=stage.join("builder-input.txt");
            let output=stage.join("safari-output.zdb");
            fs::write(&input,"word\n<p>body</p>\n</>\n")?;
            let config=BuilderConfig {input_path:input.display().to_string(),output_file:output.display().to_string(),
                data_source_format:SourceType::MdictHtml,..Default::default()};
            ZDBBuilder::build_with_config(&config,None)?;
            let own=ZdbReader::<BufReader<File>>::from_file(&output,"","")?;
            let compatible=mdictlib::MdxFile::open(&output).is_ok();
            Ok(json!({"own_reader_version":format!("{:?}",own.meta.version),"classic_v2_reader_accepts":compatible,
                "note":"Rejection by mdictlib alone does not prove other readers reject ZDB v3"}))
        }));
        let report=json!({"engine":"Safari77/mdx","version":"0.5.4","commit":"085d2a77fed2fc43a9a8e58c91bdb3be8aac4880",
            "status":"observations_only","decision":"not_selected_as_classic_v2_writer","checks":results,
            "not_proven":["external_readers","all_legacy_encodings","all_duplicate_lookup_semantics","large_files","cross_platform","mdx_util_build"]});
        fs::write(stage.join("safari-report.json"),serde_json::to_vec_pretty(&report)?)?;
        Ok(report)
    })?;
    println!("{}",serde_json::to_string_pretty(&report)?);
    Ok(())
}
