use crate::{malformed,budget,Error,ReadControl,Result};
use quick_xml::{events::Event,Reader};
use std::collections::BTreeMap;

#[derive(Clone,Copy,PartialEq)]
pub(crate) enum Kind {Start,Text,End}
pub(crate) fn visit(source:&str,control:&ReadControl<'_>,mut callback:impl FnMut(&[String],Kind,&BTreeMap<String,String>,&str)->Result<()>)->Result<()> {
    let mut reader=Reader::from_str(source);reader.config_mut().expand_empty_elements=true;
    let mut stack:Vec<String>=Vec::new();let empty=BTreeMap::new();
    loop {
        control.check()?;
        match reader.read_event().map_err(malformed)? {
            Event::Start(element)=>{
                let name=std::str::from_utf8(element.local_name().as_ref()).map_err(malformed)?.to_owned();
                if stack.len()>=64 {return Err(budget("XML nesting budget exceeded"));}
                let mut attrs=BTreeMap::new();
                for attr in element.attributes() {
                    let attr=attr.map_err(malformed)?;
                    let key=std::str::from_utf8(attr.key.as_ref()).map_err(malformed)?.to_owned();
                    let value=attr.decode_and_unescape_value(reader.decoder()).map_err(malformed)?.into_owned();
                    attrs.insert(key,value);
                }
                stack.push(name);callback(&stack,Kind::Start,&attrs,"")?;
            }
            Event::End(_)=>{callback(&stack,Kind::End,&empty,"")?;stack.pop().ok_or_else(||malformed("Unbalanced XML"))?;}
            Event::Text(text)=>{
                let text=std::str::from_utf8(text.as_ref()).map_err(malformed)?.replace("\r\n","\n").replace('\r',"\n");
                callback(&stack,Kind::Text,&empty,&text)?;
            }
            Event::CData(text)=>{
                let text=std::str::from_utf8(text.as_ref()).map_err(malformed)?.replace("\r\n","\n").replace('\r',"\n");
                callback(&stack,Kind::Text,&empty,&text)?;
            }
            Event::GeneralRef(reference)=>{
                let reference=std::str::from_utf8(reference.as_ref()).map_err(malformed)?;
                let encoded=format!("&{reference};");
                let decoded=quick_xml::escape::unescape(&encoded).map_err(malformed)?;
                callback(&stack,Kind::Text,&empty,&decoded)?;
            }
            Event::DocType(_)=>return Err(Error::new("unsupported_workbook","DTD/entity declarations are unsupported")),
            Event::Decl(decl)=>{
                if decl.version().map_err(malformed)?.as_ref()!=b"1.0" {
                    return Err(Error::new("unsupported_workbook","Only XML 1.0 OOXML parts are supported"));
                }
                if let Some(encoding)=decl.encoding() {
                    let encoding=encoding.map_err(malformed)?;
                    if !encoding.eq_ignore_ascii_case(b"UTF-8")&&!encoding.eq_ignore_ascii_case(b"UTF8") {
                        return Err(Error::new("unsupported_workbook","Only UTF-8 OOXML parts are supported"));
                    }
                }
            }
            Event::Eof=>break,
            _=>{},
        }
    }
    if !stack.is_empty() {return Err(malformed("Truncated XML"));}
    Ok(())
}

pub(crate) fn append(out:&mut String,text:&str,max:usize)->Result<()> {
    if out.len().checked_add(text.len()).ok_or_else(||budget("XML text byte overflow"))?>max {return Err(budget("Cell text byte budget exceeded"));}
    out.push_str(text);Ok(())
}
