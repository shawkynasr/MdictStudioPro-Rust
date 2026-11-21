use crate::{Header,Kind,Limits,ImportJob,Resource,Result,budget,integrity,key,sum};
use mdictlib::{MddFile,OpenOptions,ChecksumPolicy};
use std::{collections::BTreeMap,path::Path};
pub struct ResourceArchive {header:Header,rows:Vec<Resource>,exact:BTreeMap<String,Vec<usize>>,limits:Limits}
impl ResourceArchive {
    pub fn open_v2(path:&Path,limits:&Limits,job:&mut ImportJob<'_>)->Result<Self> {
        let (snapshot,header)=crate::header::snapshot(path,Kind::Mdd,limits,job)?;
        let file=MddFile::open_with_options(snapshot.path(),&OpenOptions::new().with_checksum_policy(ChecksumPolicy::Verify))?;
        let declared=usize::try_from(file.len()).map_err(|_|budget("Resource count overflow"))?;
        if declared>limits.dictionary.max_entries {return Err(budget("Import resource count exceeded"));}
        let mut out=Self {header,rows:Vec::new(),exact:BTreeMap::new(),limits:limits.clone()};let mut bytes=0;
        for physical in file.keys() {
            job.tick("indexing",out.rows.len(),declared)?;let physical=physical?;key(physical.key(),limits)?;
            let value=file.resource_at(physical.ordinal())?.ok_or_else(||integrity("Missing physical MDD resource"))?;
            if value.bytes().len()>limits.dictionary.max_entry_bytes {return Err(budget("Import resource payload exceeded"));}
            bytes=sum(bytes,sum(physical.key().len(),value.bytes().len())?)?;
            if bytes>limits.dictionary.max_decoded_bytes||out.rows.len()>=limits.dictionary.max_entries {return Err(budget("Import resource decoded budget exceeded"));}
            let ordinal=out.rows.len();out.exact.entry(physical.key().into()).or_default().push(ordinal);
            out.rows.push(Resource {key:physical.key().into(),bytes:value.bytes().into()});
        }
        if out.rows.len()!=declared {return Err(integrity("Incomplete physical MDD scan"));}
        job.tick("indexing",declared,declared)?;Ok(out)
    }
    pub fn header(&self)->&Header {&self.header}
    pub fn resources(&self)->&[Resource] {&self.rows}
    pub fn lookup(&self,query:&str,job:&mut ImportJob<'_>)->Result<Vec<Resource>> {
        job.check()?;key(query,&self.limits)?;let Some(found)=self.exact.get(query) else {return Ok(Vec::new());};
        if found.len()>self.limits.dictionary.max_result_entries {return Err(budget("Resource result count exceeded"));}
        let mut bytes=0;for &ordinal in found {job.check()?;let row=&self.rows[ordinal];bytes=sum(bytes,sum(row.key.len(),row.bytes.len())?)?;if bytes>self.limits.dictionary.max_result_bytes {return Err(budget("Resource result bytes exceeded"));}}
        let mut out=Vec::new();for &ordinal in found {job.check()?;out.push(self.rows[ordinal].clone());}Ok(out)
    }
}
