use super::*;
fn request(dir:&Path)->Request {
 let python=std::env::var_os("STUDIO_TEST_PYTHON").map(PathBuf::from).unwrap_or_else(||{
  let out=Command::new("python3").args(["-c","import sys;print(sys.executable)"]).output().unwrap();assert!(out.status.success());PathBuf::from(String::from_utf8(out.stdout).unwrap().trim())
 });
 let folder=dir.join("plugins");fs::create_dir(&folder).unwrap();
 Request {python,folder,destination:dir.join("discovery"),trusted:true}
}
const CONVERTER:&str="from base_plugin import BaseConverterPlugin\nclass Demo(BaseConverterPlugin):\n name='Repeated display name'\n def convert(self,*args): raise RuntimeError('must not convert')\n";
#[cfg(unix)]#[test]fn folder_keeps_duplicate_names_per_file_and_reports_import_errors() {
 let dir=tempfile::tempdir().unwrap();let r=request(dir.path());
 for name in ["a.py","b.py"]{fs::write(r.folder.join(name),CONVERTER).unwrap();}
 fs::write(r.folder.join("broken.py"),"raise RuntimeError('folder import fixture failure')").unwrap();fs::write(r.folder.join("notes.txt"),"ignored").unwrap();
 let receipt=execute(&r,&mut ImportJob::new("folder",&crate::CancellationToken::default(),&mut |_|{})).unwrap();
 assert_eq!(receipt.entries.len(),3);assert_eq!(receipt.ignored_entries,1);assert_eq!(receipt.entries[0].filename,"a.py");assert_eq!(receipt.entries[1].filename,"b.py");
 for item in &receipt.entries[..2]{assert_eq!(item.catalog.as_ref().unwrap().classes[0].class_name,"Demo");assert_eq!(item.plugin_sha256.as_ref().unwrap().len(),64);}
 assert!(receipt.entries[2].error.as_ref().unwrap().message.contains("folder import fixture failure"));assert!(receipt.entries[2].catalog.is_none());assert!(r.destination.join("catalog.json").is_file());
 let error=execute(&r,&mut ImportJob::new("exists",&crate::CancellationToken::default(),&mut |_|{})).unwrap_err();assert_eq!(error.code,ErrorCode::DestinationExists);
}
#[cfg(unix)]#[test]fn folder_freezes_roots_before_import_and_each_file_has_its_own_process() {
 let dir=tempfile::tempdir().unwrap();let r=request(dir.path());
 fs::write(r.folder.join("a.py"),format!("import builtins\nbuiltins.studio_folder_leak=True\nfrom pathlib import Path\nPath(__file__).with_name('b.py').write_text(\"raise RuntimeError('changed peer')\\n\")\n{CONVERTER}")).unwrap();
 let original=format!("import builtins\nassert not hasattr(builtins,'studio_folder_leak')\n{CONVERTER}");fs::write(r.folder.join("b.py"),&original).unwrap();
 let receipt=execute(&r,&mut ImportJob::new("frozen",&crate::CancellationToken::default(),&mut |_|{})).unwrap();
 assert!(receipt.entries.iter().all(|e|e.error.is_none()));assert_eq!(receipt.entries[1].catalog.as_ref().unwrap().classes[0].class_name,"Demo");
 assert_ne!(fs::read_to_string(r.folder.join("b.py")).unwrap(),original,"Trusted imports can write files; this is not a sandbox");
}
#[cfg(unix)]#[test]fn folder_caps_preflight_and_symlinks_never_import_outside_candidates() {
 let dir=tempfile::tempdir().unwrap();let mut r=request(dir.path());
 let marker=dir.path().join("imported");let code=format!("from pathlib import Path\nPath({:?}).write_text('bad')\n",marker.to_str().unwrap());
 for i in 0..17{fs::write(r.folder.join(format!("{i:02}.py")),&code).unwrap();}
 let error=execute(&r,&mut ImportJob::new("cap",&crate::CancellationToken::default(),&mut |_|{})).unwrap_err();assert_eq!(error.code,ErrorCode::LimitExceeded);assert!(!marker.exists());assert!(!r.destination.exists());
 for entry in fs::read_dir(&r.folder).unwrap(){fs::remove_file(entry.unwrap().path()).unwrap();}
 let outside=dir.path().join("outside.py");fs::write(&outside,&code).unwrap();std::os::unix::fs::symlink(&outside,r.folder.join("link.py")).unwrap();
 let receipt=execute(&r,&mut ImportJob::new("link",&crate::CancellationToken::default(),&mut |_|{})).unwrap();assert!(receipt.entries[0].error.is_some());assert!(!marker.exists());
 let alias=dir.path().join("alias");std::os::unix::fs::symlink(&r.folder,&alias).unwrap();r.folder=alias;r.destination=dir.path().join("second");assert_eq!(execute(&r,&mut ImportJob::new("alias",&crate::CancellationToken::default(),&mut |_|{})).unwrap_err().code,ErrorCode::InvalidInput);
}
#[cfg(unix)]#[test]fn folder_cancellation_during_scan_and_before_commit_leaves_no_publication() {
 for phase in ["python_folder_inspect","python_folder_commit"] {
  let dir=tempfile::tempdir().unwrap();let r=request(dir.path());fs::write(r.folder.join("a.py"),CONVERTER).unwrap();
  let token=crate::CancellationToken::default();let stop=token.clone();let error=execute(&r,&mut ImportJob::new("stop",&token,&mut |p|if p.phase==phase {stop.cancel();})).unwrap_err();
  assert_eq!(error.code,ErrorCode::Cancelled);assert!(!r.destination.exists());assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);
 }
}
#[cfg(unix)]#[test]fn folder_time_budget_kills_a_running_import_and_is_reported_without_conversion() {
 let dir=tempfile::tempdir().unwrap();let r=request(dir.path());let path=r.folder.join("slow.py");fs::write(&path,"import time\ntime.sleep(30)\n").unwrap();
 let selected=inspection::Request {python:r.python,plugin:path,destination:r.destination.clone(),trusted:true};let start=Instant::now();
 let error=inspection::execute_source(&selected,&mut ImportJob::new("deadline",&crate::CancellationToken::default(),&mut |_|{}),Duration::from_millis(100),None).unwrap_err();
 assert_eq!(error.code,ErrorCode::LimitExceeded);assert!(start.elapsed()<Duration::from_secs(10));assert!(!r.destination.exists());
}
#[cfg(unix)]#[test]fn cancelling_an_active_folder_import_stops_the_child_and_removes_stages() {
 let dir=tempfile::tempdir().unwrap();let r=request(dir.path());let marker=r.folder.join("started");
 fs::write(r.folder.join("slow.py"),"from pathlib import Path\nimport time\nPath(__file__).with_name('started').write_text('ready')\ntime.sleep(30)\n").unwrap();
 let token=crate::CancellationToken::default();let stop=token.clone();let watched=marker.clone();
 let thread=std::thread::spawn(move||{let start=Instant::now();while !watched.exists()&&start.elapsed()<Duration::from_secs(5){std::thread::sleep(Duration::from_millis(10));}stop.cancel();});
 let start=Instant::now();let error=execute(&r,&mut ImportJob::new("active-cancel",&token,&mut |_|{})).unwrap_err();thread.join().unwrap();
 assert!(marker.exists(),"The fixture import must start before cancellation");assert_eq!(error.code,ErrorCode::Cancelled);assert!(start.elapsed()<Duration::from_secs(10));assert!(!r.destination.exists());assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);
}
#[test]fn aggregate_folder_catalog_limit_is_independent_of_each_file_catalog() {
 let mut entries=Vec::new();
 for i in 0..16 {
  let classes:Vec<_>=(0..16).map(|j|json!({"class_name":format!("C{j}"),"name":"converter","description":"x".repeat(512),"fields":[],"schema_error":null})).collect();
  let catalog:inspection::Catalog=serde_json::from_value(json!({"version":1,"classes":classes})).unwrap();
  entries.push(Entry {filename:format!("{i}.py"),source:PathBuf::from(format!("/plugins/{i}.py")),plugin_sha256:Some("a".repeat(64)),catalog:Some(catalog),error:None});
 }
 let receipt=Receipt {profile:"trusted-python-folder-v1",folder:PathBuf::from("/plugins"),destination:PathBuf::from("/result"),ignored_entries:0,entries};assert_eq!(bounded(&receipt).unwrap_err().code,ErrorCode::LimitExceeded);
}
