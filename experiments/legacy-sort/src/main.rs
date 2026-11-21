use std::{env, fs, path::Path, process};
use studio_engine_probe::{Fixture, Result, stage_directory};

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    if let [command,path]=args.iter().map(String::as_str).collect::<Vec<_>>().as_slice() {
        if *command=="dump-rows" {
            if let Err(error)=studio_legacy_sort_experiment::readers::rows(Path::new(path)) {eprintln!("ERROR: {error}");process::exit(1);}
            return;
        }
    }
    let result: Result<serde_json::Value> = match args.iter().map(String::as_str).collect::<Vec<_>>().as_slice() {
        [output] => studio_legacy_sort_experiment::prove(Path::new(output)),
        ["baseline", fixture, output] => (|| {
            let fixture: Fixture = serde_json::from_slice(&fs::read(fixture)?)?;
            stage_directory(Path::new(output), |stage| studio_engine_probe::prove(&fixture, stage))
        })(),
        ["codec",output] => studio_legacy_sort_experiment::codec::prove(Path::new(output)),
        ["inspect-json",path] => studio_legacy_sort_experiment::codec::inspect(Path::new(path)),
        ["reader-fixtures",spec,output] => studio_legacy_sort_experiment::readers::fixtures(Path::new(spec),Path::new(output)),
        ["lookup-json",path,key] => studio_legacy_sort_experiment::readers::lookup(Path::new(path),key),
        _ => Err("Usage: studio-legacy-sort-experiment NEW_OUTPUT_DIRECTORY | baseline CASES.json NEW_OUTPUT_DIRECTORY | codec NEW_OUTPUT_DIRECTORY | inspect-json DICTIONARY | reader-fixtures SPEC.json NEW_OUTPUT_DIRECTORY | dump-rows DICTIONARY | lookup-json DICTIONARY KEY".into()),
    };
    match result {
        Ok(report) => println!("{}", serde_json::to_string_pretty(&report).unwrap()),
        Err(error) => { eprintln!("ERROR: {error}"); process::exit(1); }
    }
}
