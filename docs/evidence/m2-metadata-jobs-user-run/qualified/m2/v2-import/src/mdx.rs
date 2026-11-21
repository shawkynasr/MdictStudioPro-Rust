use crate::{casing::Casing,Header,Kind,Limits,ImportJob,Entry,Result,Error,ErrorCode,budget,invalid,integrity,unsupported,sum,key};
use mdictlib::{MdxFile,OpenOptions,ChecksumPolicy};
use serde::{Deserialize,Serialize};
use std::{collections::BTreeMap,path::Path};

#[derive(Clone,Copy,Debug,PartialEq,Eq,Serialize,Deserialize)]
#[serde(rename_all="snake_case")]
pub enum LookupPolicy {RawExact,HeaderAsciiV1}
impl LookupPolicy {pub fn id(self)->&'static str {match self {Self::RawExact=>"raw-exact-v1",Self::HeaderAsciiV1=>"header-ascii-strip-unicode16-v1"}}}
pub struct Dictionary {
    header:Header,rows:Vec<Entry>,exact:BTreeMap<String,Vec<usize>>,normalized:BTreeMap<String,Vec<usize>>,
    casing:Casing,policy:LookupPolicy,limits:Limits,
}
#[derive(Debug,Serialize)]
pub struct RedirectHop {pub ordinal:usize,pub key:String,pub target:String}
#[derive(Debug,Serialize)]
pub struct Resolution {pub source_ordinal:usize,pub terminal_ordinal:usize,pub entry:Entry,pub chain:Vec<RedirectHop>}
impl Dictionary {
    pub fn open_v2(path:&Path,policy:LookupPolicy,limits:&Limits,job:&mut ImportJob<'_>)->Result<Self> {
        if limits.redirects.max_hops>64||limits.redirects.max_visits==0||limits.redirects.max_visits>65536 {return Err(invalid("redirect_limits","Require <=64 hops and 1..65536 visits"));}
        let (snapshot,header)=crate::header::snapshot(path,Kind::Mdx,limits,job)?;
        if policy==LookupPolicy::HeaderAsciiV1&&(header.case_sensitive.is_none()||header.strip_key.is_none()) {return Err(unsupported("Header-guided lookup requires explicit KeyCaseSensitive and StripKey flags; raw_exact can inspect missing flags"));}
        let options=OpenOptions::new().with_checksum_policy(ChecksumPolicy::Verify);let file=MdxFile::open_with_options(snapshot.path(),&options)?;
        let declared=usize::try_from(file.len()).map_err(|_|budget("Entry count overflow"))?;
        if declared>limits.dictionary.max_entries {return Err(budget("Import entry count exceeded"));}
        let casing=Casing::pinned16().map_err(|e|Error::new(ErrorCode::Internal,"casing",e.to_string()))?;
        let mut out=Self {header,rows:Vec::new(),exact:BTreeMap::new(),normalized:BTreeMap::new(),casing,policy,limits:limits.clone()};let mut bytes=0;
        for physical in file.keys() {
            job.tick("indexing",out.rows.len(),declared)?;let physical=physical?;key(physical.key(),limits)?;
            let value=file.entry_at(physical.ordinal())?.ok_or_else(||integrity("Missing physical MDX record"))?;
            if value.text().len()>limits.dictionary.max_entry_bytes {return Err(budget("Import definition budget exceeded"));}
            bytes=sum(bytes,sum(physical.key().len(),value.text().len())?)?;
            if bytes>limits.dictionary.max_decoded_bytes||out.rows.len()>=limits.dictionary.max_entries {return Err(budget("Import decoded budget exceeded"));}
            let ordinal=out.rows.len();let row=Entry {key:physical.key().into(),text:value.text().into()};
            out.exact.entry(row.key.clone()).or_default().push(ordinal);
            if policy==LookupPolicy::HeaderAsciiV1 {let normalized=out.normalize(&row.key);out.normalized.entry(normalized).or_default().push(ordinal);}
            out.rows.push(row);
        }
        if out.rows.len()!=declared {return Err(integrity("Incomplete physical MDX scan"));}
        job.tick("indexing",declared,declared)?;Ok(out)
    }
    pub fn header(&self)->&Header {&self.header}
    pub fn entries(&self)->&[Entry] {&self.rows}
    pub fn policy(&self)->LookupPolicy {self.policy}
    fn normalize(&self,s:&str)->String {
        let value=if self.header.case_sensitive==Some(false) {self.casing.lower(s)}else{s.into()};
        if self.header.strip_key==Some(true) {value.chars().filter(|c|!c.is_ascii_punctuation()&&!matches!(c,'\t'..='\r'|' ')).collect()}else{value}
    }
    fn select(&self,query:&str)->Result<Option<&[usize]>> {
        key(query,&self.limits)?;
        if let Some(found)=self.exact.get(query) {return Ok(Some(found));}
        if self.policy==LookupPolicy::RawExact {return Ok(None);}
        let normalized=self.normalize(query);
        if normalized.is_empty() {return Err(invalid("empty_normalized_query","Query becomes empty under header_ascii_v1"));}
        Ok(self.normalized.get(&normalized).map(Vec::as_slice))
    }
    pub fn lookup(&self,query:&str,job:&mut ImportJob<'_>)->Result<Vec<Entry>> {
        job.check()?;let Some(ordinals)=self.select(query)? else {return Ok(Vec::new());};
        if ordinals.len()>self.limits.dictionary.max_result_entries {return Err(budget("Lookup result count exceeded"));}
        let mut bytes=0;for &ordinal in ordinals {job.check()?;let row=&self.rows[ordinal];bytes=sum(bytes,sum(row.key.len(),row.text.len())?)?;if bytes>self.limits.dictionary.max_result_bytes {return Err(budget("Lookup result bytes exceeded"));}}
        let mut out=Vec::new();for &ordinal in ordinals {job.check()?;out.push(self.rows[ordinal].clone());}Ok(out)
    }
    pub fn resolve(&self,query:&str,job:&mut ImportJob<'_>)->Result<Vec<Resolution>> {
        job.check()?;let Some(ordinals)=self.select(query)? else {return Ok(Vec::new());};
        let(mut out,mut path,mut visits,mut bytes)=(Vec::new(),Vec::new(),0,0);
        for &ordinal in ordinals {self.walk(ordinal,ordinal,&mut path,&mut out,&mut visits,&mut bytes,job)?;}Ok(out)
    }
    fn walk(&self,origin:usize,ordinal:usize,path:&mut Vec<(usize,String)>,out:&mut Vec<Resolution>,visits:&mut usize,bytes:&mut usize,job:&mut ImportJob<'_>)->Result<()> {
        job.check()?;*visits=visits.checked_add(1).ok_or_else(||budget("Redirect visit overflow"))?;
        if *visits>self.limits.redirects.max_visits {return Err(budget("Redirect visit budget exceeded"));}
        if path.iter().any(|(seen,_)|*seen==ordinal) {return Err(invalid("redirect_cycle","Physical redirect cycle detected"));}
        let row=&self.rows[ordinal];
        if let Some(target)=redirect(&row.text)? {
            key(target,&self.limits)?;
            if path.len()>=self.limits.redirects.max_hops {return Err(Error::new(ErrorCode::LimitExceeded,"redirect_depth","Redirect hop budget exceeded"));}
            let targets=self.select(target)?.ok_or_else(||invalid("redirect_missing",format!("Missing redirect target {target}")))?;
            path.push((ordinal,target.into()));
            for &next in targets {self.walk(origin,next,path,out,visits,bytes,job)?;}path.pop();
        }else{
            if out.len()>=self.limits.dictionary.max_result_entries {return Err(budget("Resolved result count exceeded"));}
            let mut added=sum(row.key.len(),row.text.len())?;
            for (from,target) in path.iter() {added=sum(added,sum(self.rows[*from].key.len(),target.len())?)?;}
            *bytes=sum(*bytes,added)?;if *bytes>self.limits.dictionary.max_result_bytes {return Err(budget("Resolved result bytes exceeded"));}
            let chain=path.iter().map(|(from,target)|RedirectHop {ordinal:*from,key:self.rows[*from].key.clone(),target:target.clone()}).collect();
            out.push(Resolution {source_ordinal:origin,terminal_ordinal:ordinal,entry:row.clone(),chain});
        }Ok(())
    }
}
fn redirect(text:&str)->Result<Option<&str>> {
    let Some(target)=text.strip_prefix("@@@LINK=") else {return Ok(None);};
    let target=target.strip_suffix("\r\n").or_else(||target.strip_suffix('\n')).unwrap_or(target);
    if target.is_empty()||target.contains(['\r','\n','\0']) {return Err(invalid("redirect_target","Redirect must contain one nonempty target with at most one final line ending"));}
    Ok(Some(target))
}
