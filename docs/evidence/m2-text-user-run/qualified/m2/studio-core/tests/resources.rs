use std::{fs,path::Path};
use studio_core::*;

fn request()->ResourcePackRequest {
    ResourcePackRequest {title:"Resources قاموس 字".into(),description:"Binary <MDD> & metadata".into(),resources:vec![
        Resource {key:"\\styles\\main.css".into(),bytes:b"p { color: blue; }\n".to_vec()},
        Resource {key:"fonts/probe.ttf".into(),bytes:vec![0,255,128,0]},
        Resource {key:"字/说明.txt".into(),bytes:"中文 العربية".as_bytes().to_vec()},
        Resource {key:"data/all.bin".into(),bytes:(0..=255).collect()},
        Resource {key:"data/empty.bin".into(),bytes:Vec::new()},
    ]}
}
fn pack(input:&ResourcePackRequest,path:&Path,limits:&Limits)->Result<PackSummary> {
    let token=CancellationToken::default(); let mut sink=|_|{};
    pack_mdd(input,path,limits,&mut JobContext::new(&token,&mut sink))
}
fn open(path:&Path,limits:&Limits)->Result<ResourceArchive> {
    let token=CancellationToken::default(); let mut sink=|_|{};
    ResourceArchive::open_studio_output(path,limits,&mut JobContext::new(&token,&mut sink))
}

#[test]
fn binary_empty_and_unicode_resources_reopen_with_exact_keys() {
    let dir=tempfile::tempdir().unwrap(); let path=dir.path().join("resources.mdd");
    let input=request(); let limits=Limits::default(); pack(&input,&path,&limits).unwrap();
    let before=fs::read(&path).unwrap(); let archive=open(&path,&limits).unwrap(); let token=CancellationToken::default();
    assert_eq!(archive.len(),input.resources.len()); assert_eq!(archive.title(),input.title);
    assert_eq!(archive.description(),input.description);
    for row in input.resources { assert_eq!(archive.resource(&row.key,&token).unwrap(),Some(row)); }
    assert!(archive.resource("missing.bin",&token).unwrap().is_none());
    assert!(archive.resource("/styles/main.css",&token).unwrap().is_none());
    assert_eq!(fs::read(&path).unwrap(),before);
}

#[test]
fn traversal_unc_devices_and_ambiguous_components_are_refused() {
    for key in ["", "/", "../x", "a/../x", "a/./x", "a//x", "a/", "//server/x", "\\\\server\\x",
        "C:\\x", "a:stream", "a/zero\0x", "a/line\nx", "a/trailing.", "a/trailing ",
        "con", "NUL.txt", "COM1.bin", "LPT³", "COM¹.txt", "a?.png", "a*/x", "a<.x", "CON .txt"] {
        assert_eq!(resource_relative_path(key).unwrap_err().code,ErrorCode::UnsafePath,"{key:?}");
    }
    assert_eq!(resource_relative_path("\\fonts\\字.ttf").unwrap(),Path::new("fonts/字.ttf"));
}

#[test]
fn aliases_case_and_prefix_conflicts_fail_before_output_is_created() {
    for keys in [["a.bin","a.bin"],["a/b","a\\b"],["A/one","a/two"],
        ["a","a/b"],["a/b","a"],["Ä/one","ä/two"],["/a.bin","a.bin"]] {
        let dir=tempfile::tempdir().unwrap(); let path=dir.path().join("out.mdd");
        let mut input=request(); input.resources=keys.iter().map(|k|Resource {key:(*k).into(),bytes:vec![1]}).collect();
        assert_eq!(pack(&input,&path,&Limits::default()).unwrap_err().code,ErrorCode::PathCollision);
        assert_eq!(fs::read_dir(dir.path()).unwrap().count(),0);
    }
}

