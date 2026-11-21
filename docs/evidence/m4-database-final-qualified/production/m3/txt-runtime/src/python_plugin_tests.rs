use super::*;
use crate::CancellationToken;
fn request(dir:&Path,class_name:&str)->Request {
 let python=std::env::var_os("STUDIO_TEST_PYTHON").map(PathBuf::from).unwrap_or_else(||{
  let result=Command::new("python3").args(["-c","import sys;print(sys.executable)"]).output().expect("Python 3 required for optional plugin bridge tests");assert!(result.status.success());PathBuf::from(String::from_utf8(result.stdout).unwrap().trim())
 });
 let plugin=dir.join("plugin.py");fs::write(&plugin,include_bytes!("../../fixtures/noisy_plugin.py")).unwrap();
 let source=dir.join("source.txt");fs::write(&source,include_bytes!("../../fixtures/build-source.txt")).unwrap();
 Request {python,plugin,class_name:class_name.into(),source,destination:dir.join("result"),trusted:true}
}
#[cfg(unix)]#[test]fn noisy_plugin_roundtrip_preserves_input_and_sidecar_and_refuses_overwrite() {
 let dir=tempfile::tempdir().unwrap();let r=request(dir.path(),"NoisyPlugin");let before=fs::read(&r.source).unwrap();let token=CancellationToken::default();
 let receipt=execute(&r,&mut ImportJob::new("plugin",&token,&mut |_|{})).unwrap();assert_eq!(receipt.records,5);assert_eq!(fs::read(r.destination.join("output.txt")).unwrap(),before);assert_eq!(fs::read(&r.source).unwrap(),before);
 assert!(!PathBuf::from(format!("{}_log.txt",r.source.display())).exists());assert!(r.destination.join("input-sidecars/input.txt_log.txt").exists());
 assert!(receipt.stdout_tail.contains("ordinary stdout"));assert!(receipt.stdout_tail.contains("Native stdout write"));assert!(receipt.stderr_tail.contains("Fixture stderr warning"));assert_eq!(receipt.callback_logs.len(),1);
 let e=execute(&r,&mut ImportJob::new("exists",&token,&mut |_|{})).unwrap_err();assert_eq!(e.code,ErrorCode::DestinationExists);assert_eq!(fs::read(r.destination.join("output.txt")).unwrap(),before);
}
#[cfg(unix)]#[test]fn plugin_exception_and_invalid_txt_never_publish() {
 for class_name in ["FailingPlugin","NoisyPlugin"] {
  let dir=tempfile::tempdir().unwrap();let r=request(dir.path(),class_name);if class_name=="NoisyPlugin"{fs::write(&r.source,b"word\nmissing final delimiter\n").unwrap();}
  let e=execute(&r,&mut ImportJob::new("invalid",&CancellationToken::default(),&mut |_|{})).unwrap_err();assert!(!r.destination.exists());
  if class_name=="FailingPlugin"{assert_eq!(e.code,ErrorCode::Engine);assert!(e.message.contains("Intentional fixture failure"));}else{assert_eq!(e.code,ErrorCode::InvalidInput);}
  assert_eq!(fs::read_dir(dir.path()).unwrap().count(),2,"Private stages must be removed");
 }
}
#[cfg(unix)]#[test]fn running_and_precommit_plugin_cancellation_leave_no_bundle() {
 for (class_name,phase) in [("SlowPlugin","python_convert"),("NoisyPlugin","python_commit")] {
  let dir=tempfile::tempdir().unwrap();let r=request(dir.path(),class_name);let before=fs::read(&r.source).unwrap();let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase==phase {stop.cancel();};
  let start=Instant::now();let e=execute(&r,&mut ImportJob::new("cancel",&token,&mut progress)).unwrap_err();assert_eq!(e.code,ErrorCode::Cancelled);assert!(start.elapsed()<Duration::from_secs(20));assert!(!r.destination.exists());assert_eq!(fs::read(&r.source).unwrap(),before);assert_eq!(fs::read_dir(dir.path()).unwrap().count(),2);
 }
}
#[test]fn invalid_protocol_and_untrusted_requests_are_rejected() {
 let dir=tempfile::tempdir().unwrap();let mut r=request(dir.path(),"NoisyPlugin");r.trusted=false;assert!(r.validate().is_err());r.trusted=true;r.class_name="A.b".into();assert!(r.validate().is_err());
 for bytes in [b"debug print\n".as_slice(),b"{\"type\":\"hello\",\"token\":\"wrong\",\"version\":1}\n".as_slice(),b"{\"type\":\"done\",\"message\":\"unauthenticated\"}\n".as_slice()] {
  assert!(messages(&mut bytes.to_vec(),&mut false,&mut None,&mut Vec::new(),"secret",&mut ImportJob::new("protocol",&CancellationToken::default(),&mut |_|{})).is_err());
 }
}
