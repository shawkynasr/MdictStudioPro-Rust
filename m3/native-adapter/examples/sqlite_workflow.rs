//! Exercise sequential database mutations through desktop publication jobs.
use serde_json::{json, Value};
use std::{error::Error, fs, io, path::Path, thread, time::{Duration, Instant}};
use studio_native_adapter::Adapter;

type Result<T> = std::result::Result<T, Box<dyn Error>>;
fn call(adapter: &Adapter, command: Value) -> Result<Value> {
    adapter.call_json(&command.to_string()).map_err(|e| io::Error::other(format!("{e:?}")).into())
}
fn publish(adapter: &Adapter, request: Value) -> Result<Value> {
    let submitted = call(adapter, json!({"action":"submit","request":request}))?;
    let id = submitted["job_id"].as_str().ok_or("Missing job ID")?;
    let start = Instant::now();
    loop {
        let poll = call(adapter, json!({"action":"poll"}))?;
        let row = poll["jobs"].as_array().ok_or("Missing jobs")?.iter()
            .find(|row| row["job_id"] == id).ok_or("Missing submitted job")?;
        match row["state"].as_str() {
            Some("succeeded") => break,
            Some("failed" | "cancelled") => return Err(format!("Publication failed: {row}").into()),
            _ => {}
        }
        if start.elapsed() > Duration::from_secs(120) { return Err("Publication timed out".into()); }
        thread::sleep(Duration::from_millis(20));
    }
    let receipt = call(adapter, json!({"action":"take","job_id":id}))?;
    call(adapter, json!({"action":"forget","job_id":id}))?;
    Ok(receipt)
}
fn snapshot_hash(adapter:&Adapter,source:&Path)->Result<String> {
    let opened=call(adapter,json!({"action":"database_open","source":source}))?;
    let start=Instant::now();
    loop {let state=call(adapter,json!({"action":"database_poll"}))?;match state["job_state"].as_str(){Some("succeeded")=>break,Some("failed"|"cancelled")=>return Err(format!("Open failed: {state}").into()),_=>{}}if start.elapsed()>Duration::from_secs(120){return Err("Open timed out".into());}thread::sleep(Duration::from_millis(10));}
    let info=call(adapter,json!({"action":"database_take","job_id":opened["job_id"]}))?;
    let hash=info["value"]["source_sha256"].as_str().ok_or("Missing snapshot hash")?.to_owned();
    call(adapter,json!({"action":"database_forget","job_id":opened["job_id"]}))?;
    call(adapter,json!({"action":"database_close","reader_id":opened["reader_id"]}))?;
    while call(adapter,json!({"action":"database_poll"}))?["state"]!="closed"{if start.elapsed()>Duration::from_secs(120){return Err("Close timed out".into());}thread::sleep(Duration::from_millis(10));}
    Ok(hash)
}
fn prepare(adapter: &Adapter, out: &Path) -> Result<()> {
    fs::create_dir(out)?;
    let fixture: Value = serde_json::from_str(include_str!("../../fixtures/database-stylesheet.json"))?;
    let source = out.join("entries.jsonl");
    let mut jsonl = String::new();
    for row in fixture["entries"].as_array().ok_or("Missing fixture entries")? {
        jsonl.push_str(&serde_json::to_string(row)?); jsonl.push('\n');
    }
    fs::write(&source, jsonl)?;
    let mut receipts = Vec::new();
    for (encoding, label) in [("utf8", "UTF-8"), ("utf16", "UTF-16")] {
        let dir = out.join(encoding); fs::create_dir(&dir)?;
        let original = dir.join("original.mdx");
        let database = dir.join("dictionary.db");
        let metadata_db=dir.join("metadata.db");let definition=dir.join("definition.db");let renamed=dir.join("renamed.db");let added=dir.join("added.db");let final_db=dir.join("final.db");let back=dir.join("roundtrip.db");let rebuilt=dir.join("rebuilt.mdx");
        let pack = publish(adapter, json!({"kind":"dictionary","request":{
            "operation":"pack_mdx","source":source,"destination":original,"encoding":encoding,
            "metadata":{"title":format!("Combined workflow source · {label}"),
                "description":fixture["description"],"stylesheet":fixture["stylesheet"]}
        }}))?;
        let import = publish(adapter, json!({"kind":"database","request":{
            "operation":"mdx_to_db","source":original,"destination":database
        }}))?;
        let metadata=publish(adapter,json!({"kind":"database","request":{"operation":"db_edit_metadata","source":database,"destination":metadata_db,"expected_source_sha256":snapshot_hash(adapter,&database)?,"edits":{"title":format!("Combined database workflow · {label}"),"description":"Edit, rename, add and delete into database copies."}}}))?;
        let edit=publish(adapter,json!({"kind":"database","request":{"operation":"db_edit_entry","source":metadata_db,"destination":definition,"expected_source_sha256":snapshot_hash(adapter,&metadata_db)?,"rowid":"3","text":"`1`EDITED_DUPLICATE_BOLD"}}))?;
        let rename=publish(adapter,json!({"kind":"database","request":{"operation":"db_edit_entry","source":definition,"destination":renamed,"expected_source_sha256":snapshot_hash(adapter,&definition)?,"rowid":"5","key":"renamed 字","text":"<p style=\"color:#0000ff\">INLINE_BLUE_OK</p>"}}))?;
        let add=publish(adapter,json!({"kind":"database","request":{"operation":"db_add_entry","source":renamed,"destination":added,"expected_source_sha256":snapshot_hash(adapter,&renamed)?,"key":"duplicate","text":"`2`ADDED_DUPLICATE_BLUE"}}))?;
        let delete=publish(adapter,json!({"kind":"database","request":{"operation":"db_delete_entry","source":added,"destination":final_db,"expected_source_sha256":snapshot_hash(adapter,&added)?,"rowid":"6"}}))?;
        let rebuild=publish(adapter,json!({"kind":"database","request":{"operation":"db_to_mdx","source":final_db,"destination":rebuilt}}))?;
        let back_receipt=publish(adapter,json!({"kind":"database","request":{"operation":"mdx_to_db","source":rebuilt,"destination":back}}))?;
        receipts.push(json!({"encoding":encoding,"pack":pack,"import":import,"metadata":metadata,"edit":edit,"rename":rename,"add":add,"delete":delete,"rebuild":rebuild,"back":back_receipt}));
    }
    fs::write(out.join("receipts.json"), serde_json::to_vec_pretty(&receipts)?)?;
    Ok(())
}
fn main() -> Result<()> {
    let mut args = std::env::args_os().skip(1);
    let out = args.next().ok_or("Provide a new absolute output directory")?;
    if args.next().is_some() || !Path::new(&out).is_absolute() { return Err("Provide one absolute output directory".into()); }
    let adapter = Adapter::new().map_err(|e| io::Error::other(format!("{e:?}")))?;
    let result = prepare(&adapter, Path::new(&out));
    let shutdown = adapter.shutdown().map_err(|e| io::Error::other(format!("{e:?}")));
    result?; shutdown?; Ok(())
}
