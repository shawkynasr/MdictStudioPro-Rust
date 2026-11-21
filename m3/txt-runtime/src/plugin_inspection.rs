//! Explicit selected-file inspection in the existing trusted subprocess lane.
use super::*;
#[derive(Debug,Deserialize)]#[serde(deny_unknown_fields)]pub struct Request {
 pub python:PathBuf,pub plugin:PathBuf,pub destination:PathBuf,pub trusted:bool,
}
impl Request {pub(crate) fn validate(&self)->crate::ApiResult<()> {
 if !self.trusted{return Err(crate::ApiError {code:crate::ApiCode::InvalidInput,message:"Plugin inspection imports local code; confirm trust first".into()});}Ok(())
}}
#[derive(Debug,Serialize,Deserialize)]#[serde(deny_unknown_fields)]pub struct Field {
 pub key:String,#[serde(rename="type")]pub kind:String,pub label:String,pub default:serde_json::Value,pub choices:Vec<String>,
}
#[derive(Debug,Serialize,Deserialize)]#[serde(deny_unknown_fields)]pub struct Class {
 pub class_name:String,pub name:String,pub description:String,pub fields:Vec<Field>,pub schema_error:Option<String>,
}
#[derive(Debug,Serialize,Deserialize)]#[serde(deny_unknown_fields)]pub struct Catalog {pub version:u32,pub classes:Vec<Class>}
fn identifier(s:&str,max:usize)->bool {!s.is_empty()&&s.len()<=max&&s.bytes().enumerate().all(|(i,b)|b.is_ascii_alphabetic()||b==b'_'||(i>0&&b.is_ascii_digit()))}
impl Catalog {fn validate(&self)->Result<()> {
 if self.version!=1||self.classes.len()>16{return Err(invalid("Unsupported inspection catalog"));}
 let mut names=std::collections::BTreeSet::new();
 for c in &self.classes {
  if !identifier(&c.class_name,128)||!names.insert(&c.class_name)||c.name.len()>256||c.description.len()>512||c.fields.len()>16||c.schema_error.as_ref().map_or(false,|s|s.len()>1024)||c.schema_error.is_some()&&!c.fields.is_empty(){return Err(invalid("Invalid inspected class metadata"));}
  let mut defaults=std::collections::BTreeMap::new();
  for f in &c.fields {
   if !identifier(&f.key,64)||f.label.len()>256||defaults.insert(f.key.clone(),f.default.clone()).is_some(){return Err(invalid("Invalid/duplicate inspected option"));}
   let typed=match f.kind.as_str(){"string"|"choice"=>f.default.is_string(),"boolean"=>f.default.is_boolean(),"number"=>f.default.is_number(),_=>false};
   if !typed||f.choices.len()>16||f.choices.iter().any(|s|s.len()>256){return Err(invalid("Invalid inspected option type"));}
   if f.kind=="choice" {let unique:std::collections::BTreeSet<_>=f.choices.iter().collect();if unique.len()!=f.choices.len()||!f.choices.iter().any(|s|Some(s.as_str())==f.default.as_str()){return Err(invalid("Invalid inspected choice"));}}
   else if !f.choices.is_empty(){return Err(invalid("Unexpected inspected choices"));}
  }
  if !valid_options(&defaults){return Err(invalid("Inspected defaults exceed scalar option bounds"));}
 }Ok(())
}}
#[derive(Debug,Serialize)]pub struct Receipt {
 pub profile:&'static str,pub destination:PathBuf,pub plugin_sha256:String,pub catalog:Catalog,pub stdout_tail:String,pub stderr_tail:String,
}
pub(crate) fn execute(r:&Request,job:&mut ImportJob<'_>)->Result<Receipt> {execute_source(r,job,DEADLINE,None)}
// Folder scans reuse the exact transport/validation with a frozen root file and
// the original filename for sibling imports. External dependencies are not frozen.
pub(super) fn execute_source(r:&Request,job:&mut ImportJob<'_>,timeout:Duration,original_override:Option<&Path>)->Result<Receipt> {
 #[cfg(not(any(target_os="macos",target_os="linux")))]return Err(fail(ErrorCode::UnsupportedPlatform,"Plugin inspection currently supports macOS/Linux only"));
 check(job)?;if !r.trusted{return Err(invalid("Plugin inspection requires explicit trust"));}
 match fs::symlink_metadata(&r.destination){Ok(_)=>return Err(fail(ErrorCode::DestinationExists,"Destination folder exists")),Err(e) if e.kind()==std::io::ErrorKind::NotFound=>{},Err(e)=>return Err(e.into())}
 let python=if r.python.is_absolute(){r.python.clone()}else{std::env::current_dir()?.join(&r.python)};
 if !python.is_file(){return Err(invalid("Choose an existing Python interpreter executable"));}
 let original=fs::canonicalize(original_override.unwrap_or(&r.plugin))?;
 let parent=r.destination.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new("."));
 let root=tempfile::tempdir_in(parent)?;let root_path=fs::canonicalize(root.path())?;let result=root_path.join("result");fs::create_dir(&result)?;
 event(job,"python_inspect_snapshot",0)?;
 let snapshot=root_path.join("plugin.py");let plugin_sha256=copy(&r.plugin,&snapshot,PLUGIN,job)?;
 let wrapper=root_path.join("bridge.py");let base=root_path.join("base_plugin.py");
 fs::write(&wrapper,include_bytes!("plugin_wrapper.py"))?;fs::write(&base,include_bytes!("base_plugin.py"))?;fs::write(root_path.join("plugin_catalog.py"),include_bytes!("plugin_catalog.py"))?;
 let stdout=root_path.join("stdout.log");let stderr=root_path.join("stderr.log");let catalog_path=result.join("catalog.json");
 let listener=TcpListener::bind((std::net::Ipv4Addr::LOCALHOST,0))?;listener.set_nonblocking(true)?;
 let mut random=[0u8;32];getrandom::fill(&mut random).map_err(|e|fail(ErrorCode::Internal,e.to_string()))?;let token=sha256::hex(&random);
 let config=json!({"port":listener.local_addr()?.port(),"token":token,"mode":"inspect","snapshot":snapshot,"original_plugin":original,"base":base,"catalog":catalog_path});
 event(job,"python_inspect",0)?;
 run_child(&python,&wrapper,&root_path,&result,&stdout,&stderr,listener,&token,&config,job,timeout)?;
 check(job)?;
 if !fs::symlink_metadata(&catalog_path)?.file_type().is_file()||fs::metadata(&catalog_path)?.len()>32768{return Err(invalid("Catalog must be a regular file <=32 KiB"));}
 let data=File::open(&catalog_path)?.take(32769).bytes().collect::<std::io::Result<Vec<_>>>()?;
 if data.len()>32768{return Err(limit("Catalog exceeds 32 KiB"));}
 let catalog:Catalog=serde_json::from_slice(&data).map_err(|e|invalid(format!("Invalid inspection catalog: {e}")))?;catalog.validate()?;
 copy(&stdout,&result.join("bridge-stdout.log"),RAW_LOG,job)?;copy(&stderr,&result.join("bridge-stderr.log"),RAW_LOG,job)?;inventory(&result)?;
 let receipt=Receipt {profile:"trusted-python-inspection-v1",destination:r.destination.clone(),plugin_sha256,catalog,stdout_tail:tail(&stdout),stderr_tail:tail(&stderr)};
 File::open(&catalog_path)?.sync_all()?;
 event(job,"python_inspect_commit",100)?;
 #[cfg(unix)]publish(&result,&r.destination)?;
 Ok(receipt)
}
