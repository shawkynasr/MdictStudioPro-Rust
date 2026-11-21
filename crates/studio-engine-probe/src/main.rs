use std::{env, fs, path::Path, process};
use studio_engine_probe::*;

fn main() {
    if let Err(error) = run() { eprintln!("ERROR: {error}"); process::exit(1); }
}

fn run() -> Result<()> {
    let args: Vec<String> = env::args().skip(1).collect();
    match args.iter().map(String::as_str).collect::<Vec<_>>().as_slice() {
        ["prove", fixture, output] => {
            let fixture: Fixture = serde_json::from_slice(&fs::read(fixture)?)?;
            let report = stage_directory(Path::new(output), |stage| prove(&fixture, stage))?;
            println!("{}", serde_json::to_string_pretty(&report)?);
        }
        ["pack", source, output] => {
            let entries = parse_source(&fs::read_to_string(source)?)?;
            stage_directory(Path::new(output), |stage| {
                let path = stage.join("dictionary.mdx");
                write_mdx(&path, &entries)?;
                verify_entries(&entries, &read_mdx(&path)?)
            })?;
        }
        ["unpack", source, output] => {
            if Path::new(source).extension().and_then(|x| x.to_str()).is_some_and(|x| x.eq_ignore_ascii_case("mdd")) {
                extract_mdd(Path::new(source), Path::new(output))?;
            } else {
                let text = source_text(&read_mdx(Path::new(source))?)?;
                stage_directory(Path::new(output), |stage| { fs::write(stage.join("dictionary.txt"), text)?; Ok(()) })?;
            }
        }
        ["lookup", source, word] => {
            let file = mdictlib::MdxFile::open(source)?;
            let mut found = Vec::new();
            if let Some(matches) = file.locate(word)? {
                for ordinal in matches.iter() {
                    let entry = file.entry_at(ordinal)?.ok_or("missing ordinal")?;
                    found.push(serde_json::json!({"ordinal": ordinal.get(), "text": entry.text()}));
                }
            }
            println!("{}", serde_json::to_string_pretty(&found)?);
        }
        ["dump-json", source] => {
            let path = Path::new(source);
            let data = if path.extension().and_then(|x| x.to_str()).is_some_and(|x| x.eq_ignore_ascii_case("mdd")) {
                serde_json::json!({"kind":"mdd", "resources":read_mdd(path)?})
            } else {
                serde_json::json!({"kind":"mdx", "entries":read_mdx(path)?})
            };
            println!("{}", serde_json::to_string_pretty(&data)?);
        }
        ["inspect", source] => {
            let path = Path::new(source);
            let report = if path.extension().and_then(|x| x.to_str()).is_some_and(|x| x.eq_ignore_ascii_case("mdd")) {
                let file = mdictlib::MddFile::open(path)?;
                serde_json::json!({"kind":"mdd", "records":file.len()})
            } else {
                let file = mdictlib::MdxFile::open(path)?;
                serde_json::json!({"kind":"mdx", "records":file.len(), "title":file.header().title()})
            };
            println!("{}", serde_json::to_string_pretty(&report)?);
        }
        _ => return Err("Usage: studio-engine-probe prove FIXTURE.json NEW_DIR | pack SOURCE.txt NEW_DIR | unpack DICT.mdx/mdd NEW_DIR | lookup DICT.mdx WORD | inspect DICT.mdx/mdd | dump-json DICT.mdx/mdd".into()),
    }
    Ok(())
}
