//! Generate a small redirect fixture through the real adapter.
//! Usage: cargo run --manifest-path m3/native-adapter/Cargo.toml --example redirect_fixture -- m3-shell-out-redirect-fixture
use serde_json::{json,Value};
use std::{fs,path::PathBuf,thread,time::{Duration,Instant}};
use studio_native_adapter::Adapter;
fn call(a:&Adapter,v:Value)->Value {a.call_json(&v.to_string()).expect("adapter command")}
fn publish(a:&Adapter,request:Value) {
    let id=call(a,json!({"action":"submit","request":request}))["job_id"].as_str().unwrap().to_owned();
    let start=Instant::now();
    loop {
        let p=call(a,json!({"action":"poll"}));let row=p["jobs"].as_array().unwrap().iter().find(|r|r["job_id"]==id).unwrap();
        match row["state"].as_str().unwrap() {
            "succeeded"=>{call(a,json!({"action":"take","job_id":id}));call(a,json!({"action":"forget","job_id":id}));return;},
            "failed"|"cancelled"=>panic!("Fixture publication failed: {row}"),_=>{}
        }
        assert!(start.elapsed()<Duration::from_secs(60),"Fixture timeout");thread::sleep(Duration::from_millis(10));
    }
}
fn main() {
    let folder=PathBuf::from(std::env::args().nth(1).expect("Provide a NEW output directory"));
    fs::create_dir(&folder).expect("Output directory must be new; never overwrite fixtures");
    let source=folder.join("redirects.jsonl");
    let entries=[("alias","@@@LINK=target\r\n"),("bad","@@@LINK=\n"),("case-alias","@@@LINK=TARGET"),("chain","@@@LINK=alias"),("cycle-a","@@@LINK=cycle-b"),("cycle-b","@@@LINK=cycle-a"),("missing","@@@LINK=absent"),("target","<h2>First target</h2><p>English · 中文 · العربية</p>"),("target","<h2>Second target</h2><p>Duplicate target preserved.</p>")];
    fs::write(&source,entries.iter().map(|(key,text)|json!({"key":key,"text":text}).to_string()+"\n").collect::<String>()).unwrap();
    let mdx=folder.join("redirects.mdx");let a=Adapter::new().unwrap();
    publish(&a,json!({"kind":"dictionary","request":{"operation":"pack_mdx","source":source,"destination":mdx,"encoding":"utf8","metadata":{"title":"Studio redirect checks","description":"Original nine-record test fixture"}}}));
    for (name,policy) in [("redirects-raw.idx","raw_exact"),("redirects-header.idx","header_ascii_v1")] {
        publish(&a,json!({"kind":"index","request":{"source":mdx,"destination":folder.join(name),"kind":"mdx","policy":policy}}));
    }
    a.shutdown().unwrap();
    println!("Prepared {} and raw/header indexes",mdx.display());
    println!("Lookup alias, chain, missing, cycle-a, bad. For case-alias compare raw_exact with header_ascii_v1.");
}
