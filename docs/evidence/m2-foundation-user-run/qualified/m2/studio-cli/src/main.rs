use std::{env, fs, io::{self, Read}, path::Path, process::ExitCode};
use serde_json::{json, Value};
use studio_core::{pack_mdx, CancellationToken, Dictionary, Encoding, Entry, JobContext, Limits, PackRequest, Progress};

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
fn invalid(message: &str) -> io::Error { io::Error::new(io::ErrorKind::InvalidInput, message) }
fn pack(request: &PackRequest, path: &Path) -> Result<Value> {
    let token = CancellationToken::default();
    let mut sink = |progress: Progress| eprintln!("{}", json!({"event":"progress","progress":progress}));
    Ok(serde_json::to_value(pack_mdx(request, path, &Limits::default(), &mut JobContext::new(&token, &mut sink))?)?)
}
fn lookup(path: &Path, query: &str) -> Result<Value> {
    let token = CancellationToken::default(); let mut sink = |_| {};
    let dictionary = Dictionary::open_studio_output(path, &Limits::default(), &mut JobContext::new(&token, &mut sink))?;
    Ok(json!({"title":dictionary.title(),"entries":dictionary.len(),"query":query,"rows":dictionary.lookup(query,&token)?}))
}
fn smoke(out: &Path) -> Result<Value> {
    fs::create_dir(out)?; let mut cases = Vec::new();
    for (name, encoding) in [("utf8", Encoding::Utf8), ("utf16", Encoding::Utf16)] {
        let mut entries = vec![
            Entry {key:"ΟΣ".into(),text:"SIGMA_ONE\n\nlast\n".into()},
            Entry {key:"ος".into(),text:"SIGMA_OTHER".into()},
            Entry {key:"ΟΣ".into(),text:"SIGMA_TWO".into()},
            Entry {key:"مرحبا".into(),text:"<b dir=\"rtl\">أهلاً</b>".into()},
            Entry {key:"字".into(),text:"Chinese 字".into()},
            Entry {key:"A꟎Σ".into(),text:"PINNED16".into()},
            Entry {key:"empty".into(),text:String::new()},
        ];
        for index in 1..=8 { entries.push(Entry { key:"duplicate".into(),text:format!("DUP_{index:02}") }); }
        let request = PackRequest { title:"Studio M2 قاموس 字".into(),description:"Core API smoke".into(),encoding,entries };
        let path = out.join(format!("studio-core-{name}.mdx"));
        let summary = pack(&request,&path)?;
        let mut checks = Vec::new();
        for (query, expected) in [("ΟΣ",2), ("Ος",3), ("duplicate",8), ("مرحبا",1), ("字",1), ("a꟏Σ",0), ("missing",0)] {
            let result = lookup(&path,query)?;
            if result["rows"].as_array().ok_or_else(||invalid("Invalid lookup rows"))?.len() != expected {
                return Err(invalid("Core lookup smoke mismatch").into());
            }
            checks.push(result);
        }
        cases.push(json!({"file":path,"encoding":name,"summary":summary,
            "expected_entries":request.entries,"checks":checks}));
    }
    Ok(json!({"status":"core_foundation_smoke_passed","cases":cases,
        "scope":"bounded Studio MDX API only; M2 remains partial"}))
}
fn execute() -> Result<Value> {
    let args: Vec<_> = env::args_os().skip(1).collect();
    match args.first().and_then(|s|s.to_str()) {
        Some("pack") if args.len()==3 => {
            let mut bytes = Vec::new();
            fs::File::open(&args[1])?.take(16*1024*1024+1).read_to_end(&mut bytes)?;
            if bytes.len()>16*1024*1024 { return Err(invalid("Pack request exceeds 16 MiB").into()); }
            let request: PackRequest = serde_json::from_slice(&bytes)?;
            pack(&request,Path::new(&args[2]))
        }
        Some("lookup") if args.len()==3 => lookup(Path::new(&args[1]), args[2].to_str().ok_or_else(||invalid("Query must be UTF-8"))?),
        Some("smoke") if args.len()==2 => smoke(Path::new(&args[1])),
        _ => Err(invalid("Usage: studio-cli pack REQUEST.json OUTPUT.mdx | lookup FILE.mdx QUERY | smoke NEW_DIRECTORY").into()),
    }
}
fn main() -> ExitCode {
    match execute() {
        Ok(result) => { println!("{result}"); ExitCode::SUCCESS }
        Err(error) => {
            if let Some(core) = error.downcast_ref::<studio_core::Error>() {
                eprintln!("{}", json!({"status":"failed","error":core}));
            } else { eprintln!("{}", json!({"status":"failed","error":{"code":"cli","message":error.to_string()}})); }
            ExitCode::FAILURE
        }
    }
}
