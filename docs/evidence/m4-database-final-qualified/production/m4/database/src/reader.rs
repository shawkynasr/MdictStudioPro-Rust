//! An owned, private SQLite snapshot. Desktop admission/lifecycle routing is separate.
use super::*;

#[derive(Clone,Debug,Serialize)]
pub struct ReaderInfo {
 pub profile:&'static str,
 pub database_profile:&'static str,
 pub source_sha256:String,
 pub rows_sha256:String,
 pub records:usize,
 #[serde(skip_serializing_if="Option::is_none")]
 pub dictionary_metadata:Option<BTreeMap<String,String>>,
}

#[derive(Clone,Copy,Debug)]
pub enum ReaderQuery<'a> {All,Exact(&'a str),Prefix(&'a str),LowerExact(&'a str),LowerPrefix(&'a str),Pattern(&'a str),LowerPattern(&'a str),Definition(&'a str),LowerDefinition(&'a str)}

/// One owner retains one fully validated read-only snapshot until close or drop.
/// Opening a new reader is required to observe changes to the original source.
pub struct Reader {checked:Option<Checked>}
impl Reader {
 pub fn open(source:&Path,job:&mut Job<'_>)->Result<Self> {
  let result:Result<Self>=(|| {
   let checked=open_checked(source,job)?;
   job.tick("database_reader_ready",checked.records,checked.records)?;
   Ok(Self {checked:Some(checked)})
  })();
  match result {Err(e) if e.code=="sqlite"=>{job.check()?;Err(e)},other=>other}
 }
 pub fn info(&self)->Result<ReaderInfo> {
  let c=self.checked.as_ref().ok_or_else(||error("closed","Database reader is closed"))?;
  Ok(ReaderInfo {profile:"sqlite-persistent-reader-v1",database_profile:c.db_profile,source_sha256:c.source_sha256.clone(),rows_sha256:c.rows_sha256.clone(),records:c.records,dictionary_metadata:c.dictionary_metadata.clone()})
 }
 /// Supply a fresh Job per operation. Cancellation and work budgets belong to
 /// that operation, so an interrupted page does not poison subsequent queries.
 pub fn page(&mut self,query:ReaderQuery<'_>,offset:u64,limit:usize,job:&mut Job<'_>)->Result<Page> {
  let checked=self.checked.as_mut().ok_or_else(||error("closed","Database reader is closed"))?;
  let definition=matches!(query,ReaderQuery::Definition(_)|ReaderQuery::LowerDefinition(_));
  let (query,prefix,lower,wildcard)=match query {ReaderQuery::All=>(None,false,false,false),ReaderQuery::Exact(q)=>(Some(q),false,false,false),ReaderQuery::Prefix(q)=>(Some(q),true,false,false),ReaderQuery::LowerExact(q)=>(Some(q),false,true,false),ReaderQuery::LowerPrefix(q)=>(Some(q),true,true,false),ReaderQuery::Pattern(q)=>(Some(q),false,false,true),ReaderQuery::LowerPattern(q)=>(Some(q),false,true,true),ReaderQuery::Definition(q)=>(Some(q),false,false,false),ReaderQuery::LowerDefinition(q)=>(Some(q),false,true,false)};
  job.check()?;
  if query.is_some_and(|q|q.is_empty()||q.len()>4096||q.contains('\0'))||limit==0||limit>PAGE_CAP||offset>RECORD_CAP as u64 {
   return Err(error("invalid_input","Require a nonempty <=4 KiB key, offset <=100,000 and page 1..128"));
  }
  let result=(|| {configure(&mut checked.connection,job)?;if lower || wildcard || definition {scan_page(checked,query.unwrap(),prefix,lower,wildcard,definition,offset,limit,job)}else{checked_page(checked,query,prefix,offset,limit,job)}})();
  match result {Err(e) if e.code=="sqlite"=>{job.check()?;Err(e)},other=>other}
 }
 /// Idempotent. Drops the connection before removing its private snapshot.
 pub fn close(&mut self) {self.checked.take();}
}

// The reviewed Unicode16 root-lower algorithm and table are reused by path;
// neither compiler casing nor SQLite's ASCII-only lower/NOCASE determines matches.
fn scan_page(checked:&Checked,query:&str,prefix:bool,lower:bool,wildcard:bool,definition:bool,offset:u64,limit:usize,job:&mut Job<'_>)->Result<Page> {
 static CASING:std::sync::OnceLock<std::result::Result<casing::Casing,String>>=std::sync::OnceLock::new();
 job.tick("database_page",0,checked.records)?;
 let casing=if lower{Some(CASING.get_or_init(||casing::Casing::pinned16().map_err(|e|e.to_string())).as_ref().map_err(|e|error("internal",e.clone()))?)}else{None};
 let needle=casing.map_or_else(||query.to_owned(),|c|c.lower(query));
 let pattern=if wildcard{Some(pattern::Pattern::compile(&needle)?)}else{None};let mut work=pattern::Work::new();let phase=if definition{"database_definition_scan"}else if wildcard{"database_pattern_scan"}else{"database_case_scan"};let mut stmt=checked.connection.prepare("SELECT rowid,entry,paraphrase FROM mdx ORDER BY rowid")?;let mut cursor=stmt.query([])?;
 let mut total=0u64;let mut scanned=0usize;let mut rows=Vec::new();let mut bytes=0usize;
 while let Some(row)=cursor.next()? {
  job.check()?;let key=text(row,1,4096)?;
  let body=if definition{Some(text(row,2,BODY_CAP)?)}else{None};
  let candidate=body.as_deref().unwrap_or(&key);let normalized=casing.map_or_else(||candidate.to_owned(),|c|c.lower(candidate));
  let matches=if definition{normalized.contains(&needle)}else if let Some(pattern)=&pattern{pattern.matches(&normalized,&mut work,job)?}else if prefix{normalized.starts_with(&needle)}else{normalized==needle};
  if matches {
   if total>=offset && rows.len()<limit {
    let rowid:i64=row.get(0)?;let text=match body {Some(body)=>body,None=>text(row,2,BODY_CAP)?};bytes+=key.len()+text.len();
    if bytes>REPLY_CAP{return Err(error("limit_exceeded","Complete database page exceeds 2 MiB"));}
    rows.push(Match{rowid:rowid.to_string(),key,text});
   }
   total+=1;
  }
  scanned+=1;if scanned%256==0{job.tick(phase,scanned,checked.records)?;}
 }
 job.tick(phase,scanned,checked.records)?;
 let next=offset.min(total)+rows.len() as u64;
 let page=Page{profile:checked.db_profile,source_sha256:checked.source_sha256.clone(),total,offset,next_offset:if next<total{Some(next)}else{None},rows,dictionary_metadata:checked.dictionary_metadata.clone()};
 if serde_json::to_vec(&page).map_err(|e|error("internal",e.to_string()))?.len()>REPLY_CAP{return Err(error("limit_exceeded","Serialized database page exceeds 2 MiB"));}
 job.check()?;Ok(page)
}

#[cfg(test)]
mod tests {
 use super::*;
 fn seed(path:&Path) {
  let c=Connection::open(path).unwrap();c.execute_batch(MDX_SQL).unwrap();
  for (key,body) in [("apple","first"),("application","app"),("Apple","upper"),("apple","second"),("a%b","percent"),("a_b","underscore"),("字典","Chinese"),("مرحبا","Arabic")] {
   c.execute("INSERT INTO mdx VALUES (?1,?2)",params![key,body]).unwrap();
  }
 }
 fn open(path:&Path)->Reader {Reader::open(path,&mut Job::new(&CancellationToken::default(),&mut |_|{})).unwrap()}
 fn page(reader:&mut Reader,query:ReaderQuery<'_>,offset:u64,limit:usize)->Result<Page> {reader.page(query,offset,limit,&mut Job::new(&CancellationToken::default(),&mut |_|{}))}

 fn definition_seed(path:&Path) {
  let c=Connection::open(path).unwrap();c.execute_batch(MDX_SQL).unwrap();for line in include_str!("../../../m3/fixtures/database-definition.jsonl").lines(){let row:Entry=serde_json::from_str(line).unwrap();c.execute("INSERT INTO mdx VALUES (?1,?2)",params![row.key,row.text]).unwrap();}
 }
 #[test]fn definition_search_matches_stored_text_literals_unicode_and_duplicate_rows() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("definitions.db");definition_seed(&source);let before=fs::read(&source).unwrap();let mut reader=open(&source);
  for (q,ids) in [("needle",vec!["3"]),("Needle",vec!["1"]),("NEEDLE",vec!["2"]),("中文",vec!["5","6"]),("أهلاً",vec!["7"]),("<div",vec!["1","7"]),("`2`",vec!["4"]),("? * % _",vec!["4"]),("\\",vec!["4"]),("missing",vec![])]{
   let p=page(&mut reader,ReaderQuery::Definition(q),0,16).unwrap();assert_eq!(p.rows.iter().map(|r|r.rowid.as_str()).collect::<Vec<_>>(),ids,"{q}");
  }
  for (q,total) in [("école",1),("ΟΣ",1),("οσ",0),("İ",1),("straße",1),("STRASSE",0),("𐐨",1)]{assert_eq!(page(&mut reader,ReaderQuery::LowerDefinition(q),0,16).unwrap().total,total,"{q}");}
  let a=page(&mut reader,ReaderQuery::LowerDefinition("nEeDlE"),0,2).unwrap();let b=page(&mut reader,ReaderQuery::LowerDefinition("nEeDlE"),2,2).unwrap();assert_eq!(a.total,3);assert_eq!(a.next_offset,Some(2));assert_eq!(b.next_offset,None);assert_eq!(a.rows.iter().chain(b.rows.iter()).map(|r|r.rowid.as_str()).collect::<Vec<_>>(),["1","2","3"]);assert_eq!(a.rows[1].key,"apple");assert_eq!(a.rows[1].text,"Second NEEDLE definition.");assert_eq!(page(&mut reader,ReaderQuery::Exact("needle"),0,16).unwrap().rows[0].rowid,"10");assert_eq!(fs::read(source).unwrap(),before);
 }
 #[test]fn definition_scan_cancellation_snapshot_and_page_overflow_allow_retry() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("definitions.db");definition_seed(&source);let mut reader=open(&source);
  let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase=="database_definition_scan"{stop.cancel();};assert_eq!(reader.page(ReaderQuery::Definition("definition"),0,2,&mut Job::new(&token,&mut progress)).unwrap_err().code,"cancelled");
  assert_eq!(page(&mut reader,ReaderQuery::Definition(""),0,2).unwrap_err().code,"invalid_input");assert_eq!(page(&mut reader,ReaderQuery::Definition("x"),0,0).unwrap_err().code,"invalid_input");
  fs::remove_file(&source).unwrap();assert_eq!(page(&mut reader,ReaderQuery::LowerDefinition("needle"),0,2).unwrap().total,3);reader.close();
  let c=Connection::open(&source).unwrap();c.execute_batch(MDX_SQL).unwrap();for _ in 0..3{c.execute("INSERT INTO mdx VALUES ('a',?1)",params!["x".repeat(BODY_CAP)]).unwrap();}drop(c);let mut reader=open(&source);
  assert_eq!(page(&mut reader,ReaderQuery::Definition("x"),0,3).unwrap_err().code,"limit_exceeded");assert_eq!(page(&mut reader,ReaderQuery::Definition("x"),0,1).unwrap().total,3);
 }
 #[test]fn pattern_pages_preserve_literal_modes_unicode_duplicates_and_original_rows() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("pattern.db");let c=Connection::open(&source).unwrap();c.execute_batch(MDX_SQL).unwrap();
  for (key,body) in [("apple","first"),("application","app"),("Apple","upper"),("apple","second"),("a?b","question"),("a*b","star"),("a%b","percent"),("a_b","underscore"),("a字b","Chinese"),("a𐐀b","non-BMP"),("abc","other"),("مرحبا","Arabic")] {c.execute("INSERT INTO mdx VALUES (?1,?2)",params![key,body]).unwrap();}drop(c);let before=fs::read(&source).unwrap();let mut reader=open(&source);
  for (pattern,ids) in [("a?b",vec!["5","6","7","8","9","10"]),(r"a\?b",vec!["5"]),(r"a\*b",vec!["6"]),("a%b",vec!["7"]),("a_b",vec!["8"]),("*字*",vec!["9"]),("مر*",vec!["12"]),("?apple",vec![])] {
   let p=page(&mut reader,ReaderQuery::Pattern(pattern),0,16).unwrap();assert_eq!(p.rows.iter().map(|r|r.rowid.as_str()).collect::<Vec<_>>(),ids);
  }
  let first=page(&mut reader,ReaderQuery::LowerPattern("aPp*"),0,2).unwrap();let second=page(&mut reader,ReaderQuery::LowerPattern("aPp*"),2,2).unwrap();assert_eq!(first.total,4);assert_eq!(first.next_offset,Some(2));assert_eq!(second.next_offset,None);assert_eq!(second.rows[0].key,"Apple");assert_eq!(second.rows[1].text,"second");
  assert_eq!(page(&mut reader,ReaderQuery::Exact("a?b"),0,16).unwrap().total,1);assert_eq!(page(&mut reader,ReaderQuery::Prefix("a*"),0,16).unwrap().total,1);assert_eq!(page(&mut reader,ReaderQuery::Pattern("*"),0,2).unwrap().total,12);assert_eq!(fs::read(source).unwrap(),before);
 }
 #[test]fn pattern_errors_and_cancelled_scan_leave_reader_usable() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");seed(&source);let mut reader=open(&source);
  assert_eq!(page(&mut reader,ReaderQuery::Pattern("a\\"),0,2).unwrap_err().code,"invalid_input");
  let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase=="database_pattern_scan"{stop.cancel();};assert_eq!(reader.page(ReaderQuery::Pattern("*"),0,2,&mut Job::new(&token,&mut progress)).unwrap_err().code,"cancelled");
  assert_eq!(page(&mut reader,ReaderQuery::Pattern("app*"),0,2).unwrap().total,3);
 }

 #[test]fn unicode16_lower_matches_without_merging_rows_or_interpreting_punctuation() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("case.db");let c=Connection::open(&source).unwrap();c.execute_batch(MDX_SQL).unwrap();
  for (i,key) in ["apple","application","Apple","apple","École","école","ΟΣ","ος","οσ","İ","i\u{307}","i","Straße","STRASSE","A%B","a_b","字典","مرحبا","𐐀","𐐨"].iter().enumerate(){c.execute("INSERT INTO mdx VALUES (?1,?2)",params![key,i.to_string()]).unwrap();}drop(c);let before=fs::read(&source).unwrap();let mut reader=open(&source);
  for (query,expected) in [("éCOLE",vec!["5","6"]),("ΟΣ",vec!["7","8"]),("οσ",vec!["9"]),("İ",vec!["10","11"]),("i",vec!["12"]),("straße",vec!["13"]),("STRASSE",vec!["14"]),("𐐀",vec!["19","20"])] {
   let p=page(&mut reader,ReaderQuery::LowerExact(query),0,16).unwrap();assert_eq!(p.rows.iter().map(|r|r.rowid.as_str()).collect::<Vec<_>>(),expected);
  }
  for (query,expected) in [("a%",vec!["15"]),("A_",vec!["16"]),("字",vec!["17"]),("مر",vec!["18"])]{
   let p=page(&mut reader,ReaderQuery::LowerPrefix(query),0,16).unwrap();assert_eq!(p.rows.iter().map(|r|r.rowid.as_str()).collect::<Vec<_>>(),expected);
  }
  let a=page(&mut reader,ReaderQuery::LowerPrefix("aPp"),0,2).unwrap();let b=page(&mut reader,ReaderQuery::LowerPrefix("aPp"),2,2).unwrap();assert_eq!(a.total,4);assert_eq!(a.next_offset,Some(2));assert_eq!(b.next_offset,None);assert_eq!(a.rows.iter().chain(b.rows.iter()).map(|r|r.rowid.as_str()).collect::<Vec<_>>(),["1","2","3","4"]);
  assert_eq!(page(&mut reader,ReaderQuery::Prefix("aPp"),0,2).unwrap().total,0);assert_eq!(page(&mut reader,ReaderQuery::Exact("apple"),0,16).unwrap().total,2);assert_eq!(fs::read(source).unwrap(),before);
 }
 #[test]fn lower_scan_cancellation_and_reply_overflow_allow_retry() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("case.db");let c=Connection::open(&source).unwrap();c.execute_batch(MDX_SQL).unwrap();for _ in 0..3 {c.execute("INSERT INTO mdx VALUES ('Apple',?1)",params!["x".repeat(800000)]).unwrap();}drop(c);let mut reader=open(&source);
  let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase=="database_case_scan"{stop.cancel();};
  assert_eq!(reader.page(ReaderQuery::LowerExact("APPLE"),0,1,&mut Job::new(&token,&mut progress)).unwrap_err().code,"cancelled");
  assert_eq!(page(&mut reader,ReaderQuery::LowerExact("apple"),0,3).unwrap_err().code,"limit_exceeded");assert_eq!(page(&mut reader,ReaderQuery::LowerExact("apple"),0,1).unwrap().rows.len(),1);
 }

 #[test]fn snapshot_is_pinned_across_edits_and_source_deletion() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");seed(&source);
  let mut reader=open(&source);let original=reader.info().unwrap();
  let c=Connection::open(&source).unwrap();c.execute("UPDATE mdx SET paraphrase='edited' WHERE rowid=1",[]).unwrap();drop(c);
  let mut newer=open(&source);assert_ne!(newer.info().unwrap().source_sha256,original.source_sha256);
  assert_eq!(page(&mut newer,ReaderQuery::All,0,1).unwrap().rows[0].text,"edited");
  fs::remove_file(&source).unwrap();
  assert_eq!(page(&mut reader,ReaderQuery::All,0,1).unwrap().rows[0].text,"first");
  assert_eq!(reader.info().unwrap().source_sha256,original.source_sha256);
 }
 #[test]fn repeated_queries_preserve_order_duplicates_literals_and_skip_validation() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");seed(&source);let mut reader=open(&source);
  let mut phases=Vec::new();let token=CancellationToken::default();let mut progress=|p:Progress|phases.push(p.phase);
  for (query,offset,expected,total,next) in [(ReaderQuery::Prefix("app"),0,vec!["1","2"],3,Some(2)),(ReaderQuery::Prefix("app"),2,vec!["4"],3,None),(ReaderQuery::Exact("apple"),0,vec!["1","4"],2,None),(ReaderQuery::Prefix("App"),0,vec!["3"],1,None),(ReaderQuery::Prefix("a%"),0,vec!["5"],1,None),(ReaderQuery::Prefix("a_"),0,vec!["6"],1,None),(ReaderQuery::Prefix("字"),0,vec!["7"],1,None),(ReaderQuery::Prefix("مر"),0,vec!["8"],1,None),(ReaderQuery::Exact("missing"),0,vec![],0,None)] {
   let p=reader.page(query,offset,2,&mut Job::new(&token,&mut progress)).unwrap();assert_eq!(p.total,total);assert_eq!(p.next_offset,next);assert_eq!(p.rows.iter().map(|r|r.rowid.as_str()).collect::<Vec<_>>(),expected);
  }
  assert_eq!(phases,vec!["database_page";9]);
 }
 #[test]fn cancellation_and_expired_budgets_do_not_poison_later_pages() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");seed(&source);
  let opening=CancellationToken::default();let mut reader=Reader::open(&source,&mut Job::new(&opening,&mut |_|{})).unwrap();opening.cancel();
  assert_eq!(page(&mut reader,ReaderQuery::All,0,2).unwrap().rows.len(),2);
  let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase=="database_page"{stop.cancel();};
  assert_eq!(reader.page(ReaderQuery::All,0,2,&mut Job::new(&token,&mut progress)).unwrap_err().code,"cancelled");
  assert_eq!(page(&mut reader,ReaderQuery::All,0,2).unwrap().rows.len(),2);
  // Interrupt a running SQLite VM, then prove a new page replaces its hook.
  let vm_token=CancellationToken::default();let mut noop=|_|{};let vm_job=Job::new(&vm_token,&mut noop);
  let checked=reader.checked.as_mut().unwrap();configure(&mut checked.connection,&vm_job).unwrap();vm_token.cancel();
  let interrupted:std::result::Result<i64,rusqlite::Error>=checked.connection.query_row("WITH RECURSIVE t(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM t WHERE x<10000) SELECT sum(x) FROM t",[],|r|r.get(0));
  assert!(matches!(interrupted,Err(rusqlite::Error::SqliteFailure(e,_)) if e.code==rusqlite::ErrorCode::OperationInterrupted));
  assert_eq!(page(&mut reader,ReaderQuery::All,0,2).unwrap().rows.len(),2);
  let token=CancellationToken::default();let mut progress=|_|{};let mut job=Job::new(&token,&mut progress);job.deadline=Instant::now()-Duration::from_secs(1);
  assert_eq!(reader.page(ReaderQuery::All,0,2,&mut job).unwrap_err().code,"limit_exceeded");
  assert_eq!(page(&mut reader,ReaderQuery::All,0,2).unwrap().rows.len(),2);
 }
 #[test]fn opening_can_cancel_before_and_after_snapshot_validation() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");seed(&source);let before=fs::read(&source).unwrap();
  for phase in ["database_snapshot","database_reader_ready"] {
   let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase==phase{stop.cancel();};
   let result=Reader::open(&source,&mut Job::new(&token,&mut progress));assert!(matches!(result,Err(Error{code:"cancelled",..})));
  }
  assert_eq!(fs::read(&source).unwrap(),before);
 }
 #[test]fn close_and_drop_remove_private_snapshot_and_closed_readers_refuse_work() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");seed(&source);let mut reader=open(&source);
  let snapshot=reader.checked.as_ref().unwrap()._snapshot.path().to_owned();assert!(snapshot.exists());reader.close();reader.close();assert!(!snapshot.exists());
  assert_eq!(reader.info().unwrap_err().code,"closed");assert_eq!(page(&mut reader,ReaderQuery::All,0,1).unwrap_err().code,"closed");
  let reader=open(&source);let snapshot=reader.checked.as_ref().unwrap()._snapshot.path().to_owned();drop(reader);assert!(!snapshot.exists());assert!(source.exists());
 }
 #[test]fn page_limits_and_overflow_leave_reader_usable() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");let c=Connection::open(&source).unwrap();c.execute_batch(MDX_SQL).unwrap();
  for _ in 0..3 {c.execute("INSERT INTO mdx VALUES ('same',?1)",params!["x".repeat(800000)]).unwrap();}drop(c);let mut reader=open(&source);
  for (query,offset,limit) in [(ReaderQuery::All,0,0),(ReaderQuery::All,0,129),(ReaderQuery::All,100001,1),(ReaderQuery::Exact(""),0,1),(ReaderQuery::Prefix("a\0b"),0,1)] {
   assert_eq!(page(&mut reader,query,offset,limit).unwrap_err().code,"invalid_input");
  }
  assert_eq!(page(&mut reader,ReaderQuery::All,0,3).unwrap_err().code,"limit_exceeded");assert_eq!(page(&mut reader,ReaderQuery::All,0,1).unwrap().rows.len(),1);
 }
 #[test]fn malformed_and_sidecar_sources_are_refused() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");fs::write(&source,b"bad database").unwrap();assert!(Reader::open(&source,&mut Job::new(&CancellationToken::default(),&mut |_|{})).is_err());
  fs::remove_file(&source).unwrap();seed(&source);fs::write(dir.path().join("source.db-wal"),b"sidecar").unwrap();
  assert!(matches!(Reader::open(&source,&mut Job::new(&CancellationToken::default(),&mut |_|{})),Err(Error{code:"unsupported_profile",..})));
 }
}
