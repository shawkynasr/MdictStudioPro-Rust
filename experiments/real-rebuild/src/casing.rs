//! Versioned lowercase candidate. Unicode16 tables come from the explicit
//! Python16 oracle file, never from the compiler's evolving Unicode tables.
use serde_json::{json,Value};
use std::{collections::BTreeMap,fs,path::Path};
use studio_engine_probe::Result;

pub(super) struct Casing{mapping:BTreeMap<u32,String>,cased:Vec<(u32,u32)>,ignored:Vec<(u32,u32)>}

fn ranges(value:&Value)->Result<Vec<(u32,u32)>>{
    let mut result=Vec::new();let mut previous=None;
    for row in value.as_array().ok_or("Missing property ranges")?{
        let row=row.as_array().ok_or("Invalid property range")?;
        if row.len()!=2{return Err("Property range must have two endpoints".into());}
        let lo=row[0].as_u64().ok_or("Invalid range start")?;let hi=row[1].as_u64().ok_or("Invalid range end")?;
        if lo>hi||hi>0x10ffff||(lo<=0xdfff&&hi>=0xd800)||previous.is_some_and(|p|lo<=p){return Err("Invalid or overlapping scalar ranges".into());}
        result.push((lo as u32,hi as u32));previous=Some(hi);
    }
    Ok(result)
}

fn contains(ranges:&[(u32,u32)],c:char)->bool{
    let n=c as u32;let index=ranges.partition_point(|(_,end)|*end<n);
    ranges.get(index).is_some_and(|(start,_)|*start<=n)
}

impl Casing{
    fn load(path:&Path)->Result<Self>{
        if fs::metadata(path)?.len()>2*1024*1024{return Err("Casing table exceeds 2 MiB".into());}
        let data:Value=serde_json::from_slice(&fs::read(path)?)?;
        Self::parse(&data)
    }
    pub(super) fn pinned16()->Result<Self>{
        Self::parse(&serde_json::from_str(include_str!("../../../baseline/unicode/unicode16-casing.json"))?)
    }
    fn parse(data:&Value)->Result<Self>{
        if data["profile"]!="python-unicode-16-root-lower-v1"||data["unicode_version"]!="16.0.0" {return Err("Expected explicit Python Unicode16 policy".into());}
        let mut mapping=BTreeMap::new();let mut previous=None;
        for row in data["lower_mappings"].as_array().ok_or("Missing mappings")?{
            let row=row.as_array().ok_or("Invalid mapping")?;
            if row.len()!=2{return Err("Mapping must have two fields".into());}
            let n=row[0].as_u64().ok_or("Invalid mapping codepoint")?;
            if n>0x10ffff||previous.is_some_and(|p|n<=p){return Err("Invalid or unsorted mapping".into());}
            let c=char::from_u32(n as u32).ok_or("Surrogate mapping")?;
            let text=row[1].as_str().ok_or("Invalid lowercase mapping")?;
            if text.is_empty()||text.len()>32||text==c.to_string(){return Err("Invalid identity/empty/oversized mapping".into());}
            mapping.insert(n as u32,text.to_owned());previous=Some(n);
        }
        Ok(Self{mapping,cased:ranges(&data["cased_ranges"])?,ignored:ranges(&data["case_ignorable_ranges"])?})
    }
    pub(super) fn lower(&self,text:&str)->String{
        let chars:Vec<char>=text.chars().collect();let mut following=vec![false;chars.len()];let mut next=false;
        for (i,c) in chars.iter().enumerate().rev(){
            following[i]=next;
            if !contains(&self.ignored,*c){next=contains(&self.cased,*c);}
        }
        let mut previous=false;let mut result=String::new();
        for (i,c) in chars.iter().enumerate(){
            // Context refers to the ORIGINAL string. Ignorable takes priority
            // for characters that are both Cased and Case_Ignorable.
            if *c=='Σ'&&previous&&!following[i]{result.push('ς');}
            else if let Some(mapped)=self.mapping.get(&(*c as u32)){result.push_str(mapped);}
            else{result.push(*c);}
            if !contains(&self.ignored,*c){previous=contains(&self.cased,*c);}
        }
        result
    }
}

pub fn probe(path:&Path)->Result<Value>{
    if std::char::UNICODE_VERSION!=(17,0,0){return Err("Modern comparison requires compiler Unicode17; refusing implicit version drift".into());}
    if fs::metadata(path)?.len()>2*1024*1024{return Err("Casing spec exceeds 2 MiB".into());}
    let spec:Value=serde_json::from_slice(&fs::read(path)?)?;
    let policy=Casing::load(Path::new(spec["policy_path"].as_str().ok_or("Missing policy path")?))?;
    let words=spec["words"].as_array().ok_or("Missing context words")?;
    if words.len()>4096{return Err("Too many casing contexts".into());}
    let mut contexts=Vec::new();
    for word in words{
        let word=word.as_str().ok_or("Invalid casing word")?;
        if word.chars().count()>4096{return Err("Context word too long".into());}
        contexts.push(json!({"word":word,"legacy16":policy.lower(word),"modern17":word.to_lowercase()}));
    }
    let mut legacy=Vec::new();let mut modern=Vec::new();let mut count=0u64;
    let skip_scalar_scan=spec["skip_scalar_scan"].as_bool().unwrap_or(false);
    for n in (0..=0x10ffff).take(if skip_scalar_scan{0}else{0x110000}){
        if let Some(c)=char::from_u32(n){
            count+=1;let s=c.to_string();let a=policy.lower(&s);let b=c.to_lowercase().collect::<String>();
            if a!=s{legacy.push(json!([n,a]));}if b!=s{modern.push(json!([n,b]));}
        }
    }
    Ok(json!({"profiles":["python-unicode-16-root-lower-v1","rust-unicode-17-root-lower-v1"],"scalars_scanned":count,
        "legacy_changed_mappings":legacy,"modern_changed_mappings":modern,"contexts":contexts,
        "engine_integrated":false,"scalar_scan_skipped":skip_scalar_scan,"data_status":"oracle-derived candidate; freeze reviewed file hash before production use"}))
}

#[cfg(test)]
mod tests{
    use super::*;
    #[test]
    fn final_sigma_ignores_marks_in_original_context_in_linear_passes(){
        let policy=Casing{mapping:[('A' as u32,"a".into()),('B' as u32,"b".into()),('Σ' as u32,"σ".into())].into_iter().collect(),
            cased:vec![(65,66),(0x345,0x345),(0x3a3,0x3a3)],ignored:vec![(39,39),(0x345,0x345)]};
        for (input,expected) in [("AΣ","aς"),("AΣB","aσb"),("AΣ'B","aσ'b"),("AΣ\u{345}","aς\u{345}"),("A\u{345}Σ","a\u{345}ς"),("\u{345}Σ","\u{345}σ")]{assert_eq!(policy.lower(input),expected);}
    }
}
