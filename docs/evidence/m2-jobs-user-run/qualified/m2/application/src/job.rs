use crate::{Error,ErrorCode,Result};
use serde::Serialize;
pub use studio_core::CancellationToken;

#[derive(Clone,Copy,Debug,PartialEq,Eq,Serialize)]
#[serde(rename_all="snake_case")]
pub enum Stage {ReadingWorkbook,Converting,ValidatingOutput,Publishing}
#[derive(Clone,Debug,Serialize)]
pub struct Progress {
    pub job_id:String,pub stage:Stage,pub phase:String,pub completed:usize,pub total:usize,
}
/// One synchronous job. Counters are local to each stage/phase, not a global
/// percentage. A caller may run this on its own worker and cancel from a clone.
pub struct JobContext<'a> {
    pub(crate) job_id:&'a str,pub(crate) cancellation:&'a CancellationToken,
    pub(crate) progress:&'a mut dyn FnMut(Progress),
}
impl<'a> JobContext<'a> {
    pub fn new(job_id:&'a str,cancellation:&'a CancellationToken,progress:&'a mut dyn FnMut(Progress))->Self {Self {job_id,cancellation,progress}}
    pub(crate) fn check(&self)->Result<()> {
        if self.job_id.is_empty()||self.job_id.len()>256 {return Err(Error::new(ErrorCode::InvalidInput,"Job ID must contain 1..256 UTF-8 bytes"));}
        if self.cancellation.is_cancelled() {Err(Error::new(ErrorCode::Cancelled,"Job cancelled before commit"))}else{Ok(())}
    }
    pub(crate) fn forward(&mut self,stage:Stage,phase:&str,completed:usize,total:usize) {
        (self.progress)(Progress {job_id:self.job_id.into(),stage,phase:phase.into(),completed,total});
    }
}
pub(crate) fn core_phase(phase:studio_core::Phase)->&'static str {
    use studio_core::Phase as P;
    match phase {P::Preparing=>"preparing",P::Writing=>"writing",P::Verifying=>"verifying",P::Indexing=>"indexing",
        P::Extracting=>"extracting",P::Parsing=>"parsing",P::Converting=>"converting",P::Published=>"published"}
}
