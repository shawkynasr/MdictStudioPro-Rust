use super::*;
use std::{fs,path::Path};
fn run(req:&Request,limits:&IoLimits,cancel:Option<&str>)->Result<Summary> {let token=CancellationToken::default();let stop=token.clone();let mut cb=|p:Progress| {if cancel==Some(p.phase.as_str()) {stop.cancel();}};execute(req,limits,&mut ImportJob::new("test",&token,&mut cb))}
fn input(path:&Path,rows:usize) {let mut s=String::new();for i in 0..rows {s.push_str(&serde_json::json!({"key":if i%2==0 {"Apple"}else{"apple"},"text":format!("字 مرحبا {i}\n\n")} ).to_string());s.push('\n');}fs::write(path,s).unwrap();}
fn mdx(src:&Path,dst:&Path)->Request {Request::PackMdx {source:src.into(),destination:dst.into(),encoding:studio_core::Encoding::Utf16,metadata:Metadata {title:"字 مرحبا".into(),description:"first\nsecond".into(),..Metadata::default()}}}
#[test]fn larger_duplicate_pack_and_both_exports() {
 let d=tempfile::tempdir().unwrap();let src=d.path().join("rows.jsonl");input(&src,2049);let dict=d.path().join("test.mdx");let p=run(&mdx(&src,&dict),&IoLimits::default(),None).unwrap();assert_eq!(p.records,2049);
 for (name,req) in [("out.jsonl",Request::ExportJsonl {source:dict.clone(),destination:d.path().join("out.jsonl") }),("out.txt",Request::ExportTxt {source:dict.clone(),destination:d.path().join("out.txt")})] {let r=run(&req,&IoLimits::default(),None).unwrap();assert_eq!(r.framed_records_sha256,p.framed_records_sha256);assert!(d.path().join(name).is_file());}
 let rows:Vec<serde_json::Value>=fs::read_to_string(d.path().join("out.jsonl")).unwrap().lines().map(|s|serde_json::from_str(s).unwrap()).collect();for(i,row)in rows.iter().enumerate() {assert_eq!(row["text"],format!("字 مرحبا {i}\n\n"));}
}
#[test]fn cancellation_at_each_publication_phase_leaves_no_file() {
 let d=tempfile::tempdir().unwrap();let src=d.path().join("input");input(&src,5);
 for phase in ["input_snapshot","load_records","builder_entries","encode_dictionary","encoded_dictionary","verify_records","publish_file"] {let dst=d.path().join(phase);let e=run(&mdx(&src,&dst),&IoLimits::default(),Some(phase)).unwrap_err();assert_eq!(e.code,ErrorCode::Cancelled);assert!(!dst.exists());}
 assert_eq!(fs::read_dir(d.path()).unwrap().count(),1);
}
#[test]fn lowered_limits_and_no_clobber() {
 let d=tempfile::tempdir().unwrap();let src=d.path().join("input");input(&src,5);let dst=d.path().join("out");
 for mode in 0..6 {let mut l=IoLimits::default();match mode {0=>l.max_records=4,1=>l.max_decoded_bytes=2,2=>l.max_entry_bytes=1,3=>l.max_plan_charge=1,4=>l.max_input_bytes=1,_=>l.max_output_bytes=8};assert_eq!(run(&mdx(&src,&dst),&l,None).unwrap_err().code,ErrorCode::LimitExceeded);assert!(!dst.exists());}
 fs::write(&dst,b"keep").unwrap();assert_eq!(run(&mdx(&src,&dst),&IoLimits::default(),None).unwrap_err().code,ErrorCode::DestinationExists);assert_eq!(fs::read(&dst).unwrap(),b"keep");
}
#[test]fn stylesheet_validation_and_lossless_txt_refusal() {
 let d=tempfile::tempdir().unwrap();let src=d.path().join("in");let dst=d.path().join("out.mdx");fs::write(&src,"{\"key\":\"x\",\"text\":\"`1`blue\"}\n").unwrap();let mut req=mdx(&src,&dst);assert_eq!(run(&req,&IoLimits::default(),None).unwrap_err().detail,"stylesheet_marker");
 if let Request::PackMdx {metadata,..}=&mut req {metadata.stylesheet="1\n<b>\n</b>\n".into();}run(&req,&IoLimits::default(),None).unwrap();
 let src2=d.path().join("in2");fs::write(&src2,"{\"key\":\"two\\nlines\",\"text\":\"body\"}\n").unwrap();let dst2=d.path().join("two.mdx");run(&mdx(&src2,&dst2),&IoLimits::default(),None).unwrap();let text=d.path().join("out.txt");assert_eq!(run(&Request::ExportTxt {source:dst2,destination:text.clone()},&IoLimits::default(),None).unwrap_err().code,ErrorCode::UnrepresentableSource);assert!(!text.exists());
}
#[cfg(unix)]#[test]fn resource_root_binary_and_escape_refusals() {
 let d=tempfile::tempdir().unwrap();let root=d.path().join("resources");fs::create_dir(&root).unwrap();fs::write(root.join("data.bin"),[0u8,255,1,0]).unwrap();fs::write(root.join("empty"),[]).unwrap();std::os::unix::fs::symlink("data.bin",root.join("link")).unwrap();let src=d.path().join("in");let dst=d.path().join("out.mdd");let req=Request::PackMdd {source:src.clone(),resource_root:root,destination:dst.clone(),metadata:Metadata::default()};
 for name in ["../escape","/data.bin","link"] {fs::write(&src,format!("{{\"key\":\"a\",\"file\":{}}}\n",serde_json::to_string(name).unwrap())).unwrap();assert!(run(&req,&IoLimits::default(),None).is_err());assert!(!dst.exists());}
 fs::write(&src,"{\"key\":\"a\",\"file\":\"data.bin\"}\n{\"key\":\"b\",\"file\":\"empty\"}\n").unwrap();let r=run(&req,&IoLimits::default(),None).unwrap();assert_eq!((r.records,r.payload_bytes),(2,4));
}
