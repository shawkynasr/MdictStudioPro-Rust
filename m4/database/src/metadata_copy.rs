//! Change selected title/description/numeric stylesheet in a verified new database; never edit a source.
use super::*;

#[derive(Clone,Debug,Deserialize)]#[serde(deny_unknown_fields)]
pub struct MetadataEdits {pub title:Option<String>,pub description:Option<String>,pub stylesheet:Option<String>}
fn validate(edits:&MetadataEdits)->Result<()> {
 if edits.title.is_none()&&edits.description.is_none()&&edits.stylesheet.is_none(){return Err(error("invalid_input","Choose title, description or numeric stylesheet to replace"));}
 for (value,cap) in [(&edits.title,4096),(&edits.description,8192),(&edits.stylesheet,16384)] {
  if let Some(value)=value {
   if value.len()>cap{return Err(error("limit_exceeded","Title, description or stylesheet exceeds its 4/8/16 KiB budget"));}
   if value.chars().any(|c|c<'\u{20}'&&!matches!(c,'\t'|'\n'|'\r')||matches!(c,'\u{fffe}'|'\u{ffff}')){return Err(error("invalid_input","Metadata contains a character forbidden in XML"));}
  }
 }Ok(())
}
// Same LF triplet/decimal ID profile as the accepted MDX metadata writer.
pub(super) fn rules(style:&str)->Result<std::collections::BTreeSet<String>> {
 let mut ids=std::collections::BTreeSet::new();if style.is_empty(){return Ok(ids);}
 if style.contains('\r')||!style.ends_with('\n'){return Err(error("invalid_input","Numeric stylesheet requires LF triplets and a final LF; CR/CRLF is not normalized"));}
 let lines:Vec<_>=style.strip_suffix('\n').unwrap().split('\n').collect();
 if lines.len()%3!=0{return Err(error("invalid_input","Numeric stylesheet requires ID/prefix/suffix triplets"));}
 for triple in lines.chunks_exact(3){let id=triple[0];if id.is_empty()||id.len()>32||!id.bytes().all(|b|b.is_ascii_digit())||!ids.insert(id.to_owned())||triple[1].contains('\t')||triple[2].contains('\t'){return Err(error("invalid_input","Require unique decimal IDs <=32 bytes and prefixes/suffixes without tabs"));}}
 Ok(ids)
}
pub(super) fn markers(text:&str,ids:&std::collections::BTreeSet<String>,job:&Job<'_>)->Result<()> {
 let bytes=text.as_bytes();let mut pos=0usize;
 while pos<bytes.len(){if pos%4096==0{job.check()?;}if bytes[pos]==b'`'{let start=pos+1;let mut end=start;while end<bytes.len()&&bytes[end].is_ascii_digit(){end+=1;}if end>start&&end<bytes.len()&&bytes[end]==b'`'{if !ids.contains(&text[start..end]){return Err(error("invalid_input","A numeric definition marker has no replacement stylesheet rule"));}pos=end+1;continue;}}pos+=1;}
 job.check()
}
pub(super) fn execute(source:&Path,destination:&Path,expected:&str,edits:&MetadataEdits,job:&mut Job<'_>)->Result<Publication> {
 no_destination(destination)?;validate(edits)?;
 if expected.len()!=64||!expected.bytes().all(|b|b.is_ascii_hexdigit()){return Err(error("invalid_input","Require the opened snapshot SHA-256"));}
 let checked=open_checked(source,job)?;
 if !checked.source_sha256.eq_ignore_ascii_case(expected){return Err(error("integrity","Source differs from the opened snapshot; close and reload before saving a metadata copy"));}
 let mut attrs=checked.dictionary_metadata.clone().ok_or_else(||error("unsupported_profile","Metadata copy requires a database imported from MDX"))?;
 if let Some(title)=&edits.title{attrs.insert("Title".into(),title.clone());}
 if let Some(description)=&edits.description{attrs.insert("Description".into(),description.clone());}
 let ids=if let Some(style)=&edits.stylesheet {
  let ids=rules(style)?;
  if !style.is_empty()&&(!attrs.get("Format").is_some_and(|v|v.eq_ignore_ascii_case("html"))||!attrs.get("Compact").is_some_and(|v|matches!(v.to_ascii_lowercase().as_str(),"yes"|"1"))){return Err(error("unsupported_profile","Replacing numeric styles requires existing Format=Html and Compact=Yes"));}
  attrs.insert("StyleSheet".into(),style.clone());Some(ids)
 }else{None};
 validate_origin(&checked.source_sha256,&attrs)?;
 let mut rows=Vec::new();let mut stmt=checked.connection.prepare("SELECT entry,paraphrase FROM mdx ORDER BY rowid")?;let mut cursor=stmt.query([])?;
 while let Some(row)=cursor.next()?{job.tick("database_metadata_copy",rows.len(),checked.records)?;let entry=Entry {key:text(row,0,4096)?,text:text(row,1,BODY_CAP)?};if let Some(ids)=&ids{markers(&entry.text,ids,job)?;}rows.push(entry);}
 drop(cursor);drop(stmt);
 create_rows(&rows,destination,checked.profile,&checked.source_sha256,Some(&attrs),job)
}

