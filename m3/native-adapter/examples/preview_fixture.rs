//! Generate a small, original fixture pair and indexes through the real adapter.
//! Usage: cargo run --manifest-path m3/native-adapter/Cargo.toml --example preview_fixture -- m3-shell-out-preview-fixture
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
    fs::create_dir(&folder).expect("Output directory must not already exist");
    let folder=fs::canonicalize(folder).unwrap();let assets=folder.join("assets");
    fs::create_dir(&assets).unwrap();fs::create_dir(assets.join("css")).unwrap();fs::create_dir(assets.join("images")).unwrap();
    // Original blue square, encoded as a tiny GIF; no external download needed.
    let gif:&[u8]=&[71,73,70,56,57,97,1,0,1,0,128,0,0,36,111,233,255,255,255,33,249,4,1,0,0,1,0,44,0,0,0,0,1,0,1,0,0,2,2,68,1,0,59];
    fs::write(assets.join("images/blue.gif"),gif).unwrap();
    fs::write(assets.join("css/main.css"),".resource-card{border:3px solid #246fe9;padding:20px;background:#eef4ff;color:#152638}.tile{width:40px;height:40px;background:url('../images/blue.gif')}").unwrap();
    let entries=[
        json!({"key":"plain","text":"<h2>Plain entry</h2><p>English · 中文 · <span dir=\"rtl\">العربية</span></p>"}),
        json!({"key":"styles","text":"<p style=\"color:blue\">inline-blue</p>`2`marker-blue"}),
        json!({"key":"resources","text":"<link rel=\"stylesheet\" href=\"css/main.css\"><div class=\"resource-card\">MDD CSS loaded<div class=\"tile\"></div><img src=\"images/blue.gif\" width=\"40\" alt=\"Blue resource\"></div>"}),
        json!({"key":"missing","text":"<h2>Missing resource</h2><img src=\"images/absent.png\" alt=\"Expected missing-resource warning\">"}),
        json!({"key":"isolation","text":"<h2>Static content survives</h2><script>document.body.innerHTML='SCRIPT_RAN'</script><img src=\"https://example.invalid/blocked.png\" onerror=\"document.body.innerHTML='HANDLER_RAN'\"><iframe src=\"https://example.invalid/\"></iframe><form action=\"https://example.invalid/\"><input value=\"blocked\"></form><p>Scripts, handlers, frames and network URLs must be removed.</p>"}),
    ];
    let source=folder.join("entries.jsonl");fs::write(&source,entries.iter().map(|r|r.to_string()+"\n").collect::<String>()).unwrap();
    let manifest=folder.join("resources.jsonl");fs::write(&manifest,[json!({"key":"\\css\\main.css","file":"css/main.css"}),json!({"key":"\\images\\blue.gif","file":"images/blue.gif"})].iter().map(|r|r.to_string()+"\n").collect::<String>()).unwrap();
    let mdx=folder.join("preview.mdx");let mdd=folder.join("preview.mdd");
    let a=Adapter::new().unwrap();
    publish(&a,json!({"kind":"dictionary","request":{"operation":"pack_mdx","source":source,"destination":mdx,"encoding":"utf8","metadata":{"title":"Studio static preview","description":"Original GUI qualification fixture","stylesheet":"2\n<span style=\"color:blue\">\n</span>\n"}}}));
    publish(&a,json!({"kind":"dictionary","request":{"operation":"pack_mdd","source":manifest,"resource_root":assets,"destination":mdd,"metadata":{"title":"Studio resources","description":"CSS and original GIF"}}}));
    for (kind,file) in [("mdx",&mdx),("mdd",&mdd)] {
        publish(&a,json!({"kind":"index","request":{"source":file,"destination":folder.join(format!("preview-{kind}.idx")),"kind":kind,"policy":"raw_exact"}}));
    }
    a.shutdown().unwrap();
    println!("Prepared MDX/MDD and both raw-exact indexes in {}",folder.display());
    println!("Look up: plain, styles, resources, missing, isolation");
}
