//! Bounded traversal over the actor's already-open, digest-bound index.
use super::{api,failure,ApiCode,ApiResult,CancellationToken,ErrorCode,Failure};
use serde::{Deserialize,Serialize};
use studio_indexed_engine::{Row,index::Page};

const HOPS:usize=16;
const VISITS:usize=4096;
const MATCHES:u64=256;
const RESULTS:usize=256;
const SCAN_BYTES:usize=8*1024*1024;
const REPLY_BYTES:usize=2*1024*1024;
#[derive(Clone,Debug,Deserialize)]#[serde(deny_unknown_fields)]
pub struct ResolveRequest {pub query:String,pub ordinal:u64}
impl ResolveRequest {pub(crate) fn validate(&self)->ApiResult<()> {
 if self.query.is_empty()||self.query.len()>4096||self.query.contains('\0') {return Err(api(ApiCode::InvalidInput,"Require a nonempty NUL-free redirect source key <=4 KiB"));}Ok(())
}}
#[derive(Clone,Debug,Serialize)]pub struct Hop {pub ordinal:u64,pub key:String,pub target:String}
#[derive(Debug,Serialize)]pub struct Resolution {pub row:Row,pub chain:Vec<Hop>}
#[derive(Debug,Serialize)]pub struct Reply {pub source_ordinal:u64,pub source_key:String,pub results:Vec<Resolution>,pub visits:usize}
fn invalid(detail:&'static str,message:&str)->Failure {failure(ErrorCode::InvalidInput,detail,message)}
fn limit(message:&str)->Failure {failure(ErrorCode::LimitExceeded,"redirect_limit",message)}
fn check(token:&CancellationToken)->Result<(),Failure> {if token.is_cancelled(){Err(failure(ErrorCode::Cancelled,"cancelled","Redirect resolution cancelled"))}else{Ok(())}}
fn target(text:&str)->Result<Option<&str>,Failure> {
 let Some(value)=text.strip_prefix("@@@LINK=") else {return Ok(None);};
 let value=value.strip_suffix("\r\n").or_else(||value.strip_suffix('\n')).unwrap_or(value);
 if value.is_empty()||value.len()>4096||value.contains(['\r','\n','\0']) {return Err(invalid("redirect_target","Redirect needs one nonempty target <=4 KiB with at most one final line ending"));}Ok(Some(value))
}
struct Walk<'a,F> {fetch:F,token:&'a CancellationToken,visits:usize,scanned:usize,replied:usize,results:Vec<Resolution>}
impl<F:FnMut(&str,u64,usize)->Result<Page,Failure>> Walk<'_,F> {
 fn rows(&mut self,key:&str)->Result<Vec<Row>,Failure> {
  let mut rows=Vec::new();let mut offset=0;
  loop {
   check(self.token)?;let page=(self.fetch)(key,offset,32)?;
   if page.total>MATCHES {return Err(limit("Redirect lookup exceeds 256 matches; no partial result returned"));}
   for row in page.rows {
    self.scanned=self.scanned.saturating_add(row.key.len()).saturating_add(row.text.as_ref().map_or(0,String::len));
    if self.scanned>SCAN_BYTES {return Err(limit("Redirect traversal exceeds 8 MiB cumulative decoded data"));}rows.push(row);
   }
   match page.next_offset {None=>return Ok(rows),Some(next) if next>offset=>offset=next,_=>return Err(invalid("redirect_page","Index page failed to advance"))}
  }
 }
 fn walk(&mut self,row:Row,chain:&mut Vec<Hop>)->Result<(),Failure> {
  check(self.token)?;self.visits+=1;if self.visits>VISITS {return Err(limit("Redirect traversal exceeds 4,096 visits"));}
  if chain.iter().any(|hop|hop.ordinal==row.ordinal) {return Err(invalid("redirect_cycle","Physical redirect cycle detected"));}
  let text=row.text.as_deref().ok_or_else(||invalid("redirect_kind","Redirects require an MDX reader"))?;
  if let Some(target)=target(text)? {
   if chain.len()>=HOPS {return Err(limit("Redirect chain exceeds 16 hops"));}
   let target=target.to_owned();let rows=self.rows(&target)?;
   if rows.is_empty(){return Err(invalid("redirect_missing","Redirect target has no matching entry under the reader lookup policy"));}
   chain.push(Hop {ordinal:row.ordinal,key:row.key,target});
   for row in rows {self.walk(row,chain)?;}chain.pop();
  }else{
   if self.results.len()>=RESULTS {return Err(limit("Redirect expansion exceeds 256 terminal results"));}
   self.replied=self.replied.saturating_add(row.key.len()).saturating_add(text.len());
   for hop in chain.iter(){self.replied=self.replied.saturating_add(hop.key.len()).saturating_add(hop.target.len());}
   if self.replied>REPLY_BYTES {return Err(limit("Resolved definitions and chains exceed 2 MiB"));}
   self.results.push(Resolution {row,chain:chain.clone()});
  }Ok(())
 }
}
pub(crate) fn resolve<F:FnMut(&str,u64,usize)->Result<Page,Failure>>(r:&ResolveRequest,token:&CancellationToken,fetch:F)->Result<Reply,Failure> {
 let mut w=Walk {fetch,token,visits:0,scanned:0,replied:r.query.len(),results:Vec::new()};
 let rows=w.rows(&r.query)?;
 let row=rows.into_iter().find(|row|row.ordinal==r.ordinal).ok_or_else(||invalid("redirect_source","Selected ordinal does not match the source key"))?;
 w.walk(row,&mut Vec::new())?;check(token)?;
 Ok(Reply {source_ordinal:r.ordinal,source_key:r.query.clone(),results:w.results,visits:w.visits})
}
