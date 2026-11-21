//! File-based dictionary jobs. Only qualified Studio outputs are reopened.
use crate::{Error,ErrorCode,JobContext,Limits,Stage};
use serde::{Deserialize,Serialize};
use std::{fs::{self,File},io::Read,path::{Path,PathBuf}};

#[derive(Debug,Serialize,Deserialize)]
#[serde(tag="operation",rename_all="snake_case",deny_unknown_fields)]
pub enum Request {
    PackMdx {source:PathBuf,destination:PathBuf,title:String,description:String,encoding:studio_core::Encoding,profile:studio_core::TxtProfile},
    ExportMdx {source:PathBuf,destination:PathBuf,profile:studio_core::TxtProfile},
    PackMdd {manifest:PathBuf,destination:PathBuf},
    ExtractMdd {source:PathBuf,destination:PathBuf},
}
impl Request {
    pub fn operation(&self)->&'static str {match self {Self::PackMdx {..}=>"pack_mdx",Self::ExportMdx {..}=>"export_mdx",Self::PackMdd {..}=>"pack_mdd",Self::ExtractMdd {..}=>"extract_mdd"}}
    pub fn destination(&self)->&Path {match self {Self::PackMdx {destination,..}|Self::ExportMdx {destination,..}|Self::PackMdd {destination,..}|Self::ExtractMdd {destination,..}=>destination}}
    pub(crate) fn metadata_valid(&self)->bool {
        let source=match self {Self::PackMdx {source,..}|Self::ExportMdx {source,..}|Self::ExtractMdd {source,..}=>source,Self::PackMdd {manifest,..}=>manifest};
        if source.as_os_str().len()>8192||self.destination().as_os_str().len()>8192 {return false;}
        if let Self::PackMdx {title,description,..}=self {if title.len().saturating_add(description.len())>65536 {return false;}}
        true
    }
}
#[derive(Clone,Debug,Serialize)]
#[serde(tag="operation",rename_all="snake_case")]
pub enum Output {
    PackMdx {destination:PathBuf,entries:usize,file_bytes:u64,policy:String},
    ExportMdx {destination:PathBuf,entries:usize,file_bytes:usize,profile:studio_core::TxtProfile},
    PackMdd {destination:PathBuf,resources:usize,file_bytes:u64,policy:String},
    ExtractMdd {destination:PathBuf,resources:usize,payload_bytes:usize},
}
#[derive(Debug,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
pub struct ResourceInput {pub key:String,pub source:PathBuf}
#[derive(Debug,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
pub struct ResourceManifest {pub title:String,pub description:String,pub resources:Vec<ResourceInput>}
fn limit(message:&str)->Error {Error::new(ErrorCode::LimitExceeded,message)}
fn bounded(path:&Path,cap:u64,job:&JobContext<'_>)->crate::Result<Vec<u8>> {
    job.check()?;let file=File::open(path)?;let metadata=file.metadata()?;
    if !metadata.is_file() {return Err(Error::new(ErrorCode::InvalidInput,"Expected a regular input file"));}
    if metadata.len()>cap {return Err(limit("Dictionary job input exceeds its byte budget"));}
    let count=cap.checked_add(1).ok_or_else(||limit("Invalid input byte cap"))?;let mut bytes=Vec::new();file.take(count).read_to_end(&mut bytes)?;
    if bytes.len() as u64>cap {return Err(limit("Dictionary job input grew beyond its byte budget"));}job.check()?;Ok(bytes)
}
fn resources(path:&Path,limits:&Limits,job:&mut JobContext<'_>)->crate::Result<studio_core::ResourcePackRequest> {
    job.forward(Stage::Converting,"reading_manifest",0,1);job.check()?;
    let bytes=bounded(path,131072.min(limits.dictionary.max_file_bytes),job)?;
    let manifest:ResourceManifest=serde_json::from_slice(&bytes).map_err(|e|Error::new(ErrorCode::InvalidInput,format!("Invalid resource manifest: {e}")))?;
    if manifest.resources.len()>limits.dictionary.max_entries {return Err(limit("Resource manifest count exceeds budget"));}
    let parent=path.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new("."));
    let mut out=Vec::new();let mut decoded=0usize;let total=manifest.resources.len();
    for (i,input) in manifest.resources.into_iter().enumerate() {
        job.forward(Stage::Converting,"reading_resources",i,total);job.check()?;
        studio_core::resource_relative_path(&input.key)?;
        if input.key.len()>limits.dictionary.max_key_bytes||input.source.as_os_str().len()>8192 {return Err(limit("Resource key/path exceeds budget"));}
        let source=if input.source.is_absolute() {input.source}else{parent.join(input.source)};
        let remaining=limits.dictionary.max_decoded_bytes.checked_sub(decoded).and_then(|n|n.checked_sub(input.key.len())).ok_or_else(||limit("Resource decoded budget exceeded"))?;
        let bytes=bounded(&source,limits.dictionary.max_entry_bytes.min(remaining) as u64,job)?;
        decoded=decoded.checked_add(input.key.len()).and_then(|n|n.checked_add(bytes.len())).ok_or_else(||limit("Resource size overflow"))?;
        out.push(studio_core::Resource {key:input.key,bytes});
    }
    job.check()?;Ok(studio_core::ResourcePackRequest {title:manifest.title,description:manifest.description,resources:out})
}
pub fn execute(request:&Request,limits:&Limits,job:&mut JobContext<'_>)->crate::Result<Output> {
    job.check()?;
    if !request.metadata_valid() {return Err(Error::new(ErrorCode::InvalidInput,"Dictionary request metadata exceeds limits"));}
    match fs::symlink_metadata(request.destination()) {
        Ok(_)=>return Err(Error::new(ErrorCode::DestinationExists,"Dictionary job destination already exists")),
        Err(e) if e.kind()==std::io::ErrorKind::NotFound=>{},Err(e)=>return Err(e.into()),
    }
    let destination=request.destination().to_owned();
    match request {
        Request::PackMdx {source,title,description,encoding,profile,..}=>{
            let token=job.cancellation.clone();
            let entries={let mut progress=|p:studio_core::Progress|job.forward(Stage::Converting,crate::job::core_phase(p.phase),p.completed,p.total);
                studio_core::read_txt(source,*profile,&limits.dictionary,&mut studio_core::JobContext::new(&token,&mut progress))?};
            let pack=studio_core::PackRequest {title:title.clone(),description:description.clone(),encoding:*encoding,entries};
            let mut progress=|p:studio_core::Progress|job.forward(Stage::Publishing,crate::job::core_phase(p.phase),p.completed,p.total);
            let result=studio_core::pack_mdx(&pack,&destination,&limits.dictionary,&mut studio_core::JobContext::new(&token,&mut progress))?;
            Ok(Output::PackMdx {destination,entries:result.entries,file_bytes:result.file_bytes,policy:result.policy.into()})
        },
        Request::ExportMdx {source,profile,..}=>{
            let token=job.cancellation.clone();
            let dictionary={let mut progress=|p:studio_core::Progress|job.forward(Stage::Converting,crate::job::core_phase(p.phase),p.completed,p.total);
                studio_core::Dictionary::open_studio_output(source,&limits.dictionary,&mut studio_core::JobContext::new(&token,&mut progress))?};
            let mut progress=|p:studio_core::Progress|job.forward(Stage::Publishing,crate::job::core_phase(p.phase),p.completed,p.total);
            let result=dictionary.export_txt(&destination,*profile,&mut studio_core::JobContext::new(&token,&mut progress))?;
            Ok(Output::ExportMdx {destination,entries:result.entries,file_bytes:result.file_bytes,profile:*profile})
        },
        Request::PackMdd {manifest,..}=>{
            let pack=resources(manifest,limits,job)?;let token=job.cancellation.clone();
            let mut progress=|p:studio_core::Progress|job.forward(Stage::Publishing,crate::job::core_phase(p.phase),p.completed,p.total);
            let result=studio_core::pack_mdd(&pack,&destination,&limits.dictionary,&mut studio_core::JobContext::new(&token,&mut progress))?;
            Ok(Output::PackMdd {destination,resources:result.entries,file_bytes:result.file_bytes,policy:result.policy.into()})
        },
        Request::ExtractMdd {source,..}=>{
            let token=job.cancellation.clone();
            let archive={let mut progress=|p:studio_core::Progress|job.forward(Stage::Converting,crate::job::core_phase(p.phase),p.completed,p.total);
                studio_core::ResourceArchive::open_studio_output(source,&limits.dictionary,&mut studio_core::JobContext::new(&token,&mut progress))?};
            let mut progress=|p:studio_core::Progress|job.forward(Stage::Publishing,crate::job::core_phase(p.phase),p.completed,p.total);
            let result=archive.extract(&destination,&mut studio_core::JobContext::new(&token,&mut progress))?;
            Ok(Output::ExtractMdd {destination,resources:result.resources,payload_bytes:result.payload_bytes})
        },
    }
}
