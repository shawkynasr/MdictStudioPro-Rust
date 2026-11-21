use super::{Converter,Row,text::*};
const HEAD:&str="<head><meta charset=\"utf-8\"><link rel=\"stylesheet\" type=\"text/css\" href=\"jybcb.css\">";
fn wrap(body:String,script:bool)->String {format!("{HEAD}{}</head><div class=\"edugycd\">{body}</div>",if script {"<script src=\"jybcb.js\"></script>"}else{""})}
fn span(class:&str,value:&str)->String {format!("<span class=\"{class}\">{value}</span>")}
fn radical(row:&Row,mini:bool)->String {
    let r=get(row,if mini {"部首"}else{"部首字"});let t=get(row,"總筆畫數");let o=get(row,if mini {"部首外筆畫"}else{"部首外筆畫數"});
    let mut parts=Vec::new();if !r.is_empty() {parts.push(format!("{r}部"));}if !o.is_empty() {parts.push(format!("部外 {o} 畫"));}if !t.is_empty() {parts.push(format!("總筆畫 {t} 畫"));}parts.join(" ")
}
fn title(head:&str,radical:&str)->String {format!("<div class=\"dict-title-group\">{}{}</div>",span("index",head),if radical.is_empty() {String::new()}else{span("radical",radical)})}
fn reference(out:&mut String,rows:&[&Row],key:&str,label:&str,cleaner:Option<fn(&str)->String>) {
    let values=values(rows,key);if values.is_empty() {return;}
    let values:Vec<_>=values.iter().map(|s|match cleaner {Some(f)=>f(s),None=>s.clone()}).collect();
    out.push_str(&format!("<span class=\"polyref\"><b>{label}：</b>{}</span>",values.join("；")));
}
fn concise_clean(s:&str)->String {clean(&images(s,false)).replace('\n',"<br />")}
fn enum_needed(rows:&[&Row])->bool {
    let mut ns=Vec::new();for row in rows {let n=integer(get(row,"多音排序"));if positive(&n)&&!ns.contains(&n.1) {ns.push(n.1);}}ns.len()>=2
}
fn concise(head:&str,rows:&[&Row])->String {
    let mut out=title(head,&radical(rows[0],false));let sorted=sorted(rows,true);let needed=enum_needed(&sorted);
    let(mut z,mut p,mut defs)=(Vec::new(),Vec::new(),String::new());
    for row in sorted {
        let prefix=enum_prefix(&integer(get(row,"多音排序")),needed);
        let vt=variant(row);let tag=if vt.is_empty() {String::new()}else{span("example",vt)};
        for (list,key,var_key) in [(&mut z,"注音一式","變體注音"),(&mut p,"漢語拼音","變體漢語拼音")] {
            let value=get(row,key);if !value.is_empty() {push_unique(list,format!("{prefix}{value}"));}
            let value=get(row,var_key);if !value.is_empty() {push_unique(list,format!("{tag}{value}"));}
        }
        let d=concise_clean(raw(row,"釋義"));if !d.is_empty() {defs.push_str(&span("mean",&format!("{prefix}{d}")));}
    }
    if !z.is_empty() {out.push_str(&span("bopomo",&z.join(" ")));}if !p.is_empty() {out.push_str(&span("hanyu",&p.join(" ")));}
    if !defs.is_empty() {out.push_str(&span("article",&format!("釋義：{defs}")));}
    reference(&mut out,rows,"相似詞","相似詞",None);reference(&mut out,rows,"相反詞","相反詞",None);reference(&mut out,rows,"多音參見訊息","多音參見",Some(concise_clean));wrap(out,false)
}
fn flush(out:&mut String,block:&mut Vec<String>) {
    if block.len()>1 {out.push_str("<ol style=\"margin-top:0; padding-left:2em;\">");for s in block.iter() {out.push_str(&format!("<li>{s}</li>"));}out.push_str("</ol>");}
    else if let Some(s)=block.first() {out.push_str(&format!("<div style=\"margin-top:4px; padding-left:0;\">{s}</div>"));}block.clear();
}
fn revised_defs(head:&str,rows:&[&Row])->String {
    let mut parts=String::new();
    for row in rows {
        let defs=revised_clean(raw(row,"釋義"));if defs.is_empty() {continue;}
        let n=integer(get(row,"多音排序"));let mut bits=Vec::new();
        if rows.len()>1&&positive(&n) {bits.push(format!("({})",cn(&n.1,6)));}
        let vt=variant(row);if !vt.is_empty() {bits.push(span("example",vt));}
        let header=if bits.is_empty() {String::new()}else{format!("<div style='font-weight:bold; color:#B45E13; margin-bottom:4px;'>{} {}</div>",bits.join(" "),get(row,"注音一式"))};
        let mut html=String::new();let mut block=Vec::new();
        for line in lines(&defs) {
            let line=strip_number(line).replace(head,&format!("<span style=\"color:var(--c-red); font-weight:bold;\">{head}</span>"));
            if let Some(rest)=line.strip_prefix('[') {
                if let Some(pos)=rest.strip_suffix(']') {flush(&mut html,&mut block);html.push_str(&format!("<div style=\"margin-top:12px; margin-bottom:4px;\">{}</div>",span("example",pos)));continue;}
                if let Some(end)=rest.find(']') {
                let pos=&rest[..end];let tail=trim(&rest[end+1..]);
                block.push(format!("{} {tail}",span("example",pos)));continue;
            }}block.push(line);
        }
        flush(&mut html,&mut block);parts.push_str(&span("mean",&format!("{header}{html}")));
    }
    if parts.is_empty() {String::new()}else{span("article",&parts)}
}
fn revised(head:&str,rows:&[&Row])->String {
    let rad=if integer(get(rows[0],"字數"))==(false,"1".into()) {radical(rows[0],false)}else{String::new()};
    let mut out=title(&revised_images(head),&rad);let sorted=sorted(rows,true);let needed=enum_needed(&sorted);
    let(mut z,mut p,mut zs,mut ps)=(Vec::new(),Vec::new(),Vec::new(),Vec::new());
    for row in &sorted {
        let prefix=enum_prefix(&integer(get(row,"多音排序")),needed);
        for (list,seen,key,var_key) in [(&mut z,&mut zs,"注音一式","變體注音"),(&mut p,&mut ps,"漢語拼音","變體漢語拼音")] {
            let v=get(row,key);if !v.is_empty()&&!seen.contains(&v) {list.push(format!("{prefix}{v}"));seen.push(v);}
            let v=get(row,var_key);if !v.is_empty()&&!seen.contains(&v) {list.push(v.into());seen.push(v);}
        }
    }
    if !z.is_empty() {out.push_str(&span("bopomo",&z.join(" ")));}if !p.is_empty() {out.push_str(&span("hanyu",&p.join(" ")));}
    out.push_str(&revised_defs(head,&sorted));
    for (key,label,cleaner) in [("相似詞","相似詞",None),("相反詞","相反詞",None),("多音參見訊息","多音參見",Some(revised_clean as fn(&str)->String)),("辭條別名","辭條別名",None),("異體字","異體字",None)] {reference(&mut out,rows,key,label,cleaner);}
    wrap(out,true)
}
const MINI_HEAD:&str=include_str!("mini-head.html");
fn ruby(s:&str)->String {
    fn bop(c:char)->bool {matches!(c,'ㄅ'..='ㄩ'|'˙'|'ˊ'|'ˇ'|'ˋ')}
    rewrite(s,|s,at| {
        let c=s[at..].chars().next()?;if c=='\n' {return None;}
        let start=at+c.len_utf8();let count=s[start..].chars().take_while(|c|bop(*c)).map(char::len_utf8).sum::<usize>();
        if count==0 {None}else{Some((start+count,format!("<ruby>{c}<rt>{}</rt></ruby>",&s[start..start+count])))}
    })
}
fn mini(head:&str,rows:&[&Row])->String {
    let mut out=title(head,&radical(rows[0],true));let mut z=Vec::new();let mut defs=String::new();
    for (i,row) in rows.iter().enumerate() {
        let prefix=if rows.len()>1 {format!("({}) ",cn(&(i+1).to_string(),9))}else{String::new()};
        let value=get(row,"注音");if !value.is_empty() {z.push(format!("{prefix}{value}"));}
        // Preserve the original overwritten image-substitution result.
        let d=ruby(&clean(raw(row,"解釋")).replace("&&","")).replace('\n',"<br />");
        if !d.is_empty() {defs.push_str(&span("mean",&format!("{prefix}{d}")));}
    }
    if !z.is_empty() {out.push_str(&span("bopomo",&z.join(" ")));}if !defs.is_empty() {out.push_str(&span("article",&format!("釋義：{defs}")));}
    let custom_head=MINI_HEAD.strip_suffix('\n').unwrap_or(MINI_HEAD);
    format!("{custom_head}<div class=\"edugycd\">{out}</div>")
}
fn wfg_examples(s:&str)->String {
    rewrite(s,|s,at| {
        let tail=s[at..].strip_prefix("如：「")?;
        let end=tail.find(['」','《','〈'])?;if !tail[end..].starts_with('」') {return None;}
        let end=at+"如：「".len()+end+'」'.len_utf8();Some((end,span("li",&s[at..end])))
    })
}
fn wfg_quotes(s:&str)->String {
    // Equivalent leftmost/lazy boundary, title opener, then next closing quote.
    rewrite(s,|s,at| {
        let c=s[at..].chars().next()?;let prefix=if matches!(c,'。'|'>'|'」') {c.len_utf8()}else if at==0 {0}else{return None;};
        let start=at+prefix;let tail=&s[start..];
        for (opener,c) in tail.char_indices() {
            if matches!(c,'。'|'>'|'」') {break;}
            if !matches!(c,'《'|'〈') {continue;}
            let title=&tail[opener..];let Some(close)=title.find(['<','」']) else {continue;};
            if !title[close..].starts_with('」') {continue;}
            let end=start+opener+close+'」'.len_utf8();return Some((end,format!("{}{}",&s[at..start],span("yz",&s[start..end]))));
        }None
    })
}
fn wfg_defs(s:&str)->String {
    let s=s.replace('．',"・");let mut out=String::new();let mut pos_count=0;
    for line in lines(&s) {
        let mut line=line;
        if let Some(rest)=line.strip_prefix('[') {if let Some(end)=rest.find(']') {
            if pos_count>0 {out.push_str("<span class=\"pos1\"></span>");}out.push_str(&span("pos",&rest[..end]));pos_count+=1;line=&rest[end+1..];if line.is_empty() {continue;}
        }}
        let line=wfg_quotes(&wfg_examples(line));
        if let Some((n,rest))=numbered(&line) {out.push_str(&span("entry",&format!("{}{rest}",span("num",&circled(n)))));}else{out.push_str(&span("entry-single",&line));}
    }out
}
fn wfg(head:&str,rows:&[&Row])->String {
    let mut out="<link href=\"cbgycd.css\" rel=\"stylesheet\" type=\"text/css\"><script src=\"cbgycd.js\"></script><cbgycd>".to_owned();
    let nums=["","㈠","㈡","㈢","㈣","㈤","㈥","㈦","㈧","㈨","㈩"];
    for (i,row) in sorted(rows,false).iter().enumerate() {
        out.push_str(if i==0 {"<hr class=\"hr1\">"}else{"<hr class=\"hr3\">"});out.push_str(&span("hw",head));
        if rows.len()>1&&i+1<nums.len() {out.push_str(&format!("<sup class=\"homo\">{}</sup>",nums[i+1]));}out.push_str("<hr class=\"hr2\">");
        let mut strokes=String::new();for (key,class) in [("部首字","bs"),("部首外筆畫數","bh"),("總筆畫數","zbh")] {let v=get(row,key);if !v.is_empty() {strokes.push_str(&span(class,v));}}
        if !strokes.is_empty() {out.push_str(&span("sy",&strokes));}
        for (key,class) in [("注音一式","zy"),("漢語拼音","py")] {let v=get(row,key);if !v.is_empty() {out.push_str(&span("sy",&span(class,v)));}}
        out.push_str("<hr class=\"hr2\">");let defs=trim(&images(raw(row,"釋義"),false).replace("_x000D_","").replace('\r',"")).to_owned();out.push_str(&wfg_defs(&defs));
        for (key,class) in [("相似詞","jy"),("相反詞","fy")] {let v=get(row,key);if !v.is_empty() {out.push_str(&span(class,v));}}
    }out.push_str("</cbgycd>");out
}
fn section(raw:&str,name:&str,head:&str)->String {
    let text=raw.replace("_x000D_","").replace('\r',"");if trim(&text).is_empty() {return String::new();}let text=images(&text,false);
    match name {
        "典源文獻內容"=>span("content-text source-content dianyuan-wenxian",&markers(&text.replace('\n',""),Some("source"))),
        "典源注解"=>{
            let mut out="<ul class=\"annotation-list\" style=\"list-style: none; padding-left: 0;\">".to_owned();
            for (i,line) in lines(&text).iter().enumerate() {out.push_str(&format!("<li style=\"margin-bottom: 5px;\">{} {}</li>",span("line-num",&circled(&(i+1).to_string())),strip_number(line)));}out.push_str("</ul>");span("content-text annotated-content",&out)
        },
        "書證"=>span("content-text annotated-content shuzheng",&markers(&text,Some("line")).replace('\n',"<br />")),
        "用法說明-例句"=>{
            let mut out="<ol class=\"example-list\">".to_owned();for line in lines(&text) {let line=markers(line,None);let line=trim(&line).replace(head,&format!("<em>{head}</em>"));out.push_str(&format!("<li>{line}</li>"));}out.push_str("</ol>");span("content-text",&out)
        },
        "近義成語"|"反義成語"|"參考詞語"=>{
            let words:Vec<_>=text.split('、').map(trim).filter(|s|!s.is_empty()).map(|w|format!("<span class=\"jump-word\"><a href=\"entry://{w}\">{w}</a></span>")).collect();span("content-text reference-content",&words.join("、"))
        },
        "辨識-例句"=>{
            let lines=lines(&text);if lines.is_empty() {return String::new();}let headers:Vec<_>=lines[0].split(py_space).filter(|s|!s.is_empty()).collect();
            let mut out="<table class=\"compare-table\"><tr>".to_owned();for h in &headers {out.push_str(&format!("<th>{h}</th>"));}out.push_str("<th>例句</th></tr>");
            for line in &lines[1..] {
                // Python split(maxsplit=N): preserve whitespace inside the final sentence.
                let mut rest=*line;let mut marks=Vec::new();
                for _ in &headers {rest=rest.trim_start_matches(py_space);if rest.is_empty() {break;}let end=rest.find(py_space).unwrap_or(rest.len());marks.push(&rest[..end]);rest=&rest[end..];}
                let sentence=rest.trim_start_matches(py_space);out.push_str("<tr>");for i in 0..headers.len() {out.push_str(&format!("<td class=\"mark\">{}</td>",marks.get(i).copied().unwrap_or("")));}out.push_str(&format!("<td class=\"sentence\">{sentence}</td></tr>"));
            }out.push_str("</table>");span("content-text",&out)
        },
        _=>span("content-text",&text.replace('\n',"<br />")),
    }
}
fn idioms(head:&str,rows:&[&Row])->String {
    let row=rows[0];let mut out=span("headword",head);if get(row,"主條成語／非主條成語")=="主條成語" {out.push_str("<sup class=\"main-entry-mark\">㊣</sup>");}
    for (key,class) in [("注音","bopomo"),("漢語拼音","hanyu")] {let v=get(row,key);if !v.is_empty() {out.push_str(&span(class,v));}}out.push_str("<div class=\"content-section\">");
    for col in ["釋義","典源文獻名稱","典源文獻內容","典源注解","典故說明","書證","用法說明-語義說明","用法說明-使用類別","用法說明-例句","辨識-同","辨識-異","辨識-例句","近義成語","反義成語","參考詞語","主條成語／非主條成語"] {
        let value=raw(row,col);if trim(value).is_empty() {continue;}out.push_str(&span("content-title",col));out.push_str(&section(value,col,head));
    }out.push_str("</div>");let mut out=wrap(out,true);let id=get(row,"編號");if !id.is_empty() {out.push_str(&format!("\n<div class=\"entry-id\" style=\"display:none;\">{id}</div>"));}out
}
pub fn build(kind:Converter,head:&str,rows:&[&Row])->String {match kind {Converter::Revised=>revised(head,rows),Converter::Wfg=>wfg(head,rows),Converter::Concise=>concise(head,rows),Converter::Idioms=>idioms(head,rows),Converter::Mini=>mini(head,rows)}}
