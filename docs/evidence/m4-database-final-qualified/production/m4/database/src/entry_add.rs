//! Append one entry to a verified new database without merging duplicate keys.
use super::*;
#[derive(Debug,Serialize)]
pub struct EntryAddPublication {#[serde(flatten)]pub publication:Publication,pub output_rowid:String}
pub(super) fn execute(source:&Path,destination:&Path,expected:&str,key:&str,body:&str,job:&mut Job<'_>)->Result<EntryAddPublication> {
 no_destination(destination)?;
 if expected.len()!=64||!expected.bytes().all(|b|b.is_ascii_hexdigit()){return Err(error("invalid_input","Require snapshot SHA-256"));}
 if key.is_empty()||key=="</>"||key.chars().any(|c|matches!(c,'\0'|'\r'|'\n')){return Err(error("invalid_input","Headword must be nonempty and contain no NUL, CR, LF or TXT delimiter"));}
 if key.len()>4096||body.len()>8192{return Err(error("limit_exceeded","New entries require a headword up to 4 KiB and definition up to 8 KiB UTF-8"));}
 let checked=open_checked(source,job)?;
 if !checked.source_sha256.eq_ignore_ascii_case(expected){return Err(error("integrity","Source differs from the opened snapshot; close and reload before adding an entry copy"));}
 if checked.records>=RECORD_CAP{return Err(error("limit_exceeded","Adding an entry would exceed 100,000 records"));}
 if let Some(attrs)=&checked.dictionary_metadata {
  if attrs.get("Format").is_some_and(|v|v.eq_ignore_ascii_case("html"))&&attrs.get("Compact").is_some_and(|v|matches!(v.to_ascii_lowercase().as_str(),"yes"|"1")) {
   let ids=metadata_copy::rules(attrs.get("StyleSheet").map(String::as_str).unwrap_or(""))?;metadata_copy::markers(body,&ids,job)?;
  }
 }
 let mut stmt=checked.connection.prepare("SELECT entry,paraphrase FROM mdx ORDER BY rowid")?;let mut cursor=stmt.query([])?;let mut rows=Vec::new();
 while let Some(row)=cursor.next()? {job.tick("database_entry_add",rows.len(),checked.records)?;rows.push(Entry{key:text(row,0,4096)?,text:text(row,1,BODY_CAP)?});}
 drop(cursor);drop(stmt);job.tick("database_entry_add",rows.len(),checked.records)?;
 rows.push(Entry{key:key.into(),text:body.into()});let output_rowid=rows.len().to_string();
 let publication=create_rows(&rows,destination,checked.profile,&checked.source_sha256,checked.dictionary_metadata.as_ref(),job)?;
 Ok(EntryAddPublication{publication,output_rowid})
}
#[cfg(test)]mod tests {
 use super::*;
 fn legacy(path:&Path){let c=Connection::open(path).unwrap();c.execute_batch(MDX_SQL).unwrap();for(id,k,t)in[(-2,"字","first"),(7,"字","second"),(99,"empty","")]{c.execute("INSERT INTO mdx(rowid,entry,paraphrase) VALUES (?1,?2,?3)",params![id,k,t]).unwrap();}}
 #[test]fn entry_add_appends_duplicates_literal_keys_and_preserves_sparse_source() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");legacy(&source);let before=fs::read(&source).unwrap();let hash=digest(&before);let token=CancellationToken::default();let old=read_for_rebuild(&source,&mut Job::new(&token,&mut |_|{})).unwrap();
  for(i,(key,body))in[("字","third"),(" renamed 字 مرحبا %_*? ",""),("a","<p>body</p>\r\n\0</>\n")].iter().enumerate(){let dest=dir.path().join(format!("copy{i}.db"));let receipt=execute(&source,&dest,&hash,key,body,&mut Job::new(&token,&mut |_|{})).unwrap();assert_eq!(receipt.output_rowid,"4");assert_eq!(receipt.publication.records,4);let copy=read_for_rebuild(&dest,&mut Job::new(&token,&mut |_|{})).unwrap();let mut expected=old.rows.clone();expected.push(Entry{key:(*key).into(),text:(*body).into()});assert_eq!(copy.rows,expected);assert_eq!(copy.dictionary_metadata,None);}
  assert_eq!(fs::read(&source).unwrap(),before);
 }
 #[test]fn entry_add_preserves_header_and_checks_existing_numeric_rules() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");let token=CancellationToken::default();let attrs=BTreeMap::from([("Title".into(),"keep".into()),("Description".into(),"same".into()),("Encoding".into(),"UTF-16".into()),("Format".into(),"Html".into()),("Compact".into(),"Yes".into()),("StyleSheet".into(),"1\n<b>\n</b>\n".into())]);let rows=vec![Entry{key:"字".into(),text:"x".repeat(9000)}];import_mdx_rows(&rows,&source,&"a".repeat(64),&attrs,&mut Job::new(&token,&mut |_|{})).unwrap();let before=fs::read(&source).unwrap();let hash=digest(&before);let dest=dir.path().join("copy.db");execute(&source,&dest,&hash,"字","`1`new",&mut Job::new(&token,&mut |_|{})).unwrap();let copy=read_for_rebuild(&dest,&mut Job::new(&token,&mut |_|{})).unwrap();assert_eq!(copy.dictionary_metadata,Some(attrs));assert_eq!(copy.rows[0],rows[0]);assert_eq!(copy.rows[1].text,"`1`new");let invalid=dir.path().join("invalid.db");assert_eq!(execute(&source,&invalid,&hash,"new","`9`missing rule",&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"invalid_input");assert!(!invalid.exists());assert_eq!(fs::read(source).unwrap(),before);
 }
 #[test]fn entry_add_bounds_stale_cancellation_and_publication_races_are_atomic() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");legacy(&source);let before=fs::read(&source).unwrap();let hash=digest(&before);let token=CancellationToken::default();let dest=dir.path().join("out.db");
  for key in ["","</>","a\0b","a\rb","a\nb"]{assert_eq!(execute(&source,&dest,&hash,key,"",&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"invalid_input");assert!(!dest.exists());}
  let oversized_key="字".repeat(1366);let oversized_body="x".repeat(8193);for(key,body)in[(oversized_key.as_str(),""),("a",oversized_body.as_str())]{assert_eq!(execute(&source,&dest,&hash,key,body,&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"limit_exceeded");assert!(!dest.exists());}
  assert_eq!(execute(&source,&dest,&"0".repeat(64),"new","",&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"integrity");
  for phase in ["database_snapshot","database_entry_add","database_insert","database_commit"]{let stop=CancellationToken::default();let cancel=stop.clone();let mut progress=|p:Progress|if p.phase==phase{cancel.cancel();};assert_eq!(execute(&source,&dest,&hash,"字","new",&mut Job::new(&stop,&mut progress)).unwrap_err().code,"cancelled");assert!(!dest.exists());assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);}
  let mut progress=|p:Progress|if p.phase=="database_commit"{fs::write(&dest,b"sentinel").unwrap();};assert_eq!(execute(&source,&dest,&hash,"字","new",&mut Job::new(&token,&mut progress)).unwrap_err().code,"destination_exists");assert_eq!(fs::read(&dest).unwrap(),b"sentinel");assert_eq!(execute(&source,&dest,&hash,"字","new",&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"destination_exists");assert_eq!(fs::read(source).unwrap(),before);
 }
 #[test]fn entry_add_refuses_record_cap_without_output() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("full.db");let token=CancellationToken::default();let rows=vec![Entry{key:"a".into(),text:String::new()};RECORD_CAP];create_rows(&rows,&source,TxtProfile::CanonicalV1,&"a".repeat(64),None,&mut Job::new(&token,&mut |_|{})).unwrap();let before=fs::read(&source).unwrap();let dest=dir.path().join("copy.db");assert_eq!(execute(&source,&dest,&digest(&before),"a","",&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"limit_exceeded");assert!(!dest.exists());assert_eq!(fs::read(source).unwrap(),before);
 }
}
