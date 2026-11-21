use std::{env, fs, io::{self, Read}, path::Path, process::ExitCode};
use serde_json::{json, Value};
use studio_core::{pack_mdx, CancellationToken, Dictionary, Encoding, Entry, JobContext, Limits, PackRequest, Progress};
use studio_core::{pack_mdd,ResourceArchive,ResourcePackRequest,Resource};
use studio_core::{TxtProfile,read_txt,write_txt,convert_cedict_file,cedict_pinyin};

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
fn mdd_pack(request:&ResourcePackRequest,path:&Path)->Result<Value> {
    let token=CancellationToken::default();
    let mut sink=|progress:Progress|eprintln!("{}",json!({"event":"progress","progress":progress}));
    Ok(serde_json::to_value(pack_mdd(request,path,&Limits::default(),&mut JobContext::new(&token,&mut sink))?)?)
}
fn resource(path:&Path,key:&str)->Result<Value> {
    let token=CancellationToken::default(); let mut sink=|_|{};
    let archive=ResourceArchive::open_studio_output(path,&Limits::default(),&mut JobContext::new(&token,&mut sink))?;
    Ok(json!({"title":archive.title(),"resources":archive.len(),"query":key,"resource":archive.resource(key,&token)?}))
}
fn extract(path:&Path,destination:&Path)->Result<Value> {
    let token=CancellationToken::default();
    let mut sink=|progress:Progress|eprintln!("{}",json!({"event":"progress","progress":progress}));
    let archive=ResourceArchive::open_studio_output(path,&Limits::default(),&mut JobContext::new(&token,&mut sink))?;
    Ok(serde_json::to_value(archive.extract(destination,&mut JobContext::new(&token,&mut sink))?)?)
}
fn mdd_smoke(out:&Path)->Result<Value> {
    fs::create_dir(out)?;
    let input=ResourcePackRequest {title:"Studio M2 resources قاموس 字".into(),description:"MDD core smoke".into(),resources:vec![
        Resource {key:"\\styles\\probe.css".into(),bytes:b"@font-face{font-family:Probe;src:url('../fonts/probe.ttf')}\np{color:blue}\n".to_vec()},
        Resource {key:"\\fonts\\probe.ttf".into(),bytes:include_bytes!("../../../baseline/resource-probe/studio-probe.ttf").to_vec()},
        Resource {key:"data/all.bin".into(),bytes:(0..=255).collect()},
        Resource {key:"data/empty.bin".into(),bytes:Vec::new()},
        Resource {key:"字/说明.txt".into(),bytes:"中文资源".as_bytes().to_vec()},
        Resource {key:"العربية/نص.txt".into(),bytes:"مرحبا بالعالم".as_bytes().to_vec()},
    ]};
    let path=out.join("studio-core-resources.mdd"); let summary=mdd_pack(&input,&path)?;
    let destination=out.join("extracted"); let extracted=extract(&path,&destination)?;
    let mut checks=Vec::new();
    for row in &input.resources {
        let actual=resource(&path,&row.key)?;
        if actual["resource"]!=serde_json::to_value(row)? { return Err(invalid("Resource bytes differ after reopen").into()); }
        checks.push(actual);
    }
    if !resource(&path,"missing.bin")?["resource"].is_null() { return Err(invalid("Missing resource unexpectedly found").into()); }
    Ok(json!({"status":"mdd_core_smoke_passed","file":path,"summary":summary,
        "extracted_directory":destination,"extraction":extracted,"expected_resources":input.resources,"checks":checks}))
}
fn text_profile(value:&std::ffi::OsStr)->Result<TxtProfile> {
    match value.to_str() {
        Some("canonical_v1")=>Ok(TxtProfile::CanonicalV1),
        Some("legacy_body_span_v1")=>Ok(TxtProfile::LegacyBodySpanV1),
        _=>Err(studio_core::Error {code:studio_core::ErrorCode::UnsupportedPolicy,message:"Expected canonical_v1 or legacy_body_span_v1 TXT profile".into()}.into()),
    }
}
fn request_json(path:&Path)->Result<Value> {
    let mut bytes=Vec::new();fs::File::open(path)?.take(16*1024*1024+1).read_to_end(&mut bytes)?;
    if bytes.len()>16*1024*1024 {return Err(invalid("JSON request exceeds 16 MiB").into());}
    Ok(serde_json::from_slice(&bytes)?)
}
fn txt_read(path:&Path,profile:TxtProfile)->Result<Value> {
    let token=CancellationToken::default();let mut sink=|_|{};
    Ok(json!({"profile":profile,"rows":read_txt(path,profile,&Limits::default(),&mut JobContext::new(&token,&mut sink))?}))
}
fn txt_write(request:&Path,path:&Path,profile:TxtProfile)->Result<Value> {
    let entries:Vec<Entry>=serde_json::from_value(request_json(request)?)?;
    let token=CancellationToken::default();let mut sink=|progress:Progress|eprintln!("{}",json!({"event":"progress","progress":progress}));
    Ok(serde_json::to_value(write_txt(&entries,path,profile,&Limits::default(),&mut JobContext::new(&token,&mut sink))?)?)
}
fn txt_pack(source:&Path,destination:&Path,profile:TxtProfile,encoding:&std::ffi::OsStr)->Result<Value> {
    let encoding=match encoding.to_str() {Some("utf8")=>Encoding::Utf8,Some("utf16")=>Encoding::Utf16,
        _=>return Err(invalid("Expected utf8 or utf16 encoding").into())};
    let token=CancellationToken::default();let mut sink=|progress:Progress|eprintln!("{}",json!({"event":"progress","progress":progress}));
    let entries=read_txt(source,profile,&Limits::default(),&mut JobContext::new(&token,&mut sink))?;
    pack(&PackRequest {title:"Studio TXT import".into(),description:"Explicit TXT source profile".into(),encoding,entries},destination)
}
fn txt_export(source:&Path,destination:&Path,profile:TxtProfile)->Result<Value> {
    let token=CancellationToken::default();let mut sink=|progress:Progress|eprintln!("{}",json!({"event":"progress","progress":progress}));
    let dictionary=Dictionary::open_studio_output(source,&Limits::default(),&mut JobContext::new(&token,&mut sink))?;
    Ok(serde_json::to_value(dictionary.export_txt(destination,profile,&mut JobContext::new(&token,&mut sink))?)?)
}
fn cedict(source:&Path,destination:&Path)->Result<Value> {
    let token=CancellationToken::default();let mut sink=|progress:Progress|eprintln!("{}",json!({"event":"progress","progress":progress}));
    let converted=convert_cedict_file(source,&Limits::default(),&mut JobContext::new(&token,&mut sink))?;
    let output=write_txt(&converted.entries,destination,converted.txt_profile,&Limits::default(),&mut JobContext::new(&token,&mut sink))?;
    Ok(json!({"entries":converted.entries.len(),"primary_entries":converted.primary_entries,
        "traditional_entries":converted.traditional_entries,"skipped_lines":converted.skipped_lines,
        "comments":converted.comments,"txt_profile":converted.txt_profile,"output":output}))
}
fn pinyin_probe(source:&Path)->Result<Value> {
    let words:Vec<String>=serde_json::from_value(request_json(source)?)?;
    if words.len()>1024 {return Err(invalid("Too many pinyin probes").into());}
    let mut results=Vec::new();for word in words {let output=cedict_pinyin(&word)?;results.push(json!({"input":word,"output":output}));}
    Ok(json!({"results":results}))
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
        Some("mdd-pack") if args.len()==3 => {
            let mut bytes=Vec::new(); fs::File::open(&args[1])?.take(16*1024*1024+1).read_to_end(&mut bytes)?;
            if bytes.len()>16*1024*1024 {return Err(invalid("Resource request exceeds 16 MiB").into());}
            mdd_pack(&serde_json::from_slice(&bytes)?,Path::new(&args[2]))
        }
        Some("resource") if args.len()==3 => resource(Path::new(&args[1]),args[2].to_str().ok_or_else(||invalid("Resource key must be UTF-8"))?),
        Some("extract") if args.len()==3 => extract(Path::new(&args[1]),Path::new(&args[2])),
        Some("mdd-smoke") if args.len()==2 => mdd_smoke(Path::new(&args[1])),
        Some("txt-read") if args.len()==3 => txt_read(Path::new(&args[1]),text_profile(&args[2])?),
        Some("txt-write") if args.len()==4 => txt_write(Path::new(&args[1]),Path::new(&args[2]),text_profile(&args[3])?),
        Some("txt-pack") if args.len()==5 => txt_pack(Path::new(&args[1]),Path::new(&args[2]),text_profile(&args[3])?,&args[4]),
        Some("txt-export") if args.len()==4 => txt_export(Path::new(&args[1]),Path::new(&args[2]),text_profile(&args[3])?),
        Some("cedict") if args.len()==3 => cedict(Path::new(&args[1]),Path::new(&args[2])),
        Some("cedict-pinyin") if args.len()==2 => pinyin_probe(Path::new(&args[1])),
        _ => Err(invalid("Usage: studio-cli pack REQUEST.json OUTPUT.mdx | lookup FILE.mdx QUERY | smoke NEW_DIRECTORY | mdd-pack REQUEST.json OUTPUT.mdd | resource FILE.mdd KEY | extract FILE.mdd NEW_DIRECTORY | mdd-smoke NEW_DIRECTORY | txt-read FILE PROFILE | txt-write ROWS.json OUTPUT PROFILE | txt-pack FILE OUTPUT.mdx PROFILE utf8/utf16 | txt-export FILE.mdx OUTPUT.txt PROFILE | cedict INPUT.u8 OUTPUT.txt | cedict-pinyin WORDS.json").into()),
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
