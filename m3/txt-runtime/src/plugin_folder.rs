//! Explicit bounded folder inventory; one isolated inspection process per file.
use super::*;
#[derive(Debug,Deserialize)]#[serde(deny_unknown_fields)]pub struct Request {
 pub python:PathBuf,pub folder:PathBuf,pub destination:PathBuf,pub trusted:bool,
}
impl Request {pub(crate) fn validate(&self)->crate::ApiResult<()> {
 if !self.trusted{return Err(crate::ApiError {code:crate::ApiCode::InvalidInput,message:"Folder inspection imports Python code; confirm trust for this folder".into()});}Ok(())
}}
#[derive(Debug,Serialize)]pub struct FileError {pub code:&'static str,pub message:String}
#[derive(Debug,Serialize)]pub struct Entry {
 pub filename:String,pub source:PathBuf,pub plugin_sha256:Option<String>,pub catalog:Option<inspection::Catalog>,pub error:Option<FileError>,
}
#[derive(Debug,Serialize)]pub struct Receipt {
 pub profile:&'static str,pub folder:PathBuf,pub destination:PathBuf,pub ignored_entries:usize,pub entries:Vec<Entry>,
}
fn file_error(error:&Error)->FileError {
 FileError {code:match error.code {ErrorCode::LimitExceeded=>"limit_exceeded",ErrorCode::Io=>"io",ErrorCode::InvalidInput=>"invalid_input",_=>"engine"},message:error.message.chars().take(512).collect()}
}
fn bounded(receipt:&Receipt)->Result<Vec<u8>> {
 let data=serde_json::to_vec(receipt).map_err(|e|invalid(e.to_string()))?;
 if data.len()>131072{return Err(limit("Folder catalog exceeds 128 KiB; select a smaller folder"));}Ok(data)
}
struct Candidate {filename:String,source:PathBuf,snapshot:PathBuf,hash:Option<String>,error:Option<FileError>}
pub(crate) fn execute(r:&Request,job:&mut ImportJob<'_>)->Result<Receipt> {
 #[cfg(not(any(target_os="macos",target_os="linux")))]return Err(fail(ErrorCode::UnsupportedPlatform,"Plugin folder inspection currently supports macOS/Linux only"));
 check(job)?;if !r.trusted{return Err(invalid("Plugin folder inspection requires explicit trust"));}
 if !fs::symlink_metadata(&r.folder)?.file_type().is_dir(){return Err(invalid("Select a real folder without a symlink"));}
 match fs::symlink_metadata(&r.destination){Ok(_)=>return Err(fail(ErrorCode::DestinationExists,"Destination folder exists")),Err(e) if e.kind()==std::io::ErrorKind::NotFound=>{},Err(e)=>return Err(e.into())}
 let folder=fs::canonicalize(&r.folder)?;
 let python=if r.python.is_absolute(){r.python.clone()}else{std::env::current_dir()?.join(&r.python)};
 if !python.is_file(){return Err(invalid("Choose an existing Python interpreter executable"));}
 // Inventory caps are checked before importing ANY candidate, without recursion.
 let mut names=std::collections::BTreeMap::new();let mut ignored=0;let mut count=0;
 for entry in fs::read_dir(&folder)? {
  check(job)?;let entry=entry?;count+=1;if count>256{return Err(limit("Plugin folder has more than 256 top-level entries"));}
  let name=entry.file_name();let name=name.to_str().ok_or_else(||invalid("Plugin folder filenames must be UTF-8"))?;
  if name.starts_with("__")||!name.ends_with(".py"){ignored+=1;continue;}
  if name.len()>256||name.chars().any(|c|c=='/'||c=='\\'){return Err(invalid("Plugin filenames require <=256 UTF-8 bytes and no path separators"));}
  names.insert(name.to_owned(),entry.path());if names.len()>16{return Err(limit("Plugin folder has more than 16 candidate .py files"));}
 }
 let parent=r.destination.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new("."));
 let root=tempfile::tempdir_in(parent)?;let root_path=fs::canonicalize(root.path())?;let result=root_path.join("result");fs::create_dir(&result)?;
 let start=Instant::now();let mut candidates=Vec::new();
 // Freeze all root plugin bytes before any trusted imports can affect peers.
 for (i,(filename,source)) in names.into_iter().enumerate() {
  event(job,"python_folder_snapshot",0)?;
  let snapshot=root_path.join(format!("candidate-{i:03}.py"));
  let (hash,error)=match copy(&source,&snapshot,PLUGIN,job){Ok(hash)=>(Some(hash),None),Err(e)=>{if e.code==ErrorCode::Cancelled{return Err(e);} (None,Some(file_error(&e)))}};
  candidates.push(Candidate {filename,source,snapshot,hash,error});
 }
 let mut receipt=Receipt {profile:"trusted-python-folder-v1",folder,destination:r.destination.clone(),ignored_entries:ignored,entries:Vec::new()};
 let total=candidates.len().max(1);
 for (i,c) in candidates.into_iter().enumerate() {
  event(job,"python_folder_inspect",i*100/total)?;
  let remaining=DEADLINE.checked_sub(start.elapsed()).filter(|d|!d.is_zero()).ok_or_else(||limit("Plugin folder inspection exceeded 300 seconds"))?;
  let mut entry=Entry {filename:c.filename,source:c.source.clone(),plugin_sha256:c.hash,catalog:None,error:c.error};
  if entry.error.is_none() {
   let request=inspection::Request {python:python.clone(),plugin:c.snapshot,destination:result.join(format!("file-{i:03}")),trusted:true};
   match inspection::execute_source(&request,job,remaining,Some(&c.source)) {
    Ok(found)=>{if Some(&found.plugin_sha256)!=entry.plugin_sha256.as_ref(){return Err(invalid("Plugin snapshot changed during folder inspection"));}entry.catalog=Some(found.catalog);},
    Err(e)=>{if e.code==ErrorCode::Cancelled{return Err(e);}entry.error=Some(file_error(&e));}
   }
  }
  receipt.entries.push(entry);bounded(&receipt)?;inventory(&root_path)?;
 }
 if start.elapsed()>DEADLINE{return Err(limit("Plugin folder inspection exceeded 300 seconds"));}
 let data=bounded(&receipt)?;
 let mut file=OpenOptions::new().write(true).create_new(true).open(result.join("catalog.json"))?;file.write_all(&data)?;file.sync_all()?;
 inventory(&result)?;event(job,"python_folder_commit",100)?;
 #[cfg(unix)]publish(&result,&r.destination)?;
 Ok(receipt)
}

#[cfg(test)]#[path="plugin_folder_tests.rs"]mod tests;
