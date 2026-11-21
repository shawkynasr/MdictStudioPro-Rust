use serde::Deserialize;
use std::{env,fs::File,io::Read,path::PathBuf,process::ExitCode};
use studio_v2_import::{Dictionary,ResourceArchive,LookupPolicy,Limits,ImportJob,CancellationToken};
#[derive(Deserialize)]
#[serde(rename_all="snake_case")]
enum Kind {Mdx,Mdd}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    kind:Kind,path:PathBuf,policy:Option<LookupPolicy>,queries:Vec<String>,resolve:Vec<String>,
    max_hops:Option<usize>,max_results:Option<usize>,max_entries:Option<usize>,
}
fn run()->Result<serde_json::Value,Box<dyn std::error::Error>> {
    let args:Vec<_>=env::args_os().skip(1).collect();if args.len()!=1 {return Err("Usage: studio-v2-import REQUEST.json".into());}
    let file=File::open(&args[0])?;if !file.metadata()?.is_file() {return Err("Expected regular request JSON".into());}
    let mut data=Vec::new();file.take(65537).read_to_end(&mut data)?;if data.len()>65536 {return Err("Request exceeds 64 KiB".into());}
    let req:Request=serde_json::from_slice(&data)?;if req.queries.len()+req.resolve.len()>64 {return Err("Request exceeds 64 queries".into());}
    let mut limits=Limits::default();
    if let Some(n)=req.max_hops {if n>64 {return Err("At most 64 redirect hops".into());}limits.redirects.max_hops=n;}
    if let Some(n)=req.max_results {limits.dictionary.max_result_entries=n.min(limits.dictionary.max_result_entries);}
    if let Some(n)=req.max_entries {limits.dictionary.max_entries=n.min(limits.dictionary.max_entries);}
    let token=CancellationToken::default();let mut progress=|p|eprintln!("{}",serde_json::to_string(&p).expect("Progress JSON"));
    let mut job=ImportJob::new("v2-import-cli",&token,&mut progress);
    Ok(match req.kind {
        Kind::Mdx=>{
            let policy=req.policy.ok_or("MDX request must explicitly select raw_exact or header_ascii_v1")?;
            let dict=Dictionary::open_v2(&req.path,policy,&limits,&mut job)?;
            let queries:Vec<_>=req.queries.iter().map(|q|match dict.lookup(q,&mut job) {Ok(rows)=>serde_json::json!({"query":q,"entries":rows}),Err(e)=>serde_json::json!({"query":q,"error":e})}).collect();
            let resolved:Vec<_>=req.resolve.iter().map(|q|match dict.resolve(q,&mut job) {Ok(rows)=>serde_json::json!({"query":q,"results":rows}),Err(e)=>serde_json::json!({"query":q,"error":e})}).collect();
            serde_json::json!({"header":dict.header(),"policy":dict.policy().id(),"entries":dict.entries(),"queries":queries,"resolutions":resolved})
        },
        Kind::Mdd=>{
            if req.policy.is_some()||!req.resolve.is_empty() {return Err("MDD lookup is raw-exact and does not resolve redirects".into());}
            let archive=ResourceArchive::open_v2(&req.path,&limits,&mut job)?;
            let queries:Vec<_>=req.queries.iter().map(|q|match archive.lookup(q,&mut job) {Ok(rows)=>serde_json::json!({"query":q,"resources":rows}),Err(e)=>serde_json::json!({"query":q,"error":e})}).collect();
            serde_json::json!({"header":archive.header(),"policy":"resource-raw-exact-v1","resources":archive.resources(),"queries":queries})
        },
    })
}
fn main()->ExitCode {match run() {Ok(value)=>{println!("{value}");ExitCode::SUCCESS},Err(e)=>{
    let value=if let Some(e)=e.downcast_ref::<studio_v2_import::Error>() {serde_json::json!({"status":"failed","error":e})}else{serde_json::json!({"status":"failed","error":{"code":"invalid_input","detail":"request","message":e.to_string()}})};
    eprintln!("{value}");ExitCode::FAILURE
}}}
