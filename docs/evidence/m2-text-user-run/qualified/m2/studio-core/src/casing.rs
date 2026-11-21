//! Versioned lowercase candidate. Unicode16 tables come from the explicit
//! Python16 oracle file, never from the compiler's evolving Unicode tables.
use serde_json::Value;
use std::collections::BTreeMap;
type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

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
