use std::{env,path::Path,process::ExitCode};
use studio_xlsx::{Error,Limits,ReadControl,read_xlsx};

fn main()->ExitCode {
    let args:Vec<_>=env::args_os().skip(1).collect();
    let result=if args.first().and_then(|a|a.to_str())==Some("read")&&(args.len()==2||args.len()==3) {
        let cancelled=||false;let mut sink=|_|{};
        match args.get(2).map(|a|a.to_str()) {
            Some(None)=>Err(Error {code:"invalid_input",message:"Worksheet name must be valid UTF-8".into()}),
            value=>read_xlsx(Path::new(&args[1]),value.flatten(),&Limits::default(),&mut ReadControl::new(&cancelled,&mut sink)),
        }
    }else{Err(Error {code:"invalid_input",message:"Usage: studio-xlsx read FILE.xlsx [SHEET_NAME]".into()})};
    match result {
        Ok(table)=>{println!("{}",serde_json::to_string(&table).expect("Serialize string table"));ExitCode::SUCCESS}
        Err(error)=>{eprintln!("{}",serde_json::json!({"status":"failed","error":error}));ExitCode::FAILURE}
    }
}
