//! Transient inspection for the one-file import UI: no user result directory.
use super::*;
#[derive(Debug,Deserialize)]#[serde(deny_unknown_fields)]pub struct Request {pub python:PathBuf,pub plugin:PathBuf,pub trusted:bool}
impl Request {pub(crate) fn validate(&self)->crate::ApiResult<()> {
 if !self.trusted{return Err(crate::ApiError {code:crate::ApiCode::InvalidInput,message:"Importing a plugin executes trusted Python; confirm trust first".into()});}Ok(())
}}
#[derive(Debug,Serialize)]pub struct Receipt {pub profile:&'static str,pub plugin_sha256:String,pub catalog:inspection::Catalog}
pub(crate) fn execute(r:&Request,job:&mut ImportJob<'_>)->Result<Receipt> {
 check(job)?;if !r.trusted{return Err(invalid("Plugin import requires explicit trust"));}
 let root=tempfile::tempdir()?;
 let selected=inspection::Request {python:r.python.clone(),plugin:r.plugin.clone(),destination:root.path().join("inspection"),trusted:true};
 let found=inspection::execute(&selected,job)?;check(job)?;
 Ok(Receipt {profile:"trusted-python-probe-v1",plugin_sha256:found.plugin_sha256,catalog:found.catalog})
}

#[cfg(test)]mod tests {
 use super::*;
 #[cfg(unix)]#[test]fn transient_probe_has_no_user_destination_and_retains_source_binding() {
  let dir=tempfile::tempdir().unwrap();let plugin=dir.path().join("plugin.py");fs::write(&plugin,include_bytes!("../../fixtures/noisy_plugin.py")).unwrap();
  let python=std::env::var_os("STUDIO_TEST_PYTHON").map(PathBuf::from).unwrap_or_else(||{let r=Command::new("python3").args(["-c","import sys;print(sys.executable)"]).output().unwrap();assert!(r.status.success());PathBuf::from(String::from_utf8(r.stdout).unwrap().trim())});
  let mut request=Request {python,plugin,trusted:false};assert!(request.validate().is_err());request.trusted=true;
  let receipt=execute(&request,&mut ImportJob::new("probe",&crate::CancellationToken::default(),&mut |_|{})).unwrap();
  assert_eq!(receipt.catalog.classes.len(),4);assert_eq!(receipt.plugin_sha256.len(),64);assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);
  let encoded=serde_json::to_value(&receipt).unwrap();assert!(encoded.get("destination").is_none());
  let token=crate::CancellationToken::default();let stop=token.clone();let error=execute(&request,&mut ImportJob::new("stop",&token,&mut |p|if p.phase=="python_inspect_commit"{stop.cancel();})).unwrap_err();assert_eq!(error.code,ErrorCode::Cancelled);assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);
 }
}
