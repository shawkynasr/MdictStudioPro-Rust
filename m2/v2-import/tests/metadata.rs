use std::{fs,path::Path};
use studio_v2_import::{*,application::metadata::{self,Request,Edits,FileKind}};
fn source(dir:&Path)->std::path::PathBuf {
    let path=dir.join("source.mdx");let token=CancellationToken::default();
    studio_core::pack_mdx(&studio_core::PackRequest {title:"Original".into(),description:"Original description".into(),encoding:studio_core::Encoding::Utf8,entries:vec![Entry {key:"apple".into(),text:"first".into()},Entry {key:"apple".into(),text:"second".into()},Entry {key:"marker".into(),text:"`1`blue".into()}]},&path,&studio_core::Limits::default(),&mut studio_core::JobContext::new(&token,&mut |_|{})).unwrap();path
}
fn request(dir:&Path)->Request {Request {source:source(dir),destination:dir.join("rebuilt.mdx"),kind:FileKind::Mdx,edits:Edits {title:Some("中文 العربية & <title> \"quoted\"".into()),description:Some("Line1\r\nLine2\t&amp; literal".into()),stylesheet:Some("1\n<span style=\"color:blue\">\n</span>\n".into())}}}
fn tail(data:&[u8])->&[u8] {let n=u32::from_be_bytes(data[..4].try_into().unwrap()) as usize;&data[n+8..]}
#[test]
fn metadata_rebuild_preserves_sections_duplicates_and_raw_markers() {
    let temp=tempfile::tempdir().unwrap();let req=request(temp.path());let before=fs::read(&req.source).unwrap();
    let summary=metadata::rebuild(&req,&mut ImportJob::new("metadata",&CancellationToken::default(),&mut |_|{})).unwrap();
    assert_eq!(summary.records,3);assert_eq!(summary.stylesheet_rules,1);assert_eq!(summary.header.attributes["Description"],req.edits.description.as_ref().unwrap().as_str());
    assert_eq!(summary.header.attributes["Title"],req.edits.title.as_ref().unwrap().as_str());assert_eq!(summary.header.attributes["StyleSheet"],req.edits.stylesheet.as_ref().unwrap().as_str());assert_eq!(summary.header.attributes["Compact"],"Yes");
    assert_eq!(tail(&before),tail(&fs::read(&req.destination).unwrap()));assert_eq!(fs::read(&req.source).unwrap(),before);
    let bytes=fs::read(&req.destination).unwrap();let n=u32::from_be_bytes(bytes[..4].try_into().unwrap()) as usize;
    let units:Vec<_>=bytes[4..4+n].chunks_exact(2).map(|b|u16::from_le_bytes([b[0],b[1]])).collect();let xml=String::from_utf16(&units).unwrap();assert!(xml.contains("&#13;&#10;"));assert!(xml.contains("StyleSheet=\"1\n"));
}
#[test]
fn invalid_styles_controls_and_dangling_markers_never_publish() {
    for style in ["1\n<b>\n</b>","2\n<b>\n</b>\n","", "1\r\n<b>\r\n</b>\r\n"] {
        let temp=tempfile::tempdir().unwrap();let mut req=request(temp.path());req.edits.stylesheet=Some(style.into());assert!(metadata::rebuild(&req,&mut ImportJob::new("invalid",&CancellationToken::default(),&mut |_|{})).is_err());assert!(!req.destination.exists());
    }
    let temp=tempfile::tempdir().unwrap();let mut req=request(temp.path());req.edits.title=Some("bad\u{1}".into());assert_eq!(metadata::rebuild(&req,&mut ImportJob::new("control",&CancellationToken::default(),&mut |_|{})).unwrap_err().detail,"metadata_xml");assert!(!req.destination.exists());
}
#[test]
fn copy_and_commit_cancellation_clean_stages_and_existing_destination_is_kept() {
    for phase in ["metadata_copy","metadata_commit"] {
        let temp=tempfile::tempdir().unwrap();let req=request(temp.path());let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase==phase {stop.cancel();};
        let e=metadata::rebuild(&req,&mut ImportJob::new("cancel",&token,&mut progress)).unwrap_err();assert_eq!(e.code,ErrorCode::Cancelled);assert!(!req.destination.exists());assert_eq!(fs::read_dir(temp.path()).unwrap().count(),1);
    }
    let temp=tempfile::tempdir().unwrap();let req=request(temp.path());fs::write(&req.destination,b"sentinel").unwrap();assert_eq!(metadata::rebuild(&req,&mut ImportJob::new("existing",&CancellationToken::default(),&mut |_|{})).unwrap_err().code,ErrorCode::DestinationExists);assert_eq!(fs::read(&req.destination).unwrap(),b"sentinel");
}
#[test]
fn mdd_metadata_and_unknown_attributes_preserve_duplicate_binary_resources() {
    let temp=tempfile::tempdir().unwrap();let path=temp.path().join("source.mdd");
    let mut builder=mdictlib::MddBuilder::with_options(mdictlib::WriteOptions::new().with_legacy_sort(mdictlib::LegacySort::PreserveInput));
    builder.header_attribute("ForeignExtension","retain & <extension>").unwrap();builder.add_resource("data.bin",&[0,255]).unwrap();builder.add_resource("data.bin",&[128]).unwrap();builder.add_resource("empty.bin",&[]).unwrap();builder.finish(&mut fs::File::create(&path).unwrap()).unwrap();
    let before=fs::read(&path).unwrap();let req=Request {source:path,destination:temp.path().join("rebuilt.mdd"),kind:FileKind::Mdd,edits:Edits {title:Some("字 العربية".into()),description:Some("A\r\nB\t&".into()),stylesheet:None}};
    let summary=metadata::rebuild(&req,&mut ImportJob::new("mdd",&CancellationToken::default(),&mut |_|{})).unwrap();assert_eq!(summary.records,3);assert_eq!(summary.header.attributes["ForeignExtension"],"retain & <extension>");assert_eq!(tail(&before),tail(&fs::read(&req.destination).unwrap()));
}
