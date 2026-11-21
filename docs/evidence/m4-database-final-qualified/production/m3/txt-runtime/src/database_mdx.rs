//! Rebuild an MDX through the accepted bounded writer, then verify before commit.
use crate::{Error,ErrorCode,ImportJob,Progress,Result};
use std::{collections::BTreeMap,fs::{self,File},io::{Read,Write,BufRead,BufReader,Seek,SeekFrom},path::Path};
use studio_core::Entry;
fn fail(code:ErrorCode,message:impl Into<String>)->Error {Error {code,detail:"db_to_mdx",message:message.into(),limit:None}}
fn tick(job:&mut ImportJob<'_>,phase:&str,completed:usize,total:usize)->Result<()> {
 if job.token.is_cancelled(){return Err(fail(ErrorCode::Cancelled,"SQLite to MDX cancelled before publication"));}
 (job.progress)(Progress {job_id:job.id.into(),stage:if phase=="db_to_mdx_commit"{studio_application::Stage::Publishing}else{studio_application::Stage::Converting},phase:phase.into(),completed,total});
 if job.token.is_cancelled(){return Err(fail(ErrorCode::Cancelled,"SQLite to MDX cancelled before publication"));}Ok(())
}
#[cfg(test)]mod tests {
 use super::*;use crate::CancellationToken;
 fn plain(dir:&Path)->std::path::PathBuf {let source=dir.join("source.txt");let db=dir.join("dictionary.db");fs::write(&source,"z\nlast\n</>\na\nfirst\n</>\na\nsecond\n</>\nempty\n\n</>\n").unwrap();studio_database::execute(&studio_database::Request::TxtToDb{source,destination:db.clone(),profile:studio_core::TxtProfile::CanonicalV1},&mut studio_database::Job::new(&CancellationToken::default(),&mut |_|{})).unwrap();db}
 #[test]fn plain_database_rebuild_sorts_keys_preserves_duplicate_order_and_uses_defaults() {
  let dir=tempfile::tempdir().unwrap();let db=plain(dir.path());let before=fs::read(&db).unwrap();let dest=dir.path().join("rebuilt.mdx");let token=CancellationToken::default();let receipt=execute(&db,&dest,&mut ImportJob::new("build",&token,&mut |_|{})).unwrap();assert_eq!(receipt.records,4);assert_eq!(receipt.dictionary_metadata["Title"],"dictionary");assert_eq!(receipt.encoding,"UTF-8");
  let verify=dir.path().join("rows.jsonl");studio_large_io::execute(&studio_large_io::Request::ExportJsonl{source:dest,destination:verify.clone()},&studio_large_io::IoLimits::default(),&mut studio_large_io::ImportJob::new("verify",&token,&mut |_|{})).unwrap();let rows=decoded_rows(&verify,&mut ImportJob::new("decode",&token,&mut |_|{})).unwrap();assert_eq!(rows.iter().map(|r|r.key.as_str()).collect::<Vec<_>>(),["a","a","empty","z"]);assert_eq!(rows[0].text,"first");assert_eq!(rows[1].text,"second");assert_eq!(rows[2].text,"");assert_eq!(fs::read(db).unwrap(),before);
 }
 #[test]fn rebuild_cancellation_overwrite_and_final_destination_race_publish_nothing() {
  let dir=tempfile::tempdir().unwrap();let db=plain(dir.path());let before=fs::read(&db).unwrap();
  for phase in ["db_to_mdx_spool","db_to_mdx_copy","db_to_mdx_verify","db_to_mdx_commit"] {
   let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase==phase{stop.cancel();};let dest=dir.path().join(format!("cancel-{phase}.mdx"));assert_eq!(execute(&db,&dest,&mut ImportJob::new("cancel",&token,&mut progress)).unwrap_err().code,ErrorCode::Cancelled);assert!(!dest.exists());
  }
  let token=CancellationToken::default();let dest=dir.path().join("race.mdx");let mut progress=|p:Progress|if p.phase=="db_to_mdx_commit"{fs::write(&dest,b"sentinel").unwrap();};assert_eq!(execute(&db,&dest,&mut ImportJob::new("race",&token,&mut progress)).unwrap_err().code,ErrorCode::DestinationExists);assert_eq!(fs::read(&dest).unwrap(),b"sentinel");assert_eq!(execute(&db,&dest,&mut ImportJob::new("exists",&token,&mut |_|{})).unwrap_err().code,ErrorCode::DestinationExists);assert_eq!(fs::read(db).unwrap(),before);
  assert_eq!(fs::read_dir(dir.path()).unwrap().count(),3);
 }
 #[test]fn unsupported_header_flags_are_refused_instead_of_rewritten() {
  let attrs=BTreeMap::from([("GeneratedByEngineVersion".into(),"2.0".into()),("RequiredEngineVersion".into(),"2.0".into()),("Encoding".into(),"UTF-8".into()),("Format".into(),"Html".into()),("KeyCaseSensitive".into(),"Yes".into()),("StripKey".into(),"No".into())]);
  let dir=tempfile::tempdir().unwrap();let db=dir.path().join("input.db");let rows=vec![Entry{key:"a".into(),text:"body".into()}];let token=CancellationToken::default();studio_database::import_mdx_rows(&rows,&db,&"a".repeat(64),&attrs,&mut studio_database::Job::new(&token,&mut |_|{})).unwrap();let dest=dir.path().join("refused.mdx");assert_eq!(execute(&db,&dest,&mut ImportJob::new("unsupported",&token,&mut |_|{})).unwrap_err().code,ErrorCode::UnsupportedPolicy);assert!(!dest.exists());
 }
}
fn adler(data:&[u8])->u32 {let(mut a,mut b)=(1u32,0u32);for &c in data {a=(a+u32::from(c))%65521;b=(b+a)%65521;}(b<<16)|a}
fn groups(rows:&[Entry])->BTreeMap<&str,Vec<&str>> {let mut out:BTreeMap<&str,Vec<&str>>=BTreeMap::new();for row in rows {out.entry(&row.key).or_default().push(&row.text);}out}
fn decoded_rows(path:&Path,job:&mut ImportJob<'_>)->Result<Vec<Entry>> {
 let mut input=BufReader::new(File::open(path)?);let mut rows=Vec::new();let mut bytes=0;
 loop {tick(job,"db_to_mdx_verify",rows.len(),0)?;let mut line=Vec::new();let cap=6*(1024*1024+4096)+128;let n=(&mut input).take((cap+1) as u64).read_until(b'\n',&mut line)?;if n==0{break;}
  if n>cap||line.last()!=Some(&b'\n'){return Err(fail(ErrorCode::LimitExceeded,"Verification JSONL line limit exceeded"));}
  let row:Entry=serde_json::from_slice(&line).map_err(|e|fail(ErrorCode::Integrity,e.to_string()))?;bytes+=row.key.len()+row.text.len();if rows.len()>=100000||bytes>32*1024*1024{return Err(fail(ErrorCode::LimitExceeded,"Verification rows exceed database profile"));}rows.push(row);
 }Ok(rows)
}
fn original_encoding(attrs:&BTreeMap<String,String>)->Result<studio_core::Encoding> {
 for name in ["KeyCaseSensitive","StripKey"] {if !attrs.get(name).is_some_and(|v|matches!(v.to_ascii_lowercase().as_str(),"no"|"0")){return Err(fail(ErrorCode::UnsupportedPolicy,"Rebuild requires explicit KeyCaseSensitive=No and StripKey=No; flags are never silently changed"));}}
 if !attrs.get("Encrypted").map_or(true,|v|matches!(v.to_ascii_lowercase().as_str(),"no"|"0"|"")){return Err(fail(ErrorCode::UnsupportedPolicy,"Encrypted rebuild is unsupported"));}
 if !attrs.get("Format").is_some_and(|v|matches!(v.to_ascii_lowercase().as_str(),"html"|"text")){return Err(fail(ErrorCode::UnsupportedPolicy,"Require HTML or Text definitions"));}
 for name in ["GeneratedByEngineVersion","RequiredEngineVersion"] {if !attrs.get(name).is_some_and(|v|matches!(v.as_str(),"2"|"2.0")){return Err(fail(ErrorCode::UnsupportedPolicy,"Only MDX v2 rebuilding is supported"));}}
 if attrs.get("StyleSheet").is_some_and(|s|!s.is_empty()) && (!attrs.get("Format").is_some_and(|v|v.eq_ignore_ascii_case("html"))||!attrs.get("Compact").is_some_and(|v|matches!(v.to_ascii_lowercase().as_str(),"yes"|"1"))) {return Err(fail(ErrorCode::UnsupportedPolicy,"Numeric stylesheet rebuilding requires HTML and Compact=Yes"));}
 match attrs.get("Encoding").map(|v|v.to_ascii_uppercase()).as_deref(){Some("UTF-8"|"UTF8")=>Ok(studio_core::Encoding::Utf8),Some("UTF-16"|"UTF-16LE")=>Ok(studio_core::Encoding::Utf16),_=>Err(fail(ErrorCode::UnsupportedPolicy,"Unsupported stored MDX encoding"))}
}
pub(crate) fn execute(source:&Path,destination:&Path,job:&mut ImportJob<'_>)->Result<studio_database::MdxPublication> {
 match fs::symlink_metadata(destination){Ok(_)=>return Err(fail(ErrorCode::DestinationExists,"Destination exists")),Err(e) if e.kind()==std::io::ErrorKind::NotFound=>{},Err(e)=>return Err(e.into())}
 let data={let id=job.id;let token=job.token;let mut progress=|p:studio_database::Progress|(job.progress)(Progress {job_id:id.into(),stage:studio_application::Stage::Converting,phase:p.phase.into(),completed:p.completed,total:p.total});studio_database::read_for_rebuild(source,&mut studio_database::Job::new(token,&mut progress)).map_err(crate::database::mapped)?};
 let encoding=if let Some(attrs)=&data.dictionary_metadata {original_encoding(attrs)?}else{studio_core::Encoding::Utf8};
 let parent=destination.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new("."));let work=tempfile::tempdir_in(parent)?;let jsonl=work.path().join("source.jsonl");let packed=work.path().join("packed.mdx");
 let mut input=File::create(&jsonl)?;for(i,row)in data.rows.iter().enumerate(){tick(job,"db_to_mdx_spool",i,data.rows.len())?;serde_json::to_writer(&mut input,row).map_err(|e|fail(ErrorCode::Io,e.to_string()))?;input.write_all(b"\n")?;if input.stream_position()? >128*1024*1024{return Err(fail(ErrorCode::LimitExceeded,"Private JSONL exceeds 128 MiB"));}}input.flush()?;drop(input);
 let attrs=data.dictionary_metadata.as_ref();let metadata=studio_large_io::Metadata {title:attrs.and_then(|m|m.get("Title")).cloned().unwrap_or_else(||source.file_stem().and_then(|v|v.to_str()).unwrap_or("Dictionary").into()),description:attrs.and_then(|m|m.get("Description")).cloned().unwrap_or_default(),stylesheet:attrs.and_then(|m|m.get("StyleSheet")).cloned().unwrap_or_default(),extra:BTreeMap::new()};
 let limits=studio_large_io::IoLimits::default();let built=studio_large_io::execute(&studio_large_io::Request::PackMdx {source:jsonl,destination:packed.clone(),encoding,metadata},&limits,&mut studio_large_io::ImportJob::new(job.id,job.token,&mut *job.progress))?;
 let desired=data.dictionary_metadata.as_ref().unwrap_or(&built.metadata);
 let encoded=studio_v2_import::application::metadata::serialize(studio_v2_import::application::metadata::FileKind::Mdx,desired).map_err(|e|Error {code:e.code,detail:e.detail,message:e.message,limit:None})?;
 let mut original=File::open(&packed)?;let mut length=[0;4];original.read_exact(&mut length)?;let start=8+u64::from(u32::from_be_bytes(length));let total=original.metadata()?.len();let size=total.checked_sub(start).and_then(|n|n.checked_add(8+encoded.len() as u64)).ok_or_else(||fail(ErrorCode::Integrity,"Invalid staged MDX header length"))?;
 if size>128*1024*1024{return Err(fail(ErrorCode::LimitExceeded,"Rebuilt MDX exceeds 128 MiB"));}
 let mut stage=tempfile::NamedTempFile::new_in(work.path())?;stage.write_all(&(encoded.len() as u32).to_be_bytes())?;stage.write_all(&encoded)?;stage.write_all(&adler(&encoded).to_le_bytes())?;original.seek(SeekFrom::Start(start))?;let mut copied=0;let mut buffer=[0;65536];
 loop {tick(job,"db_to_mdx_copy",copied,(total-start) as usize)?;let n=original.read(&mut buffer)?;if n==0{break;}stage.write_all(&buffer[..n])?;copied+=n;}stage.flush()?;stage.as_file().sync_all()?;
 let verify=work.path().join("verify.jsonl");let checked=studio_large_io::execute(&studio_large_io::Request::ExportJsonl {source:stage.path().to_owned(),destination:verify.clone()},&limits,&mut studio_large_io::ImportJob::new(job.id,job.token,&mut *job.progress))?;
 let found=decoded_rows(&verify,job)?;if checked.metadata!=*desired||found.len()!=data.rows.len()||groups(&found)!=groups(&data.rows)||stage.as_file().metadata()?.len()!=size{return Err(fail(ErrorCode::Integrity,"Rebuilt MDX records, duplicate order, metadata or extent differ"));}
 let result=studio_database::MdxPublication {profile:"sqlite-mdx-v2-rebuild-v1",destination:destination.to_owned(),source_sha256:data.source_sha256,rows_sha256:data.rows_sha256,records:data.rows.len(),bytes:size,encoding:desired.get("Encoding").cloned().unwrap_or_else(||"UTF-8".into()),key_order:"stable-unicode16-lower",dictionary_metadata:desired.clone()};
 tick(job,"db_to_mdx_commit",1,1)?;stage.persist_noclobber(destination).map_err(|e|if e.error.kind()==std::io::ErrorKind::AlreadyExists {fail(ErrorCode::DestinationExists,"Destination exists")}else{e.error.into()})?;Ok(result)
}
