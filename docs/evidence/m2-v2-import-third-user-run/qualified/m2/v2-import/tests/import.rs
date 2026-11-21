use std::{fs,path::{Path,PathBuf}};
use studio_v2_import::*;
fn rows()->Vec<Entry> {vec![Entry {key:"Apple".into(),text:"upper".into()},Entry {key:"apple".into(),text:"first".into()},Entry {key:"apple".into(),text:"second".into()},Entry {key:"a-b".into(),text:"punctuation".into()},Entry {key:"alias".into(),text:"@@@LINK=apple\r\n".into()},Entry {key:"missing-alias".into(),text:"@@@LINK=absent".into()},Entry {key:"cycle".into(),text:"@@@LINK=cycle".into()},Entry {key:"字".into(),text:"`1`raw formatting".into()}]}
fn adler(data:&[u8])->u32 {let(mut a,mut b)=(1u32,0u32);for &c in data {a=(a+u32::from(c))%65521;b=(b+a)%65521;}(b<<16)|a}
fn rewrite(path:&Path,changes:&[(&str,&str)]) {
    let data=fs::read(path).unwrap();let n=u32::from_be_bytes(data[..4].try_into().unwrap()) as usize;
    let units:Vec<_>=data[4..4+n].chunks_exact(2).map(|b|u16::from_le_bytes([b[0],b[1]])).collect();let mut xml=String::from_utf16(&units).unwrap();
    for (a,b) in changes {assert!(xml.contains(a),"Missing anchor {a}");xml=xml.replacen(a,b,1);}
    let bytes:Vec<_>=xml.encode_utf16().flat_map(u16::to_le_bytes).collect();let mut out=(bytes.len() as u32).to_be_bytes().to_vec();out.extend(&bytes);out.extend(adler(&bytes).to_le_bytes());out.extend(&data[4+n+4..]);fs::write(path,out).unwrap();
}
fn foreign(dir:&Path)->PathBuf {
    let path=dir.join("foreign.mdx");let token=CancellationToken::default();
    let request=studio_core::PackRequest {title:"Foreign fixture".into(),description:"v2 import".into(),encoding:studio_core::Encoding::Utf8,entries:rows()};
    studio_core::pack_mdx(&request,&path,&studio_core::Limits::default(),&mut studio_core::JobContext::new(&token,&mut |_|{})).unwrap();
    rewrite(&path,&[("StudioCasingPolicy","ForeignCasingPolicy"),("StudioCasingDataSha256","ForeignCasingDataSha256")]);path
}
fn open(path:&Path,policy:LookupPolicy)->Result<Dictionary> {Dictionary::open_v2(path,policy,&Limits::default(),&mut ImportJob::new("test",&CancellationToken::default(),&mut |_|{}))}
#[test]
fn untagged_import_exact_first_duplicates_and_explicit_header_normalization() {
    let temp=tempfile::tempdir().unwrap();let path=foreign(temp.path());let token=CancellationToken::default();let mut sink=|_|{};let mut job=ImportJob::new("lookup",&token,&mut sink);
    let raw=open(&path,LookupPolicy::RawExact).unwrap();assert!(raw.lookup("aPpLe",&mut job).unwrap().is_empty());
    let dict=open(&path,LookupPolicy::HeaderAsciiV1).unwrap();assert_eq!(dict.lookup("apple",&mut job).unwrap().iter().map(|e|e.text.as_str()).collect::<Vec<_>>(),["first","second"]);
    assert_eq!(dict.lookup("aPpLe",&mut job).unwrap().len(),3);assert!(dict.lookup("ab",&mut job).unwrap().is_empty());
    rewrite(&path,&[("StripKey=\"No\"","Stripkey=\"Yes\"")]);let stripped=open(&path,LookupPolicy::HeaderAsciiV1).unwrap();assert_eq!(stripped.lookup("ab",&mut job).unwrap()[0].key,"a-b");
    rewrite(&path,&[("KeyCaseSensitive=\"No\"","KeyCaseSensitive=\"Yes\"")]);let sensitive=open(&path,LookupPolicy::HeaderAsciiV1).unwrap();assert!(sensitive.lookup("APPLE",&mut job).unwrap().is_empty());
    assert!(studio_core::Dictionary::open_studio_output(&path,&studio_core::Limits::default(),&mut studio_core::JobContext::new(&token,&mut |_|{})).is_err());
}
#[test]
fn redirect_duplicates_missing_cycles_depth_and_raw_bodies_are_explicit() {
    let temp=tempfile::tempdir().unwrap();let path=foreign(temp.path());let dict=open(&path,LookupPolicy::HeaderAsciiV1).unwrap();let token=CancellationToken::default();let mut sink=|_|{};let mut job=ImportJob::new("redirect",&token,&mut sink);
    assert_eq!(dict.lookup("alias",&mut job).unwrap()[0].text,"@@@LINK=apple\r\n");let resolved=dict.resolve("alias",&mut job).unwrap();assert_eq!(resolved.len(),2);assert_eq!(resolved[0].entry.text,"first");assert_eq!(resolved[1].entry.text,"second");assert_eq!(resolved[0].chain.len(),1);
    assert_eq!(dict.resolve("cycle",&mut job).unwrap_err().detail,"redirect_cycle");assert_eq!(dict.resolve("missing-alias",&mut job).unwrap_err().detail,"redirect_missing");
    let mut limits=Limits::default();limits.redirects.max_hops=0;let dict=Dictionary::open_v2(&path,LookupPolicy::RawExact,&limits,&mut job).unwrap();assert_eq!(dict.resolve("alias",&mut job).unwrap_err().detail,"redirect_depth");
}
#[test]
fn budgets_and_cancellation_return_no_partial_success() {
    let temp=tempfile::tempdir().unwrap();let path=foreign(temp.path());let mut limits=Limits::default();limits.dictionary.max_result_entries=1;let token=CancellationToken::default();let mut sink=|_|{};let mut job=ImportJob::new("budget",&token,&mut sink);
    let dict=Dictionary::open_v2(&path,LookupPolicy::RawExact,&limits,&mut job).unwrap();assert_eq!(dict.lookup("apple",&mut job).unwrap_err().code,ErrorCode::LimitExceeded);assert_eq!(dict.resolve("alias",&mut job).unwrap_err().code,ErrorCode::LimitExceeded);
    let stop=token.clone();let mut progress=|p:Progress|if p.phase=="indexing" {stop.cancel();};let result=Dictionary::open_v2(&path,LookupPolicy::RawExact,&Limits::default(),&mut ImportJob::new("cancel",&token,&mut progress));assert!(matches!(result,Err(Error {code:ErrorCode::Cancelled,..})));
}
#[test]
fn unsupported_version_encryption_encoding_and_bad_header_checksum_are_refused() {
    for (a,b) in [("GeneratedByEngineVersion=\"2.0\"","GeneratedByEngineVersion=\"3.0\""),("Encrypted=\"No\"","Encrypted=\"2\""),("Encoding=\"UTF-8\"","Encoding=\"ISO8859-1\"")] {
        let temp=tempfile::tempdir().unwrap();let path=foreign(temp.path());rewrite(&path,&[(a,b)]);assert!(matches!(open(&path,LookupPolicy::RawExact),Err(Error {code:ErrorCode::UnsupportedPolicy,..})));
    }
    let temp=tempfile::tempdir().unwrap();let path=foreign(temp.path());let mut data=fs::read(&path).unwrap();let n=u32::from_be_bytes(data[..4].try_into().unwrap()) as usize;data[4+n]^=1;fs::write(&path,data).unwrap();assert!(matches!(open(&path,LookupPolicy::RawExact),Err(Error {code:ErrorCode::Integrity,..})));
}
#[test]
fn header_styles_and_missing_flags_are_preserved_without_silent_defaults() {
    let temp=tempfile::tempdir().unwrap();let path=foreign(temp.path());rewrite(&path,&[("StyleSheet=\"\"","StyleSheet=\"1&#10;&lt;b&gt;&#10;&lt;/b&gt;&#10;\""),(" StripKey=\"No\"","")]);
    let dict=open(&path,LookupPolicy::RawExact).unwrap();assert!(dict.header().raw_xml.contains("&#10;"));assert!(dict.header().attributes["StyleSheet"].contains("<b>"));assert_eq!(dict.header().strip_key,None);assert!(open(&path,LookupPolicy::HeaderAsciiV1).is_err());
    assert!(dict.entries().iter().any(|e|e.text=="`1`raw formatting"));
}
#[test]
fn ordinary_mdd_import_preserves_binary_bytes_and_exact_key_lookup() {
    let temp=tempfile::tempdir().unwrap();let path=temp.path().join("foreign.mdd");let token=CancellationToken::default();
    let request=studio_core::ResourcePackRequest {title:"Resources".into(),description:"raw".into(),resources:vec![Resource {key:"\\A.bin".into(),bytes:vec![0,255,128]},Resource {key:"empty.bin".into(),bytes:vec![]}]};
    studio_core::pack_mdd(&request,&path,&studio_core::Limits::default(),&mut studio_core::JobContext::new(&token,&mut |_|{})).unwrap();rewrite(&path,&[("StudioResourcePolicy","ForeignResourcePolicy"),("StudioCasingDataSha256","ForeignCasingDataSha256")]);
    let mut sink=|_|{};let mut job=ImportJob::new("mdd",&token,&mut sink);let archive=ResourceArchive::open_v2(&path,&Limits::default(),&mut job).unwrap();assert_eq!(archive.resources().len(),2);assert_eq!(archive.lookup("\\A.bin",&mut job).unwrap()[0].bytes,[0,255,128]);assert!(archive.lookup("\\a.bin",&mut job).unwrap().is_empty());
}
