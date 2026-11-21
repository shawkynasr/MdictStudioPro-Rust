//! Shared native conversion facade. Existing qualified crates remain unchanged.
//! Synchronous API only: a UI owns worker execution and callback delivery.
mod error;
mod job;
pub use error::{Error,ErrorCode,Result};
pub use job::{JobContext,CancellationToken,Stage,Progress};
pub use studio_core::{Entry,TxtProfile};
pub use studio_xlsx::Table;
use serde::{Deserialize,Serialize};
use std::path::{Path,PathBuf};
use studio_xlsx::moe;

#[derive(Clone,Copy,Debug,PartialEq,Eq,Serialize,Deserialize)]
#[serde(rename_all="snake_case")]
pub enum ConverterId {CcCedict,MoeRevised,MoeRevisedWfg,MoeConcise,MoeIdioms,MoeMini}
impl ConverterId {
    fn moe(self)->Option<moe::Converter> {Some(match self {
        Self::CcCedict=>return None,Self::MoeRevised=>moe::Converter::Revised,Self::MoeRevisedWfg=>moe::Converter::Wfg,
        Self::MoeConcise=>moe::Converter::Concise,Self::MoeIdioms=>moe::Converter::Idioms,Self::MoeMini=>moe::Converter::Mini,
    })}
}
#[derive(Clone,Debug,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
pub struct ConversionRequest {pub converter:ConverterId,pub input:PathBuf,pub worksheet:Option<String>}
#[derive(Clone,Debug,Deserialize,Serialize)]
#[serde(deny_unknown_fields)]
pub struct PublishRequest {pub conversion:ConversionRequest,pub destination:PathBuf}
#[derive(Clone,Debug,Default)]
pub struct Limits {
    pub dictionary:studio_core::Limits,pub workbook:studio_xlsx::Limits,pub moe:moe::Limits,
}
#[derive(Debug,Serialize)]
pub struct Metrics {
    pub primary_entries:usize,pub alias_redirects:usize,pub traditional_entries:usize,
    pub skipped_rows_or_lines:usize,
}
#[derive(Debug,Serialize)]
pub struct Conversion {
    pub converter:ConverterId,pub txt_profile:TxtProfile,pub entries:Vec<Entry>,
    pub metrics:Metrics,pub comments:Vec<String>,
}
#[derive(Debug,Serialize)]
pub struct Published {
    pub converter:ConverterId,pub txt_profile:TxtProfile,pub entries:usize,
    pub file_bytes:usize,pub metrics:Metrics,pub comments:Vec<String>,
}

pub fn read_workbook(input:&Path,worksheet:Option<&str>,limits:&Limits,job:&mut JobContext<'_>)->Result<Table> {
    job.check()?;
    let token=job.cancellation.clone();let cancelled=||token.is_cancelled();
    let mut progress=|p:studio_xlsx::Progress|job.forward(Stage::ReadingWorkbook,p.phase,p.completed,p.total);
    studio_xlsx::read_xlsx(input,worksheet,&limits.workbook,&mut studio_xlsx::ReadControl::new(&cancelled,&mut progress)).map_err(Error::from)
}

/// Returns all entries or an error. Common canonical TXT validation runs before
/// success, so callers cannot receive a result that the same limits cannot export.
pub fn convert(request:&ConversionRequest,limits:&Limits,job:&mut JobContext<'_>)->Result<Conversion> {
    job.check()?;
    let result=if let Some(kind)=request.converter.moe() {
        let table=read_workbook(&request.input,request.worksheet.as_deref(),limits,job)?;
        job.check()?;
        let token=job.cancellation.clone();let cancelled=||token.is_cancelled();
        let mut progress=|p:studio_xlsx::Progress|job.forward(Stage::Converting,p.phase,p.completed,p.total);
        let mut moe_limits=limits.moe.clone();
        moe_limits.max_entries=moe_limits.max_entries.min(limits.dictionary.max_entries);
        moe_limits.max_key_bytes=moe_limits.max_key_bytes.min(limits.dictionary.max_key_bytes);
        moe_limits.max_entry_bytes=moe_limits.max_entry_bytes.min(limits.dictionary.max_entry_bytes);
        moe_limits.max_output_bytes=moe_limits.max_output_bytes.min(limits.dictionary.max_decoded_bytes);
        let result=moe::convert(&table,kind,&moe_limits,&mut studio_xlsx::ReadControl::new(&cancelled,&mut progress))?;
        Conversion {converter:request.converter,txt_profile:TxtProfile::CanonicalV1,
            entries:result.entries.into_iter().map(|e|Entry {key:e.key,text:e.text}).collect(),
            metrics:Metrics {primary_entries:result.primary_entries,alias_redirects:result.alias_redirects,traditional_entries:0,skipped_rows_or_lines:result.skipped_rows},comments:Vec::new()}
    }else{
        if request.worksheet.is_some() {return Err(Error::new(ErrorCode::InvalidInput,"CC-CEDICT input does not accept a worksheet selector"));}
        let token=job.cancellation.clone();
        let mut progress=|p:studio_core::Progress|job.forward(Stage::Converting,job::core_phase(p.phase),p.completed,p.total);
        let result=studio_core::convert_cedict_file(&request.input,&limits.dictionary,&mut studio_core::JobContext::new(&token,&mut progress))?;
        Conversion {converter:request.converter,txt_profile:result.txt_profile,entries:result.entries,
            metrics:Metrics {primary_entries:result.primary_entries,alias_redirects:0,traditional_entries:result.traditional_entries,skipped_rows_or_lines:result.skipped_lines},comments:result.comments}
    };
    job.check()?;
    let token=job.cancellation.clone();
    let mut progress=|p:studio_core::Progress|job.forward(Stage::ValidatingOutput,job::core_phase(p.phase),p.completed,p.total);
    // This allocates bounded canonical bytes and discards them. Publication
    // renders again through the existing verified no-clobber writer.
    studio_core::render_txt(&result.entries,result.txt_profile,&limits.dictionary,&mut studio_core::JobContext::new(&token,&mut progress))?;
    Ok(result)
}

pub fn convert_to_txt(request:&PublishRequest,limits:&Limits,job:&mut JobContext<'_>)->Result<Published> {
    job.check()?;
    match std::fs::symlink_metadata(&request.destination) {
        Ok(_)=>return Err(Error::new(ErrorCode::DestinationExists,"Text destination already exists")),
        Err(e) if e.kind()==std::io::ErrorKind::NotFound=>{},Err(e)=>return Err(e.into()),
    }
    let result=convert(&request.conversion,limits,job)?;
    job.check()?;
    let token=job.cancellation.clone();
    let mut progress=|p:studio_core::Progress|job.forward(Stage::Publishing,job::core_phase(p.phase),p.completed,p.total);
    let summary=studio_core::write_txt(&result.entries,&request.destination,result.txt_profile,&limits.dictionary,&mut studio_core::JobContext::new(&token,&mut progress))?;
    // The writer has committed. A cancellation from its published callback
    // cannot retroactively turn successful publication into an error.
    Ok(Published {converter:result.converter,txt_profile:result.txt_profile,entries:summary.entries,
        file_bytes:summary.file_bytes,metrics:result.metrics,comments:result.comments})
}

pub mod runner;
