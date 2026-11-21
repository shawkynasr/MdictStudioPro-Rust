use super::Row;
use crate::{Error,Result,py_space};
pub fn trim(s:&str)->&str {s.trim_matches(py_space)}
pub fn get<'a>(row:&'a Row,key:&str)->&'a str {trim(row.get(key).map(String::as_str).unwrap_or(""))}
pub fn raw<'a>(row:&'a Row,key:&str)->&'a str {row.get(key).map(String::as_str).unwrap_or("")}
fn unsupported()->Error {Error::new("unsupported_policy","MOE v1 requires bounded ASCII numeric syntax, ASCII image-marker filenames and ASCII generic-GIF neighbors")}
pub fn check_profile(key:&str,value:&str)->Result<()> {
    // Do not silently substitute Rust's newer Unicode regex/number semantics.
    if matches!(key,"多音排序"|"字數")&&value.chars().any(|c|!c.is_ascii()&&c.is_numeric()) {return Err(unsupported());}
    for part in value.split('&').skip(1) {
        let candidate=part.split(|c:char|py_space(c)||matches!(c,';'|'<'|'>'|'&')).next().unwrap_or("");
        if candidate.chars().any(|c|!c.is_ascii())&&[".png",".jpg",".jpeg",".gif"].iter().any(|ext|candidate.to_ascii_lowercase().contains(ext)) {return Err(unsupported());}
    }
    for line in value.split('\n') {
        let line=trim(line);
        let n:String=line.chars().take_while(|c|c.is_numeric()).collect();
        if !n.is_ascii()&&line[n.len()..].starts_with('.') {return Err(unsupported());}
        for part in line.split('*').skip(1) {
            let n:String=part.chars().take_while(|c|c.is_numeric()).collect();
            if !n.is_ascii()&&part[n.len()..].starts_with('*') {return Err(unsupported());}
        }
    }
    // Generic GIF uses Python word boundaries; v1 only qualifies ASCII
    // adjacent characters, avoiding a compiler-dependent Unicode \w table.
    for (at,_) in value.match_indices("._104_0.gif") {
        if at>=4&&value.as_bytes()[at-4..at].iter().all(u8::is_ascii_hexdigit) {
            let before=value[..at-4].chars().next_back();let after=value[at+11..].chars().next();
            if before.into_iter().chain(after).any(|c|!c.is_ascii()) {return Err(unsupported());}
        }
    }
    if (matches!(key,"多音排序"|"字數")&&value.len()>4096)||value.as_bytes().split(|b|!b.is_ascii_digit()).any(|digits|digits.len()>4096) {return Err(unsupported());}
    Ok(())
}
// Python int allows signs and interior underscores. Arbitrarily long values
// sort by decimal magnitude rather than overflowing a machine integer.
pub fn integer(s:&str)->(bool,String) {
    let s=trim(s);let negative=s.starts_with('-');let s=s.strip_prefix(['+','-']).unwrap_or(s);
    let valid=!s.is_empty()&&s.as_bytes().first().is_some_and(u8::is_ascii_digit)&&s.as_bytes().last().is_some_and(u8::is_ascii_digit)
        &&s.bytes().all(|b|b.is_ascii_digit()||b==b'_')&&!s.contains("__");
    if !valid {return (false,"0".into());}
    let n=s.replace('_',"");let n=n.trim_start_matches('0');
    if n.is_empty() {(false,"0".into())}else{(negative,n.into())}
}
pub fn positive(n:&(bool,String))->bool {!n.0&&n.1!="0"}
pub fn cmp(a:&(bool,String),b:&(bool,String))->std::cmp::Ordering {
    if a.0!=b.0 {return b.0.cmp(&a.0);}
    let order=a.1.len().cmp(&b.1.len()).then_with(||a.1.cmp(&b.1));if a.0 {order.reverse()}else{order}
}
pub fn sorted<'a>(rows:&[&'a Row],positive_first:bool)->Vec<&'a Row> {
    let mut rows=rows.to_vec();rows.sort_by(|a,b| {
        let a=integer(get(a,"多音排序"));let b=integer(get(b,"多音排序"));
        if positive_first&&positive(&a)!=positive(&b) {positive(&b).cmp(&positive(&a))}else{cmp(&a,&b)}
    });rows
}
pub fn cn(n:&str,max:usize)->String {
    let names=["","一","二","三","四","五","六","七","八","九"];
    match n.parse::<usize>() {Ok(i) if i>0&&i<=max=>names[i].into(),_=>n.into()}
}
pub fn enum_prefix(n:&(bool,String),needed:bool)->String {if needed&&positive(n) {format!("({}) ",cn(&n.1,6))}else{String::new()}}
pub fn variant(row:&Row)->&str {match get(row,"變體類型 1:變 2:又音 3:語音 4:讀音") {"1"=>"變","2"=>"又音","3"=>"語音","4"=>"讀音",x=>x}}
pub fn push_unique(values:&mut Vec<String>,s:String) {if !s.is_empty()&&!values.contains(&s) {values.push(s);}}
pub fn values(rows:&[&Row],key:&str)->Vec<String> {let mut out=Vec::new();for row in rows {push_unique(&mut out,get(row,key).into());}out}
pub fn clean(s:&str)->String {trim(&s.replace("_x000D_","").replace("\r\n","\n").replace('\r',"\n")).into()}
pub fn lines(s:&str)->Vec<&str> {s.split('\n').map(trim).filter(|l|!l.is_empty()).collect()}

