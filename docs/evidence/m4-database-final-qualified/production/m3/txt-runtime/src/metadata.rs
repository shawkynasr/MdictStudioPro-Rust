//! Metadata-only publication using the unchanged, bounded M2 rebuild engine.
use crate::{Error,ImportJob,Result};
pub use studio_v2_import::application::metadata::{Request,Summary};
pub(crate) fn execute(r:&Request,job:&mut ImportJob<'_>)->Result<Summary> {
 studio_v2_import::application::metadata::rebuild(r,&mut studio_v2_import::ImportJob::new(job.id,job.token,&mut *job.progress))
  .map_err(|e|Error {code:e.code,detail:e.detail,message:e.message,limit:None})
}

#[cfg(test)] mod tests {
 use super::*;
 use crate::{CancellationToken,ErrorCode,Progress};
 use studio_v2_import::application::metadata::{Edits,FileKind};
 #[test] fn shared_token_cancels_copy_and_precommit_without_output() {
  for phase in ["metadata_copy","metadata_commit"] {
   let dir=tempfile::tempdir().unwrap();let source=dir.path().join("original.mdx");
   studio_core::pack_mdx(&studio_core::PackRequest {title:"original".into(),description:"".into(),encoding:studio_core::Encoding::Utf8,entries:vec![studio_core::Entry {key:"字".into(),text:"hello".into()}]},&source,&studio_core::Limits::default(),&mut studio_core::JobContext::new(&CancellationToken::default(),&mut |_|{})).unwrap();
   let before=std::fs::read(&source).unwrap();let destination=dir.path().join("edited.mdx");
   let r=Request {source:source.clone(),destination:destination.clone(),kind:FileKind::Mdx,edits:Edits {title:Some("edited".into()),..Edits::default()}};
   let token=CancellationToken::default();let stop=token.clone();let mut progress=|p:Progress|if p.phase==phase {stop.cancel();};
   assert_eq!(execute(&r,&mut ImportJob::new("metadata-cancel",&token,&mut progress)).unwrap_err().code,ErrorCode::Cancelled);
   assert!(!destination.exists());assert_eq!(std::fs::read(&source).unwrap(),before);assert_eq!(std::fs::read_dir(dir.path()).unwrap().count(),1);
  }
 }
}
