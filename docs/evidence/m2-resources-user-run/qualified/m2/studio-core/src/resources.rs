use crate::{casing::Casing,resource_paths::{plan,PlannedPath},safe_fs,
    CancellationToken,Error,ErrorCode,ExtractionSummary,JobContext,Limits,PackSummary,Phase,
    Resource,ResourcePackRequest,Result,POLICY_SHA256,RESOURCE_POLICY_ID};
use mdictlib::{ChecksumPolicy,LegacySort,MddBuilder,MddFile,OpenOptions,WriteOptions};
use std::{collections::BTreeMap,fs,path::Path};

fn limit(message:&str)->Error { Error::new(ErrorCode::LimitExceeded,message) }
fn sum(left:usize,right:usize)->Result<usize> { left.checked_add(right).ok_or_else(||limit("Resource byte counter overflow")) }
fn casing()->Result<Casing> { Casing::pinned16().map_err(|e|Error::new(ErrorCode::Internal,e.to_string())) }
fn cancelled(token:&CancellationToken)->Result<()> {
    if token.is_cancelled() { Err(Error::new(ErrorCode::Cancelled,"Resource lookup cancelled")) } else { Ok(()) }
}
fn metadata(request:&ResourcePackRequest,limits:&Limits)->Result<()> {
    if sum(request.title.len(),request.description.len())?>limits.max_metadata_bytes { return Err(limit("Metadata byte budget exceeded")); }
    if [&request.title,&request.description].iter().any(|text|text.chars().any(|c|c.is_control()||matches!(c,'\u{fffe}'|'\u{ffff}'))) {
        return Err(Error::new(ErrorCode::InvalidInput,"Resource metadata must be single-line without control characters"));
    }
    Ok(())
}

/// Owned resource index for bounded, versioned Studio MDD output. Arbitrary
/// foreign archives and hard pre-decompression memory caps are not implemented.
pub struct ResourceArchive {
    rows:Vec<Resource>, paths:Vec<PlannedPath>, exact:BTreeMap<String,usize>,
    limits:Limits, title:String, description:String,
}
impl ResourceArchive {
    pub fn open_studio_output(path:&Path,limits:&Limits,job:&mut JobContext<'_>)->Result<Self> {
        Self::open(path,limits,job,Phase::Indexing)
    }
    fn open(path:&Path,limits:&Limits,job:&mut JobContext<'_>,phase:Phase)->Result<Self> {
        job.checkpoint(phase,0,0)?;
        if fs::metadata(path)?.len()>limits.max_file_bytes { return Err(limit("MDD file byte budget exceeded")); }
        let options=OpenOptions::new().with_checksum_policy(ChecksumPolicy::Verify);
        let file=MddFile::open_with_options(path,&options)?;
        let attrs:BTreeMap<String,String>=file.header().attributes().map(|(k,v)|(k.to_owned(),v.to_owned())).collect();
        for (name,expected) in [("GeneratedByEngineVersion","2.0"),("StudioResourcePolicy",RESOURCE_POLICY_ID),
            ("StudioCasingDataSha256",POLICY_SHA256),("Encoding","")] {
            if attrs.get(name).map(String::as_str)!=Some(expected) {
                return Err(Error::new(ErrorCode::UnsupportedPolicy,format!("Unsupported or missing MDD {name}")));
            }
        }
        if !["No","no","0", ""].contains(&attrs.get("Encrypted").map(String::as_str).unwrap_or("No")) {
            return Err(Error::new(ErrorCode::UnsupportedPolicy,"Encrypted MDD is outside this slice"));
        }
        let declared=usize::try_from(file.len()).map_err(|_|limit("MDD resource count overflow"))?;
        if declared==0 { return Err(Error::new(ErrorCode::InvalidInput,"Empty MDD archive")); }
        if declared>limits.max_entries { return Err(limit("MDD resource count budget exceeded")); }
        let policy=casing()?; let mut previous:Option<String>=None; let mut rows=Vec::new();
        let mut bytes=0; let mut exact=BTreeMap::new();
        for physical in file.keys() {
            job.checkpoint(phase,rows.len(),declared)?;
            let physical=physical?;
            if physical.key().len()>limits.max_key_bytes { return Err(limit("Resource key byte budget exceeded")); }
            crate::resource_relative_path(physical.key())?;
            let normalized=policy.lower(physical.key());
            if previous.as_ref().is_some_and(|old|old>&normalized) {
                return Err(Error::new(ErrorCode::Integrity,"MDD keys violate persisted sort policy"));
            }
            previous=Some(normalized);
            let value=file.resource_at(physical.ordinal())?.ok_or_else(||Error::new(ErrorCode::Integrity,"Missing resource record"))?;
            if value.bytes().len()>limits.max_entry_bytes { return Err(limit("Resource payload byte budget exceeded")); }
            bytes=sum(bytes,sum(physical.key().len(),value.bytes().len())?)?;
            if rows.len()>=limits.max_entries||bytes>limits.max_decoded_bytes { return Err(limit("Decoded resource budget exceeded")); }
            if exact.insert(physical.key().to_owned(),rows.len()).is_some() {
                return Err(Error::new(ErrorCode::PathCollision,"Duplicate resource key"));
            }
            rows.push(Resource {key:physical.key().to_owned(),bytes:value.bytes().to_vec()});
        }
        if rows.len()!=declared { return Err(Error::new(ErrorCode::Integrity,"Incomplete MDD resource scan")); }
        let paths=plan(&rows,limits)?;
        job.checkpoint(phase,declared,declared)?;
        Ok(Self {rows,paths,exact,limits:limits.clone(),title:attrs.get("Title").cloned().unwrap_or_default(),
            description:attrs.get("Description").cloned().unwrap_or_default()})
    }
    pub fn len(&self)->usize { self.rows.len() }
    pub fn is_empty(&self)->bool { self.rows.is_empty() }
    pub fn title(&self)->&str { &self.title }
    pub fn description(&self)->&str { &self.description }
    /// Exact archive-key lookup only. Filesystem aliases are never query aliases.
    pub fn resource(&self,key:&str,token:&CancellationToken)->Result<Option<Resource>> {
        cancelled(token)?;
        if key.len()>self.limits.max_key_bytes { return Err(limit("Resource query byte budget exceeded")); }
        crate::resource_relative_path(key)?;
        let Some(index)=self.exact.get(key) else { return Ok(None); };
        let row=&self.rows[*index];
        if self.limits.max_result_entries==0 || sum(row.key.len(),row.bytes.len())?>self.limits.max_result_bytes {
            return Err(limit("Resource result budget exceeded"));
        }
        cancelled(token)?; Ok(Some(row.clone()))
    }
    pub fn extract(&self,destination:&Path,job:&mut JobContext<'_>)->Result<ExtractionSummary> {
        job.checkpoint(Phase::Preparing,0,self.rows.len())?;
        safe_fs::supported()?;
        if fs::symlink_metadata(destination).is_ok() {
            return Err(Error::new(ErrorCode::DestinationExists,"Extraction destination already exists"));
        }
        let parent=destination.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new("."));
        let stage=tempfile::Builder::new().prefix(".studio-extract-").tempdir_in(parent)?;
        safe_fs::write(stage.path(),&self.paths,&self.rows,job)?;
        job.check()?;
        safe_fs::publish(stage.path(),destination)?;
        // Publication succeeded: do not run TempDir cleanup against its old name.
        let _=stage.keep();
        job.published(self.rows.len());
        let payload_bytes=self.rows.iter().map(|r|r.bytes.len()).sum();
        Ok(ExtractionSummary {resources:self.rows.len(),payload_bytes})
    }
}

