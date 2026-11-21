//! Line-delimited Rust-only diagnostic controller. No Python plugins run here.
use studio_sessions::*;
use serde::Deserialize;
use serde_json::{Value,json};
use std::{collections::BTreeMap,io::{BufRead,Write},time::Duration};
#[derive(Deserialize)]#[serde(tag="op",rename_all="snake_case",deny_unknown_fields)]enum Command {
 Open {request:OpenRequest,#[serde(default)]pre_cancel:bool},
 Submit {session:String,request:PageRequest,#[serde(default)]pre_cancel:bool},
 Job {session:String,job:String},Wait {session:String,job:String},Take {session:String,job:String},Forget {session:String,job:String},Cancel {session:String,job:String},
 Snapshot {session:String},Events {session:String},Close {session:String},WaitClosed {session:String},Release {session:String},Admission,Shutdown,
}
fn session<'a>(sessions:&'a BTreeMap<String,Session>,id:&str)->ApiResult<&'a Session> {sessions.get(id).ok_or(ApiError {code:ApiCode::NotFound,message:"Unknown session handle".into()})}
fn execute(command:Command,pool:&Pool,sessions:&mut BTreeMap<String,Session>)->ApiResult<Value> {
 Ok(match command {
  Command::Open {request,pre_cancel}=>{if sessions.len()>=8 {return Err(ApiError {code:ApiCode::ResourceLimit,message:"Controller retains at most eight handles".into()});}let token=CancellationToken::default();if pre_cancel {token.cancel();}let s=pool.open_with_token(request,token)?;let id=s.id().to_string();let open=s.open_job_id();sessions.insert(id.clone(),s);json!({"session":id,"job":open})},
  Command::Submit {session:id,request,pre_cancel}=>{let token=CancellationToken::default();if pre_cancel {token.cancel();}json!({"job":session(sessions,&id)?.submit_page_with_token(request,token)?})},
  Command::Job {session:id,job}=>json!(session(sessions,&id)?.job(&job)?),
  Command::Wait {session:id,job}=>json!(session(sessions,&id)?.wait_job(&job,Duration::from_secs(30))?),
  Command::Take {session:id,job}=>json!(session(sessions,&id)?.take_result(&job)?),
  Command::Forget {session:id,job}=>{session(sessions,&id)?.forget(&job)?;Value::Null},
  Command::Cancel {session:id,job}=>json!(session(sessions,&id)?.cancel(&job)?),
  Command::Snapshot {session:id}=>json!(session(sessions,&id)?.snapshot()),
  Command::Events {session:id}=>json!(session(sessions,&id)?.drain_events()),
  Command::Close {session:id}=>{session(sessions,&id)?.close();Value::Null},
  Command::WaitClosed {session:id}=>json!({"closed":session(sessions,&id)?.wait_closed(Duration::from_secs(30))}),
  Command::Release {session:id}=>{let s=sessions.remove(&id).ok_or(ApiError {code:ApiCode::NotFound,message:"Unknown session handle".into()})?;s.join()?;Value::Null},
  Command::Admission=>json!(pool.admission()),
  Command::Shutdown=>{pool.shutdown();Value::Null},
 })
}
fn line(reader:&mut impl BufRead)->std::io::Result<Option<Vec<u8>>> {
 let mut out=Vec::new();loop {let bytes=reader.fill_buf()?;if bytes.is_empty() {return if out.is_empty(){Ok(None)}else{Err(std::io::Error::other("Incomplete final command line"))};}let n=bytes.iter().position(|b|*b==b'\n').map_or(bytes.len(),|n|n+1);if out.len()+n>65536 {return Err(std::io::Error::other("Command exceeds 64 KiB"));}out.extend_from_slice(&bytes[..n]);reader.consume(n);if out.last()==Some(&b'\n') {return Ok(Some(out));}}
}
fn run()->Result<(),Box<dyn std::error::Error>> {
 let pool=Pool::new(Config::default())?;let mut sessions=BTreeMap::new();let stdin=std::io::stdin();let mut input=stdin.lock();let stdout=std::io::stdout();let mut output=stdout.lock();
 while let Some(bytes)=line(&mut input)? {
  let reply=match serde_json::from_slice::<Command>(&bytes) {Ok(command)=>match execute(command,&pool,&mut sessions) {Ok(value)=>json!({"ok":value}),Err(e)=>json!({"error":e})},Err(e)=>json!({"error":{"code":"invalid_input","message":e.to_string()}})};
  // Responses have already passed the session's 2 MiB serialized cap. The
  // diagnostic envelope adds only a few bytes; no second payload is retained.
  serde_json::to_writer(&mut output,&reply)?;output.write_all(b"\n")?;output.flush()?;
 }
 pool.shutdown();for (_,s) in sessions {s.join()?;}Ok(())
}
fn main()->std::process::ExitCode {match run() {Ok(())=>std::process::ExitCode::SUCCESS,Err(e)=>{eprintln!("{}",json!({"error":{"code":"controller_io","message":e.to_string()}}));std::process::ExitCode::FAILURE}}}
