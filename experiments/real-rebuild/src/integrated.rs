//! Bounded engine-adapter integration: one versioned normalization for sorting
//! and exact-first lookup. No changes to mdictlib's built-in locator.
use mdictlib::{MdxBuilder,MdxFile,WriteOptions,WriteEncoding,LegacySort};
use serde_json::{json,Value};
use std::{collections::BTreeMap,fs,path::Path};
use studio_engine_probe::{Entry,Result,stage_directory};
use super::casing::Casing;

const SHA16:&str="f69d2e55d6b8c8d5fe33f764cc47b829bccc6d73aaff1791e1216328a1c24071";
const LEGACY:&str="unicode16-literal-v1";
const MODERN:&str="unicode17-literal-comparison-v1";

struct Policy{legacy:Option<Casing>}
impl Policy{
    fn named(name:&str)->Result<Self>{match name{
        LEGACY=>Ok(Self{legacy:Some(Casing::pinned16()?)}),
        MODERN if std::char::UNICODE_VERSION==(17,0,0)=>Ok(Self{legacy:None}),
        _=>Err("Unknown or unavailable explicit casing policy".into())}}
    fn lower(&self,key:&str)->String{match &self.legacy{Some(p)=>p.lower(key),None=>key.to_lowercase()}}
}

fn specification(path:&Path)->Result<Value>{
    if fs::metadata(path)?.len()>2*1024*1024{return Err("Integrated spec exceeds 2 MiB".into());}
    Ok(serde_json::from_slice(&fs::read(path)?)?)
}

pub fn inspect(spec_path:&Path,path:&Path)->Result<Value>{
    let spec=specification(spec_path)?;let name=spec["profile"].as_str().ok_or("Missing casing policy")?;let policy=Policy::named(name)?;
    if fs::metadata(path)?.len()>16*1024*1024{return Err("Integrated file exceeds 16 MiB".into());}
    let file=MdxFile::open_with_options(path,&super::strict::options())?;let attrs=super::attributes(file.header());
    if attrs.get("StudioCasingPolicy").map(String::as_str)!=Some(name){return Err("Dictionary casing policy does not match requested policy".into());}
    if attrs.get("StripKey").map(String::as_str)!=Some("No")||attrs.get("KeyCaseSensitive").map(String::as_str)!=Some("No"){return Err("Integrated adapter requires explicit literal insensitive flags".into());}
    if name==LEGACY&&attrs.get("StudioCasingDataSha256").map(String::as_str)!=Some(SHA16){return Err("Unrecognized Unicode16 casing data identity".into());}
    let mut rows=Vec::new();let mut decoded=0usize;
    let mut exact:BTreeMap<String,Vec<usize>>=BTreeMap::new();let mut normalized:BTreeMap<String,Vec<usize>>=BTreeMap::new();
    for key in file.keys(){
        let key=key?;let entry=file.entry_at(key.ordinal())?.ok_or("Missing integrated record")?;
        decoded=decoded.checked_add(key.key().len()+entry.text().len()).ok_or("Integrated size overflow")?;
        if rows.len()>=1000||decoded>8*1024*1024{return Err("Integrated index limit exceeded: 1000 records / 8 MiB decoded".into());}
        let ordinal=rows.len();exact.entry(key.key().to_owned()).or_default().push(ordinal);
        normalized.entry(policy.lower(key.key())).or_default().push(ordinal);
        rows.push(Entry{key:key.key().to_owned(),text:entry.text().to_owned()});
    }
    if rows.len() as u64!=file.len() as u64{return Err("Incomplete integrated scan".into());}
    let queries=spec["queries"].as_array().ok_or("Missing queries")?;
    if queries.len()>1024{return Err("Too many integrated queries".into());}
    let mut lookups=Vec::new();let mut builtin=Vec::new();
    for query in queries{
        let query=query.as_str().ok_or("Invalid integrated query")?;
        let selected=exact.get(query).or_else(||normalized.get(&policy.lower(query)));
        let found:Vec<&Entry>=selected.into_iter().flatten().map(|i|&rows[*i]).collect();
        lookups.push(json!({"query":query,"rows":found}));
        let mut original=Vec::new();
        if let Some(found)=file.locate(query)?{for ordinal in found.iter(){let e=file.entry_at(ordinal)?.ok_or("Missing built-in comparison record")?;original.push(Entry{key:e.key().to_owned(),text:e.text().to_owned()});}}
        builtin.push(json!({"query":query,"rows":original}));
    }
    Ok(json!({"profile":name,"rows":rows,"lookups":lookups,"builtin_engine_lookups":builtin,"attributes":attrs,
        "checksum_policy":"Verify","lookup_implementation":"bounded adapter index, raw-exact first then the same whole-string casing policy used for sorting"}))
}

pub fn build(spec_path:&Path,out:&Path)->Result<Value>{
    let spec=specification(spec_path)?;let name=spec["profile"].as_str().ok_or("Missing profile")?;let policy=Policy::named(name)?;
    let entries:Vec<Entry>=serde_json::from_value(spec["entries"].clone())?;
    if entries.is_empty()||entries.len()>1000{return Err("Expected 1..1000 integrated entries".into());}
    let mut bytes=0usize;
    for e in &entries{bytes=bytes.checked_add(e.key.len()+e.text.len()).ok_or("Integrated size overflow")?;}
    if bytes>8*1024*1024{return Err("Integrated decoded input exceeds 8 MiB".into());}
    let mut ordered:Vec<(String,Entry)>=entries.into_iter().map(|e|(policy.lower(&e.key),e)).collect();
    ordered.sort_by(|left,right|left.0.cmp(&right.0));
    let encoding=match spec["encoding"].as_str(){Some("utf8")=>WriteEncoding::Utf8,Some("utf16")=>WriteEncoding::Utf16Le,_=>return Err("Unknown integrated encoding".into())};
    stage_directory(out,|stage|{
        // Prevent the wire engine from re-sorting our explicit versioned order.
        let options=WriteOptions::new().with_encoding(encoding).with_legacy_sort(LegacySort::PreserveInput).with_key_block_target_bytes(48).with_record_block_target_bytes(96);
        let mut builder=MdxBuilder::with_options(options);
        for (key,value) in [("Title",spec["title"].as_str().ok_or("Missing title")?),("Description","Versioned casing adapter qualification"),("Format","Html"),("Compact","No"),("Compat","Yes"),("StyleSheet",""),("RegisterBy",""),("StudioCasingPolicy",name),("StudioCasingDataSha256",if name==LEGACY{SHA16}else{""})]{builder.header_attribute(key,value)?;}
        for (_,e) in &ordered{builder.add_entry(&e.key,&e.text)?;}
        let path=stage.join("integrated.mdx");let summary=builder.finish(fs::File::create(&path)?)?;super::strict::validate(&path)?;
        let mut result=inspect(spec_path,&path)?;result["key_blocks"]=json!(summary.key_blocks);result["record_blocks"]=json!(summary.record_blocks);
        Ok(result)
    })
}

#[cfg(test)]
mod tests{
    use super::*;
    #[test]
    fn pinned_context_policy_remains_separate_from_native_unicode17(){
        let old=Policy::named(LEGACY).unwrap();assert_eq!(old.lower("꟎Σ"),"꟎σ");
        assert_eq!(old.lower("ΟΣ"),"ος");assert_eq!(old.lower("İ"),"i\u{307}");
        if std::char::UNICODE_VERSION==(17,0,0){assert_eq!(Policy::named(MODERN).unwrap().lower("꟎Σ"),"꟏ς");}
        assert!(Policy::named("guess-from-host").is_err());
    }
}
