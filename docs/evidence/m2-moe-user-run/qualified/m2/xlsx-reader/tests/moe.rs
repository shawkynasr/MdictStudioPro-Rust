use std::{cell::Cell,path::PathBuf};
use studio_xlsx::{read_xlsx,Table,ReadControl,moe::{self,Converter,Row}};
fn table(rows:Vec<Row>)->Table {Table {profile:studio_xlsx::PROFILE,backend:"test",sheet_name:"test".into(),headers:Vec::new(),rows,scanned_data_rows:0,skipped_blank_rows:0}}
fn row(fields:&[(&str,&str)])->Row {fields.iter().map(|(k,v)|(k.to_string(),v.to_string())).collect()}
fn convert(t:&Table,k:Converter)->studio_xlsx::Result<moe::Conversion> {moe::convert(t,k,&moe::Limits::default(),&mut ReadControl::new(&||false,&mut |_|{}))}

// Python set-derived reference order is unspecified. Normalize only those
// blocks, preserving every value (including repeats inside a compound alias).
// This is a fixture comparator, not a change to emitted converter content.
fn reference_order(text:&str,kind:Converter)->String {
    if !matches!(kind,Converter::Revised|Converter::Concise) {return text.into();}
    let mut text=text.to_owned();
    for label in ["相似詞","相反詞","多音參見","辭條別名","異體字"] {
        let prefix=format!("<span class=\"polyref\"><b>{label}：</b>");let mut cursor=0;
        while let Some(at)=text[cursor..].find(&prefix) {
            let start=cursor+at+prefix.len();let end=start+text[start..].find("</span>").expect("Complete fixture reference span");
            let mut values:Vec<_>=text[start..end].split('；').collect();values.sort();let value=values.join("；");
            text.replace_range(start..end,&value);cursor=start+value.len()+"</span>".len();
        }
    }text
}

#[test]
fn all_five_captured_layouts_match_original_baseline_content() {
    let root=PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../baseline");
    let t=read_xlsx(&root.join("xlsx-reader-kit/moe-rows.xlsx"),None,&studio_xlsx::Limits::default(),&mut ReadControl::new(&||false,&mut |_|{})).unwrap();
    let expected:serde_json::Value=serde_json::from_slice(&std::fs::read(root.join("moe-converter-kit/expected.json")).unwrap()).unwrap();
    for kind in [Converter::Revised,Converter::Wfg,Converter::Concise,Converter::Idioms,Converter::Mini] {
        let actual=convert(&t,kind).unwrap();let want=expected[kind.name()].as_array().unwrap();
        assert_eq!(actual.primary_entries,2);assert_eq!(actual.entries.len(),want.len());assert_eq!(actual.skipped_rows,1);
        let main:Vec<_>=actual.entries.iter().filter(|e|!e.text.starts_with("@@@LINK=")).map(|e|e.key.as_str()).collect();
        assert_eq!(main,if kind==Converter::Idioms {vec!["和衷共濟","一字千金"]}else{vec!["和","字"]});
        // Both alias record order and set-derived reference value order vary
        // in Python. Main group order is asserted above; all content is exact
        // after the same documented normalization used by the Python runner.
        let mut a:Vec<_>=actual.entries.iter().map(|e|(e.key.clone(),reference_order(&e.text,kind))).collect();a.sort();
        let mut b:Vec<_>=want.iter().map(|e|(e["key"].as_str().unwrap().to_owned(),reference_order(e["text"].as_str().unwrap(),kind))).collect();b.sort();
        assert_eq!(a,b,"{}",kind.name());
    }
}
#[test]
fn reference_comparison_preserves_duplicates_targets_and_other_html() {
    let a="<span class=\"polyref\"><b>辭條別名：</b>和平；和諧；和平</span>";
    let b="<span class=\"polyref\"><b>辭條別名：</b>和平；和平；和諧</span>";
    assert_eq!(reference_order(a,Converter::Revised),reference_order(b,Converter::Revised));
    assert_ne!(reference_order(a,Converter::Revised),reference_order(&b.replacen("和平；","",1),Converter::Revised));
    assert_ne!(reference_order(a,Converter::Revised),reference_order(&b.replace("和諧","別詞"),Converter::Revised));
    assert_ne!(reference_order(a,Converter::Revised),reference_order(&format!("{b}<br>"),Converter::Revised));
    assert_ne!(reference_order("@@@LINK=甲",Converter::Revised),reference_order("@@@LINK=乙",Converter::Revised));
    for kind in [Converter::Wfg,Converter::Mini,Converter::Idioms] {assert_ne!(reference_order(a,kind),reference_order(b,kind));}
}
#[test]
fn first_seen_references_aliases_and_cross_head_alias_duplicates_are_stable() {
    let t=table(vec![row(&[("字詞名","甲"),("相似詞","乙"),("辭條別名","別乙；別甲；別乙")]),
        row(&[("字詞名","甲"),("相似詞","丙")]),row(&[("字詞名","乙"),("辭條別名","別乙")])]);
    let a=convert(&t,Converter::Revised).unwrap();let b=convert(&t,Converter::Revised).unwrap();assert_eq!(a.entries,b.entries);
    assert_eq!(a.entries.iter().map(|e|e.key.as_str()).collect::<Vec<_>>(),["甲","別乙","別甲","乙","別乙"]);
    assert!(a.entries[0].text.contains("相似詞：</b>乙；丙</span>"));assert_eq!(a.alias_redirects,3);
}
#[test]
fn limits_cancel_errors_and_canonical_txt_refusals_are_all_or_error() {
    let t=table(vec![row(&[("字詞名","甲"),("釋義","definition")])]);
    let mut limits=moe::Limits::default();limits.max_output_bytes=1;
    assert_eq!(moe::convert(&t,Converter::Revised,&limits,&mut ReadControl::new(&||false,&mut |_|{})).unwrap_err().code,"limit_exceeded");
    let cancel=Cell::new(false);let cancelled=||cancel.get();let mut progress=|_|cancel.set(true);
    assert_eq!(moe::convert(&t,Converter::Revised,&moe::Limits::default(),&mut ReadControl::new(&cancelled,&mut progress)).unwrap_err().code,"cancelled");
    for (t,code) in [(table(vec![row(&[("other","no head")])]),"malformed_source"),
        (table(vec![row(&[("字詞名","bad\nkey")])]),"unrepresentable_source"),
        (table(vec![row(&[("字詞名","字"),("釋義","&圖.png;")])]),"unsupported_policy"),
        (table(vec![row(&[("字詞名","字"),("多音排序","٢")])]),"unsupported_policy")] {
        assert_eq!(convert(&t,Converter::Revised).unwrap_err().code,code);
    }
}
#[test]
fn idioms_use_first_row_and_mini_retains_original_literal_image_marker() {
    let t=table(vec![row(&[("單字","字"),("解釋","&&字ㄗˋ&& &test.png;"),("成語","成語"),("釋義","first")]),
        row(&[("成語","成語"),("釋義","ignored second row")])]);
    let mini=convert(&t,Converter::Mini).unwrap();assert!(mini.entries[0].text.contains("<ruby>字<rt>ㄗˋ</rt></ruby> &test.png;"));
    let idiom=convert(&t,Converter::Idioms).unwrap();assert!(idiom.entries[0].text.contains("first"));assert!(!idiom.entries[0].text.contains("ignored second row"));
}
