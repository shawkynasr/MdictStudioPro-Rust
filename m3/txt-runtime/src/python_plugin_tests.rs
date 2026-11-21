use super::*;
use crate::CancellationToken;
fn request(dir:&Path,class_name:&str)->Request {
 let python=std::env::var_os("STUDIO_TEST_PYTHON").map(PathBuf::from).unwrap_or_else(||{
  let result=Command::new("python3").args(["-c","import sys;print(sys.executable)"]).output().expect("Python 3 required for optional plugin bridge tests");assert!(result.status.success());PathBuf::from(String::from_utf8(result.stdout).unwrap().trim())
 });
 let plugin=dir.join("plugin.py");fs::write(&plugin,include_bytes!("../../fixtures/noisy_plugin.py")).unwrap();
 let source=dir.join("source.txt");fs::write(&source,include_bytes!("../../fixtures/build-source.txt")).unwrap();
 Request {python,plugin,class_name:class_name.into(),source,destination:dir.join("result"),trusted:true,expected_plugin_sha256:None,options:Default::default()}
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

#[test]fn scalar_options_reject_nested_values_and_limits_before_admission() {
 let dir=tempfile::tempdir().unwrap();let mut r=request(dir.path(),"NoisyPlugin");
 for value in [json!({"nested":{}}),json!({"array":[]}),json!({"null":null}),json!({"bad-key":true}),json!({"x":"字".repeat(683)}),json!({"x":9007199254740992u64})] {
  r.options=serde_json::from_value(value).unwrap();assert!(r.validate().is_err());
 }
 r.options=serde_json::from_value(json!({"prefix":"字 · مرحبا","uppercase":true,"count":2})).unwrap();assert!(r.validate().is_ok());
 r.options=(0..65).map(|i|(format!("k{i}"),json!(true))).collect();assert!(r.validate().is_err());
 r.options=(0..5).map(|i|(format!("k{i}"),json!("x".repeat(2048)))).collect();assert!(r.validate().is_err());
}
#[cfg(unix)]#[test]fn plugin_scalar_options_reach_selected_converter_and_receipt() {
 let dir=tempfile::tempdir().unwrap();let mut r=request(dir.path(),"OptionsPlugin");
 r.options=serde_json::from_value(json!({"prefix":"字 مرحبا","uppercase":true})).unwrap();
 let receipt=execute(&r,&mut ImportJob::new("options",&CancellationToken::default(),&mut |_|{})).unwrap();
 assert_eq!(receipt.option_fields,2);assert_eq!(receipt.options_sha256.len(),64);
 let body=fs::read_to_string(r.destination.join("output.txt")).unwrap();assert!(body.contains("字 مرحبا"));assert!(body.contains("APPLE"));
}

#[cfg(unix)]#[test]fn inspected_classes_are_source_bound_and_inspection_never_converts_or_clobbers() {
 let dir=tempfile::tempdir().unwrap();let mut r=request(dir.path(),"OptionsPlugin");
 let inspect=inspection::Request {python:r.python.clone(),plugin:r.plugin.clone(),destination:dir.path().join("inspection"),trusted:true};
 let token=CancellationToken::default();
 let receipt=inspection::execute(&inspect,&mut ImportJob::new("inspect",&token,&mut |_|{})).unwrap();
 assert_eq!(receipt.catalog.classes.len(),4);assert_eq!(receipt.plugin_sha256.len(),64);
 assert!(!inspect.destination.join("output.txt").exists());assert!(inspect.destination.join("catalog.json").is_file());
 let options=receipt.catalog.classes.iter().find(|c|c.class_name=="OptionsPlugin").unwrap();assert_eq!(options.fields.len(),2);
 let error=inspection::execute(&inspect,&mut ImportJob::new("exists",&token,&mut |_|{})).unwrap_err();assert_eq!(error.code,ErrorCode::DestinationExists);
 r.expected_plugin_sha256=Some(receipt.plugin_sha256);
 let mut body=fs::read(&r.plugin).unwrap();body.extend_from_slice(b"\n# changed after inspection\n");fs::write(&r.plugin,body).unwrap();
 let error=execute(&r,&mut ImportJob::new("stale",&token,&mut |_|{})).unwrap_err();assert_eq!(error.code,ErrorCode::InvalidInput);assert!(error.message.contains("changed since inspection"));assert!(!r.destination.exists());
}

#[cfg(unix)]#[test]fn inspection_cancellation_and_import_failure_never_publish() {
 for phase in ["python_inspect","python_inspect_commit","import_failure"] {
  let dir=tempfile::tempdir().unwrap();let r=request(dir.path(),"NoisyPlugin");
  if phase=="import_failure"{fs::write(&r.plugin,b"raise RuntimeError('inspection import failed')\n").unwrap();}
  let inspect=inspection::Request {python:r.python,plugin:r.plugin,destination:r.destination,trusted:true};
  let token=CancellationToken::default();let stop=token.clone();
  let error=inspection::execute(&inspect,&mut ImportJob::new("inspect-stop",&token,&mut |p|if p.phase==phase{stop.cancel();})).unwrap_err();
  assert!(!inspect.destination.exists());assert_eq!(fs::read_dir(dir.path()).unwrap().count(),2);
  assert_eq!(error.code,if phase=="import_failure"{ErrorCode::Engine}else{ErrorCode::Cancelled});
 }
}
