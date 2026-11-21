//! Explicit Verify policy and exhaustive lazy block access for validation jobs.
use mdictlib::{ChecksumPolicy,OpenOptions,MdxFile,MddFile,Error};
use serde_json::{json,Value};
use std::path::Path;

pub fn options()->OpenOptions {OpenOptions::new().with_checksum_policy(ChecksumPolicy::Verify)}

fn update(hash:&mut u64,bytes:&[u8]) {
    // Diagnostic fingerprint only. Corpus qualification separately uses SHA-256.
    let length=(bytes.len() as u64).to_be_bytes();
    for byte in length.iter().chain(bytes.iter()) {
        *hash=(*hash ^ u64::from(*byte)).wrapping_mul(0x100000001b3);
    }
}

fn scan(path:&Path,verify:bool,phase:&mut &'static str)->mdictlib::Result<Value> {
    let policy=if verify {ChecksumPolicy::Verify} else {ChecksumPolicy::Skip};
    let options=OpenOptions::new().with_checksum_policy(policy);
    let mut records=0u64;let mut bytes=0u64;let mut fingerprint=0xcbf29ce484222325u64;let declared;
    *phase="open";
    let is_mdd=path.extension().and_then(|x|x.to_str()).is_some_and(|x|x.eq_ignore_ascii_case("mdd"));
    if is_mdd {
        let file=MddFile::open_with_options(path,&options)?;
        declared=file.len() as u64;
        for key in file.keys() {
            *phase="keys";let key=key?;update(&mut fingerprint,key.key().as_bytes());
            *phase="records";let value=file.resource_at(key.ordinal())?.ok_or_else(||Error::InvalidData("Missing validation resource".to_owned()))?;
            update(&mut fingerprint,value.bytes());bytes+=value.bytes().len() as u64;records+=1;
        }
    } else {
        let file=MdxFile::open_with_options(path,&options)?;
        declared=file.len() as u64;
        for key in file.keys() {
            *phase="keys";let key=key?;update(&mut fingerprint,key.key().as_bytes());
            *phase="records";let value=file.entry_at(key.ordinal())?.ok_or_else(||Error::InvalidData("Missing validation entry".to_owned()))?;
            update(&mut fingerprint,value.text().as_bytes());bytes+=value.text().len() as u64;records+=1;
        }
    }
    if records!=declared {return Err(Error::InvalidData("Incomplete full checksum scan".to_owned()));}
    *phase="complete";
    Ok(json!({"status":"validated","checksum_policy":if verify {"Verify"} else {"Skip"},
        "records":records,"payload_bytes":bytes,"diagnostic_fingerprint_fnv1a64":format!("{fingerprint:016x}"),
        "scope":"all physical keys and payloads materialized; fingerprint is non-cryptographic"}))
}

pub fn validate(path:&Path)->mdictlib::Result<Value> {let mut phase="open";scan(path,true,&mut phase)}

pub fn observe(path:&Path,verify:bool)->(i32,Value) {
    let mut phase="open";
    match scan(path,verify,&mut phase) {
        Ok(value)=>(0,value),
        Err(error)=>{
            let detail=match &error {
                Error::ChecksumMismatch{context,expected,actual}=>json!({"error_kind":"ChecksumMismatch","context":context,"expected":expected,"actual":actual}),
                Error::InvalidData(_)=>json!({"error_kind":"InvalidData"}),
                _=>json!({"error_kind":"Other"}),
            };
            let mut value=json!({"status":"rejected","checksum_policy":if verify {"Verify"} else {"Skip"},"phase":phase,"error":error.to_string(),"error_debug":format!("{error:?}")});
            if let Some(fields)=detail.as_object() {for (key,value_field) in fields {value[key.as_str()]=value_field.clone();}}
            (1,value)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use mdictlib::MdxBuilder;
    #[test]
    fn strict_validates_payloads_and_reports_a_typed_header_checksum_error() {
        let temp=tempfile::tempdir().unwrap();let path=temp.path().join("source.mdx");
        let mut builder=MdxBuilder::new();builder.add_entry("word","body\n").unwrap();
        let mut bytes=Vec::new();builder.finish(&mut bytes).unwrap();
        std::fs::write(&path,&bytes).unwrap();assert_eq!(observe(&path,true).0,0);
        let size=u32::from_be_bytes(bytes[..4].try_into().unwrap()) as usize;bytes[4+size]^=1;
        std::fs::write(&path,&bytes).unwrap();let (code,result)=observe(&path,true);
        assert_eq!(code,1);assert_eq!(result["error_kind"],"ChecksumMismatch");
    }
}
