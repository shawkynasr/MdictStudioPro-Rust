use super::*;
use studio_indexed_engine::{Row,index::BuildOptions};
fn fixture()->(tempfile::TempDir,OpenRequest) {
 let dir=tempfile::tempdir().unwrap();let source=dir.path().join("redirect.mdx");let artifact=dir.path().join("redirect.idx");
 let mut b=mdictlib::MdxBuilder::with_options(mdictlib::WriteOptions::new().with_legacy_sort(mdictlib::LegacySort::PreserveInput));
 // General v2 import requires an explicit supported content format.
 b.header_attribute("Format","Html").unwrap();
 for (key,text) in [("alias","@@@LINK=middle\r\n"),("bad","@@@LINK=\n"),("cycle","@@@LINK=cycle"),("middle","@@@LINK=target"),("missing","@@@LINK=absent"),("target","<b>first 字</b>"),("target","second مرحبا")] {b.add_entry(key,text).unwrap();}
 b.finish(&mut std::fs::File::create(&source).unwrap()).unwrap();
 let token=CancellationToken::default();let mut cb=|_|{};let mut job=ImportJob::new("seed",&token,&mut cb);
 let dictionary=Dictionary::open_v2(&source,Kind::Mdx,&Limits::default(),&mut job).unwrap();Index::build(&dictionary,&artifact,Policy::RawExact,BuildOptions::default(),&mut job).unwrap();
 (dir,OpenRequest {source,artifact,kind:DictionaryKind::Mdx,policy:Policy::RawExact})
}
fn ready(pool:&Pool,r:OpenRequest)->Session {
 let s=pool.open(r).unwrap();let id=s.open_job_id();assert_eq!(s.wait_job(&id,Duration::from_secs(20)).unwrap().unwrap().state,JobState::Succeeded);s.take_result(&id).unwrap();s.forget(&id).unwrap();s
}
#[test]fn actual_index_follows_chains_duplicates_and_snapshot_with_one_transfer() {
 let (_dir,r)=fixture();let path=r.source.clone();let pool=Pool::new(Config::default()).unwrap();let s=ready(&pool,r);
 std::fs::write(path,b"public source replaced after opening").unwrap();
 let id=s.submit_resolve(ResolveRequest {query:"alias".into(),ordinal:0}).unwrap();
 assert_eq!(s.wait_job(&id,Duration::from_secs(20)).unwrap().unwrap().state,JobState::Succeeded);
 let Some(Response::Resolved(reply))=s.take_result(&id).unwrap() else {panic!("Missing resolved reply")};
 assert_eq!(reply.results.len(),2);assert_eq!(reply.results[0].row.ordinal,5);assert_eq!(reply.results[1].row.ordinal,6);
 assert_eq!(reply.results[0].chain.iter().map(|h|h.target.as_str()).collect::<Vec<_>>(),["middle","target"]);
 assert_eq!(reply.results[1].row.text.as_deref(),Some("second مرحبا"));assert!(s.take_result(&id).unwrap().is_none());s.forget(&id).unwrap();assert_eq!(pool.admission().retained_reply_bytes,0);s.join().unwrap();
}
#[test]fn malformed_missing_cycle_and_selected_ordinal_errors_have_no_partial_reply() {
 let (_dir,r)=fixture();let pool=Pool::new(Config::default()).unwrap();let s=ready(&pool,r);
 for (key,ordinal,detail) in [("bad",1,"redirect_target"),("cycle",2,"redirect_cycle"),("missing",4,"redirect_missing"),("alias",6,"redirect_source")] {
  let id=s.submit_resolve(ResolveRequest {query:key.into(),ordinal}).unwrap();let result=s.wait_job(&id,Duration::from_secs(20)).unwrap().unwrap();assert_eq!(result.state,JobState::Failed);assert_eq!(result.error.unwrap().detail,detail);assert!(s.take_result(&id).unwrap().is_none());s.forget(&id).unwrap();
 }s.join().unwrap();
}
#[test]fn resolve_observes_running_and_commit_cancellation_without_retaining_reply() {
 for phase in ["index_lookup","session_result_commit"] {
  let (_dir,r)=fixture();let token=CancellationToken::default();let stop=token.clone();
  let pool=Pool::with_hook(Config::default(),Arc::new(move|id,p|if id.ends_with("0000000000000002")&&p.phase==phase {stop.cancel();}));
  let s=ready(&pool,r);let id=s.submit_resolve_with_token(ResolveRequest {query:"alias".into(),ordinal:0},token).unwrap();
  assert_eq!(s.wait_job(&id,Duration::from_secs(20)).unwrap().unwrap().state,JobState::Cancelled);assert!(s.take_result(&id).unwrap().is_none());assert_eq!(pool.admission().retained_reply_bytes,0);s.join().unwrap();
 }
}
fn page(rows:Vec<Row>,total:u64)->Page {Page {basis:"exact".into(),offset:0,next_offset:None,total,rows}}
fn row(key:&str,text:&str,ordinal:u64)->Row {Row {key:key.into(),text:Some(text.into()),ordinal,bytes:None}}
#[test]fn depth_match_and_decoded_caps_reject_instead_of_truncating() {
 let token=CancellationToken::default();let r=ResolveRequest {query:"0".into(),ordinal:0};
 let e=redirects::resolve(&r,&token,|key,_,_|{let n=key.parse::<u64>().unwrap();Ok(page(vec![row(key,&format!("@@@LINK={}",n+1),n)],1))}).unwrap_err();assert_eq!(e.detail,"redirect_limit");
 let e=redirects::resolve(&r,&token,|_,_,_|Ok(page(Vec::new(),257))).unwrap_err();assert_eq!(e.detail,"redirect_limit");
 let e=redirects::resolve(&r,&token,|key,_,_|Ok(page(vec![row(key,&"x".repeat(8*1024*1024+1),0)],1))).unwrap_err();assert_eq!(e.detail,"redirect_limit");
}
#[test]fn normalized_target_matches_and_shared_branches_remain_distinct() {
 let r=ResolveRequest {query:"alias".into(),ordinal:0};let token=CancellationToken::default();
 let reply=redirects::resolve(&r,&token,|key,_,_|Ok(match key {
  "alias"=>page(vec![row("alias","@@@LINK=TARGET",0)],1),
  "TARGET"=>{let mut p=page(vec![row("target","@@@LINK=end",1),row("target","@@@LINK=end",2)],2);p.basis="normalized".into();p},
  _=>page(vec![row("end","definition",3)],1)
 })).unwrap();assert_eq!(reply.results.len(),2);assert_eq!(reply.results[0].row.ordinal,3);assert_eq!(reply.results[1].row.ordinal,3);assert_eq!(reply.results[0].chain[1].ordinal,1);assert_eq!(reply.results[1].chain[1].ordinal,2);
}
#[test]fn all_duplicate_target_pages_are_collected_and_partial_branch_failures_discarded() {
 let r=ResolveRequest {query:"alias".into(),ordinal:0};let token=CancellationToken::default();
 let reply=redirects::resolve(&r,&token,|key,offset,_|Ok(if key=="alias" {page(vec![row(key,"@@@LINK=target",0)],1)}else{
  let end=(offset+32).min(33);let mut p=page((offset..end).map(|i|row("target","body",i+1)).collect(),33);p.offset=offset;p.next_offset=if end<33{Some(end)}else{None};p
 })).unwrap();assert_eq!(reply.results.len(),33);assert_eq!(reply.results[32].row.ordinal,33);
 let e=redirects::resolve(&r,&token,|key,_,_|Ok(match key {
  "alias"=>page(vec![row(key,"@@@LINK=target",0)],1),
  "target"=>page(vec![row(key,"good",1),row(key,"@@@LINK=absent",2)],2),
  _=>page(Vec::new(),0)
 })).unwrap_err();assert_eq!(e.detail,"redirect_missing");
 let e=redirects::resolve(&r,&token,|key,_,_|Ok(page(vec![row(key,&"x".repeat(2*1024*1024+1),0)],1))).unwrap_err();assert_eq!(e.detail,"redirect_limit");
}
