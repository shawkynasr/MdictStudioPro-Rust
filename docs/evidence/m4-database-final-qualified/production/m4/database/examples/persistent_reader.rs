//! Standalone backend qualification; deliberately not a desktop command.
use std::{fs,path::PathBuf};
use studio_database::{CancellationToken,Job,Reader,ReaderQuery,Request,TxtProfile,execute};

fn qualify()->Result<(),Box<dyn std::error::Error>> {
 let out=PathBuf::from(std::env::args_os().nth(1).ok_or("Require a fresh output directory")?);
 fs::create_dir(&out)?;
 let source=out.join("source.txt");let original=out.join("original.db");let copy=out.join("reader-source.db");
 fs::write(&source,include_bytes!("../../../m3/fixtures/database-prefix.txt"))?;
 let token=CancellationToken::default();
 let native=|e:studio_database::Error|std::io::Error::other(format!("{e:?}"));
 execute(&Request::TxtToDb{source,destination:original.clone(),profile:TxtProfile::CanonicalV1},&mut Job::new(&token,&mut |_|{})).map_err(native)?;
 fs::copy(&original,&copy)?;
 let mut opening_phases=Vec::new();let mut opening=|p|opening_phases.push(p);
 let mut reader=Reader::open(&copy,&mut Job::new(&token,&mut opening)).map_err(native)?;
 let info=reader.info().map_err(native)?;
 // The following calls must use the retained snapshot, not the original path.
 fs::remove_file(&copy)?;
 let mut page_phases=Vec::new();let mut progress=|p|page_phases.push(p);
 let mut pages=Vec::new();let mut offset=0;
 loop {
  let p=reader.page(ReaderQuery::All,offset,2,&mut Job::new(&token,&mut progress)).map_err(native)?;
  let next=p.next_offset;pages.push(p);if let Some(next)=next{offset=next;}else{break;}
 }
 let mut lookups=Vec::new();
 for (kind,query,offset) in [("prefix","app",0),("prefix","app",2),("exact","apple",0),("prefix","App",0),("prefix","a%",0),("prefix","a_",0),("prefix","字",0),("prefix","مر",0),("exact","app",0)] {
  let q=if kind=="prefix"{ReaderQuery::Prefix(query)}else{ReaderQuery::Exact(query)};
  let page=reader.page(q,offset,2,&mut Job::new(&token,&mut progress)).map_err(native)?;
  lookups.push(serde_json::json!({"kind":kind,"query":query,"page":page}));
 }
 reader.close();reader.close();
 let closed_info=reader.info().unwrap_err().code;
 let closed_page=reader.page(ReaderQuery::All,0,2,&mut Job::new(&token,&mut |_|{})).unwrap_err().code;
 let report=serde_json::json!({"info":info,"browse":pages,"lookups":lookups,"opening_phases":opening_phases,"page_phases":page_phases,"closed_info":closed_info,"closed_page":closed_page,"source_removed":!copy.exists()});
 fs::write(out.join("reader.json"),serde_json::to_vec_pretty(&report)?)?;
 Ok(())
}
fn main() {if let Err(e)=qualify(){eprintln!("{e}");std::process::exit(1);}}
