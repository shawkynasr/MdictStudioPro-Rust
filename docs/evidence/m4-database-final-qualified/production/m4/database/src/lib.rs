//! Additive SQLite backend qualification. No Tauri routing in this first slice.
use rusqlite::{params,Connection,OpenFlags,config::DbConfig,limits::Limit,types::ValueRef};
use serde::{Deserialize,Serialize};
use std::{collections::BTreeMap,fs::{self,File},io::{Read,Write},path::{Path,PathBuf},sync::{Arc,atomic::{AtomicBool,Ordering}},time::{Duration,Instant}};
pub use studio_core::{CancellationToken,Entry,TxtProfile};
#[path="../../../m2/indexed-engine/src/sha256.rs"]mod sha256;
#[path="../../../m2/studio-core/src/casing.rs"]mod casing;
pub const PROFILE:&str="studio-sqlite-text-v1";
pub const MDX_PROFILE:&str="studio-sqlite-mdx-v1";
const APP_ID:i32=1296323408;
const FILE_CAP:u64=128*1024*1024;
const RECORD_CAP:usize=100000;
const DECODED_CAP:usize=32*1024*1024;
const BODY_CAP:usize=1024*1024;
const PAGE_CAP:usize=128;
const REPLY_CAP:usize=2*1024*1024;
const META_SQL:&str="CREATE TABLE studio_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)";
const MDX_SQL:&str="CREATE TABLE mdx (entry TEXT NOT NULL, paraphrase TEXT NOT NULL)";
#[derive(Debug,Serialize)]pub struct Error {pub code:&'static str,pub message:String}
pub type Result<T>=std::result::Result<T,Error>;
fn error(code:&'static str,message:impl Into<String>)->Error {Error {code,message:message.into()}}
impl From<std::io::Error> for Error {fn from(e:std::io::Error)->Self {error("io",e.to_string())}}
impl From<rusqlite::Error> for Error {fn from(e:rusqlite::Error)->Self {error("sqlite",e.to_string())}}
impl From<studio_core::Error> for Error {fn from(e:studio_core::Error)->Self {
 let code=match e.code {studio_core::ErrorCode::Cancelled=>"cancelled",studio_core::ErrorCode::LimitExceeded=>"limit_exceeded",studio_core::ErrorCode::UnrepresentableSource=>"unrepresentable_source",studio_core::ErrorCode::InvalidEncoding=>"invalid_encoding",_=>"invalid_input"};error(code,e.message)
}}
#[derive(Debug,Deserialize)]#[serde(tag="operation",rename_all="snake_case",deny_unknown_fields)]pub enum Request {
 TxtToDb {source:PathBuf,destination:PathBuf,profile:TxtProfile},
 DbToTxt {source:PathBuf,destination:PathBuf},
 DbToJsonl {source:PathBuf,destination:PathBuf},
 DbAddEntry {source:PathBuf,destination:PathBuf,expected_source_sha256:String,key:String,text:String},
 DbDeleteEntry {source:PathBuf,destination:PathBuf,expected_source_sha256:String,rowid:String},
 DbEditEntry {source:PathBuf,destination:PathBuf,expected_source_sha256:String,rowid:String,text:String,#[serde(default)]key:Option<String>},
 DbEditMetadata {source:PathBuf,destination:PathBuf,expected_source_sha256:String,edits:MetadataEdits},
 JsonlToDb {source:PathBuf,destination:PathBuf},
 Lookup {source:PathBuf,query:String,offset:u64,limit:usize},
 DefinitionLookup {source:PathBuf,query:String,#[serde(default)]lower:bool,offset:u64,limit:usize},
 PrefixLookup {source:PathBuf,query:String,offset:u64,limit:usize},
 Browse {source:PathBuf,offset:u64,limit:usize},
}
#[derive(Clone,Debug,Serialize)]pub struct Progress {pub phase:&'static str,pub completed:usize,pub total:usize}
pub struct Job<'a> {token:&'a CancellationToken,progress:&'a mut dyn FnMut(Progress),exhausted:Arc<AtomicBool>,deadline:Instant}
impl<'a> Job<'a> {
 pub fn new(token:&'a CancellationToken,progress:&'a mut dyn FnMut(Progress))->Self {Self {token,progress,exhausted:Arc::new(AtomicBool::new(false)),deadline:Instant::now()+Duration::from_secs(60)}}
 fn check(&self)->Result<()> {if self.token.is_cancelled(){Err(error("cancelled","Database operation cancelled before publication"))}else if Instant::now()>self.deadline||self.exhausted.load(Ordering::Relaxed){Err(error("limit_exceeded","SQLite statement/time work budget exceeded"))}else{Ok(())}}
 fn tick(&mut self,phase:&'static str,completed:usize,total:usize)->Result<()> {self.check()?;(self.progress)(Progress {phase,completed,total});self.check()}
}
/// A bounded, validated snapshot for the native MDX writer; never an IPC reply.
#[derive(Debug)]pub struct RebuildRows {pub rows:Vec<Entry>,pub source_sha256:String,pub rows_sha256:String,pub dictionary_metadata:Option<BTreeMap<String,String>>}
pub fn read_for_rebuild(source:&Path,job:&mut Job<'_>)->Result<RebuildRows> {
 let result:Result<RebuildRows>=(|| {
  let checked=open_checked(source,job)?;let mut stmt=checked.connection.prepare("SELECT entry,paraphrase FROM mdx ORDER BY rowid")?;let mut cursor=stmt.query([])?;let mut rows=Vec::new();
  while let Some(row)=cursor.next()? {job.tick("database_rebuild_read",rows.len(),checked.records)?;rows.push(Entry {key:text(row,0,4096)?,text:text(row,1,BODY_CAP)?});}
  job.check()?;Ok(RebuildRows {rows,source_sha256:checked.source_sha256,rows_sha256:checked.rows_sha256,dictionary_metadata:checked.dictionary_metadata})
 })();
 match result {Err(e) if e.code=="sqlite"=>{job.check()?;Err(e)},other=>other}
}
#[derive(Debug,Serialize)]pub struct MdxPublication {pub profile:&'static str,pub destination:PathBuf,pub source_sha256:String,pub rows_sha256:String,pub records:usize,pub bytes:u64,pub encoding:String,pub key_order:&'static str,pub dictionary_metadata:BTreeMap<String,String>}
#[derive(Debug,Serialize)]pub struct Publication {pub profile:&'static str,pub destination:PathBuf,pub records:usize,pub source_sha256:String,pub rows_sha256:String,pub bytes:u64,pub sqlite_version:String,pub text_profile:TxtProfile,#[serde(skip_serializing_if="Option::is_none")]pub dictionary_metadata:Option<BTreeMap<String,String>>}
#[derive(Debug,Serialize)]pub struct Match {pub rowid:String,pub key:String,pub text:String}
#[derive(Debug,Serialize)]pub struct Page {pub profile:&'static str,pub source_sha256:String,pub total:u64,pub offset:u64,pub next_offset:Option<u64>,pub rows:Vec<Match>,#[serde(skip_serializing_if="Option::is_none")]pub dictionary_metadata:Option<BTreeMap<String,String>>}
#[derive(Debug,Serialize)]#[serde(tag="operation",content="value",rename_all="snake_case")]pub enum Response {DbToMdx(MdxPublication),MdxToDb(Publication),TxtToDb(Publication),DbToTxt(Publication),DbToJsonl(Publication),JsonlToDb(Publication),DbEditMetadata(Publication),DbEditEntry(EntryEditPublication),DbDeleteEntry(EntryDeletePublication),DbAddEntry(EntryAddPublication),DefinitionLookup(Page),Lookup(Page),Browse(Page)}
fn limits()->studio_core::Limits {studio_core::Limits {max_entries:RECORD_CAP,max_decoded_bytes:DECODED_CAP,max_entry_bytes:BODY_CAP,max_file_bytes:FILE_CAP,max_source_lines:8_000_000,..studio_core::Limits::default()}}
fn no_destination(path:&Path)->Result<()> {match fs::symlink_metadata(path){Ok(_)=>Err(error("destination_exists","Destination exists")),Err(e) if e.kind()==std::io::ErrorKind::NotFound=>Ok(()),Err(e)=>Err(e.into())}}
fn parent(path:&Path)->&Path {path.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new("."))}
fn snapshot(source:&Path,database:bool,job:&mut Job<'_>)->Result<(tempfile::NamedTempFile,String)> {
 if database {for suffix in ["-wal","-shm","-journal"]{let mut sidecar=source.as_os_str().to_os_string();sidecar.push(suffix);if fs::symlink_metadata(PathBuf::from(sidecar)).is_ok(){return Err(error("unsupported_profile","Close/checkpoint the database and remove stale sidecars before importing; live WAL/journal databases are not copied"));}}}
 if !fs::symlink_metadata(source)?.file_type().is_file(){return Err(error("invalid_input","Require a regular non-symlink source"));}
 let mut input=File::open(source)?;if !input.metadata()?.is_file(){return Err(error("invalid_input","Require a regular source"));}
 let mut stage=tempfile::NamedTempFile::new()?;let mut hash=sha256::Sha256::new();let mut bytes=0u64;let mut buffer=[0u8;65536];
 loop {job.check()?;let n=input.read(&mut buffer)?;if n==0{break;}bytes+=n as u64;if bytes>FILE_CAP{return Err(error("limit_exceeded","Input exceeds 128 MiB"));}stage.write_all(&buffer[..n])?;hash.update(&buffer[..n]);}
 stage.flush()?;Ok((stage,sha256::hex(&hash.finish())))
}
fn configure(connection:&mut Connection,job:&Job<'_>)->Result<()> {
 connection.busy_timeout(Duration::ZERO)?;
 connection.set_db_config(DbConfig::SQLITE_DBCONFIG_DEFENSIVE,true)?;
 connection.set_db_config(DbConfig::SQLITE_DBCONFIG_ENABLE_TRIGGER,false)?;
 connection.set_db_config(DbConfig::SQLITE_DBCONFIG_ENABLE_VIEW,false)?;
 for (kind,cap) in [(Limit::SQLITE_LIMIT_LENGTH,(BODY_CAP+8192) as i32),(Limit::SQLITE_LIMIT_SQL_LENGTH,16384),(Limit::SQLITE_LIMIT_COLUMN,16),(Limit::SQLITE_LIMIT_EXPR_DEPTH,32),(Limit::SQLITE_LIMIT_COMPOUND_SELECT,4),(Limit::SQLITE_LIMIT_ATTACHED,0),(Limit::SQLITE_LIMIT_VARIABLE_NUMBER,8),(Limit::SQLITE_LIMIT_WORKER_THREADS,0)]{connection.set_limit(kind,cap)?;}
 let token=job.token.clone();let exhausted=job.exhausted.clone();let deadline=job.deadline;let mut calls=0usize;
 connection.progress_handler(1000,Some(move||{calls+=1;let hit=calls>50000||Instant::now()>deadline;if hit{exhausted.store(true,Ordering::Relaxed);}token.is_cancelled()||hit}))?;
 connection.execute_batch("PRAGMA trusted_schema=OFF; PRAGMA mmap_size=0; PRAGMA cache_size=-4096; PRAGMA temp_store=FILE;")?;Ok(())
}
fn text(row:&rusqlite::Row<'_>,column:usize,cap:usize)->Result<String> {
 let ValueRef::Text(bytes)=row.get_ref(column)? else{return Err(error("unsupported_profile","Require TEXT cells; NULL, numeric cells, resource BLOBs and compressed definitions are not coerced"));};
 if bytes.len()>cap{return Err(error("limit_exceeded","Database cell exceeds key/body budget"));}
 Ok(std::str::from_utf8(bytes).map_err(|e|error("invalid_encoding",e.to_string()))?.to_owned())
}
fn schema(connection:&Connection)->Result<bool> {
 let mut stmt=connection.prepare("SELECT type,name,sql FROM sqlite_schema WHERE name NOT GLOB 'sqlite_*' ORDER BY name")?;let mut rows=stmt.query([])?;let mut objects=BTreeMap::new();
 while let Some(row)=rows.next()? {if objects.len()>=8{return Err(error("unsupported_profile","Unexpected schema objects"));}let kind=text(row,0,32)?;let name=text(row,1,128)?;let sql=text(row,2,8192)?;
  if !matches!((kind.as_str(),name.as_str()),("table","mdx")|("table","studio_meta")|("index","entry_index"))||kind=="table"&&!sql.trim_start().to_ascii_uppercase().starts_with("CREATE TABLE "){return Err(error("unsupported_profile","Only ordinary mdx/studio_meta tables and entry_index are supported"));}objects.insert(name,kind);
 }
 if objects.get("mdx").map(String::as_str)!=Some("table"){return Err(error("unsupported_profile","Missing ordinary mdx table"));}
 let mut stmt=connection.prepare("PRAGMA main.table_xinfo(mdx)")?;let mut rows=stmt.query([])?;let mut names=Vec::new();
 while let Some(row)=rows.next()? {if names.len()>=2{return Err(error("unsupported_profile","mdx must have exactly entry/paraphrase columns"));}let name=text(row,1,128)?;let datatype=text(row,2,32)?;let not_null:i64=row.get(3)?;let pk:i64=row.get(5)?;let hidden:i64=row.get(6)?;if !datatype.eq_ignore_ascii_case("text")||not_null!=1||pk!=0||hidden!=0{return Err(error("unsupported_profile","Require two ordinary NOT NULL TEXT columns without primary-key deduplication"));}names.push(name);}
 if names!=["entry","paraphrase"]{return Err(error("unsupported_profile","Unsupported mdx columns"));}
 Ok(objects.contains_key("studio_meta"))
}
fn metadata(connection:&Connection)->Result<BTreeMap<String,String>> {
 let mut stmt=connection.prepare("SELECT key,value FROM studio_meta")?;let mut rows=stmt.query([])?;let mut meta=BTreeMap::new();
 while let Some(row)=rows.next()? {if meta.len()>=8{return Err(error("unsupported_profile","Metadata field cap exceeded"));}let key=text(row,0,128)?;let value=text(row,1,if key=="mdx_header_json"{512*1024}else{4096})?;if meta.insert(key,value).is_some(){return Err(error("integrity","Duplicate metadata keys"));}}
 let mut columns=connection.prepare("PRAGMA main.table_xinfo(studio_meta)")?;let mut cursor=columns.query([])?;let mut index=0;
 while let Some(row)=cursor.next()?{let name=text(row,1,128)?;let kind=text(row,2,32)?;let not_null:i64=row.get(3)?;let pk:i64=row.get(5)?;let hidden:i64=row.get(6)?;
  if index>=2||name!=(if index==0{"key"}else{"value"})||!kind.eq_ignore_ascii_case("text")||hidden!=0||pk!=(if index==0{1}else{0})||(index==1&&not_null!=1){return Err(error("unsupported_profile","Unsupported Studio metadata columns"));}index+=1;
 }if index!=2{return Err(error("unsupported_profile","Missing metadata columns"));}
 let base=["profile","records","rows_sha256","source_sha256","text_profile"];
 let is_mdx=meta.get("profile").map(String::as_str)==Some(MDX_PROFILE);
 let expected=if is_mdx{7}else{5};
 if meta.len()!=expected||base.iter().any(|k|!meta.contains_key(*k))||(!is_mdx&&meta["profile"]!=PROFILE){return Err(error("unsupported_profile","Unknown Studio metadata schema"));}
 if is_mdx {
  let raw=meta.get("mdx_header_json").ok_or_else(||error("integrity","Missing MDX header"))?;
  if meta.get("mdx_header_sha256")!=Some(&digest(raw.as_bytes())){return Err(error("integrity","MDX metadata digest differs"));}
  let attrs:BTreeMap<String,String>=serde_json::from_str(raw).map_err(|e|error("integrity",e.to_string()))?;validate_origin(&meta["source_sha256"],&attrs)?;
 }Ok(meta)
}
fn frame(hash:&mut sha256::Sha256,ordinal:usize,key:&str,body:&str) {hash.update(&(ordinal as u64).to_be_bytes());for data in [key.as_bytes(),body.as_bytes()]{hash.update(&(data.len() as u64).to_be_bytes());hash.update(data);}}
fn profile_name(profile:TxtProfile)->&'static str {match profile {TxtProfile::CanonicalV1=>"canonical_v1",TxtProfile::LegacyBodySpanV1=>"legacy_body_span_v1"}}
struct Checked {connection:Connection,_snapshot:tempfile::NamedTempFile,source_sha256:String,rows_sha256:String,records:usize,profile:TxtProfile,db_profile:&'static str,dictionary_metadata:Option<BTreeMap<String,String>>}
fn open_checked(source:&Path,job:&mut Job<'_>)->Result<Checked> {
 job.tick("database_snapshot",0,1)?;let(snapshot,source_sha256)=snapshot(source,true,job)?;
 let mut header=[0u8;100];File::open(snapshot.path())?.read_exact(&mut header).map_err(|_|error("invalid_input","Truncated SQLite header"))?;
 if &header[..16]!=b"SQLite format 3\0"{return Err(error("invalid_input","Not a SQLite 3 database"));}
 if header[18]!=1||header[19]!=1{return Err(error("unsupported_profile","Only closed rollback-journal databases are supported; switch WAL databases to journal_mode=DELETE first"));}
 let mut connection=Connection::open_with_flags(snapshot.path(),OpenFlags::SQLITE_OPEN_READ_ONLY|OpenFlags::SQLITE_OPEN_NO_MUTEX)?;configure(&mut connection,job)?;
 let own=schema(&connection)?;
 let app:i32=connection.pragma_query_value(None,"application_id",|r|r.get(0))?;let revision:i32=connection.pragma_query_value(None,"user_version",|r|r.get(0))?;
 let meta=if own {if app!=APP_ID||!matches!(revision,1|2){return Err(error("unsupported_profile","Unknown Studio SQLite revision"));}Some(metadata(&connection)?)}else{if app!=0||revision!=0{return Err(error("unsupported_profile","Legacy import requires unclaimed application/schema IDs"));}None};
 let db_profile=if meta.as_ref().is_some_and(|m|m["profile"]==MDX_PROFILE){MDX_PROFILE}else{PROFILE};
 if own&&revision!=(if db_profile==MDX_PROFILE{2}else{1}){return Err(error("unsupported_profile","Metadata and SQLite revision disagree"));}
 let dictionary_metadata=meta.as_ref().filter(|m|m["profile"]==MDX_PROFILE).map(|m|serde_json::from_str::<BTreeMap<String,String>>(&m["mdx_header_json"]).map_err(|e|error("integrity",e.to_string()))).transpose()?;
 let profile=match meta.as_ref().map(|m|m["text_profile"].as_str()){None|Some("canonical_v1")=>TxtProfile::CanonicalV1,Some("legacy_body_span_v1")=>TxtProfile::LegacyBodySpanV1,_=>return Err(error("unsupported_profile","Unknown stored text profile"))};
 let integrity:String=connection.query_row("PRAGMA quick_check(1)",[],|r|r.get(0))?;if integrity!="ok"{return Err(error("integrity",integrity));}
 let mut stmt=connection.prepare("SELECT entry,paraphrase FROM mdx ORDER BY rowid")?;let mut rows=stmt.query([])?;let mut count=0;let mut decoded=0;let mut hash=sha256::Sha256::new();
 while let Some(row)=rows.next()? {job.check()?;if count>=RECORD_CAP{return Err(error("limit_exceeded","Database exceeds 100,000 records"));}let key=text(row,0,4096)?;let body=text(row,1,BODY_CAP)?;if key.is_empty()||key=="</>"||key.contains(['\0','\r','\n']){return Err(error("invalid_input","Invalid database headword"));}decoded+=key.len()+body.len();if decoded>DECODED_CAP{return Err(error("limit_exceeded","Database decoded rows exceed 32 MiB"));}frame(&mut hash,count,&key,&body);count+=1;if count%256==0{job.tick("database_validate",count,0)?;}}
 if count==0{return Err(error("invalid_input","Empty dictionary table"));}let rows_sha256=sha256::hex(&hash.finish());
 if let Some(meta)=meta {if meta["rows_sha256"]!=rows_sha256||meta["records"]!=count.to_string(){return Err(error("integrity","Studio row digest/count differs; external edits require a later editing profile"));}}
 drop(rows);drop(stmt);job.check()?;Ok(Checked {connection,_snapshot:snapshot,source_sha256,rows_sha256,records:count,profile,db_profile,dictionary_metadata})
}
fn publication(stage:tempfile::NamedTempFile,destination:&Path,job:&mut Job<'_>)->Result<u64> {
 stage.as_file().sync_all()?;let bytes=stage.as_file().metadata()?.len();if bytes>FILE_CAP{return Err(error("limit_exceeded","Output exceeds 128 MiB"));}job.tick("database_commit",1,1)?;
 stage.persist_noclobber(destination).map_err(|e|if e.error.kind()==std::io::ErrorKind::AlreadyExists{error("destination_exists","Destination exists")}else{e.error.into()})?;Ok(bytes)
}
fn create(source:&Path,destination:&Path,profile:TxtProfile,job:&mut Job<'_>)->Result<Publication> {
 no_destination(destination)?;job.tick("txt_snapshot",0,1)?;let(snapshot,source_sha256)=snapshot(source,false,job)?;
 let token=job.token.clone();let rows=studio_core::read_txt(snapshot.path(),profile,&limits(),&mut studio_core::JobContext::new(&token,&mut |_|{}))?;
 create_rows(&rows,destination,profile,&source_sha256,None,job)
}
fn digest(bytes:&[u8])->String {let mut hash=sha256::Sha256::new();hash.update(bytes);sha256::hex(&hash.finish())}
fn validate_origin(source_sha256:&str,attributes:&BTreeMap<String,String>)->Result<()> {
 if source_sha256.len()!=64||!source_sha256.bytes().all(|b|b.is_ascii_hexdigit()){return Err(error("invalid_input","Require source SHA-256"));}
 if attributes.is_empty()||attributes.len()>256||attributes.iter().map(|(k,v)|k.len()+v.len()).sum::<usize>()>65536{return Err(error("limit_exceeded","MDX metadata exceeds 256 attributes or 64 KiB"));}Ok(())
}
/// Called only after the desktop's bounded MDX exporter verifies the source.
/// This API stores decoded header attributes; it does not assert raw MDX bytes.
pub fn import_mdx_rows(rows:&[Entry],destination:&Path,source_sha256:&str,attributes:&BTreeMap<String,String>,job:&mut Job<'_>)->Result<Publication> {
 validate_origin(source_sha256,attributes)?;create_rows(rows,destination,TxtProfile::CanonicalV1,source_sha256,Some(attributes),job)
}
fn create_rows(rows:&[Entry],destination:&Path,profile:TxtProfile,source_sha256:&str,attributes:Option<&BTreeMap<String,String>>,job:&mut Job<'_>)->Result<Publication> {
 no_destination(destination)?;job.check()?;
 if rows.is_empty()||rows.len()>RECORD_CAP{return Err(error("limit_exceeded","Require 1..100,000 rows"));}
 let mut decoded=0;for row in rows {job.check()?;if row.key.is_empty()||row.key=="</>"||row.key.contains(['\0','\r','\n']){return Err(error("invalid_input","Headword cannot be represented by this database profile"));}if row.key.len()>4096||row.text.len()>BODY_CAP{return Err(error("limit_exceeded","Key or body budget exceeded"));}decoded+=row.key.len()+row.text.len();if decoded>DECODED_CAP{return Err(error("limit_exceeded","Decoded rows exceed 32 MiB"));}}
 let db_profile=if attributes.is_some(){MDX_PROFILE}else{PROFILE};
 let mut hash=sha256::Sha256::new();for(i,row)in rows.iter().enumerate(){frame(&mut hash,i,&row.key,&row.text);}let rows_sha256=sha256::hex(&hash.finish());
 let work=tempfile::tempdir_in(parent(destination))?;let stage=tempfile::NamedTempFile::new_in(work.path())?;let mut connection=Connection::open_with_flags(stage.path(),OpenFlags::SQLITE_OPEN_READ_WRITE|OpenFlags::SQLITE_OPEN_NO_MUTEX)?;configure(&mut connection,job)?;
 connection.execute_batch("PRAGMA page_size=4096; PRAGMA max_page_count=32768; PRAGMA journal_mode=DELETE; PRAGMA synchronous=FULL;")?;
 connection.pragma_update(None,"application_id",APP_ID)?;connection.pragma_update(None,"user_version",if attributes.is_some(){2}else{1})?;
 {let tx=connection.transaction()?;tx.execute_batch(MDX_SQL)?;tx.execute_batch(META_SQL)?;
  {let mut insert=tx.prepare("INSERT INTO mdx(entry,paraphrase) VALUES (?1,?2)")?;for(i,row)in rows.iter().enumerate(){job.tick("database_insert",i,rows.len())?;insert.execute(params![row.key,row.text])?;}}
  tx.execute_batch("CREATE INDEX entry_index ON mdx(entry COLLATE BINARY)")?;
  for(key,value)in [("profile",db_profile.to_owned()),("records",rows.len().to_string()),("rows_sha256",rows_sha256.clone()),("source_sha256",source_sha256.to_owned()),("text_profile",profile_name(profile).to_owned())]{tx.execute("INSERT INTO studio_meta(key,value) VALUES (?1,?2)",params![key,value])?;}
  if let Some(attrs)=attributes {let raw=serde_json::to_string(attrs).map_err(|e|error("internal",e.to_string()))?;for(key,value)in [("mdx_header_sha256",digest(raw.as_bytes())),("mdx_header_json",raw)]{tx.execute("INSERT INTO studio_meta(key,value) VALUES (?1,?2)",params![key,value])?;}}
  tx.commit()?;
 }connection.close().map_err(|(_,e)|Error::from(e))?;
 let verified=open_checked(stage.path(),job)?;if verified.records!=rows.len()||verified.rows_sha256!=rows_sha256||verified.profile!=profile||verified.db_profile!=db_profile||verified.dictionary_metadata.as_ref()!=attributes{return Err(error("integrity","Staged database failed row verification"));}drop(verified);
 let receipt=Publication {profile:db_profile,destination:destination.to_owned(),records:rows.len(),source_sha256:source_sha256.to_owned(),rows_sha256,bytes:stage.as_file().metadata()?.len(),sqlite_version:rusqlite::version().into(),text_profile:profile,dictionary_metadata:attributes.cloned()};
 publication(stage,destination,job)?;Ok(receipt)
}
fn export(source:&Path,destination:&Path,job:&mut Job<'_>)->Result<Publication> {
 no_destination(destination)?;let checked=open_checked(source,job)?;let mut stmt=checked.connection.prepare("SELECT entry,paraphrase FROM mdx ORDER BY rowid")?;let mut cursor=stmt.query([])?;let mut rows=Vec::new();
 while let Some(row)=cursor.next()?{job.check()?;rows.push(Entry {key:text(row,0,4096)?,text:text(row,1,BODY_CAP)?});}
 let token=job.token.clone();let data=studio_core::render_txt(&rows,checked.profile,&limits(),&mut studio_core::JobContext::new(&token,&mut |_|{}))?;
 let parsed=studio_core::parse_txt(&data,checked.profile,&limits(),&mut studio_core::JobContext::new(&token,&mut |_|{}))?;if parsed!=rows{return Err(error("unrepresentable_source","TXT reparse differs from stored database rows"));}drop(parsed);
 let mut stage=tempfile::NamedTempFile::new_in(parent(destination))?;for chunk in data.chunks(65536){job.check()?;stage.write_all(chunk)?;}stage.flush()?;
 let receipt=Publication {profile:checked.db_profile,destination:destination.to_owned(),records:checked.records,source_sha256:checked.source_sha256,rows_sha256:checked.rows_sha256,bytes:data.len() as u64,sqlite_version:rusqlite::version().into(),text_profile:checked.profile,dictionary_metadata:checked.dictionary_metadata};
 publication(stage,destination,job)?;Ok(receipt)
}
fn page(source:&Path,query:Option<&str>,prefix:bool,offset:u64,limit:usize,job:&mut Job<'_>)->Result<Page> {
 if query.is_some_and(|q|q.is_empty()||q.len()>4096||q.contains('\0'))||limit>PAGE_CAP||offset>RECORD_CAP as u64{return Err(error("invalid_input","Require a nonempty <=4 KiB key, offset <=100,000 and page <=128"));}
 let checked=open_checked(source,job)?;checked_page(&checked,query,prefix,offset,limit,job)
}
fn checked_page(checked:&Checked,query:Option<&str>,prefix:bool,offset:u64,limit:usize,job:&mut Job<'_>)->Result<Page> {
 job.tick("database_page",0,checked.records)?;
 let count:i64=checked.connection.query_row("SELECT count(*) FROM mdx WHERE (?1 IS NULL OR (?2=0 AND entry=?1 COLLATE BINARY) OR (?2=1 AND substr(entry,1,length(?1))=?1 COLLATE BINARY))",params![query,prefix],|r|r.get(0))?;
 let total=u64::try_from(count).map_err(|_|error("integrity","SQLite returned a negative row count"))?;
 let mut stmt=checked.connection.prepare("SELECT rowid,entry,paraphrase FROM mdx WHERE (?1 IS NULL OR (?2=0 AND entry=?1 COLLATE BINARY) OR (?2=1 AND substr(entry,1,length(?1))=?1 COLLATE BINARY)) ORDER BY rowid LIMIT ?3 OFFSET ?4")?;
 let mut cursor=stmt.query(params![query,prefix,limit as i64,offset as i64])?;let mut rows=Vec::new();let mut bytes=0;
 while let Some(row)=cursor.next()?{job.check()?;let rowid:i64=row.get(0)?;let key=text(row,1,4096)?;let text=text(row,2,BODY_CAP)?;bytes+=key.len()+text.len();if bytes>REPLY_CAP{return Err(error("limit_exceeded","Complete database page exceeds 2 MiB"));}rows.push(Match {rowid:rowid.to_string(),key,text});}
 let next=offset.min(total)+rows.len() as u64;let page=Page {profile:checked.db_profile,source_sha256:checked.source_sha256.clone(),total,offset,next_offset:if limit>0&&next<total{Some(next)}else{None},rows,dictionary_metadata:checked.dictionary_metadata.clone()};
 if serde_json::to_vec(&page).map_err(|e|error("internal",e.to_string()))?.len()>REPLY_CAP{return Err(error("limit_exceeded","Serialized database page exceeds 2 MiB"));}
 job.check()?;Ok(page)
}
pub fn execute(request:&Request,job:&mut Job<'_>)->Result<Response> {
 job.check()?;let result=match request {Request::DbAddEntry {source,destination,expected_source_sha256,key,text}=>entry_add::execute(source,destination,expected_source_sha256,key,text,job).map(Response::DbAddEntry),Request::DbDeleteEntry {source,destination,expected_source_sha256,rowid}=>entry_delete::execute(source,destination,expected_source_sha256,rowid,job).map(Response::DbDeleteEntry),Request::TxtToDb {source,destination,profile}=>create(source,destination,*profile,job).map(Response::TxtToDb),Request::DbToTxt {source,destination}=>export(source,destination,job).map(Response::DbToTxt),Request::DbEditEntry {source,destination,expected_source_sha256,rowid,text,key}=>entry_copy::execute_with_key(source,destination,expected_source_sha256,rowid,text,key.as_deref(),job).map(Response::DbEditEntry),Request::DbEditMetadata {source,destination,expected_source_sha256,edits}=>metadata_copy::execute(source,destination,expected_source_sha256,edits,job).map(Response::DbEditMetadata),Request::JsonlToDb {source,destination}=>jsonl::import(source,destination,job).map(Response::JsonlToDb),Request::DbToJsonl {source,destination}=>jsonl::export(source,destination,job).map(Response::DbToJsonl),Request::DefinitionLookup {source,query,lower,offset,limit}=>Reader::open(source,job).and_then(|mut reader|reader.page(if *lower{ReaderQuery::LowerDefinition(query)}else{ReaderQuery::Definition(query)},*offset,*limit,job)).map(Response::DefinitionLookup),Request::Lookup {source,query,offset,limit}=>page(source,Some(query),false,*offset,*limit,job).map(Response::Lookup),Request::PrefixLookup {source,query,offset,limit}=>page(source,Some(query),true,*offset,*limit,job).map(Response::Lookup),Request::Browse {source,offset,limit}=>page(source,None,false,*offset,*limit,job).map(Response::Browse)};
 match result {Err(e) if e.code=="sqlite"=>{job.check()?;Err(e)},other=>other}
}
mod jsonl;
mod metadata_copy;
mod entry_copy;
mod entry_delete;
mod entry_add;
pub use entry_add::EntryAddPublication;
pub use entry_delete::EntryDeletePublication;
pub use entry_copy::EntryEditPublication;
pub use metadata_copy::MetadataEdits;
mod pattern;
mod reader;
pub use reader::{Reader,ReaderInfo,ReaderQuery};
#[cfg(test)]mod tests;