// Leftmost non-overlapping replacement. Matchers return byte boundaries.
pub fn rewrite(s:&str,mut matcher:impl FnMut(&str,usize)->Option<(usize,String)>)->String {
    let mut out=String::new();let mut at=0;
    while at<s.len() {if let Some((end,replacement))=matcher(s,at) {out.push_str(&replacement);at=end;}else{let c=s[at..].chars().next().unwrap();out.push(c);at+=c.len_utf8();}}
    out
}
pub fn images(s:&str,alt:bool)->String {
    rewrite(s,|s,at| {
        if s.as_bytes()[at]!=b'&' {return None;}
        let tail=&s[at+1..];let len=tail.bytes().take_while(|b|b.is_ascii_alphanumeric()||matches!(*b,b'_'|b'.'|b'-')).count();
        // Greedy filename, then Python's ordered extension alternatives.
        for dot in (1..len).rev() {if tail.as_bytes()[dot]!=b'.' {continue;}
            for ext in ["jpg","jpeg","gif","png"] {
                let end=dot+1+ext.len();
                if end<=len&&tail[dot+1..end].eq_ignore_ascii_case(ext) {
                    let filename=&tail[..end];let semi=usize::from(tail.as_bytes().get(end)==Some(&b';'));
                    let extra=if alt {format!(" alt=\"{filename}\"")}else{String::new()};
                    return Some((at+1+end+semi,format!("<img class=\"pic-inline\" src=\"{filename}\"{extra}>")));
                }
            }
        }None
    })
}
fn word(c:char)->bool {c=='_'||c.is_alphanumeric()}
pub fn revised_images(s:&str)->String {
    let s=rewrite(s,|s,at| {
        let tail=&s[at..];let b=tail.as_bytes();
        if b.len()<15||!b[..4].iter().all(u8::is_ascii_hexdigit)||&b[4..15]!=b"._104_0.gif" {return None;}
        if s[..at].chars().next_back().is_some_and(word)||tail[15..].chars().next().is_some_and(word) {return None;}
        let fname=&tail[..15];let alt=match fname {"9868._104_0.gif"=>"未收錄篆字","9b46._104_0.gif"=>"e^x","9a73._104_0.gif"=>"x^2","975d._104_0.gif"=>"a^π",_=>&fname[..4]};
        Some((at+15,format!("<img src=\"{fname}\" class=\"imgchar\" alt=\"{alt}\" />")))
    });
    let s=rewrite(&s,|s,at| {
        let b=&s.as_bytes()[at..];
        if b.len()<11||b[0]!=b'&'||!b[1..5].iter().all(u8::is_ascii_hexdigit)||&b[5..11]!=b"_.png;" {return None;}
        let hex=s[at+1..at+5].to_ascii_lowercase();Some((at+11,format!("<img src=\"{hex}_.png\" class=\"imgchar\" alt=\"{hex}\" />")))
    });images(&s,true)
}
pub fn revised_clean(s:&str)->String {
    let s=clean(s);
    let s=if (s.starts_with('"')&&s.ends_with('"')&&s.len()>=2)||(s.starts_with('「')&&s.ends_with('」')) {let first=s.chars().next().unwrap().len_utf8();let last=s.chars().next_back().unwrap().len_utf8();trim(&s[first..s.len()-last])}else{&s};
    revised_images(s)
}
pub fn numbered(s:&str)->Option<(&str,&str)> {
    let n=s.bytes().take_while(u8::is_ascii_digit).count();
    if n==0||s.as_bytes().get(n)!=Some(&b'.') {return None;}
    Some((&s[..n],s[n+1..].trim_start_matches(py_space)))
}
pub fn strip_number(s:&str)->&str {trim(numbered(s).map(|(_,rest)|rest).unwrap_or(s))}
pub fn circled(n:&str)->String {
    let n=n.trim_start_matches('0');let n=if n.is_empty() {"0"}else{n};
    match n.parse::<u32>() {Ok(v) if (1..=20).contains(&v)=>char::from_u32(9311+v).unwrap().into(),_=>format!("({n})")}
}
pub fn markers(s:&str,tag:Option<&str>)->String {
    rewrite(s,|s,at| {
        if s.as_bytes()[at]!=b'*' {return None;}
        let tail=&s[at+1..];let n=tail.bytes().take_while(u8::is_ascii_digit).count();
        if n==0||tail.as_bytes().get(n)!=Some(&b'*') {return None;}
        let value=match tag {Some("source")=>format!("<sup class=\"source-num\">{}</sup>",circled(&tail[..n])),Some(_)=>format!("<span class=\"line-num\">{}</span>",circled(&tail[..n])),None=>String::new()};
        Some((at+1+n+1,value))
    })
}
