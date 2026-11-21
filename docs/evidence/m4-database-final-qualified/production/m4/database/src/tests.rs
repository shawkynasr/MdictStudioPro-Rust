use super::*;
fn run(request:Request)->Response {execute(&request,&mut Job::new(&CancellationToken::default(),&mut |_|{})).unwrap()}
fn seed(dir:&Path)->(PathBuf,PathBuf) {let source=dir.join("source.txt");let db=dir.join("dict.db");fs::write(&source,include_bytes!("../../../m3/fixtures/build-source.txt")).unwrap();(source,db)}
#[test]fn prefix_lookup_is_literal_unicode_case_sensitive_and_duplicate_aware() {
 let dir=tempfile::tempdir().unwrap();let db=dir.path().join("prefix.db");
 let c=Connection::open(&db).unwrap();c.execute_batch(MDX_SQL).unwrap();
 for (key,text) in [("apple","first"),("application","app"),("Apple","upper"),("apple","second"),("a%b","percent"),("a_b","underscore"),("a?b","question"),("a b","space"),("字典","Chinese"),("字","short"),("مرحبا","Arabic"),("مرح","short Arabic")] {c.execute("INSERT INTO mdx VALUES (?1,?2)",params![key,text]).unwrap();}drop(c);
 let before=fs::read(&db).unwrap();
 for (query,expected) in [("app",vec!["apple","application","apple"]),("App",vec!["Apple"]),("a%",vec!["a%b"]),("a_",vec!["a_b"]),("a?",vec!["a?b"]),("a ",vec!["a b"]),("字",vec!["字典","字"]),("مر",vec!["مرحبا","مرح"]),("%",vec![]),("' OR 1=1 --",vec![])] {
  let Response::Lookup(page)=run(Request::PrefixLookup{source:db.clone(),query:query.into(),offset:0,limit:16})else{panic!()};
  assert_eq!(page.total,expected.len() as u64);assert_eq!(page.rows.iter().map(|r|r.key.as_str()).collect::<Vec<_>>(),expected);assert_eq!(page.next_offset,None);
 }
 let mut bodies=Vec::new();let mut rowids=Vec::new();
 for offset in 0..3 {
  let Response::Lookup(page)=run(Request::PrefixLookup{source:db.clone(),query:"app".into(),offset,limit:1})else{panic!()};
  assert_eq!(page.total,3);assert_eq!(page.next_offset,if offset<2{Some(offset+1)}else{None});
  bodies.push(page.rows[0].text.clone());rowids.push(page.rows[0].rowid.clone());
 }
 assert_eq!(bodies,["first","app","second"]);assert_eq!(rowids,["1","2","4"]);
 let Response::Lookup(exact)=run(Request::Lookup{source:db.clone(),query:"app".into(),offset:0,limit:16})else{panic!()};assert_eq!(exact.total,0);
 let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase=="database_page"{stop.cancel();};
 assert_eq!(execute(&Request::PrefixLookup{source:db.clone(),query:"app".into(),offset:0,limit:1},&mut Job::new(&token,&mut progress)).unwrap_err().code,"cancelled");
 assert_eq!(fs::read(&db).unwrap(),before);
}
#[test]fn mdx_origin_rows_preserve_metadata_markers_and_reject_header_corruption() {
 let dir=tempfile::tempdir().unwrap();let db=dir.path().join("mdx.db");let rows=vec![Entry{key:"字".into(),text:"`2`blue\n\n".into()},Entry{key:"字".into(),text:"</>\nembedded TXT delimiter".into()}];
 let attrs=BTreeMap::from([("Title".into(),"字".repeat(2000)),("Description".into(),"العربية & description".into()),("StyleSheet".into(),"2\n<span style=\"color:blue\">\n</span>\n".into())]);let token=CancellationToken::default();
 let receipt=import_mdx_rows(&rows,&db,&"a".repeat(64),&attrs,&mut Job::new(&token,&mut |_|{})).unwrap();assert_eq!(receipt.profile,MDX_PROFILE);assert_eq!(receipt.dictionary_metadata.as_ref(),Some(&attrs));
 let mut reader=Reader::open(&db,&mut Job::new(&token,&mut |_|{})).unwrap();assert_eq!(reader.info().unwrap().dictionary_metadata.as_ref(),Some(&attrs));
 let persistent=reader.page(ReaderQuery::All,0,2,&mut Job::new(&token,&mut |_|{})).unwrap();assert_eq!(persistent.dictionary_metadata.as_ref(),Some(&attrs));assert_eq!(persistent.rows[0].text,rows[0].text);reader.close();
 let Response::Browse(page)=run(Request::Browse{source:db.clone(),offset:0,limit:2})else{panic!()};assert_eq!(page.dictionary_metadata,Some(attrs));assert_eq!(page.rows[0].text,rows[0].text);assert_eq!(page.rows[1].text,rows[1].text);
 let out=dir.path().join("unrepresentable.txt");assert!(execute(&Request::DbToTxt{source:db.clone(),destination:out.clone()},&mut Job::new(&token,&mut |_|{})).is_err());assert!(!out.exists());
 let c=Connection::open(&db).unwrap();c.execute("UPDATE studio_meta SET value='{}' WHERE key='mdx_header_json'",[]).unwrap();drop(c);
 assert_eq!(execute(&Request::Browse{source:db,offset:0,limit:1},&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"integrity");
}
#[test]fn browse_pages_preserve_order_empty_bodies_and_full_precision_rowids() {
 let dir=tempfile::tempdir().unwrap();let(source,db)=seed(dir.path());run(Request::TxtToDb {source,destination:db.clone(),profile:TxtProfile::CanonicalV1});let before=fs::read(&db).unwrap();
 let mut offset=0;let mut rows=Vec::new();
 loop {let Response::Browse(page)=run(Request::Browse {source:db.clone(),offset,limit:2})else{panic!()};assert_eq!(page.total,5);rows.extend(page.rows.into_iter().map(|r|(r.key,r.text)));if let Some(next)=page.next_offset{offset=next;}else{break;}}
 assert_eq!(rows.iter().map(|r|r.0.as_str()).collect::<Vec<_>>(),["apple","字","字","مرحبا","empty"]);assert_eq!(rows[4].1,"");assert_ne!(rows[1].1,rows[2].1);assert_eq!(fs::read(&db).unwrap(),before);
 let large=dir.path().join("rowid.db");let c=Connection::open(&large).unwrap();c.execute_batch(MDX_SQL).unwrap();c.execute("INSERT INTO mdx(rowid,entry,paraphrase) VALUES (9007199254740993,'a?%_','literal')",[]).unwrap();drop(c);
 let Response::Browse(page)=run(Request::Browse {source:large.clone(),offset:0,limit:1})else{panic!()};assert_eq!(page.rows[0].rowid,"9007199254740993");
 let Response::Lookup(page)=run(Request::Lookup {source:large.clone(),query:"a?%_".into(),offset:0,limit:1})else{panic!()};assert_eq!(page.total,1);
 let Response::Lookup(page)=run(Request::Lookup {source:large,query:"A?%_".into(),offset:0,limit:1})else{panic!()};assert_eq!(page.total,0);
}
#[test]fn studio_roundtrip_preserves_duplicates_multilingual_and_blank_lines() {
 let dir=tempfile::tempdir().unwrap();let(source,db)=seed(dir.path());let before=fs::read(&source).unwrap();
 let Response::TxtToDb(receipt)=run(Request::TxtToDb {source:source.clone(),destination:db.clone(),profile:TxtProfile::CanonicalV1})else{panic!()};assert_eq!(receipt.records,5);
 let token=CancellationToken::default();let expected=studio_core::parse_txt(&before,TxtProfile::CanonicalV1,&limits(),&mut studio_core::JobContext::new(&token,&mut |_|{})).unwrap();
 let connection=Connection::open(&db).unwrap();let count:i64=connection.query_row("SELECT count(*) FROM mdx",[],|r|r.get(0)).unwrap();assert_eq!(count,5);drop(connection);
 let query=expected.iter().find(|row|expected.iter().filter(|other|other.key==row.key).count()>1).unwrap().key.clone();
 let Response::Lookup(page)=run(Request::Lookup {source:db.clone(),query:query.clone(),offset:0,limit:1})else{panic!()};assert_eq!(page.total,2);assert_eq!(page.rows.len(),1);assert_eq!(page.next_offset,Some(1));
 let Response::Lookup(next)=run(Request::Lookup {source:db.clone(),query,offset:1,limit:1})else{panic!()};assert_eq!(next.rows.len(),1);assert_ne!(page.rows[0].rowid,next.rows[0].rowid);
 let Response::Lookup(missing)=run(Request::Lookup {source:db.clone(),query:"not-present".into(),offset:0,limit:1})else{panic!()};assert_eq!(missing.total,0);assert!(missing.rows.is_empty());assert_eq!(missing.next_offset,None);
 let out=dir.path().join("export.txt");run(Request::DbToTxt {source:db,destination:out.clone()});let actual=studio_core::read_txt(&out,TxtProfile::CanonicalV1,&limits(),&mut studio_core::JobContext::new(&token,&mut |_|{})).unwrap();assert_eq!(actual,expected);assert_eq!(fs::read(&source).unwrap(),before);
}
#[test]fn legacy_two_text_columns_are_imported_in_rowid_order() {
 let dir=tempfile::tempdir().unwrap();let db=dir.path().join("legacy.db");let c=Connection::open(&db).unwrap();c.execute_batch(MDX_SQL).unwrap();for text in ["first\n\nline","", "third"]{c.execute("INSERT INTO mdx VALUES (?1,?2)",params!["字",text]).unwrap();}drop(c);
 let out=dir.path().join("export.txt");run(Request::DbToTxt {source:db,destination:out.clone()});let data=fs::read_to_string(&out).unwrap();assert!(data.contains("first\n\nline"));assert!(data.find("first").unwrap()<data.find("third").unwrap());
}
#[test]fn legacy_body_span_profile_retains_crlf_body_without_conversion() {
 let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.txt");let db=dir.path().join("dict.db");fs::write(&source,b"word\r\nbody\r\n\r\n</>\r\n").unwrap();run(Request::TxtToDb {source,destination:db.clone(),profile:TxtProfile::LegacyBodySpanV1});
 let out=dir.path().join("out.txt");run(Request::DbToTxt {source:db,destination:out.clone()});assert_eq!(fs::read(out).unwrap(),b"word\nbody\r\n\r\n</>\n");
}
#[test]fn bad_schemas_types_compressed_cells_and_unrepresentable_txt_are_refused() {
 for schema in ["CREATE TABLE mdx(entry TEXT NOT NULL, paraphrase BLOB NOT NULL)","CREATE TABLE other(entry TEXT NOT NULL, paraphrase TEXT NOT NULL)","CREATE TABLE data(x TEXT); CREATE VIEW mdx AS SELECT x AS entry,x AS paraphrase FROM data", "CREATE TABLE mdx(entry TEXT PRIMARY KEY,paraphrase TEXT NOT NULL)"] {
  let dir=tempfile::tempdir().unwrap();let db=dir.path().join("bad.db");let c=Connection::open(&db).unwrap();c.execute_batch(schema).unwrap();drop(c);let dest=dir.path().join("out.txt");assert!(execute(&Request::DbToTxt {source:db,destination:dest.clone()},&mut Job::new(&CancellationToken::default(),&mut |_|{})).is_err());assert!(!dest.exists());
 }
 for body in [rusqlite::types::Value::Blob(vec![0,255]),rusqlite::types::Value::Text("</>".into())] {
  let dir=tempfile::tempdir().unwrap();let db=dir.path().join("bad.db");let c=Connection::open(&db).unwrap();c.execute_batch(MDX_SQL).unwrap();c.execute("INSERT INTO mdx VALUES (?1,?2)",params!["word",body]).unwrap();drop(c);let dest=dir.path().join("out.txt");assert!(execute(&Request::DbToTxt {source:db,destination:dest.clone()},&mut Job::new(&CancellationToken::default(),&mut |_|{})).is_err());assert!(!dest.exists());
 }
}
#[test]fn overwrite_cancellation_and_commit_race_leave_no_new_output() {
 for phase in ["txt_snapshot","database_insert","database_commit"] {
  let dir=tempfile::tempdir().unwrap();let(source,db)=seed(dir.path());let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase==phase{stop.cancel();};
  let e=execute(&Request::TxtToDb {source,destination:db.clone(),profile:TxtProfile::CanonicalV1},&mut Job::new(&token,&mut progress)).unwrap_err();assert_eq!(e.code,"cancelled");assert!(!db.exists());assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);
 }
 let dir=tempfile::tempdir().unwrap();let(source,db)=seed(dir.path());let token=CancellationToken::default();let mut progress=|p:Progress|if p.phase=="database_commit"{fs::write(&db,b"sentinel").unwrap();};
 let e=execute(&Request::TxtToDb {source:source.clone(),destination:db.clone(),profile:TxtProfile::CanonicalV1},&mut Job::new(&token,&mut progress)).unwrap_err();assert_eq!(e.code,"destination_exists");assert_eq!(fs::read(&db).unwrap(),b"sentinel");
 assert_eq!(execute(&Request::TxtToDb {source,destination:db.clone(),profile:TxtProfile::CanonicalV1},&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"destination_exists");assert_eq!(fs::read(&db).unwrap(),b"sentinel");
}
#[test]fn edited_studio_rows_and_wal_inputs_fail_explicitly() {
 let dir=tempfile::tempdir().unwrap();let(source,db)=seed(dir.path());run(Request::TxtToDb {source,destination:db.clone(),profile:TxtProfile::CanonicalV1});
 let c=Connection::open(&db).unwrap();c.execute("UPDATE mdx SET paraphrase='changed' WHERE rowid=1",[]).unwrap();drop(c);
 let e=execute(&Request::Lookup {source:db.clone(),query:"word".into(),offset:0,limit:1},&mut Job::new(&CancellationToken::default(),&mut |_|{})).unwrap_err();assert_eq!(e.code,"integrity");
 fs::write(PathBuf::from(format!("{}-wal",db.display())),b"present").unwrap();let e=execute(&Request::Lookup {source:db,query:"word".into(),offset:0,limit:1},&mut Job::new(&CancellationToken::default(),&mut |_|{})).unwrap_err();assert_eq!(e.code,"unsupported_profile");
}
#[test]fn database_and_lookup_envelopes_are_not_silently_truncated() {
 let dir=tempfile::tempdir().unwrap();let db=dir.path().join("big.db");let c=Connection::open(&db).unwrap();c.execute_batch(MDX_SQL).unwrap();
 let body="x".repeat(800000);for _ in 0..3{c.execute("INSERT INTO mdx VALUES (?1,?2)",params!["same",body]).unwrap();}drop(c);
 let e=execute(&Request::Lookup {source:db,query:"same".into(),offset:0,limit:3},&mut Job::new(&CancellationToken::default(),&mut |_|{})).unwrap_err();assert_eq!(e.code,"limit_exceeded");
}
