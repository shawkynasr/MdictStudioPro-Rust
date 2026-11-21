//! Prepare reader fixtures through the same publication jobs as the desktop.
use serde_json::{json, Value};
use std::{error::Error, fs, io, path::Path, thread, time::{Duration, Instant}};
use studio_native_adapter::Adapter;

type Result<T> = std::result::Result<T, Box<dyn Error>>;
fn call(adapter: &Adapter, command: Value) -> Result<Value> {
    adapter.call_json(&command.to_string()).map_err(|e| io::Error::other(format!("{e:?}")).into())
}
fn publish(adapter:&Adapter,request:Value)->Result<Value> {
 let start=Instant::now();let submitted=call(adapter,json!({"action":"submit","request":request}))?;let id=submitted["job_id"].as_str().ok_or("Missing job ID")?;
 loop {let poll=call(adapter,json!({"action":"poll"}))?;let row=poll["jobs"].as_array().ok_or("Missing jobs")?.iter().find(|r|r["job_id"]==id).ok_or("Missing job")?;
  if matches!(row["state"].as_str(),Some("succeeded"|"failed"|"cancelled")) {
   let receipt=if row["state"]=="succeeded"{call(adapter,json!({"action":"take","job_id":id}))?}else{Value::Null};
   let result=json!({"state":row["state"],"error":row["error"],"elapsed_ms":start.elapsed().as_secs_f64()*1000.0,"receipt":receipt});call(adapter,json!({"action":"forget","job_id":id}))?;return Ok(result);
  }
  if start.elapsed()>Duration::from_secs(240){return Err("Publication timed out".into());}thread::sleep(Duration::from_millis(1));
 }
}
fn reader_result(adapter:&Adapter,id:&Value)->Result<Value> {
 let start=Instant::now();loop {let state=call(adapter,json!({"action":"database_poll"}))?;match state["job_state"].as_str(){Some("succeeded")=>break,Some("failed"|"cancelled")=>return Err(format!("Reader failed: {state}").into()),_=>{}}if start.elapsed()>Duration::from_secs(120){return Err("Reader timed out".into());}thread::sleep(Duration::from_millis(1));}
 let result=call(adapter,json!({"action":"database_take","job_id":id}))?;call(adapter,json!({"action":"database_forget","job_id":id}))?;Ok(result)
}
fn prepare(adapter:&Adapter,config:&Value,out:&Path)->Result<()> {
 fs::create_dir(out)?;let db=out.join("dictionary.db");let export=out.join("export.jsonl");
 let import=publish(adapter,json!({"kind":"database","request":{"operation":config["operation"],"source":config["source"],"destination":db}}))?;
 let mut result=json!({"import":import});
 if let Some(expected)=config["expected_error"].as_str() {
  if import["state"]!="failed"||import["error"]["code"]!=expected||db.exists(){return Err(format!("Expected controlled refusal: {import}").into());}
  if fs::read_dir(out)?.next().is_some(){return Err("Refusal left an output artifact".into());}
  result["controlled_refusal"]=json!(true);
 }else{
  if import["state"]!="succeeded"{return Err(format!("Import failed: {import}").into());}
  let start=Instant::now();let opened=call(adapter,json!({"action":"database_open","source":db}))?;let info=reader_result(adapter,&opened["job_id"])?;result["open_ms"]=json!(start.elapsed().as_secs_f64()*1000.0);result["info"]=info;
  let mut queries=Vec::new();
  for spec in config["queries"].as_array().ok_or("Missing queries")? {
   for repeat in 0..5 {let start=Instant::now();let submitted=call(adapter,json!({"action":"database_query","reader_id":opened["reader_id"],"request":spec["request"]}))?;let reply=reader_result(adapter,&submitted["job_id"])?;
    queries.push(json!({"label":spec["label"],"repeat":repeat,"elapsed_ms":start.elapsed().as_secs_f64()*1000.0,"reply":reply}));
   }
  }
  result["queries"]=json!(queries);let start=Instant::now();call(adapter,json!({"action":"database_close","reader_id":opened["reader_id"]}))?;
  while call(adapter,json!({"action":"database_poll"}))?["state"]!="closed" {if start.elapsed()>Duration::from_secs(120){return Err("Close timed out".into());}thread::sleep(Duration::from_millis(1));}
  let exported=publish(adapter,json!({"kind":"database","request":{"operation":"db_to_jsonl","source":db,"destination":export}}))?;
  if exported["state"]!="succeeded"{return Err(format!("Export failed: {exported}").into());}result["export"]=exported;
  result["admission_after_close"]=call(adapter,json!({"action":"poll"}))?["admission"].clone();
 }
 fs::write(out.join("result.json"),serde_json::to_vec_pretty(&result)?)?;Ok(())
}
fn main()->Result<()> {
 let mut args=std::env::args_os().skip(1);let config=args.next().ok_or("Require configuration path")?;let out=args.next().ok_or("Require new output directory")?;if args.next().is_some()||!Path::new(&out).is_absolute(){return Err("Require configuration and absolute new output directory".into());}
 let config:Value=serde_json::from_slice(&fs::read(config)?)?;let adapter=Adapter::new().map_err(|e|io::Error::other(format!("{e:?}")))?;let result=prepare(&adapter,&config,Path::new(&out));let shutdown=adapter.shutdown().map_err(|e|io::Error::other(format!("{e:?}")));result?;shutdown?;Ok(())
}
