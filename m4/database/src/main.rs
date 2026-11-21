use std::{io::Read,path::PathBuf};
fn run()->Result<studio_database::Response,studio_database::Error> {
 let mut args=std::env::args_os().skip(1);let operation=args.next();let file=args.next().map(PathBuf::from);
 if operation.as_deref()!=Some(std::ffi::OsStr::new("execute"))||file.is_none()||args.next().is_some(){return Err(studio_database::Error {code:"usage",message:"studio-database execute REQUEST.json".into()});}
 let mut data=Vec::new();std::fs::File::open(file.unwrap())?.take(65537).read_to_end(&mut data)?;if data.len()>65536{return Err(studio_database::Error {code:"invalid_input",message:"Request exceeds 64 KiB".into()});}
 let request=serde_json::from_slice(&data).map_err(|e|studio_database::Error {code:"invalid_input",message:e.to_string()})?;
 studio_database::execute(&request,&mut studio_database::Job::new(&studio_database::CancellationToken::default(),&mut |_|{}))
}
fn main()->std::process::ExitCode {match run(){Ok(result)=>{println!("{}",serde_json::json!({"status":"passed","result":result}));std::process::ExitCode::SUCCESS},Err(error)=>{println!("{}",serde_json::json!({"status":"failed","error":error}));std::process::ExitCode::FAILURE}}}
