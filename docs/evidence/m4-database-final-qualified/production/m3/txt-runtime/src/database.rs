//! Database publications run on the shared serial worker and use its token/lease.
use crate::{Error,ErrorCode,ImportJob,Progress,Result};
use serde::Deserialize;
use std::path::{Path,PathBuf};
#[derive(Debug,Deserialize)]
#[serde(tag="operation",rename_all="snake_case",deny_unknown_fields)]
pub enum Request {
 TxtToDb {source:PathBuf,destination:PathBuf,profile:studio_core::TxtProfile},
 DbToTxt {source:PathBuf,destination:PathBuf},
 DbToJsonl {source:PathBuf,destination:PathBuf},
 DbAddEntry {source:PathBuf,destination:PathBuf,expected_source_sha256:String,key:String,text:String},
 DbDeleteEntry {source:PathBuf,destination:PathBuf,expected_source_sha256:String,rowid:String},
 DbEditEntry {source:PathBuf,destination:PathBuf,expected_source_sha256:String,rowid:String,text:String,#[serde(default)]key:Option<String>},
 DbEditMetadata {source:PathBuf,destination:PathBuf,expected_source_sha256:String,edits:studio_database::MetadataEdits},
 JsonlToDb {source:PathBuf,destination:PathBuf},
 MdxToDb {source:PathBuf,destination:PathBuf},
 DbToMdx {source:PathBuf,destination:PathBuf},
}
impl Request {
 pub fn source(&self)->&Path {match self {Self::TxtToDb{source,..}|Self::DbToTxt{source,..}|Self::DbAddEntry{source,..}|Self::DbDeleteEntry{source,..}|Self::DbEditEntry{source,..}|Self::DbEditMetadata{source,..}|Self::JsonlToDb{source,..}|Self::DbToJsonl{source,..}|Self::MdxToDb{source,..}|Self::DbToMdx{source,..}=>source}}
 pub fn destination(&self)->&Path {match self {Self::TxtToDb{destination,..}|Self::DbToTxt{destination,..}|Self::DbAddEntry{destination,..}|Self::DbDeleteEntry{destination,..}|Self::DbEditEntry{destination,..}|Self::DbEditMetadata{destination,..}|Self::JsonlToDb{destination,..}|Self::DbToJsonl{destination,..}|Self::MdxToDb{destination,..}|Self::DbToMdx{destination,..}=>destination}}
 pub fn operation(&self)->&'static str {match self {Self::DbToMdx{..}=>"db_to_mdx",Self::MdxToDb{..}=>"mdx_to_db",Self::TxtToDb{..}=>"txt_to_db",Self::DbToTxt{..}=>"db_to_txt",Self::DbAddEntry{..}=>"db_add_entry",Self::DbDeleteEntry{..}=>"db_delete_entry",Self::DbEditEntry{..}=>"db_edit_entry",Self::DbEditMetadata{..}=>"db_edit_metadata",Self::JsonlToDb{..}=>"jsonl_to_db",Self::DbToJsonl{..}=>"db_to_jsonl"}}
}
pub(crate) fn mapped(e:studio_database::Error)->Error {
 let code=match e.code {"cancelled"=>ErrorCode::Cancelled,"destination_exists"=>ErrorCode::DestinationExists,"limit_exceeded"=>ErrorCode::LimitExceeded,"invalid_input"=>ErrorCode::InvalidInput,"invalid_encoding"=>ErrorCode::InvalidEncoding,"unsupported_profile"=>ErrorCode::UnsupportedPolicy,"unrepresentable_source"=>ErrorCode::UnrepresentableSource,"integrity"=>ErrorCode::Integrity,"io"=>ErrorCode::Io,"sqlite"=>ErrorCode::Engine,_=>ErrorCode::Internal};
 Error {code,detail:"database",message:format!("{}: {}",e.code,e.message),limit:None}
}
#[derive(Debug,Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PageRequest {pub source:PathBuf,pub query:Option<String>,#[serde(default)]pub prefix:bool,pub offset:u64,pub limit:usize,pub expected_source_sha256:Option<String>}
impl PageRequest {
 pub(crate) fn validate(&self)->crate::ApiResult<()> {
  if (self.prefix&&self.query.is_none())||self.limit==0||self.limit>128||self.offset>100000||self.query.as_ref().is_some_and(|q|q.is_empty()||q.len()>4096||q.contains('\0'))||self.expected_source_sha256.as_ref().is_some_and(|h|h.len()!=64||!h.bytes().all(|b|b.is_ascii_hexdigit())) {
   return Err(crate::ApiError {code:crate::ApiCode::InvalidInput,message:"Require page 1..128, offset <=100,000, exact/prefix key <=4 KiB and optional SHA-256".into()});
  }Ok(())
 }
}
pub(crate) fn page(r:&PageRequest,job:&mut ImportJob<'_>)->Result<studio_database::Page> {
 r.validate().map_err(|e|Error {code:ErrorCode::InvalidInput,detail:"database_page",message:e.message,limit:None})?;
 let request=match &r.query {
  Some(query) if r.prefix=>studio_database::Request::PrefixLookup {source:r.source.clone(),query:query.clone(),offset:r.offset,limit:r.limit},
  Some(query)=>studio_database::Request::Lookup {source:r.source.clone(),query:query.clone(),offset:r.offset,limit:r.limit},
  None=>studio_database::Request::Browse {source:r.source.clone(),offset:r.offset,limit:r.limit},
 };
 let id=job.id;let token=job.token;
 let mut progress=|p:studio_database::Progress|(job.progress)(Progress {job_id:id.into(),stage:studio_application::Stage::Converting,phase:p.phase.into(),completed:p.completed,total:p.total});
 let result=studio_database::execute(&request,&mut studio_database::Job::new(token,&mut progress)).map_err(mapped)?;
 let result=match result {studio_database::Response::Lookup(page)|studio_database::Response::Browse(page)=>page,_=>return Err(Error {code:ErrorCode::Internal,detail:"database_page",message:"Unexpected database page response".into(),limit:None})};
 if r.expected_source_sha256.as_ref().is_some_and(|expected|expected!=&result.source_sha256){return Err(Error {code:ErrorCode::Integrity,detail:"database_changed",message:"Database changed since the previous page; browse again from the beginning".into(),limit:None});}
 Ok(result)
}
pub(crate) fn execute(r:&Request,job:&mut ImportJob<'_>)->Result<studio_database::Response> {
 if let Request::DbToMdx{source,destination}=r{return crate::database_mdx::execute(source,destination,job).map(studio_database::Response::DbToMdx);}
 if let Request::MdxToDb{source,destination}=r{return crate::mdx_database::execute(source,destination,job).map(studio_database::Response::MdxToDb);}
 let request=match r {
  Request::MdxToDb{..}|Request::DbToMdx{..}=>unreachable!(),
  Request::TxtToDb{source,destination,profile}=>studio_database::Request::TxtToDb {source:source.clone(),destination:destination.clone(),profile:*profile},
  Request::DbAddEntry{source,destination,expected_source_sha256,key,text}=>studio_database::Request::DbAddEntry {source:source.clone(),destination:destination.clone(),expected_source_sha256:expected_source_sha256.clone(),key:key.clone(),text:text.clone()},
  Request::DbDeleteEntry{source,destination,expected_source_sha256,rowid}=>studio_database::Request::DbDeleteEntry {source:source.clone(),destination:destination.clone(),expected_source_sha256:expected_source_sha256.clone(),rowid:rowid.clone()},
  Request::DbEditEntry{source,destination,expected_source_sha256,rowid,text,key}=>studio_database::Request::DbEditEntry {source:source.clone(),destination:destination.clone(),expected_source_sha256:expected_source_sha256.clone(),rowid:rowid.clone(),text:text.clone(),key:key.clone()},
  Request::DbEditMetadata{source,destination,expected_source_sha256,edits}=>studio_database::Request::DbEditMetadata {source:source.clone(),destination:destination.clone(),expected_source_sha256:expected_source_sha256.clone(),edits:edits.clone()},
  Request::JsonlToDb{source,destination}=>studio_database::Request::JsonlToDb {source:source.clone(),destination:destination.clone()},
  Request::DbToJsonl{source,destination}=>studio_database::Request::DbToJsonl {source:source.clone(),destination:destination.clone()},
  Request::DbToTxt{source,destination}=>studio_database::Request::DbToTxt {source:source.clone(),destination:destination.clone()},
 };
 let id=job.id;let token=job.token;
 let mut progress=|p:studio_database::Progress|(job.progress)(Progress {job_id:id.into(),stage:if p.phase=="database_commit"{studio_application::Stage::Publishing}else{studio_application::Stage::Converting},phase:p.phase.into(),completed:p.completed,total:p.total});
 studio_database::execute(&request,&mut studio_database::Job::new(token,&mut progress)).map_err(mapped)
}

#[cfg(test)]mod tests {
 use super::*;use crate::{AdmissionLimits,Budget,Operation,CancellationToken};
 #[test]fn jsonl_route_preserves_rows_cancels_and_success_wins_late_cancellation() {
  use crate::runner;
  use std::{sync::Arc,time::Duration};
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("in.txt");let db=dir.path().join("out.db");std::fs::write(&source,include_bytes!("../../fixtures/build-source.txt")).unwrap();let token=CancellationToken::default();
  execute(&Request::TxtToDb{source,destination:db.clone(),profile:studio_core::TxtProfile::CanonicalV1},&mut ImportJob::new("create",&token,&mut |_|{})).unwrap();
  let cancelled=dir.path().join("cancel.jsonl");let cancel_token=CancellationToken::default();let stop=cancel_token.clone();let mut progress=|p:Progress|if p.phase=="database_jsonl_verify"{stop.cancel();};assert_eq!(execute(&Request::DbToJsonl{source:db.clone(),destination:cancelled.clone()},&mut ImportJob::new("cancel",&cancel_token,&mut progress)).unwrap_err().code,ErrorCode::Cancelled);assert!(!cancelled.exists());
  let destination=dir.path().join("rows.jsonl");let request=crate::Request::Database(Request::DbToJsonl{source:db,destination:destination.clone()});assert_eq!(request.destination(),Some(destination.as_path()));assert_eq!(request.operation(),"db_to_jsonl");
  let budget=Budget::new(AdmissionLimits::default()).unwrap();let runner=runner::Runner::with_executor(runner::Config::default(),budget.clone(),Arc::new(|r,j|{let response=crate::execute(r,j)?;j.token.cancel();Ok(response)})).unwrap();
  let id=runner.submit(request).unwrap();let state=runner.wait_for_terminal(&id,Duration::from_secs(30)).unwrap().unwrap();assert_eq!(state.state,runner::State::Succeeded);assert!(destination.exists());let text=std::fs::read_to_string(destination).unwrap();assert_eq!(text.lines().count(),5);assert_eq!(budget.snapshot().active_operations,0);runner.join().unwrap();
 }
 #[test]fn entry_copy_route_cancels_retries_and_rebuilds_selected_definition() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.txt");let db=dir.path().join("source.db");let dest=dir.path().join("edited.db");let token=CancellationToken::default();std::fs::write(&source,"字\nfirst\n</>\n字\nsecond\n</>\n").unwrap();execute(&Request::TxtToDb{source,destination:db.clone(),profile:studio_core::TxtProfile::CanonicalV1},&mut ImportJob::new("seed",&token,&mut |_|{})).unwrap();
  let old=studio_database::read_for_rebuild(&db,&mut studio_database::Job::new(&token,&mut |_|{})).unwrap();let request=Request::DbEditEntry{source:db,destination:dest.clone(),expected_source_sha256:old.source_sha256,rowid:"2".into(),text:"<p>edited second</p>".into(),key:None};assert_eq!(request.operation(),"db_edit_entry");let stop=CancellationToken::default();let cancel=stop.clone();let mut progress=|p:Progress|if p.phase=="database_entry_copy"{cancel.cancel();};assert_eq!(execute(&request,&mut ImportJob::new("cancel",&stop,&mut progress)).unwrap_err().code,ErrorCode::Cancelled);assert!(!dest.exists());
  let studio_database::Response::DbEditEntry(receipt)=execute(&request,&mut ImportJob::new("edit",&token,&mut |_|{})).unwrap()else{panic!()};assert_eq!(receipt.source_rowid,"2");assert_eq!(receipt.output_rowid,"2");let rows=studio_database::read_for_rebuild(&dest,&mut studio_database::Job::new(&token,&mut |_|{})).unwrap().rows;assert_eq!(rows[0].text,"first");assert_eq!(rows[1].text,"<p>edited second</p>");let rebuilt=crate::database_mdx::execute(&dest,&dir.path().join("edited.mdx"),&mut ImportJob::new("rebuild",&token,&mut |_|{})).unwrap();assert_eq!(rebuilt.records,2);
 }
 #[test]fn entry_rename_route_cancels_retries_and_resorts_mdx() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.txt");let db=dir.path().join("source.db");let dest=dir.path().join("edited.db");let token=CancellationToken::default();std::fs::write(&source,"字\nfirst\n</>\n字\nsecond\n</>\n").unwrap();execute(&Request::TxtToDb{source,destination:db.clone(),profile:studio_core::TxtProfile::CanonicalV1},&mut ImportJob::new("seed",&token,&mut |_|{})).unwrap();
  let old=studio_database::read_for_rebuild(&db,&mut studio_database::Job::new(&token,&mut |_|{})).unwrap();let request=Request::DbEditEntry{source:db,destination:dest.clone(),expected_source_sha256:old.source_sha256,rowid:"2".into(),text:"<p>edited second</p>".into(),key:Some("a renamed".into())};assert_eq!(request.operation(),"db_edit_entry");let stop=CancellationToken::default();let cancel=stop.clone();let mut progress=|p:Progress|if p.phase=="database_entry_copy"{cancel.cancel();};assert_eq!(execute(&request,&mut ImportJob::new("cancel",&stop,&mut progress)).unwrap_err().code,ErrorCode::Cancelled);assert!(!dest.exists());
  let studio_database::Response::DbEditEntry(receipt)=execute(&request,&mut ImportJob::new("edit",&token,&mut |_|{})).unwrap()else{panic!()};assert_eq!(receipt.source_rowid,"2");assert_eq!(receipt.output_rowid,"2");let rows=studio_database::read_for_rebuild(&dest,&mut studio_database::Job::new(&token,&mut |_|{})).unwrap().rows;assert_eq!(rows[0].text,"first");assert_eq!(rows[1].text,"<p>edited second</p>");let rebuilt=crate::database_mdx::execute(&dest,&dir.path().join("edited.mdx"),&mut ImportJob::new("rebuild",&token,&mut |_|{})).unwrap();assert_eq!(rebuilt.records,2);assert_eq!(rows[1].key,"a renamed");let imported=dir.path().join("roundtrip.db");crate::mdx_database::execute(&dir.path().join("edited.mdx"),&imported,&mut ImportJob::new("import",&token,&mut |_|{})).unwrap();let back=studio_database::read_for_rebuild(&imported,&mut studio_database::Job::new(&token,&mut |_|{})).unwrap();assert_eq!(back.rows,vec![rows[1].clone(),rows[0].clone()]);
 }
 #[test]fn entry_delete_route_cancels_retries_and_rebuilds_surviving_duplicate() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.txt");let db=dir.path().join("source.db");let dest=dir.path().join("deleted.db");let token=CancellationToken::default();std::fs::write(&source,"字\nfirst\n</>\n字\nsecond\n</>\na\nlast\n</>\n").unwrap();execute(&Request::TxtToDb{source,destination:db.clone(),profile:studio_core::TxtProfile::CanonicalV1},&mut ImportJob::new("seed",&token,&mut |_|{})).unwrap();
  let before=std::fs::read(&db).unwrap();let old=studio_database::read_for_rebuild(&db,&mut studio_database::Job::new(&token,&mut |_|{})).unwrap();let request=Request::DbDeleteEntry{source:db.clone(),destination:dest.clone(),expected_source_sha256:old.source_sha256,rowid:"2".into()};assert_eq!(request.operation(),"db_delete_entry");assert_eq!(request.source(),db.as_path());assert_eq!(request.destination(),dest.as_path());let stop=CancellationToken::default();let cancel=stop.clone();let mut progress=|p:Progress|if p.phase=="database_entry_delete"{cancel.cancel();};assert_eq!(execute(&request,&mut ImportJob::new("cancel",&stop,&mut progress)).unwrap_err().code,ErrorCode::Cancelled);assert!(!dest.exists());
  let studio_database::Response::DbDeleteEntry(receipt)=execute(&request,&mut ImportJob::new("delete",&token,&mut |_|{})).unwrap()else{panic!()};assert_eq!(receipt.source_rowid,"2");assert_eq!(receipt.publication.records,2);let rows=studio_database::read_for_rebuild(&dest,&mut studio_database::Job::new(&token,&mut |_|{})).unwrap().rows;assert_eq!(rows,vec![old.rows[0].clone(),old.rows[2].clone()]);let mdx=dir.path().join("deleted.mdx");let rebuilt=crate::database_mdx::execute(&dest,&mdx,&mut ImportJob::new("rebuild",&token,&mut |_|{})).unwrap();assert_eq!(rebuilt.records,2);let imported=dir.path().join("roundtrip.db");crate::mdx_database::execute(&mdx,&imported,&mut ImportJob::new("import",&token,&mut |_|{})).unwrap();let back=studio_database::read_for_rebuild(&imported,&mut studio_database::Job::new(&token,&mut |_|{})).unwrap();assert_eq!(back.rows,vec![rows[1].clone(),rows[0].clone()]);assert_eq!(std::fs::read(&db).unwrap(),before);
 }
 #[test]fn entry_add_route_cancels_retries_and_rebuilds_duplicate_order() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.txt");let db=dir.path().join("source.db");let dest=dir.path().join("added.db");let token=CancellationToken::default();std::fs::write(&source,"字\nfirst\n</>\na\nlast\n</>\n").unwrap();execute(&Request::TxtToDb{source,destination:db.clone(),profile:studio_core::TxtProfile::CanonicalV1},&mut ImportJob::new("seed",&token,&mut |_|{})).unwrap();
  let before=std::fs::read(&db).unwrap();let old=studio_database::read_for_rebuild(&db,&mut studio_database::Job::new(&token,&mut |_|{})).unwrap();let request=Request::DbAddEntry{source:db.clone(),destination:dest.clone(),expected_source_sha256:old.source_sha256,key:"字".into(),text:"second".into()};assert_eq!(request.operation(),"db_add_entry");assert_eq!(request.source(),db.as_path());assert_eq!(request.destination(),dest.as_path());let stop=CancellationToken::default();let cancel=stop.clone();let mut progress=|p:Progress|if p.phase=="database_entry_add"{cancel.cancel();};assert_eq!(execute(&request,&mut ImportJob::new("cancel",&stop,&mut progress)).unwrap_err().code,ErrorCode::Cancelled);assert!(!dest.exists());
  let studio_database::Response::DbAddEntry(receipt)=execute(&request,&mut ImportJob::new("add",&token,&mut |_|{})).unwrap()else{panic!()};assert_eq!(receipt.output_rowid,"3");assert_eq!(receipt.publication.records,3);let rows=studio_database::read_for_rebuild(&dest,&mut studio_database::Job::new(&token,&mut |_|{})).unwrap().rows;assert_eq!(rows[0],old.rows[0]);assert_eq!(rows[1],old.rows[1]);assert_eq!(rows[2].key,"字");assert_eq!(rows[2].text,"second");let mdx=dir.path().join("added.mdx");let rebuilt=crate::database_mdx::execute(&dest,&mdx,&mut ImportJob::new("rebuild",&token,&mut |_|{})).unwrap();assert_eq!(rebuilt.records,3);let imported=dir.path().join("roundtrip.db");crate::mdx_database::execute(&mdx,&imported,&mut ImportJob::new("import",&token,&mut |_|{})).unwrap();let back=studio_database::read_for_rebuild(&imported,&mut studio_database::Job::new(&token,&mut |_|{})).unwrap();assert_eq!(back.rows,vec![rows[1].clone(),rows[0].clone(),rows[2].clone()]);assert_eq!(std::fs::read(&db).unwrap(),before);
 }
 #[test]fn database_metadata_copy_route_cancels_retries_and_rebuilds_edited_header() {
  use std::collections::BTreeMap;
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");let dest=dir.path().join("edited.db");let token=CancellationToken::default();let attrs=BTreeMap::from([("Title".into(),"before".into()),("Description".into(),"original".into()),("GeneratedByEngineVersion".into(),"2.0".into()),("RequiredEngineVersion".into(),"2.0".into()),("Encoding".into(),"UTF-8".into()),("Format".into(),"Html".into()),("StyleSheet".into(),"2\n<b>\n</b>\n".into()),("Compact".into(),"Yes".into()),("KeyCaseSensitive".into(),"No".into()),("StripKey".into(),"No".into())]);let rows=vec![studio_core::Entry{key:"字".into(),text:"`2`first".into()},studio_core::Entry{key:"字".into(),text:"second".into()}];
  studio_database::import_mdx_rows(&rows,&source,&"a".repeat(64),&attrs,&mut studio_database::Job::new(&token,&mut |_|{})).unwrap();let info=studio_database::read_for_rebuild(&source,&mut studio_database::Job::new(&token,&mut |_|{})).unwrap();
  let request=Request::DbEditMetadata{source:source.clone(),destination:dest.clone(),expected_source_sha256:info.source_sha256,edits:studio_database::MetadataEdits{title:Some("new 字".into()),description:Some("hi new world".into()),stylesheet:Some("2\n<span style=\"color:#008000\">\n</span>\n".into())}};assert_eq!(request.operation(),"db_edit_metadata");
  let cancelled=CancellationToken::default();let stop=cancelled.clone();let mut progress=|p:Progress|if p.phase=="database_insert"{stop.cancel();};assert_eq!(execute(&request,&mut ImportJob::new("cancel",&cancelled,&mut progress)).unwrap_err().code,ErrorCode::Cancelled);assert!(!dest.exists());
  let receipt=execute(&request,&mut ImportJob::new("copy",&token,&mut |_|{})).unwrap();let studio_database::Response::DbEditMetadata(receipt)=receipt else{panic!()};assert_eq!(receipt.rows_sha256,info.rows_sha256);assert_eq!(receipt.dictionary_metadata.as_ref().unwrap()["Title"],"new 字");
  let rebuilt=crate::database_mdx::execute(&dest,&dir.path().join("edited.mdx"),&mut ImportJob::new("rebuild",&token,&mut |_|{})).unwrap();assert_eq!(rebuilt.dictionary_metadata["Title"],"new 字");assert_eq!(rebuilt.dictionary_metadata["Description"],"hi new world");assert_eq!(rebuilt.dictionary_metadata["StyleSheet"],"2\n<span style=\"color:#008000\">\n</span>\n");
 }
 #[test]fn jsonl_import_route_maps_cancellation_and_receipts() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("rows.jsonl");let dest=dir.path().join("rows.db");std::fs::write(&source,b"{\"key\":\"a\",\"text\":\"first\"}\n{\"key\":\"a\",\"text\":\"second\"}\n").unwrap();
  let request=Request::JsonlToDb {source,destination:dest.clone()};assert_eq!(request.operation(),"jsonl_to_db");assert_eq!(request.destination(),dest.as_path());
  let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase=="database_insert"{stop.cancel();};assert_eq!(execute(&request,&mut ImportJob::new("cancel",&token,&mut progress)).unwrap_err().code,ErrorCode::Cancelled);assert!(!dest.exists());
  let token=CancellationToken::default();let response=execute(&request,&mut ImportJob::new("import",&token,&mut |_|{})).unwrap();match response {studio_database::Response::JsonlToDb(p)=>assert_eq!(p.records,2),_=>panic!("Wrong receipt")};assert!(dest.exists());
 }
 #[test]fn prefix_page_defaults_to_exact_and_requires_a_query() {
  let legacy:PageRequest=serde_json::from_str(r#"{"source":"input.db","query":"app","offset":0,"limit":2,"expected_source_sha256":null}"#).unwrap();
  assert!(!legacy.prefix);assert!(legacy.validate().is_ok());
  let invalid:PageRequest=serde_json::from_str(r#"{"source":"input.db","query":null,"prefix":true,"offset":0,"limit":2,"expected_source_sha256":null}"#).unwrap();assert!(invalid.validate().is_err());
 }
 #[test]fn database_pages_pin_source_identity_and_cancel_without_touching_input() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.txt");let db=dir.path().join("test.db");std::fs::write(&source,"字\nfirst\n</>\n字\nsecond\n</>\n").unwrap();
  let token=CancellationToken::default();execute(&Request::TxtToDb{source,destination:db.clone(),profile:studio_core::TxtProfile::CanonicalV1},&mut ImportJob::new("create",&token,&mut |_|{})).unwrap();let before=std::fs::read(&db).unwrap();
  let mut r=PageRequest{source:db.clone(),query:None,prefix:false,offset:0,limit:1,expected_source_sha256:None};let first=page(&r,&mut ImportJob::new("browse",&token,&mut |_|{})).unwrap();assert_eq!(first.total,2);assert_eq!(first.next_offset,Some(1));
  r.offset=1;r.query=Some("字".into());r.expected_source_sha256=Some(first.source_sha256);let second=page(&r,&mut ImportJob::new("next",&token,&mut |_|{})).unwrap();assert_eq!(second.rows[0].text,"second");
  r.expected_source_sha256=Some("0".repeat(64));assert_eq!(page(&r,&mut ImportJob::new("changed",&token,&mut |_|{})).unwrap_err().code,ErrorCode::Integrity);
  r.expected_source_sha256=None;let stop=token.clone();let mut progress=|p:Progress|if p.phase=="database_page"{stop.cancel();};assert_eq!(page(&r,&mut ImportJob::new("cancel",&token,&mut progress)).unwrap_err().code,ErrorCode::Cancelled);assert_eq!(std::fs::read(&db).unwrap(),before);
  assert!(crate::Request::DatabasePage(r).destination().is_none());
 }
 #[test]fn shared_database_publication_preserves_rows_and_errors_and_cancels() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("in.txt");let db=dir.path().join("out.db");
  std::fs::write(&source,"字\nfirst\n\nline\n</>\n字\nsecond\n</>\n").unwrap();
  let r=Request::TxtToDb{source:source.clone(),destination:db.clone(),profile:studio_core::TxtProfile::CanonicalV1};
  let token=CancellationToken::default();execute(&r,&mut ImportJob::new("db",&token,&mut |_|{})).unwrap();
  let before=std::fs::read(&db).unwrap();assert_eq!(execute(&r,&mut ImportJob::new("exists",&token,&mut |_|{})).unwrap_err().code,ErrorCode::DestinationExists);assert_eq!(std::fs::read(&db).unwrap(),before);
  let out=dir.path().join("roundtrip.txt");execute(&Request::DbToTxt{source:db,destination:out.clone()},&mut ImportJob::new("export",&token,&mut |_|{})).unwrap();assert_eq!(std::fs::read(out).unwrap(),std::fs::read(&source).unwrap());
  for export in [false,true] {
   let token=CancellationToken::default();let dest=dir.path().join(if export{"cancel.txt"}else{"cancel.db"});let stop=token.clone();let mut progress=|p:Progress|if p.phase=="database_commit"{stop.cancel();};
   let r=if export {Request::DbToTxt{source:dir.path().join("out.db"),destination:dest.clone()}}else{Request::TxtToDb{source:source.clone(),destination:dest.clone(),profile:studio_core::TxtProfile::CanonicalV1}};
   assert_eq!(execute(&r,&mut ImportJob::new("cancel",&token,&mut progress)).unwrap_err().code,ErrorCode::Cancelled);assert!(!dest.exists());
  }
 }
 #[test]fn database_uses_exclusive_shared_budget_and_rejects_lookup_ipc() {
  let budget=Budget::new(AdmissionLimits::default()).unwrap();let reader=budget.reserve(Operation::Reader).unwrap();
  assert!(budget.reserve(Operation::CcPacking).is_err());drop(reader);let db=budget.reserve(Operation::CcPacking).unwrap();assert!(budget.reserve(Operation::Reader).is_err());drop(db);assert_eq!(budget.snapshot().active_operations,0);
  assert!(serde_json::from_str::<Request>(r#"{"operation":"lookup","source":"x","query":"a","offset":0,"limit":1}"#).is_err());
 }
}