pub fn pack_mdd(request:&ResourcePackRequest,destination:&Path,limits:&Limits,job:&mut JobContext<'_>)->Result<PackSummary> {
    job.checkpoint(Phase::Preparing,0,request.resources.len())?;
    if fs::symlink_metadata(destination).is_ok() { return Err(Error::new(ErrorCode::DestinationExists,"MDD destination already exists")); }
    if request.resources.is_empty() { return Err(Error::new(ErrorCode::InvalidInput,"No resources supplied")); }
    if request.resources.len()>limits.max_entries { return Err(limit("Resource count budget exceeded")); }
    metadata(request,limits)?;
    // Preflight every path and logical collision before creating a temporary file.
    plan(&request.resources,limits)?;
    let policy=casing()?; let mut ordered=Vec::new(); let mut bytes=0;
    for (index,resource) in request.resources.iter().enumerate() {
        job.checkpoint(Phase::Preparing,index,request.resources.len())?;
        if resource.bytes.len()>limits.max_entry_bytes { return Err(limit("Resource payload byte budget exceeded")); }
        bytes=sum(bytes,sum(resource.key.len(),resource.bytes.len())?)?;
        if bytes>limits.max_decoded_bytes { return Err(limit("Decoded resource input budget exceeded")); }
        ordered.push((policy.lower(&resource.key),resource));
    }
    ordered.sort_by(|a,b|a.0.cmp(&b.0));
    let mut builder=MddBuilder::with_options(WriteOptions::new().with_legacy_sort(LegacySort::PreserveInput)
        .with_key_block_target_bytes(16*1024).with_record_block_target_bytes(64*1024));
    for (name,value) in [("Title",request.title.as_str()),("Description",request.description.as_str()),
        ("StudioResourcePolicy",RESOURCE_POLICY_ID),("StudioCasingDataSha256",POLICY_SHA256)] {
        builder.header_attribute(name,value)?;
    }
    for (index,(_,resource)) in ordered.iter().enumerate() {
        job.checkpoint(Phase::Writing,index,ordered.len())?;
        builder.add_resource(&resource.key,&resource.bytes)?;
    }
    let parent=destination.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new("."));
    let mut temporary=tempfile::NamedTempFile::new_in(parent)?;
    builder.finish(temporary.as_file_mut())?; temporary.as_file().sync_all()?;
    let file_bytes=temporary.as_file().metadata()?.len();
    if file_bytes>limits.max_file_bytes { return Err(limit("MDD output file byte budget exceeded")); }
    let verified=ResourceArchive::open(temporary.path(),limits,job,Phase::Verifying)?;
    if verified.rows.len()!=ordered.len() || verified.rows.iter().zip(&ordered).any(|(a,(_,b))|a!=*b)
        || verified.title!=request.title || verified.description!=request.description {
        return Err(Error::new(ErrorCode::Integrity,"Verified MDD bytes, keys or metadata differ"));
    }
    job.check()?;
    temporary.persist_noclobber(destination).map_err(|e|Error::from(e.error))?;
    job.published(ordered.len());
    Ok(PackSummary {entries:ordered.len(),file_bytes,policy:RESOURCE_POLICY_ID})
}
