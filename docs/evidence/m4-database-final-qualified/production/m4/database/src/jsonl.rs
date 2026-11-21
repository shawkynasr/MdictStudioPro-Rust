//! Streaming row-only JSONL export, verified before no-clobber publication.
use super::*;
use std::io::{BufRead,BufReader};
const LINE_CAP:usize=6*(BODY_CAP+4096)+128;

// A separate wire type enforces exact fields and rejects duplicate fields.
#[derive(Deserialize)]#[serde(deny_unknown_fields)]
struct InputRow {key:String,text:String}
pub(super) fn import(source:&Path,destination:&Path,job:&mut Job<'_>)->Result<Publication> {
 no_destination(destination)?;job.tick("jsonl_snapshot",0,1)?;
 let (snapshot,source_sha256)=snapshot(source,false,job)?;
 let mut input=BufReader::new(File::open(snapshot.path())?);let mut rows=Vec::new();let mut decoded=0usize;
 loop {
  job.tick("database_jsonl_import",rows.len(),0)?;
  let mut line=Vec::new();let n=(&mut input).take((LINE_CAP+1) as u64).read_until(b'\n',&mut line)?;
  if n==0{break;}
  if n>LINE_CAP{return Err(error("limit_exceeded","JSONL line exceeds budget"));}
  if line.last()!=Some(&b'\n'){return Err(error("invalid_input","Every JSONL record must end with a newline"));}
  let row:InputRow=serde_json::from_slice(&line).map_err(|e|error("invalid_input",format!("JSONL record {}: {}",rows.len()+1,e)))?;
  if rows.len()>=RECORD_CAP||row.key.len()>4096||row.text.len()>BODY_CAP{return Err(error("limit_exceeded","JSONL key, body or record budget exceeded"));}
  decoded+=row.key.len()+row.text.len();if decoded>DECODED_CAP{return Err(error("limit_exceeded","JSONL decoded text exceeds 32 MiB"));}
  rows.push(Entry {key:row.key,text:row.text});
 }
 // Reuse the checked database writer, staged readback and no-clobber commit.
 create_rows(&rows,destination,TxtProfile::CanonicalV1,&source_sha256,None,job)
}

pub(super) fn export(source:&Path,destination:&Path,job:&mut Job<'_>)->Result<Publication> {
 export_bounded(source,destination,FILE_CAP,job)
}
fn export_bounded(source:&Path,destination:&Path,cap:u64,job:&mut Job<'_>)->Result<Publication> {
 debug_assert!(cap<=FILE_CAP);
 no_destination(destination)?;let checked=open_checked(source,job)?;
 let mut stage=tempfile::NamedTempFile::new_in(parent(destination))?;
 let mut stmt=checked.connection.prepare("SELECT entry,paraphrase FROM mdx ORDER BY rowid")?;let mut cursor=stmt.query([])?;
 let mut bytes=0u64;let mut records=0usize;
 while let Some(row)=cursor.next()? {
  job.tick("database_jsonl_export",records,checked.records)?;
  let entry=Entry {key:text(row,0,4096)?,text:text(row,1,BODY_CAP)?};
  let encoded=serde_json::to_vec(&entry).map_err(|e|error("internal",e.to_string()))?;
  if encoded.len()>LINE_CAP || encoded.len() as u64+1>cap.saturating_sub(bytes){return Err(error("limit_exceeded","JSONL output exceeds file/line budget"));}
  for chunk in encoded.chunks(65536){job.check()?;stage.write_all(chunk)?;}
  stage.write_all(b"\n")?;bytes+=encoded.len() as u64+1;records+=1;
 }
 drop(cursor);drop(stmt);stage.flush()?;
 if records!=checked.records{return Err(error("integrity","JSONL export row count differs from snapshot"));}
 verify(stage.as_file(),checked.records,&checked.rows_sha256,job)?;
 if stage.as_file().metadata()?.len()!=bytes{return Err(error("integrity","JSONL output extent changed"));}
 let receipt=Publication {profile:checked.db_profile,destination:destination.to_owned(),records,source_sha256:checked.source_sha256,rows_sha256:checked.rows_sha256,bytes,sqlite_version:rusqlite::version().into(),text_profile:checked.profile,dictionary_metadata:checked.dictionary_metadata};
 publication(stage,destination,job)?;Ok(receipt)
}
fn verify(file:&File,expected_records:usize,expected_digest:&str,job:&mut Job<'_>)->Result<()> {
 // try_clone shares a file offset, so seek explicitly before verifying the stage.
 use std::io::{Seek,SeekFrom};
 let mut file=file.try_clone()?;file.seek(SeekFrom::Start(0))?;let mut input=BufReader::new(file);
 let mut records=0usize;let mut decoded=0usize;let mut hash=sha256::Sha256::new();
 loop {
  job.tick("database_jsonl_verify",records,expected_records)?;
  let mut line=Vec::new();let n=(&mut input).take((LINE_CAP+1) as u64).read_until(b'\n',&mut line)?;
  if n==0{break;}
  if n>LINE_CAP || line.last()!=Some(&b'\n'){return Err(error("integrity","Invalid staged JSONL line extent"));}
  let row:Entry=serde_json::from_slice(&line).map_err(|e|error("integrity",e.to_string()))?;
  decoded+=row.key.len()+row.text.len();if records>=RECORD_CAP||decoded>DECODED_CAP||row.key.len()>4096||row.text.len()>BODY_CAP{return Err(error("limit_exceeded","Staged JSONL rows exceed database budget"));}
  frame(&mut hash,records,&row.key,&row.text);records+=1;
 }
 if records!=expected_records||sha256::hex(&hash.finish())!=expected_digest{return Err(error("integrity","Staged JSONL row order, text or multiplicity differs"));}
 job.check()
}

