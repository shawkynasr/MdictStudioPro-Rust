//! Emit bounded v2 blocks to private files, never a whole dictionary buffer.
use super::*;
use studio_core::Encoding;
const KEY_TARGET:usize=16*1024;
const RECORD_TARGET:usize=64*1024;
const MAX_BLOCKS:usize=8192;
const MAX_INFO:usize=16*1024*1024;
fn encode(s:&str,encoding:Encoding)->Vec<u8> {match encoding {Encoding::Utf8=>s.as_bytes().to_vec(),Encoding::Utf16=>s.encode_utf16().flat_map(u16::to_le_bytes).collect()}}
fn units(encoding:Encoding)->usize {match encoding {Encoding::Utf8=>1,Encoding::Utf16=>2}}
fn envelope(data:&[u8])->Vec<u8> {let mut out=Vec::with_capacity(data.len()+8);out.extend_from_slice(&2u32.to_le_bytes());out.extend_from_slice(&adler(data).to_be_bytes());out.extend_from_slice(&miniz_oxide::deflate::compress_to_vec_zlib(data,6));out}
struct Blocks {file:tempfile::NamedTempFile,info:Vec<u8>,count:usize,bytes:u64}
impl Blocks {
 fn new()->Result<Self> {Ok(Self {file:tempfile::NamedTempFile::new()?,info:Vec::new(),count:0,bytes:0})}
 fn append(&mut self,raw:&[u8],prefix:&[u8],limits:&IoLimits,job:&mut ImportJob<'_>)->Result<()> {
  job.tick("block_compress",self.count,MAX_BLOCKS)?;
  if self.count>=MAX_BLOCKS||self.info.len().checked_add(prefix.len()+16).is_none_or(|n|n>MAX_INFO) {return Err(budget("Block count or index cap exceeded"));}
  if raw.len()>8*1024*1024 {return Err(budget("Decompressed block cap exceeded"));}
  let packed=envelope(raw);if packed.len()>8*1024*1024||self.bytes+packed.len() as u64>limits.max_output_bytes {return Err(budget("Compressed block spool cap exceeded"));}
  self.file.write_all(&packed)?;self.info.extend_from_slice(prefix);self.info.extend_from_slice(&(packed.len() as u64).to_be_bytes());self.info.extend_from_slice(&(raw.len() as u64).to_be_bytes());self.count+=1;self.bytes+=packed.len() as u64;Ok(())
 }
}
fn summary(out:&mut Vec<u8>,raw:&[u8],unit:usize)->Result<()> {let n=u16::try_from(raw.len()/unit).map_err(|_|budget("Summary encoding units exceed u16"))?;out.extend_from_slice(&n.to_be_bytes());out.extend_from_slice(raw);out.resize(out.len()+unit,0);Ok(())}
fn key_prefix(count:usize,first:&[u8],last:&[u8],unit:usize)->Result<Vec<u8>> {let mut prefix=(count as u64).to_be_bytes().to_vec();summary(&mut prefix,first,unit)?;summary(&mut prefix,last,unit)?;Ok(prefix)}
fn copy(source:&mut tempfile::NamedTempFile,out:&mut Output<'_>,job:&mut ImportJob<'_>)->Result<()> {
 source.flush()?;source.seek(SeekFrom::Start(0))?;let mut b=[0;65536];loop {job.check()?;let n=source.read(&mut b)?;if n==0 {break;}out.write_all(&b[..n])?;}Ok(())
}
pub(super) fn write_mdx(spool:&mut tempfile::NamedTempFile,rows:&[Descriptor],encoding:Encoding,raw:&mut File,limits:&IoLimits,job:&mut ImportJob<'_>,expected:&mut Digest)->Result<()> {
 let unit=units(encoding);let mut keys=Blocks::new()?;let mut records=Blocks::new()?;let mut kb=Vec::with_capacity(KEY_TARGET);let mut rb=Vec::with_capacity(RECORD_TARGET);let mut first=Vec::new();let mut last=Vec::new();let mut key_count=0usize;let mut offset=0u64;
 for(i,row)in rows.iter().enumerate() {
  job.tick("block_entries",i,rows.len())?;let bytes=payload(spool,row)?;let text=std::str::from_utf8(&bytes).map_err(|_|integrity("Spool UTF-8 changed"))?;expected.row(&row.key,&bytes);
  let key=encode(&row.key,encoding);let mut body=encode(text,encoding);body.resize(body.len()+unit,0);let row_size=8+key.len()+unit;
  if !kb.is_empty()&&kb.len()+row_size>KEY_TARGET {let prefix=key_prefix(key_count,&first,&last,unit)?;keys.append(&kb,&prefix,limits,job)?;kb.clear();key_count=0;}
  if !rb.is_empty()&&rb.len()+body.len()>RECORD_TARGET {records.append(&rb,&[],limits,job)?;rb.clear();}
  if key_count==0 {first=key.clone();}last=key.clone();kb.extend_from_slice(&offset.to_be_bytes());kb.extend_from_slice(&key);kb.resize(kb.len()+unit,0);key_count+=1;
  rb.extend_from_slice(&body);offset=offset.checked_add(body.len() as u64).ok_or_else(||budget("Record stream offset overflow"))?;
 }
 if !kb.is_empty() {keys.append(&kb,&key_prefix(key_count,&first,&last,unit)?,limits,job)?;}
 if !rb.is_empty() {records.append(&rb,&[],limits,job)?;}
 drop(kb);drop(rb);drop(first);drop(last);
 let attrs:BTreeMap<String,String>=[("GeneratedByEngineVersion","2.0"),("RequiredEngineVersion","2.0"),("Encrypted","No"),("Encoding",match encoding {Encoding::Utf8=>"UTF-8",Encoding::Utf16=>"UTF-16"}),("Format","Html"),("Compact","No"),("Compat","Yes"),("StyleSheet",""),("KeyCaseSensitive","No"),("StripKey","No")].into_iter().map(|(k,v)|(k.into(),v.into())).collect();
 let xml=serialize(FileKind::Mdx,&attrs)?;let info=envelope(&keys.info);if info.len()>8*1024*1024 {return Err(budget("Compressed key index cap exceeded"));}let total=xml.len() as u64+8+44+info.len() as u64+keys.bytes+32+records.info.len() as u64+records.bytes;
 if total>limits.max_output_bytes {return Err(budget("Encoded dictionary exceeds output cap"));}
 job.tick("assemble_dictionary",0,1)?;let mut out=Output {file:raw,bytes:0,cap:limits.max_output_bytes,exceeded:false};
 out.write_all(&(xml.len() as u32).to_be_bytes())?;out.write_all(&xml)?;out.write_all(&adler(&xml).to_le_bytes())?;
 let mut header=Vec::with_capacity(40);for n in [keys.count as u64,rows.len() as u64,keys.info.len() as u64,info.len() as u64,keys.bytes] {header.extend_from_slice(&n.to_be_bytes());}
 out.write_all(&header)?;out.write_all(&adler(&header).to_be_bytes())?;out.write_all(&info)?;copy(&mut keys.file,&mut out,job)?;
 for n in [records.count as u64,rows.len() as u64,records.info.len() as u64,records.bytes] {out.write_all(&n.to_be_bytes())?;}
 out.write_all(&records.info)?;copy(&mut records.file,&mut out,job)?;out.flush()?;
 if out.bytes!=total {return Err(integrity("Assembled dictionary extent differs"));}Ok(())
}
