//! Whole-headword glob matching over Unicode scalar values, without recursion.
use super::{error,Job,Result};
#[derive(Clone,Copy,Debug,PartialEq,Eq)]enum Token {Literal(char),One,Any}
pub(super) struct Pattern {tokens:Vec<Token>}
pub(super) struct Work {steps:usize,cap:usize}
impl Work {
 pub(super) fn new()->Self {Self {steps:0,cap:50_000_000}}
 fn step(&mut self,job:&Job<'_>)->Result<()> {
  if self.steps>=self.cap{return Err(error("limit_exceeded","Wildcard matching work budget exceeded"));}
  self.steps+=1;if self.steps%1024==0{job.check()?;}Ok(())
 }
}
impl Pattern {
 pub(super) fn compile(input:&str)->Result<Self> {
  let mut chars=input.chars();let mut tokens=Vec::new();
  while let Some(c)=chars.next() {
   let token=match c {
    '*'=>Token::Any,'?'=>Token::One,
    '\\'=>match chars.next(){Some(c @ ('*'|'?'|'\\'))=>Token::Literal(c),_=>return Err(error("invalid_input","Escape only ?, * or backslash; an escape needs a following character"))},
    c=>Token::Literal(c),
   };
   if token!=Token::Any || tokens.last()!=Some(&Token::Any){tokens.push(token);}
  }
  Ok(Self {tokens})
 }
 pub(super) fn matches(&self,text:&str,work:&mut Work,job:&Job<'_>)->Result<bool> {
  let chars:Vec<char>=text.chars().collect();let (mut p,mut t,mut retry)=(0,0,0);let mut star=None;
  while t<chars.len() {
   work.step(job)?;
   match self.tokens.get(p) {
    Some(Token::One)=>{p+=1;t+=1;},
    Some(Token::Literal(c)) if *c==chars[t]=>{p+=1;t+=1;},
    Some(Token::Any)=>{star=Some(p);p+=1;retry=t;},
    _=>if let Some(s)=star {retry+=1;t=retry;p=s+1;}else{return Ok(false);},
   }
  }
  while self.tokens.get(p)==Some(&Token::Any){work.step(job)?;p+=1;}
  Ok(p==self.tokens.len())
 }
}

#[cfg(test)]mod tests {
 use super::*;
 use crate::CancellationToken;
 #[test]fn glob_matches_reference_dynamic_program_exhaustively() {
  fn words(alphabet:&[char],max:usize)->Vec<String>{let mut all=vec![String::new()];let mut layer=vec![String::new()];for _ in 0..max{layer=layer.iter().flat_map(|s|alphabet.iter().map(move|c|format!("{s}{c}"))).collect();all.extend(layer.clone());}all}
  fn reference(pattern:&[char],text:&[char])->bool {
   let mut previous=vec![false;text.len()+1];previous[0]=true;
   for &p in pattern {let mut next=vec![false;text.len()+1];if p=='*'{next[0]=previous[0];}for i in 1..=text.len(){next[i]=if p=='*'{previous[i]||next[i-1]}else{previous[i-1]&&(p=='?'||p==text[i-1])};}previous=next;}previous[text.len()]
  }
  let token=CancellationToken::default();let mut noop=|_|{};let job=Job::new(&token,&mut noop);
  for input in words(&['a','字','?','*'],4) {let pattern=Pattern::compile(&input).unwrap();for text in words(&['a','字'],4){assert_eq!(pattern.matches(&text,&mut Work::new(),&job).unwrap(),reference(&input.chars().collect::<Vec<_>>(),&text.chars().collect::<Vec<_>>()),"{input:?} {text:?}");}}
 }
 #[test]fn escapes_unicode_scalars_and_bounded_work_are_explicit() {
  let token=CancellationToken::default();let mut noop=|_|{};let job=Job::new(&token,&mut noop);
  for (p,t,expected) in [(r"a\?b","a?b",true),(r"a\*b","a*b",true),(r"a\\b",r"a\b",true),("?","𐐀",true),("?","i\u{307}",false),("??","i\u{307}",true),("a%b","axxb",false),("a_b","a_b",true),("a?b","ab",false),("*","",true),("a*?b","a字b",true)] {assert_eq!(Pattern::compile(p).unwrap().matches(t,&mut Work::new(),&job).unwrap(),expected);}
  for p in ["x\\",r"\a"] {assert!(Pattern::compile(p).is_err());}
  let mut budget=Work {steps:0,cap:2};assert_eq!(Pattern::compile("*z").unwrap().matches("aaaa",&mut budget,&job).unwrap_err().code,"limit_exceeded");
  token.cancel();let mut budget=Work {steps:1023,cap:5000};assert_eq!(Pattern::compile("*").unwrap().matches("abc",&mut budget,&job).unwrap_err().code,"cancelled");
 }
}
