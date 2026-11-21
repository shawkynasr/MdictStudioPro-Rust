//! Replace one physical row's definition in a verified new database.
use super::*;
const EDIT_CAP:usize=8192;
#[derive(Debug,Serialize)]
pub struct EntryEditPublication {#[serde(flatten)]pub publication:Publication,pub source_rowid:String,pub output_rowid:String}
#[cfg(test)]
fn execute(source:&Path,destination:&Path,expected:&str,rowid:&str,body:&str,job:&mut Job<'_>)->Result<EntryEditPublication> {
 execute_with_key(source,destination,expected,rowid,body,None,job)
}
pub(super) fn execute_with_key(source:&Path,destination:&Path,expected:&str,rowid:&str,body:&str,new_key:Option<&str>,job:&mut Job<'_>)->Result<EntryEditPublication> {
 no_destination(destination)?;
 if let Some(key)=new_key {
  if key.is_empty()||key=="</>"||key.chars().any(|c|matches!(c,'\0'|'\r'|'\n')){return Err(error("invalid_input","Headword must be nonempty and contain no NUL, CR, LF or TXT delimiter"));}
  if key.len()>4096{return Err(error("limit_exceeded","Headword exceeds 4 KiB UTF-8"));}
 }
 if body.len()>EDIT_CAP{return Err(error("limit_exceeded","Definition edits are limited to 8 KiB UTF-8"));}
 let id=rowid.parse::<i64>().map_err(|_|error("invalid_input","Require an exact signed SQLite rowid string"))?;
 if id.to_string()!=rowid||expected.len()!=64||!expected.bytes().all(|b|b.is_ascii_hexdigit()){return Err(error("invalid_input","Require a canonical SQLite rowid and snapshot SHA-256"));}
 let checked=open_checked(source,job)?;
 if !checked.source_sha256.eq_ignore_ascii_case(expected){return Err(error("integrity","Source differs from the opened snapshot; close and reload before saving an entry copy"));}
 if let Some(attrs)=&checked.dictionary_metadata {
  if attrs.get("Format").is_some_and(|v|v.eq_ignore_ascii_case("html"))&&attrs.get("Compact").is_some_and(|v|matches!(v.to_ascii_lowercase().as_str(),"yes"|"1")) {
   let ids=metadata_copy::rules(attrs.get("StyleSheet").map(String::as_str).unwrap_or(""))?;
   metadata_copy::markers(body,&ids,job)?;
  }
 }
 let mut stmt=checked.connection.prepare("SELECT rowid,entry,paraphrase FROM mdx ORDER BY rowid")?;let mut cursor=stmt.query([])?;let mut rows=Vec::new();let mut selected=None;
 while let Some(row)=cursor.next()? {
  job.tick("database_entry_copy",rows.len(),checked.records)?;let physical:i64=row.get(0)?;let original_key=text(row,1,4096)?;let key=if physical==id{new_key.unwrap_or(&original_key).to_owned()}else{original_key};let original=text(row,2,BODY_CAP)?;
  let definition=if physical==id{selected=Some((rows.len()+1).to_string());body.to_owned()}else{original};rows.push(Entry {key,text:definition});
 }
 drop(cursor);drop(stmt);
 let output_rowid=selected.ok_or_else(||error("invalid_input","Selected rowid does not exist in the opened source"))?;
 let publication=create_rows(&rows,destination,checked.profile,&checked.source_sha256,checked.dictionary_metadata.as_ref(),job)?;
 Ok(EntryEditPublication {publication,source_rowid:rowid.into(),output_rowid})
}

#[cfg(test)]mod tests {
 use super::*;
 fn legacy(path:&Path){let c=Connection::open(path).unwrap();c.execute_batch(MDX_SQL).unwrap();for (id,key,body) in [(-2,"字","first"),(7,"字","second"),(99,"empty","")] {c.execute("INSERT INTO mdx(rowid,entry,paraphrase) VALUES (?1,?2,?3)",params![id,key,body]).unwrap();}}
 #[test]fn entry_rename_preserves_selected_body_duplicates_order_and_metadata() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");let token=CancellationToken::default();let attrs=BTreeMap::from([("Title".into(),"keep".into()),("Description".into(),"same".into()),("Encoding".into(),"UTF-16".into())]);
  let rows=vec![Entry{key:"字".into(),text:"first".into()},Entry{key:"字".into(),text:"second".into()},Entry{key:"empty".into(),text:"".into()}];
  import_mdx_rows(&rows,&source,&"a".repeat(64),&attrs,&mut Job::new(&token,&mut |_|{})).unwrap();let before=fs::read(&source).unwrap();let hash=digest(&before);
  for (i,key) in ["empty"," renamed 字 مرحبا %_*? ",&"x".repeat(4096)].iter().enumerate() {
   let dest=dir.path().join(format!("copy{i}.db"));execute_with_key(&source,&dest,&hash,"2","second",Some(key),&mut Job::new(&token,&mut |_|{})).unwrap();let copy=read_for_rebuild(&dest,&mut Job::new(&token,&mut |_|{})).unwrap();let mut expected=rows.clone();expected[1].key=key.to_string();assert_eq!(copy.rows,expected);assert_eq!(copy.dictionary_metadata,Some(attrs.clone()));
  }
  assert_eq!(fs::read(&source).unwrap(),before);
 }
 #[test]fn entry_rename_rejects_invalid_keys_and_cancels_without_publication() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");legacy(&source);let before=fs::read(&source).unwrap();let hash=digest(&before);let dest=dir.path().join("copy.db");let token=CancellationToken::default();
  for key in ["","</>","a\0b","a\rb","a\nb",&"字".repeat(1366)] {
   let e=execute_with_key(&source,&dest,&hash,"7","second",Some(key),&mut Job::new(&token,&mut |_|{})).unwrap_err();assert_eq!(e.code,if key.len()>4096{"limit_exceeded"}else{"invalid_input"});assert!(!dest.exists());
  }
  for phase in ["database_entry_copy","database_insert","database_commit"] {
   let stop=CancellationToken::default();let cancel=stop.clone();let mut progress=|p:Progress|if p.phase==phase{cancel.cancel();};assert_eq!(execute_with_key(&source,&dest,&hash,"7","second",Some("empty"),&mut Job::new(&stop,&mut progress)).unwrap_err().code,"cancelled");assert!(!dest.exists());assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);
  }
  assert_eq!(fs::read(&source).unwrap(),before);
 }
 #[test]fn entry_copy_changes_only_selected_duplicate_even_with_sparse_rowids() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");legacy(&source);let before=fs::read(&source).unwrap();let token=CancellationToken::default();let hash=digest(&before);let dest=dir.path().join("copy.db");let body="<p>edited 字</p>\r\n</>\n\0";
  let receipt=execute(&source,&dest,&hash,"7",body,&mut Job::new(&token,&mut |_|{})).unwrap();assert_eq!(receipt.source_rowid,"7");assert_eq!(receipt.output_rowid,"2");assert_eq!(receipt.publication.source_sha256,hash);let copy=read_for_rebuild(&dest,&mut Job::new(&token,&mut |_|{})).unwrap();assert_eq!(copy.rows,vec![Entry{key:"字".into(),text:"first".into()},Entry{key:"字".into(),text:body.into()},Entry{key:"empty".into(),text:String::new()}]);assert_eq!(fs::read(&source).unwrap(),before);
  let empty=dir.path().join("clear.db");execute(&source,&empty,&hash,"-2","",&mut Job::new(&token,&mut |_|{})).unwrap();assert_eq!(read_for_rebuild(&empty,&mut Job::new(&token,&mut |_|{})).unwrap().rows[0].text,"");
 }
 #[test]fn entry_copy_preserves_stored_header_and_checks_numeric_markers() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");let attrs=BTreeMap::from([("Title".into(),"keep".into()),("Description".into(),"before".into()),("Format".into(),"Html".into()),("Compact".into(),"Yes".into()),("Encoding".into(),"UTF-16".into()),("StyleSheet".into(),"2\n<b>\n</b>\n".into())]);let rows=vec![Entry{key:"字".into(),text:"`2`first".into()},Entry{key:"字".into(),text:"second".into()}];let token=CancellationToken::default();import_mdx_rows(&rows,&source,&"a".repeat(64),&attrs,&mut Job::new(&token,&mut |_|{})).unwrap();let hash=digest(&fs::read(&source).unwrap());let dest=dir.path().join("edited.db");execute(&source,&dest,&hash,"2","`2`edited",&mut Job::new(&token,&mut |_|{})).unwrap();let copy=read_for_rebuild(&dest,&mut Job::new(&token,&mut |_|{})).unwrap();assert_eq!(copy.dictionary_metadata,Some(attrs));assert_eq!(copy.rows[0],rows[0]);assert_eq!(copy.rows[1].text,"`2`edited");let invalid=dir.path().join("bad.db");assert_eq!(execute(&source,&invalid,&hash,"2","`9`missing rule",&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"invalid_input");assert!(!invalid.exists());
 }
 #[test]fn entry_copy_stale_bounds_cancellation_and_destination_races_are_atomic() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");legacy(&source);let before=fs::read(&source).unwrap();let hash=digest(&before);let token=CancellationToken::default();let dest=dir.path().join("out.db");
  for id in ["+7","07","-0","9223372036854775808","3"]{assert_eq!(execute(&source,&dest,&hash,id,"edited",&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"invalid_input");assert!(!dest.exists());}
  assert_eq!(execute(&source,&dest,&"0".repeat(64),"7","edited",&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"integrity");assert_eq!(execute(&source,&dest,&hash,"7",&"x".repeat(8193),&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"limit_exceeded");
  for phase in ["database_snapshot","database_entry_copy","database_insert","database_commit"]{let stop=CancellationToken::default();let cancel=stop.clone();let mut progress=|p:Progress|if p.phase==phase{cancel.cancel();};assert_eq!(execute(&source,&dest,&hash,"7","edited",&mut Job::new(&stop,&mut progress)).unwrap_err().code,"cancelled");assert!(!dest.exists());assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);}
  let mut progress=|p:Progress|if p.phase=="database_commit"{fs::write(&dest,b"sentinel").unwrap();};assert_eq!(execute(&source,&dest,&hash,"7","edited",&mut Job::new(&token,&mut progress)).unwrap_err().code,"destination_exists");assert_eq!(fs::read(&dest).unwrap(),b"sentinel");assert_eq!(execute(&source,&dest,&hash,"7","edited",&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"destination_exists");assert_eq!(fs::read(source).unwrap(),before);
 }
}