#[cfg(test)]mod tests {
 use super::*;
 fn seed(dir:&Path)->PathBuf {
  let source=dir.join("source.db");let c=Connection::open(&source).unwrap();c.execute_batch(MDX_SQL).unwrap();
  for (key,body) in [("字","first\r\n\n</>\n\"quoted\"\\tail\0"),("字","second"),("مرحبا","أهلاً وسهلاً"),("empty","")] {c.execute("INSERT INTO mdx VALUES (?1,?2)",params![key,body]).unwrap();}drop(c);source
 }
 #[test]fn jsonl_import_roundtrip_preserves_rows_and_origin() {
  let dir=tempfile::tempdir().unwrap();let source=seed(dir.path());let jsonl=dir.path().join("rows.jsonl");let db=dir.path().join("import.db");let token=CancellationToken::default();
  let original=export(&source,&jsonl,&mut Job::new(&token,&mut |_|{})).unwrap();let before=fs::read(&jsonl).unwrap();
  let imported=import(&jsonl,&db,&mut Job::new(&token,&mut |_|{})).unwrap();assert_eq!(imported.records,4);assert_eq!(imported.rows_sha256,original.rows_sha256);assert_eq!(imported.source_sha256,digest(&before));assert!(imported.dictionary_metadata.is_none());
  let again=dir.path().join("again.jsonl");export(&db,&again,&mut Job::new(&token,&mut |_|{})).unwrap();assert_eq!(fs::read(again).unwrap(),before);assert_eq!(fs::read(jsonl).unwrap(),before);
 }
 #[test]fn jsonl_import_rejects_malformed_shape_keys_and_bounds() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("in.jsonl");let destination=dir.path().join("out.db");let token=CancellationToken::default();
  for data in [b"".as_slice(),b"\n",b"[]\n",b"{}\n",b"{\"key\":\"a\",\"text\":null}\n",b"{\"key\":\"a\",\"key\":\"b\",\"text\":\"c\"}\n",b"{\"key\":\"a\",\"text\":\"b\",\"extra\":1}\n",b"{\"key\":\"a\",\"text\":\"b\"}",b"\xef\xbb\xbf{}\n",b"\xff\n"] {
   fs::write(&source,data).unwrap();assert!(import(&source,&destination,&mut Job::new(&token,&mut |_|{})).is_err());assert!(!destination.exists());
  }
  for key in ["", "</>", "a\n", "a\r", "a\0"] {
   fs::write(&source,format!("{}\n",serde_json::to_string(&Entry {key:key.into(),text:String::new()}).unwrap())).unwrap();assert_eq!(import(&source,&destination,&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"invalid_input");assert!(!destination.exists());
  }
  for row in [Entry {key:"x".repeat(4097),text:String::new()},Entry {key:"a".into(),text:"x".repeat(BODY_CAP+1)}] {
   fs::write(&source,format!("{}\n",serde_json::to_string(&row).unwrap())).unwrap();assert_eq!(import(&source,&destination,&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"limit_exceeded");assert!(!destination.exists());
  }
  fs::write(&source,vec![b' ';LINE_CAP+1]).unwrap();assert_eq!(import(&source,&destination,&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"limit_exceeded");assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);
 }
 #[test]fn jsonl_import_cancel_and_destination_race_are_atomic() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("rows.jsonl");fs::write(&source,b"{\"key\":\"a\",\"text\":\"body\"}\n").unwrap();let before=fs::read(&source).unwrap();
  for phase in ["jsonl_snapshot","database_jsonl_import","database_insert","database_snapshot","database_commit"] {
   let destination=dir.path().join(format!("{phase}.db"));let token=CancellationToken::default();let stop=token.clone();let mut seen=false;let mut progress=|p:Progress|if p.phase==phase{seen=true;stop.cancel();};let result=import(&source,&destination,&mut Job::new(&token,&mut progress));assert!(seen,"{phase}");assert_eq!(result.unwrap_err().code,"cancelled");assert!(!destination.exists());assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);
  }
  let destination=dir.path().join("race.db");let token=CancellationToken::default();let mut progress=|p:Progress|if p.phase=="database_commit"{fs::write(&destination,b"sentinel").unwrap();};assert_eq!(import(&source,&destination,&mut Job::new(&token,&mut progress)).unwrap_err().code,"destination_exists");assert_eq!(fs::read(&destination).unwrap(),b"sentinel");assert_eq!(import(&source,&destination,&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"destination_exists");assert_eq!(fs::read(source).unwrap(),before);assert_eq!(fs::read_dir(dir.path()).unwrap().count(),2);
 }
 #[test]fn jsonl_preserves_order_duplicates_empty_bodies_and_text_controls() {
  let dir=tempfile::tempdir().unwrap();let source=seed(dir.path());let before=fs::read(&source).unwrap();let destination=dir.path().join("rows.jsonl");
  let receipt=export(&source,&destination,&mut Job::new(&CancellationToken::default(),&mut |_|{})).unwrap();assert_eq!(receipt.records,4);assert_eq!(receipt.bytes,fs::metadata(&destination).unwrap().len());
  let lines=fs::read_to_string(&destination).unwrap();assert_eq!(lines.lines().count(),4);assert!(lines.ends_with('\n'));assert!(!lines.contains('\0'));
  let rows=lines.lines().map(|line|serde_json::from_str::<Entry>(line).unwrap()).collect::<Vec<_>>();assert_eq!(rows[0].key,"字");assert_eq!(rows[0].text,"first\r\n\n</>\n\"quoted\"\\tail\0");assert_eq!(rows[1].key,"字");assert_eq!(rows[1].text,"second");assert_eq!(rows[2].text,"أهلاً وسهلاً");assert_eq!(rows[3].text,"");assert_eq!(fs::read(source).unwrap(),before);
 }
 #[test]fn cancellation_output_limits_and_destination_races_leave_no_partial_export() {
  let dir=tempfile::tempdir().unwrap();let source=seed(dir.path());let before=fs::read(&source).unwrap();
  for phase in ["database_snapshot","database_jsonl_export","database_jsonl_verify","database_commit"] {
   let destination=dir.path().join(format!("{phase}.jsonl"));let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase==phase{stop.cancel();};assert_eq!(export(&source,&destination,&mut Job::new(&token,&mut progress)).unwrap_err().code,"cancelled");assert!(!destination.exists());assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);
  }
  let token=CancellationToken::default();let small=dir.path().join("small.jsonl");assert_eq!(export_bounded(&source,&small,32,&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"limit_exceeded");assert!(!small.exists());assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);
  let destination=dir.path().join("race.jsonl");let mut progress=|p:Progress|if p.phase=="database_commit"{fs::write(&destination,b"sentinel").unwrap();};assert_eq!(export(&source,&destination,&mut Job::new(&token,&mut progress)).unwrap_err().code,"destination_exists");assert_eq!(fs::read(&destination).unwrap(),b"sentinel");assert_eq!(export(&source,&destination,&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"destination_exists");assert_eq!(fs::read_dir(dir.path()).unwrap().count(),2);assert_eq!(fs::read(source).unwrap(),before);
 }
 #[test]fn staged_verifier_rejects_changed_missing_reordered_and_duplicate_rows() {
  let token=CancellationToken::default();let expected=[Entry {key:"a".into(),text:"first".into()},Entry {key:"a".into(),text:"second".into()}];let mut hash=sha256::Sha256::new();for(i,row)in expected.iter().enumerate(){frame(&mut hash,i,&row.key,&row.text);}let digest=sha256::hex(&hash.finish());
  for rows in [vec![&expected[0]],vec![&expected[1],&expected[0]],vec![&expected[0],&expected[0]]] {
   let mut stage=tempfile::NamedTempFile::new().unwrap();for row in rows {serde_json::to_writer(&mut stage,row).unwrap();stage.write_all(b"\n").unwrap();}stage.flush().unwrap();assert_eq!(verify(stage.as_file(),2,&digest,&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"integrity");
  }
 }
}
