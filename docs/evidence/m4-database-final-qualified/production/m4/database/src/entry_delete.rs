//! Remove exactly one physical source row into a verified new database.
use super::*;
#[derive(Debug,Serialize)]
pub struct EntryDeletePublication {#[serde(flatten)]pub publication:Publication,pub source_rowid:String}
pub(super) fn execute(source:&Path,destination:&Path,expected:&str,rowid:&str,job:&mut Job<'_>)->Result<EntryDeletePublication> {
 no_destination(destination)?;
 let id=rowid.parse::<i64>().map_err(|_|error("invalid_input","Require an exact signed SQLite rowid string"))?;
 if id.to_string()!=rowid||expected.len()!=64||!expected.bytes().all(|b|b.is_ascii_hexdigit()){return Err(error("invalid_input","Require a canonical SQLite rowid and snapshot SHA-256"));}
 let checked=open_checked(source,job)?;
 if !checked.source_sha256.eq_ignore_ascii_case(expected){return Err(error("integrity","Source differs from the opened snapshot; close and reload before saving a deletion copy"));}
 let mut stmt=checked.connection.prepare("SELECT rowid,entry,paraphrase FROM mdx ORDER BY rowid")?;let mut cursor=stmt.query([])?;let mut rows=Vec::new();let mut found=false;let mut processed=0;
 while let Some(row)=cursor.next()? {
  job.tick("database_entry_delete",processed,checked.records)?;processed+=1;let physical:i64=row.get(0)?;
  if physical==id {found=true;}else{rows.push(Entry{key:text(row,1,4096)?,text:text(row,2,BODY_CAP)?});}
 }
 drop(cursor);drop(stmt);
 if !found{return Err(error("invalid_input","Selected rowid does not exist in the opened source"));}
 if rows.is_empty(){return Err(error("invalid_input","Cannot delete the only entry in this database profile"));}
 let publication=create_rows(&rows,destination,checked.profile,&checked.source_sha256,checked.dictionary_metadata.as_ref(),job)?;
 Ok(EntryDeletePublication{publication,source_rowid:rowid.into()})
}
#[cfg(test)]mod tests {
 use super::*;
 fn legacy(path:&Path){let c=Connection::open(path).unwrap();c.execute_batch(MDX_SQL).unwrap();for(id,k,t)in[(-2,"字","first"),(7,"字","second"),(99,"empty","")]{c.execute("INSERT INTO mdx(rowid,entry,paraphrase) VALUES (?1,?2,?3)",params![id,k,t]).unwrap();}}
 #[test]fn entry_delete_targets_sparse_row_and_preserves_duplicate_sibling_and_order() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");legacy(&source);let before=fs::read(&source).unwrap();let hash=digest(&before);let token=CancellationToken::default();
  let old=read_for_rebuild(&source,&mut Job::new(&token,&mut |_|{})).unwrap();
  for(i,id)in["-2","7","99"].iter().enumerate(){let dest=dir.path().join(format!("copy{i}.db"));let receipt=execute(&source,&dest,&hash,id,&mut Job::new(&token,&mut |_|{})).unwrap();assert_eq!(receipt.source_rowid,*id);assert_eq!(receipt.publication.records,2);let copy=read_for_rebuild(&dest,&mut Job::new(&token,&mut |_|{})).unwrap();let mut expected=old.rows.clone();expected.remove(i);assert_eq!(copy.rows,expected);assert_eq!(copy.dictionary_metadata,None);assert_eq!(copy.source_sha256,digest(&fs::read(&dest).unwrap()));}
  assert_eq!(fs::read(&source).unwrap(),before);
 }
 #[test]fn entry_delete_preserves_metadata_large_bodies_and_refuses_last_entry() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");let token=CancellationToken::default();let attrs=BTreeMap::from([("Title".into(),"keep".into()),("Description".into(),"same".into()),("Encoding".into(),"UTF-16".into()),("StyleSheet".into(),"1\n<b>\n</b>\n".into())]);let rows=vec![Entry{key:"字".into(),text:"x".repeat(9000)},Entry{key:"字".into(),text:"`1`second".into()}];import_mdx_rows(&rows,&source,&"a".repeat(64),&attrs,&mut Job::new(&token,&mut |_|{})).unwrap();let before=fs::read(&source).unwrap();let hash=digest(&before);let dest=dir.path().join("copy.db");execute(&source,&dest,&hash,"1",&mut Job::new(&token,&mut |_|{})).unwrap();let copy=read_for_rebuild(&dest,&mut Job::new(&token,&mut |_|{})).unwrap();assert_eq!(copy.rows,vec![rows[1].clone()]);assert_eq!(copy.dictionary_metadata,Some(attrs));let last=dir.path().join("last.db");assert_eq!(execute(&dest,&last,&copy.source_sha256,"1",&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"invalid_input");assert!(!last.exists());assert_eq!(fs::read(source).unwrap(),before);
 }
 #[test]fn entry_delete_stale_ids_cancellation_and_publication_races_are_atomic() {
  let dir=tempfile::tempdir().unwrap();let source=dir.path().join("source.db");legacy(&source);let before=fs::read(&source).unwrap();let hash=digest(&before);let token=CancellationToken::default();let dest=dir.path().join("out.db");
  for id in ["+7","07","-0","9223372036854775808","3"]{assert_eq!(execute(&source,&dest,&hash,id,&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"invalid_input");assert!(!dest.exists());}
  assert_eq!(execute(&source,&dest,&"0".repeat(64),"7",&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"integrity");
  for phase in ["database_snapshot","database_entry_delete","database_insert","database_commit"]{let stop=CancellationToken::default();let cancel=stop.clone();let mut progress=|p:Progress|if p.phase==phase{cancel.cancel();};assert_eq!(execute(&source,&dest,&hash,"7",&mut Job::new(&stop,&mut progress)).unwrap_err().code,"cancelled");assert!(!dest.exists());assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);}
  let mut progress=|p:Progress|if p.phase=="database_commit"{fs::write(&dest,b"sentinel").unwrap();};assert_eq!(execute(&source,&dest,&hash,"7",&mut Job::new(&token,&mut progress)).unwrap_err().code,"destination_exists");assert_eq!(fs::read(&dest).unwrap(),b"sentinel");assert_eq!(execute(&source,&dest,&hash,"7",&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"destination_exists");assert_eq!(fs::read(source).unwrap(),before);
 }
}