#[test]
fn resource_budgets_and_result_caps_are_explicit_errors() {
    let dir=tempfile::tempdir().unwrap(); let path=dir.path().join("out.mdd");
    let mut limits=Limits::default(); limits.max_entries=1;
    assert_eq!(pack(&request(),&path,&limits).unwrap_err().code,ErrorCode::LimitExceeded);
    limits=Limits::default(); limits.max_entry_bytes=1;
    assert_eq!(pack(&request(),&path,&limits).unwrap_err().code,ErrorCode::LimitExceeded);
    assert_eq!(fs::read_dir(dir.path()).unwrap().count(),0);
    pack(&request(),&path,&Limits::default()).unwrap();
    limits=Limits::default(); limits.max_result_bytes=1;
    let archive=open(&path,&limits).unwrap(); let token=CancellationToken::default();
    assert_eq!(archive.resource("data/all.bin",&token).unwrap_err().code,ErrorCode::LimitExceeded);
    token.cancel(); assert_eq!(archive.resource("missing.bin",&token).unwrap_err().code,ErrorCode::Cancelled);
}

#[test]
fn cancellation_during_pack_verification_cleans_temporary_output() {
    let dir=tempfile::tempdir().unwrap(); let path=dir.path().join("out.mdd");
    let token=CancellationToken::default();
    let mut sink=|p:Progress|if p.phase==Phase::Verifying {token.cancel();};
    assert_eq!(pack_mdd(&request(),&path,&Limits::default(),&mut JobContext::new(&token,&mut sink)).unwrap_err().code,ErrorCode::Cancelled);
    assert_eq!(fs::read_dir(dir.path()).unwrap().count(),0);
}

#[test]
fn mdd_header_checksum_corruption_is_typed_integrity_error() {
    let dir=tempfile::tempdir().unwrap(); let path=dir.path().join("out.mdd"); pack(&request(),&path,&Limits::default()).unwrap();
    let mut bytes=fs::read(&path).unwrap(); let length=u32::from_be_bytes(bytes[..4].try_into().unwrap()) as usize;
    bytes[4+length]^=1; fs::write(&path,bytes).unwrap();
    let error=match open(&path,&Limits::default()){Ok(_)=>panic!("corrupt MDD accepted"),Err(e)=>e};
    assert_eq!(error.code,ErrorCode::Integrity);
}

#[cfg(any(target_os="macos",target_os="linux"))]
#[test]
fn extract_commits_exact_bytes_and_rejects_existing_destination() {
    let dir=tempfile::tempdir().unwrap(); let path=dir.path().join("in.mdd"); let destination=dir.path().join("extracted");
    let input=request(); pack(&input,&path,&Limits::default()).unwrap(); let archive=open(&path,&Limits::default()).unwrap();
    let token=CancellationToken::default(); let mut sink=|_|{};
    let summary=archive.extract(&destination,&mut JobContext::new(&token,&mut sink)).unwrap();
    assert_eq!(summary.resources,input.resources.len());
    for row in input.resources {assert_eq!(fs::read(destination.join(resource_relative_path(&row.key).unwrap())).unwrap(),row.bytes);}
    assert_eq!(archive.extract(&destination,&mut JobContext::new(&token,&mut sink)).unwrap_err().code,ErrorCode::DestinationExists);
}

#[cfg(any(target_os="macos",target_os="linux"))]
#[test]
fn extraction_cancellation_removes_partial_stage_and_leaves_no_destination() {
    let dir=tempfile::tempdir().unwrap(); let path=dir.path().join("in.mdd"); let destination=dir.path().join("extracted");
    pack(&request(),&path,&Limits::default()).unwrap(); let archive=open(&path,&Limits::default()).unwrap();
    let token=CancellationToken::default();
    let mut sink=|p:Progress|if p.phase==Phase::Extracting && p.completed==1 {token.cancel();};
    assert_eq!(archive.extract(&destination,&mut JobContext::new(&token,&mut sink)).unwrap_err().code,ErrorCode::Cancelled);
    assert!(!destination.exists()); assert_eq!(fs::read_dir(dir.path()).unwrap().count(),1);
}

