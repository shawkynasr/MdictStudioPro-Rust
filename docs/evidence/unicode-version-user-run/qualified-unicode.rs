//! Enumerate the compiler's lowercase mapping without writing a dictionary.
use serde_json::{json,Value};
use std::{fs,path::Path};
use studio_engine_probe::Result;

pub fn probe(path:&Path)->Result<Value>{
    if fs::metadata(path)?.len()>1024*1024{return Err("Unicode probe spec limit is 1 MiB".into());}
    let spec:Value=serde_json::from_slice(&fs::read(path)?)?;
    let words=spec["words"].as_array().ok_or("Missing words")?;
    if words.len()>1000{return Err("Unicode context probe limit is 1000 words".into());}
    let mut contexts=Vec::new();
    for word in words{
        let word=word.as_str().ok_or("Invalid context word")?;
        contexts.push(json!({"word":word,"string_lower":word.to_lowercase(),"scalar_lower":word.chars().flat_map(char::to_lowercase).collect::<String>()}));
    }
    let mut changed=Vec::new();let mut scanned=0u64;
    for n in 0..=0x10ffff {
        if let Some(ch)=char::from_u32(n){
            scanned+=1;let lower=ch.to_lowercase().collect::<String>();
            if lower!=ch.to_string(){changed.push(json!([n,lower]));}
        }
    }
    Ok(json!({"rust_unicode_version":std::char::UNICODE_VERSION,"scalars_scanned":scanned,"changed_scalar_mappings":changed,"contexts":contexts,
        "scope":"Unicode lowercase only; not casefold, NFC/NFKC, locale collation or official builder mapping"}))
}