#[cfg(test)]mod tests {
 use super::*;
 fn seed(dir:&Path,encoding:&str)->PathBuf {
  let source=dir.join("source.db");let attrs=BTreeMap::from([("Title".into(),"original".into()),("Description".into(),"before".into()),("StyleSheet".into(),"2\n<b>\n</b>\n".into()),("Format".into(),"Html".into()),("Compact".into(),"Yes".into()),("Encoding".into(),encoding.into()),("KeyCaseSensitive".into(),"No".into()),("StripKey".into(),"No".into())]);
  let rows=vec![Entry{key:"字".into(),text:"`2`first\r\n".into()},Entry{key:"字".into(),text:"second".into()},Entry{key:"مرحبا".into(),text:"أهلاً".into()},Entry{key:"empty".into(),text:String::new()}];
  import_mdx_rows(&rows,&source,&"a".repeat(64),&attrs,&mut Job::new(&CancellationToken::default(),&mut |_|{})).unwrap();source
 }
 fn edits()->MetadataEdits{MetadataEdits{title:Some("new 字 / مرحبا & <title>".into()),description:Some("new\nworld".into()),stylesheet:None}}
 #[test]fn stylesheet_copy_preserves_rows_and_unselected_metadata_and_rejects_missing_markers() {
  for encoding in ["UTF-8","UTF-16"] {
   let dir=tempfile::tempdir().unwrap();let source=seed(dir.path(),encoding);let token=CancellationToken::default();let original=read_for_rebuild(&source,&mut Job::new(&token,&mut |_|{})).unwrap();let dest=dir.path().join("styled.db");
   let style="2\n<span style=\"color:#008000\">\n</span>\n";
   let edit=MetadataEdits{title:None,description:None,stylesheet:Some(style.into())};let receipt=execute(&source,&dest,&original.source_sha256,&edit,&mut Job::new(&token,&mut |_|{})).unwrap();let copy=read_for_rebuild(&dest,&mut Job::new(&token,&mut |_|{})).unwrap();assert_eq!(copy.rows,original.rows);assert_eq!(receipt.rows_sha256,original.rows_sha256);let mut attrs=original.dictionary_metadata.clone().unwrap();attrs.insert("StyleSheet".into(),style.into());assert_eq!(copy.dictionary_metadata,Some(attrs));
   let missing=dir.path().join("missing.db");for style in ["", "1\n<b>\n</b>\n"] {let edits=MetadataEdits{title:None,description:None,stylesheet:Some(style.into())};assert_eq!(execute(&source,&missing,&original.source_sha256,&edits,&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"invalid_input");assert!(!missing.exists());}
   let stop=CancellationToken::default();let cancel=stop.clone();let mut progress=|p:Progress|if p.phase=="database_metadata_copy"{cancel.cancel();};assert_eq!(execute(&source,&missing,&original.source_sha256,&edit,&mut Job::new(&stop,&mut progress)).unwrap_err().code,"cancelled");assert!(!missing.exists());
  }
 }
 #[test]fn stylesheet_shape_bounds_flags_and_clearing_unmarked_bodies_are_checked() {
  let dir=tempfile::tempdir().unwrap();let source=seed(dir.path(),"UTF-8");let token=CancellationToken::default();let original=read_for_rebuild(&source,&mut Job::new(&token,&mut |_|{})).unwrap();let dest=dir.path().join("bad.db");
  for style in ["2\n<b>\n</b>","2\r\n<b>\r\n</b>\r\n","2\n<b>\n","x\n<b>\n</b>\n","2\n<b>\n</b>\n2\n<i>\n</i>\n","2\n<b>\t\n</b>\n"] {let edits=MetadataEdits{title:None,description:None,stylesheet:Some(style.into())};assert_eq!(execute(&source,&dest,&original.source_sha256,&edits,&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"invalid_input");assert!(!dest.exists());}
  let edits=MetadataEdits{title:None,description:None,stylesheet:Some("x".repeat(16385))};assert_eq!(execute(&source,&dest,&original.source_sha256,&edits,&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"limit_exceeded");
  let rows=vec![Entry{key:"a".into(),text:"unmarked".into()}];let base=original.dictionary_metadata.unwrap();
  for (name,value) in [("Format","Text"),("Compact","No")] {let mut attrs=base.clone();attrs.insert(name.into(),value.into());let input=dir.path().join(format!("{name}.db"));import_mdx_rows(&rows,&input,&"a".repeat(64),&attrs,&mut Job::new(&token,&mut |_|{})).unwrap();let hash=digest(&fs::read(&input).unwrap());let edits=MetadataEdits{title:None,description:None,stylesheet:Some("2\n<b>\n</b>\n".into())};assert_eq!(execute(&input,&dest,&hash,&edits,&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"unsupported_profile");}
  let input=dir.path().join("unmarked.db");import_mdx_rows(&rows,&input,&"a".repeat(64),&base,&mut Job::new(&token,&mut |_|{})).unwrap();let hash=digest(&fs::read(&input).unwrap());let edits=MetadataEdits{title:None,description:None,stylesheet:Some(String::new())};let receipt=execute(&input,&dest,&hash,&edits,&mut Job::new(&token,&mut |_|{})).unwrap();assert_eq!(receipt.dictionary_metadata.unwrap()["StyleSheet"],"");assert_eq!(read_for_rebuild(&dest,&mut Job::new(&token,&mut |_|{})).unwrap().rows,rows);
 }
 #[test]fn metadata_copy_preserves_every_row_styles_encoding_and_other_attributes() {
  for encoding in ["UTF-8","UTF-16"] {
   let dir=tempfile::tempdir().unwrap();let source=seed(dir.path(),encoding);let before=fs::read(&source).unwrap();let expected=digest(&before);let dest=dir.path().join("copy.db");let token=CancellationToken::default();
   let receipt=execute(&source,&dest,&expected,&edits(),&mut Job::new(&token,&mut |_|{})).unwrap();let original=read_for_rebuild(&source,&mut Job::new(&token,&mut |_|{})).unwrap();let copy=read_for_rebuild(&dest,&mut Job::new(&token,&mut |_|{})).unwrap();
   assert_eq!(copy.rows,original.rows);assert_eq!(copy.rows_sha256,original.rows_sha256);assert_eq!(receipt.source_sha256,expected);assert_eq!(receipt.records,4);
   let mut attrs=original.dictionary_metadata.unwrap();attrs.insert("Title".into(),edits().title.unwrap());attrs.insert("Description".into(),edits().description.unwrap());assert_eq!(copy.dictionary_metadata,Some(attrs));assert_eq!(fs::read(&source).unwrap(),before);
   let dest=dir.path().join("empty-title.db");execute(&source,&dest,&expected,&MetadataEdits{title:Some(String::new()),description:None,stylesheet:None},&mut Job::new(&token,&mut |_|{})).unwrap();let attrs=read_for_rebuild(&dest,&mut Job::new(&token,&mut |_|{})).unwrap().dictionary_metadata.unwrap();assert_eq!(attrs["Title"],"");assert_eq!(attrs["Description"],"before");
  }
 }
 #[test]fn stale_sources_cancel_and_destination_races_leave_no_partial_copy() {
  let dir=tempfile::tempdir().unwrap();let source=seed(dir.path(),"UTF-8");let before=fs::read(&source).unwrap();let expected=digest(&before);let token=CancellationToken::default();let dest=dir.path().join("out.db");
  assert_eq!(execute(&source,&dest,&"0".repeat(64),&edits(),&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"integrity");assert!(!dest.exists());
  for phase in ["database_snapshot","database_metadata_copy","database_insert","database_commit"] {
   let stop=CancellationToken::default();let cancel=stop.clone();let mut progress=|p:Progress|if p.phase==phase{cancel.cancel();};assert_eq!(execute(&source,&dest,&expected,&edits(),&mut Job::new(&stop,&mut progress)).unwrap_err().code,"cancelled");assert!(!dest.exists());assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);
  }
  let mut progress=|p:Progress|if p.phase=="database_commit"{fs::write(&dest,b"sentinel").unwrap();};assert_eq!(execute(&source,&dest,&expected,&edits(),&mut Job::new(&token,&mut progress)).unwrap_err().code,"destination_exists");assert_eq!(fs::read(&dest).unwrap(),b"sentinel");assert_eq!(execute(&source,&dest,&expected,&edits(),&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"destination_exists");assert_eq!(fs::read(source).unwrap(),before);assert_eq!(fs::read_dir(dir.path()).unwrap().count(),2);
 }
 #[test]fn invalid_metadata_and_databases_without_headers_are_refused() {
  let dir=tempfile::tempdir().unwrap();let source=seed(dir.path(),"UTF-8");let expected=digest(&fs::read(&source).unwrap());let dest=dir.path().join("out.db");let token=CancellationToken::default();
  for edits in [MetadataEdits{title:None,description:None,stylesheet:None},MetadataEdits{title:Some("bad\0".into()),description:None,stylesheet:None},MetadataEdits{title:Some("\u{ffff}".into()),description:None,stylesheet:None},MetadataEdits{title:Some("x".repeat(4097)),description:None,stylesheet:None},MetadataEdits{title:None,description:Some("x".repeat(8193)),stylesheet:None}] {assert!(execute(&source,&dest,&expected,&edits,&mut Job::new(&token,&mut |_|{})).is_err());assert!(!dest.exists());}
  let c=Connection::open(&source).unwrap();c.execute_batch("DROP TABLE studio_meta; PRAGMA application_id=0; PRAGMA user_version=0").unwrap();drop(c);let expected=digest(&fs::read(&source).unwrap());assert_eq!(execute(&source,&dest,&expected,&edits(),&mut Job::new(&token,&mut |_|{})).unwrap_err().code,"unsupported_profile");assert!(!dest.exists());
  assert!(serde_json::from_str::<MetadataEdits>(r#"{"title":"x","encoding":"changed"}"#).is_err());
 }
}