#[cfg(any(target_os="macos",target_os="linux"))]
#[test]
fn extraction_race_preserves_even_an_empty_destination_directory() {
    for with_file in [false,true] {
        let dir=tempfile::tempdir().unwrap(); let path=dir.path().join("in.mdd"); let destination=dir.path().join("extracted");
        pack(&request(),&path,&Limits::default()).unwrap(); let archive=open(&path,&Limits::default()).unwrap();
        let token=CancellationToken::default(); let mut appeared=false;
        let mut sink=|p:Progress|if p.phase==Phase::Extracting && !appeared {
            fs::create_dir(&destination).unwrap(); if with_file {fs::write(destination.join("sentinel"),b"unchanged").unwrap();} appeared=true;
        };
        assert_eq!(archive.extract(&destination,&mut JobContext::new(&token,&mut sink)).unwrap_err().code,ErrorCode::DestinationExists);
        assert_eq!(fs::read_dir(&destination).unwrap().count(),if with_file {1}else{0});
        if with_file {assert_eq!(fs::read(destination.join("sentinel")).unwrap(),b"unchanged");}
        assert_eq!(fs::read_dir(dir.path()).unwrap().count(),2);
    }
}

#[cfg(any(target_os="macos",target_os="linux"))]
#[test]
fn target_filesystem_unicode_aliases_are_detected_without_publishing() {
    let dir=tempfile::tempdir().unwrap(); let probe=dir.path().join("probe"); fs::create_dir(&probe).unwrap();
    fs::create_dir(probe.join("é")).unwrap();
    let aliases=match fs::create_dir(probe.join("e\u{301}")) {Ok(())=>false,Err(e) if e.kind()==std::io::ErrorKind::AlreadyExists=>true,Err(e)=>panic!("{e}")};
    fs::remove_dir_all(probe).unwrap();
    let mut input=request(); input.resources=vec![Resource {key:"é/one".into(),bytes:vec![1]},Resource {key:"e\u{301}/two".into(),bytes:vec![2]}];
    let path=dir.path().join("in.mdd"); pack(&input,&path,&Limits::default()).unwrap(); let archive=open(&path,&Limits::default()).unwrap();
    let destination=dir.path().join("out"); let token=CancellationToken::default(); let mut sink=|_|{};
    let result=archive.extract(&destination,&mut JobContext::new(&token,&mut sink));
    if aliases {assert_eq!(result.unwrap_err().code,ErrorCode::PathCollision);assert!(!destination.exists());}
    else {assert_eq!(result.unwrap().resources,2);}
}

#[cfg(any(target_os="macos",target_os="linux"))]
#[test]
fn cancellation_after_extraction_commit_reports_success() {
    let dir=tempfile::tempdir().unwrap(); let path=dir.path().join("in.mdd"); let destination=dir.path().join("out");
    pack(&request(),&path,&Limits::default()).unwrap(); let archive=open(&path,&Limits::default()).unwrap();
    let token=CancellationToken::default(); let mut sink=|p:Progress|if p.phase==Phase::Published {token.cancel();};
    assert!(archive.extract(&destination,&mut JobContext::new(&token,&mut sink)).is_ok()); assert!(destination.is_dir());
}

#[cfg(any(target_os="macos",target_os="linux"))]
#[test]
fn dangling_destination_symlink_is_never_followed() {
    let dir=tempfile::tempdir().unwrap(); let path=dir.path().join("in.mdd"); let destination=dir.path().join("out");
    pack(&request(),&path,&Limits::default()).unwrap(); let archive=open(&path,&Limits::default()).unwrap();
    std::os::unix::fs::symlink("uncreated",&destination).unwrap();
    let token=CancellationToken::default(); let mut sink=|_|{};
    assert_eq!(archive.extract(&destination,&mut JobContext::new(&token,&mut sink)).unwrap_err().code,ErrorCode::DestinationExists);
    assert_eq!(fs::read_link(&destination).unwrap(),Path::new("uncreated")); assert!(!dir.path().join("uncreated").exists());
}
