//! CC-CEDICT UTF-8 converter: preserve the captured plugin's HTML and ordering.
//! No Python runtime, regex dependency or source-adjacent log writes.
use crate::{casing::Casing,ConversionResult,Entry,Error,ErrorCode,JobContext,Limits,Phase,Result,TxtProfile};
use std::{cmp::Reverse,path::Path};

fn limit()->Error {Error::new(ErrorCode::LimitExceeded,"CC-CEDICT conversion budget exceeded")}
fn push(out:&mut String,text:&str,max:usize)->Result<()> {
    if out.len().checked_add(text.len()).ok_or_else(limit)?>max {return Err(limit());}
    out.push_str(text);Ok(())
}
// Explicit Python16 str.isspace set, independent of compiler Unicode version.
fn whitespace(c:char)->bool {
    matches!(c,'\t'..='\r'|'\u{1c}'..='\u{20}'|'\u{85}'|'\u{a0}'|'\u{1680}'|
        '\u{2000}'..='\u{200a}'|'\u{2028}'|'\u{2029}'|'\u{202f}'|'\u{205f}'|'\u{3000}')
}
fn field(text:&str)->Option<(&str,&str)> {
    let end=text.find(whitespace)?;
    if end==0 {return None;}
    Some((&text[..end],text[end..].trim_start_matches(whitespace)))
}
fn line(text:&str)->Option<(&str,&str,&str,&str)> {
    let (trad,rest)=field(text)?;let(simp,rest)=field(rest)?;
    let rest=rest.strip_prefix('[')?;let end=rest.find(']')?;
    if end==0 {return None;}
    let pinyin=&rest[..end];let tail=&rest[end+1..];
    if !tail.chars().next().is_some_and(whitespace) {return None;}
    let defs=tail.trim_start_matches(whitespace).strip_prefix('/')?.strip_suffix('/')?;
    if defs.is_empty() {return None;}
    Some((trad,simp,pinyin,defs))
}
fn pinyin(text:&str,policy:&Casing)->Result<String> {
    if text.len()>4096 {return Err(limit());}
    let mut result=Vec::new();
    for word in text.split(' ') {
        let Some(last)=word.chars().last() else {result.push(String::new());continue;};
        if !last.is_ascii_digit() {
            if last.is_numeric() {return Err(Error::new(ErrorCode::UnsupportedPolicy,"Pinyin profile accepts ASCII tone digits only"));}
            result.push(word.replace("u:","ü"));continue;
        }
        let prefix=&word[..word.len()-1];let tone=last as u8-b'0';
        if !(1..=5).contains(&tone) {result.push(prefix.replace("u:","ü"));continue;}
        let mut value=policy.lower(prefix).replace("u:","ü");
        if tone!=5 {
            let target=if value.contains('a') {Some('a')} else if value.contains('e') {Some('e')}
                else if value.contains("ou") {Some('o')} else {value.chars().rev().find(|c|"aeiouvü".contains(*c))};
            if let Some(target)=target {
                let marks=match target {'a'=>"āáǎàa",'e'=>"ēéěèe",'i'=>"īíǐìi",'o'=>"ōóǒòo",'u'=>"ūúǔùu",'v'|'ü'=>"ǖǘǚǜü",_=>""};
                let marked=marks.chars().nth((tone-1) as usize).ok_or_else(||Error::new(ErrorCode::Internal,"Missing pinyin tone"))?;
                value=value.replacen(target,&marked.to_string(),1);
            }
        }
        result.push(value);
    }
    Ok(result.join(" "))
}
pub fn cedict_pinyin(text:&str)->Result<String> {
    let policy=Casing::pinned16().map_err(|e|Error::new(ErrorCode::Internal,e.to_string()))?;
    pinyin(text,&policy)
}
fn blocked(c:char)->bool { c.is_ascii_lowercase()||matches!(c,'['|'<'|' ') }
fn xrefs(text:&str,max:usize)->Result<String> {
    let mut out=String::new();
    for segment in text.split_inclusive(' ') {
        let run=segment.strip_suffix(' ').unwrap_or(segment);
        // The legacy regex's first group greedily chooses the last usable pipe
        // in this ASCII-space-delimited run. Preserve that unusual behavior.
        let pipe=run.char_indices().rev().find(|(i,c)|*c=='|'&&*i>0&&run[*i+1..].chars().next().is_some_and(|c|!blocked(c)));
        if let Some((index,_))=pipe {
            let left=&run[..index];let tail=&run[index+1..];
            let stop=tail.find(blocked).unwrap_or(tail.len());let right=&tail[..stop];
            push(&mut out,&format!("<a href=\"entry://{left}\">{left}</a>|<a href=\"entry://{right}\">{right}</a><font class=\"cc_def_pinyin\">"),max)?;
            push(&mut out,&tail[stop..],max)?;
        } else {push(&mut out,run,max)?;}
        if segment.ends_with(' ') {push(&mut out," ",max)?;}
    }
    if let Some(index)=out.find("\"cc_def_pinyin\"") {
        if index+"\"cc_def_pinyin\"".len()<out.len() {push(&mut out,"</font>",max)?;}
    }
    Ok(out.replace("<font class=\"cc_def_pinyin\"></p><p class=\"cc_def\">",""))
}
fn tags(text:&str,max:usize)->Result<String> {
    let mut patterns:Vec<(&str,&str)>=vec![
        ("(old)","cc_tag"),("(slang)","cc_tag"),("(coll.)","cc_tag"),("(archaic)","cc_tag"),
        ("(bird species of China)","cc_tag"),("(idiom)","cc_tag"),("(Tw)","cc_tag"),("(vulgar)","cc_tag"),
        ("(Internet slang)","cc_tag"),("(loanword)","cc_tag"),("(computing)","cc_tag"),("(math.)","cc_tag"),
        ("(chemistry)","cc_tag"),("(medicine)","cc_tag"),("(Chinese medicine)","cc_tag"),("(botany)","cc_tag"),
        ("(Buddhism)","cc_tag"),("(dialect)","cc_tag"),("(Cantonese)","cc_tag"),("(Taiwanese)","cc_tag"),
        ("i.e.","cc_ie"),("e.g.","cc_ie"),("fig.","cc_ie"),("lit.","cc_ie"),("CL: ","cl_long"),("CL","cc_ie"),("(abbr.)","cc_ie")];
    patterns.sort_by_key(|(needle,_)|Reverse(needle.len()));
    let mut out=String::new();let mut cursor=0;
    while cursor<text.len() {
        let rest=&text[cursor..];
        if let Some((needle,class))=patterns.iter().find(|(needle,_)|rest.starts_with(*needle)) {
            if *class=="cl_long" {push(&mut out,"<span class=\"cc_ie\">CL</span> :",max)?;}
            else {push(&mut out,&format!("<span class=\"{class}\">{needle}</span>"),max)?;}
            cursor+=needle.len();
        } else {
            let c=rest.chars().next().ok_or_else(||Error::new(ErrorCode::Internal,"Invalid text cursor"))?;
            push(&mut out,&c.to_string(),max)?;cursor+=c.len_utf8();
        }
    }
    Ok(out)
}
pub fn convert_cedict_utf8(bytes:&[u8],limits:&Limits,job:&mut JobContext<'_>)->Result<ConversionResult> {
    job.checkpoint(Phase::Converting,0,bytes.len())?;
    if bytes.len() as u64>limits.max_file_bytes {return Err(limit());}
    let source=std::str::from_utf8(bytes).map_err(|e|Error::new(ErrorCode::InvalidEncoding,format!("CC-CEDICT UTF-8 decode failed at byte {}",e.valid_up_to())))?;
    if source.starts_with('\u{feff}') {return Err(Error::new(ErrorCode::InvalidEncoding,"CC-CEDICT profile requires UTF-8 without BOM"));}
    let source=source.replace("\r\n","\n").replace('\r',"\n");
    let policy=Casing::pinned16().map_err(|e|Error::new(ErrorCode::Internal,e.to_string()))?;
    let mut result=ConversionResult {entries:Vec::new(),txt_profile:TxtProfile::CanonicalV1,comments:Vec::new(),primary_entries:0,traditional_entries:0,skipped_lines:0};
    let mut decoded=0usize;let mut offset=0usize;
    for (index,raw) in source.split_inclusive('\n').enumerate() {
        job.check()?;
        if index>=limits.max_source_lines||raw.len()>limits.max_entry_bytes {return Err(limit());}
        if index%256==0 {job.checkpoint(Phase::Converting,offset,source.len())?;}
        offset+=raw.len();let trimmed=raw.trim_matches(whitespace);
        if trimmed.is_empty() {continue;}
        if trimmed.starts_with('#') {
            if result.comments.len()>=limits.max_entries {return Err(limit());}
            decoded=decoded.checked_add(trimmed.len()).ok_or_else(limit)?;
            if decoded>limits.max_decoded_bytes {return Err(limit());}
            result.comments.push(trimmed.to_owned());continue;
        }
        let Some((trad,simp,raw_pinyin,defs))=line(trimmed) else {result.skipped_lines+=1;continue;};
        if [trad,simp].iter().any(|k|k.len()>limits.max_key_bytes||*k=="</>"||k.contains('\0')) {
            return Err(Error::new(ErrorCode::MalformedSource,format!("Line {}: unrepresentable CC-CEDICT key",index+1)));
        }
        if trimmed.contains('\0') {return Err(Error::new(ErrorCode::MalformedSource,"NUL in CC-CEDICT record"));}
        let accented=pinyin(raw_pinyin,&policy)?;let max=limits.max_entry_bytes;
        let mut html=String::new();
        push(&mut html,"<link rel=\"stylesheet\" type=\"text/css\" href=\"cedict_ts.css\">",max)?;
        push(&mut html,&format!("<div class=\"cc_wrapper\"><div class=\"cc_header\"><span class=\"cc_trad\">{trad}</span><span class=\"cc_simp\">{simp}</span></div><div class=\"cc_header_pinyin\">{accented}</div><div class=\"cc_defs\">"),max)?;
        for definition in defs.split('/').filter(|d|!d.is_empty()) {
            let definition=tags(&xrefs(definition,max)?,max)?;
            push(&mut html,&format!("<p class=\"cc_def\">{definition}</p>"),max)?;
        }
        push(&mut html,"</div></div>",max)?;
        for head in [Some(simp),if trad!=simp {Some(trad)} else {None}].into_iter().flatten() {
            if result.entries.len()>=limits.max_entries {return Err(limit());}
            decoded=decoded.checked_add(head.len()).and_then(|v|v.checked_add(html.len())).ok_or_else(limit)?;
            if decoded>limits.max_decoded_bytes {return Err(limit());}
            result.entries.push(Entry {key:head.to_owned(),text:html.clone()});
        }
        result.primary_entries+=1;if trad!=simp {result.traditional_entries+=1;}
    }
    if result.entries.is_empty() {return Err(Error::new(ErrorCode::MalformedSource,"CC-CEDICT source has no matching entries"));}
    job.checkpoint(Phase::Converting,source.len(),source.len())?;Ok(result)
}
pub fn convert_cedict_file(path:&Path,limits:&Limits,job:&mut JobContext<'_>)->Result<ConversionResult> {
    job.check()?;convert_cedict_utf8(&crate::text::read_bounded(path,limits)?,limits,job)
}
