use crate::{Entry,Error,ErrorCode,JobContext,Limits,Phase,Result,TextSummary,TxtProfile};
use std::{fs,io::{Read,Write},path::Path};

fn error(code:ErrorCode,line:usize,message:&str)->Error { Error::new(code,format!("Line {line}: {message}")) }
fn sum(a:usize,b:usize)->Result<usize> { a.checked_add(b).ok_or_else(||Error::new(ErrorCode::LimitExceeded,"Text byte counter overflow")) }
fn key(value:&str,limits:&Limits,line:usize)->Result<()> {
    if value.is_empty()||value=="</>"||value.contains(['\0','\r','\n']) {
        return Err(error(ErrorCode::MalformedSource,line,"Expected a nonempty single-line key without NUL or delimiter"));
    }
    if value.len()>limits.max_key_bytes {return Err(error(ErrorCode::LimitExceeded,line,"Key byte budget exceeded"));}
    Ok(())
}
pub(crate) fn read_bounded(path:&Path,limits:&Limits)->Result<Vec<u8>> {
    if !fs::metadata(path)?.is_file() {return Err(Error::new(ErrorCode::InvalidInput,"Source must be a regular file"));}
    let mut file=fs::File::open(path)?;
    let info=file.metadata()?;
    if !info.is_file() {return Err(Error::new(ErrorCode::InvalidInput,"Source must be a regular file"));}
    if info.len()>limits.max_file_bytes {return Err(Error::new(ErrorCode::LimitExceeded,"Source file byte budget exceeded"));}
    let cap=limits.max_file_bytes.checked_add(1).ok_or_else(||Error::new(ErrorCode::LimitExceeded,"File budget overflow"))?;
    let mut bytes=Vec::new(); (&mut file).take(cap).read_to_end(&mut bytes)?;
    if bytes.len() as u64>limits.max_file_bytes {return Err(Error::new(ErrorCode::LimitExceeded,"Source grew beyond file byte budget"));}
    Ok(bytes)
}
fn parse(bytes:&[u8],profile:TxtProfile,limits:&Limits,job:&mut JobContext<'_>,phase:Phase)->Result<Vec<Entry>> {
    job.checkpoint(phase,0,bytes.len())?;
    if bytes.len() as u64>limits.max_file_bytes {return Err(Error::new(ErrorCode::LimitExceeded,"Source file byte budget exceeded"));}
    let source=std::str::from_utf8(bytes).map_err(|e|Error::new(ErrorCode::InvalidEncoding,format!("Strict UTF-8 decode failed at byte {}",e.valid_up_to())))?;
    let source=source.strip_prefix('\u{feff}').unwrap_or(source);
    let mut entries=Vec::new(); let mut current:Option<String>=None; let mut body=String::new();
    let mut body_lines=0; let mut decoded=0; let mut offset=0;
    for (index,raw) in source.split_inclusive('\n').enumerate() {
        let line=index+1;
        job.check()?;
        if index>=limits.max_source_lines {return Err(error(ErrorCode::LimitExceeded,line,"Source line budget exceeded"));}
        if index%256==0 {job.checkpoint(phase,offset,bytes.len())?;}
        offset=sum(offset,raw.len())?;
        let logical=raw.strip_suffix("\r\n").or_else(||raw.strip_suffix('\n')).unwrap_or(raw);
        if logical.contains('\r') {return Err(error(ErrorCode::MalformedSource,line,"Lone CR is unsupported; use LF or CRLF"));}
        if logical.contains('\0') {return Err(error(ErrorCode::MalformedSource,line,"NUL is not representable in text records"));}
        if current.is_none() {
            key(logical,limits,line)?;
            if entries.len()>=limits.max_entries {return Err(error(ErrorCode::LimitExceeded,line,"Entry count budget exceeded"));}
            current=Some(logical.to_owned());
        } else if logical=="</>" {
            if body_lines==0 {return Err(error(ErrorCode::MalformedSource,line,"Record needs at least one body line"));}
            if profile==TxtProfile::CanonicalV1 {
                // Every body preceding a standalone delimiter necessarily has LF.
                if !body.ends_with('\n') {return Err(error(ErrorCode::MalformedSource,line,"Missing body separator"));}
                body.pop();
            }
            if body.len()>limits.max_entry_bytes {return Err(error(ErrorCode::LimitExceeded,line,"Definition byte budget exceeded"));}
            let head=current.take().ok_or_else(||error(ErrorCode::Internal,line,"Missing current key"))?;
            decoded=sum(decoded,sum(head.len(),body.len())?)?;
            if decoded>limits.max_decoded_bytes {return Err(error(ErrorCode::LimitExceeded,line,"Decoded source budget exceeded"));}
            entries.push(Entry {key:head,text:std::mem::take(&mut body)}); body_lines=0;
        } else {
            let added=if profile==TxtProfile::CanonicalV1 {sum(logical.len(),if raw.ends_with('\n') {1}else{0})?} else {raw.len()};
            let next=sum(body.len(),added)?;
            let allowance=sum(limits.max_entry_bytes,if profile==TxtProfile::CanonicalV1 {1}else{0})?;
            if next>allowance {return Err(error(ErrorCode::LimitExceeded,line,"Definition byte budget exceeded"));}
            if profile==TxtProfile::CanonicalV1 {body.push_str(logical);if raw.ends_with('\n') {body.push('\n');}}
            else {body.push_str(raw);}
            body_lines+=1;
        }
    }
    if current.is_some() {return Err(Error::new(ErrorCode::MalformedSource,"Unterminated final record: missing standalone </>"));}
    if entries.is_empty() {return Err(Error::new(ErrorCode::MalformedSource,"No complete text records"));}
    job.checkpoint(phase,bytes.len(),bytes.len())?;
    Ok(entries)
}
pub fn parse_txt(bytes:&[u8],profile:TxtProfile,limits:&Limits,job:&mut JobContext<'_>)->Result<Vec<Entry>> {
    parse(bytes,profile,limits,job,Phase::Parsing)
}
pub fn read_txt(path:&Path,profile:TxtProfile,limits:&Limits,job:&mut JobContext<'_>)->Result<Vec<Entry>> {
    job.check()?;parse_txt(&read_bounded(path,limits)?,profile,limits,job)
}
fn append(bytes:&mut Vec<u8>,text:&str,limits:&Limits)->Result<()> {
    if sum(bytes.len(),text.len())? as u64>limits.max_file_bytes {return Err(Error::new(ErrorCode::LimitExceeded,"Export file byte budget exceeded"));}
    bytes.extend_from_slice(text.as_bytes());Ok(())
}
pub fn render_txt(entries:&[Entry],profile:TxtProfile,limits:&Limits,job:&mut JobContext<'_>)->Result<Vec<u8>> {
    job.checkpoint(Phase::Preparing,0,entries.len())?;
    if entries.is_empty() {return Err(Error::new(ErrorCode::InvalidInput,"No entries to export"));}
    if entries.len()>limits.max_entries {return Err(Error::new(ErrorCode::LimitExceeded,"Export entry count budget exceeded"));}
    let mut bytes=Vec::new();let mut decoded=0;let mut source_lines=0usize;
    for (index,entry) in entries.iter().enumerate() {
        job.checkpoint(Phase::Writing,index,entries.len())?;
        key(&entry.key,limits,index+1)?;
        if index==0&&entry.key.starts_with('\u{feff}') {return Err(Error::new(ErrorCode::UnrepresentableSource,"First key begins with ambiguous UTF-8 BOM"));}
        if entry.text.contains('\0')||entry.text.split('\n').any(|line|line.strip_suffix('\r').unwrap_or(line)=="</>") {
            return Err(Error::new(ErrorCode::UnrepresentableSource,"Definition contains NUL or a standalone delimiter"));
        }
        if entry.text.len()>limits.max_entry_bytes {return Err(Error::new(ErrorCode::LimitExceeded,"Export definition byte budget exceeded"));}
        if profile==TxtProfile::CanonicalV1&&entry.text.contains('\r') {
            return Err(Error::new(ErrorCode::UnrepresentableSource,"Canonical export requires LF body newlines; no silent CR conversion"));
        }
        if profile==TxtProfile::LegacyBodySpanV1 {
            if !entry.text.ends_with('\n')||entry.text.replace("\r\n","").contains('\r') {
                return Err(Error::new(ErrorCode::UnrepresentableSource,"Legacy body-span export requires a terminating LF/CRLF and no lone CR"));
            }
        }
        decoded=sum(decoded,sum(entry.key.len(),entry.text.len())?)?;
        if decoded>limits.max_decoded_bytes {return Err(Error::new(ErrorCode::LimitExceeded,"Decoded export budget exceeded"));}
        let body_lfs=entry.text.bytes().filter(|b|*b==b'\n').count();
        source_lines=sum(source_lines,sum(body_lfs,if profile==TxtProfile::CanonicalV1 {3}else{2})?)?;
        if source_lines>limits.max_source_lines {return Err(Error::new(ErrorCode::LimitExceeded,"Export source line budget exceeded"));}
        append(&mut bytes,&entry.key,limits)?;append(&mut bytes,"\n",limits)?;append(&mut bytes,&entry.text,limits)?;
        if profile==TxtProfile::CanonicalV1 {append(&mut bytes,"\n",limits)?;}
        append(&mut bytes,"</>\n",limits)?;
    }
    job.check()?;Ok(bytes)
}
pub fn write_txt(entries:&[Entry],destination:&Path,profile:TxtProfile,limits:&Limits,job:&mut JobContext<'_>)->Result<TextSummary> {
    job.check()?;
    if fs::symlink_metadata(destination).is_ok() {return Err(Error::new(ErrorCode::DestinationExists,"Text destination already exists"));}
    let bytes=render_txt(entries,profile,limits,job)?;
    let parent=destination.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new("."));
    let mut temporary=tempfile::NamedTempFile::new_in(parent)?;
    temporary.write_all(&bytes)?;temporary.as_file().sync_all()?;
    let actual=read_bounded(temporary.path(),limits)?;
    let verified=parse(&actual,profile,limits,job,Phase::Verifying)?;
    if actual!=bytes||verified.as_slice()!=entries {return Err(Error::new(ErrorCode::Integrity,"Text export differs after strict reopen"));}
    job.check()?;temporary.persist_noclobber(destination).map_err(|e|Error::from(e.error))?;
    job.published(entries.len());Ok(TextSummary {entries:entries.len(),file_bytes:bytes.len(),profile})
}
