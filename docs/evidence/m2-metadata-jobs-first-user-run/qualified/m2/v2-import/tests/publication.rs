use studio_v2_import::{*,application::metadata::{self,publication::{self,Request,Metadata,runner::{Runner,Config,State}}}};
use std::{fs,path::Path,time::Duration};
fn request(dir:&Path,name:&str,encoding:studio_core::Encoding)->Request {
    Request::PackMdx {destination:dir.join(name),encoding,metadata:Metadata {title:"Title & 字 العربية".into(),description:"A\r\nB\t&amp; literal".into(),stylesheet:"1\n<span style=\"color:blue\">\n</span>\n".into(),extra:[("ForeignExtension".into(),"A\nB <extension>".into())].into()},entries:vec![Entry {key:"apple".into(),text:"first".into()},Entry {key:"Apple".into(),text:"upper".into()},Entry {key:"apple".into(),text:"second".into()},Entry {key:"alias".into(),text:"@@@LINK=apple".into()},Entry {key:"style".into(),text:"`1`blue".into()}]}
}
fn execute(req:&Request)->Result<publication::Output> {publication::execute(req,&mut ImportJob::new("publication-integration",&CancellationToken::default(),&mut |_|{}))}
#[test]fn fresh_both_encodings_preserve_metadata_stable_duplicates_and_markers() {
    for encoding in [studio_core::Encoding::Utf8,studio_core::Encoding::Utf16] {
        let temp=tempfile::tempdir().unwrap();let req=request(temp.path(),"packed.mdx",encoding);let summary=execute(&req).unwrap();assert_eq!(summary.records,5);
        let token=CancellationToken::default();let mut progress=|_|{};let mut job=ImportJob::new("read",&token,&mut progress);let d=Dictionary::open_v2(req.destination(),LookupPolicy::RawExact,&Limits::default(),&mut job).unwrap();
        assert_eq!(d.entries().iter().map(|r|r.key.as_str()).collect::<Vec<_>>(),["alias","apple","Apple","apple","style"]);
        assert_eq!(d.lookup("apple",&mut job).unwrap().iter().map(|r|r.text.as_str()).collect::<Vec<_>>(),["first","second"]);assert_eq!(d.resolve("alias",&mut job).unwrap().len(),2);assert_eq!(d.lookup("style",&mut job).unwrap()[0].text,"`1`blue");
        assert_eq!(d.header().attributes["Description"],"A\r\nB\t&amp; literal");assert_eq!(d.header().attributes["ForeignExtension"],"A\nB <extension>");assert_eq!(d.header().attributes["StripKey"],"No");assert_eq!(d.header().attributes["Compact"],"Yes");
    }
}
#[test]fn raw_mdd_duplicates_and_empty_resources_are_preserved_without_extraction() {
    let temp=tempfile::tempdir().unwrap();let req=Request::PackMdd {destination:temp.path().join("raw.mdd"),metadata:Metadata {title:"资源".into(),description:"A\nB".into(),..Metadata::default()},resources:vec![Resource {key:"data.bin".into(),bytes:vec![0,255]},Resource {key:"data.bin".into(),bytes:vec![128]},Resource {key:"empty.bin".into(),bytes:vec![]},Resource {key:"../raw.bin".into(),bytes:vec![1]}]};
    execute(&req).unwrap();let d=ResourceArchive::open_v2(req.destination(),&Limits::default(),&mut ImportJob::new("mdd",&CancellationToken::default(),&mut |_|{})).unwrap();assert_eq!(d.resources().len(),4);assert_eq!(d.resources()[1].bytes,[0,255]);assert_eq!(d.resources()[2].bytes,[128]);assert_eq!(d.resources()[3].bytes,[]);assert_eq!(fs::read_dir(temp.path()).unwrap().count(),1);
}
#[test]fn precommit_cancellation_and_no_clobber_leave_no_new_destination() {
    for phase in ["packing_encoded","packing_header_copy","metadata_commit"] {
        let temp=tempfile::tempdir().unwrap();let req=request(temp.path(),"cancelled.mdx",studio_core::Encoding::Utf8);let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase==phase {stop.cancel();};let error=publication::execute(&req,&mut ImportJob::new("cancel",&token,&mut progress)).unwrap_err();assert_eq!(error.code,ErrorCode::Cancelled);assert!(!req.destination().exists());assert_eq!(fs::read_dir(temp.path()).unwrap().count(),0);
    }
    let temp=tempfile::tempdir().unwrap();let req=request(temp.path(),"existing.mdx",studio_core::Encoding::Utf8);fs::write(req.destination(),b"sentinel").unwrap();assert_eq!(execute(&req).unwrap_err().code,ErrorCode::DestinationExists);assert_eq!(fs::read(req.destination()).unwrap(),b"sentinel");
}
#[test]fn background_metadata_rebuild_and_failed_job_recovery() {
    let temp=tempfile::tempdir().unwrap();let packed=request(temp.path(),"packed.mdx",studio_core::Encoding::Utf8);execute(&packed).unwrap();let destination=temp.path().join("rebuilt.mdx");
    let req=Request::Rebuild {request:metadata::Request {source:packed.destination().into(),destination:destination.clone(),kind:metadata::FileKind::Mdx,edits:metadata::Edits {description:Some("changed\nmetadata".into()),..metadata::Edits::default()}}};
    let r=Runner::new(Config::default()).unwrap();let failed=r.submit(packed).unwrap();let failed=r.wait_for_terminal(&failed,Duration::from_secs(10)).unwrap().unwrap();assert_eq!(failed.state,State::Failed);assert!(!failed.error.unwrap().publication_uncertain);
    let id=r.submit(req).unwrap();assert_eq!(r.wait_for_terminal(&id,Duration::from_secs(10)).unwrap().unwrap().state,State::Succeeded);let summary=r.take_result(&id).unwrap().unwrap();assert_eq!(summary.destination,destination);assert!(destination.exists());assert!(r.take_result(&id).unwrap().is_none());r.join().unwrap();
}
