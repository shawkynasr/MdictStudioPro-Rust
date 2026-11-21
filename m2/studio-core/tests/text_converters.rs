use std::fs;
use studio_core::*;

fn parse(bytes:&[u8],profile:TxtProfile,limits:&Limits)->Result<Vec<Entry>> {
    let token=CancellationToken::default();let mut sink=|_|{};
    parse_txt(bytes,profile,limits,&mut JobContext::new(&token,&mut sink))
}
fn render(rows:&[Entry],profile:TxtProfile,limits:&Limits)->Result<Vec<u8>> {
    let token=CancellationToken::default();let mut sink=|_|{};
    render_txt(rows,profile,limits,&mut JobContext::new(&token,&mut sink))
}
fn convert(bytes:&[u8],limits:&Limits)->Result<ConversionResult> {
    let token=CancellationToken::default();let mut sink=|_|{};
    convert_cedict_utf8(bytes,limits,&mut JobContext::new(&token,&mut sink))
}

#[test]
fn six_captured_converter_txt_outputs_roundtrip_byte_for_byte_in_both_profiles() {
    let cases:[&[u8];6]=[
        include_bytes!("../../../baseline/expected/cc_cedict.txt"),
        include_bytes!("../../../baseline/expected/moe_revised.txt"),
        include_bytes!("../../../baseline/expected/moe_revised_wfg.txt"),
        include_bytes!("../../../baseline/expected/moe_concise.txt"),
        include_bytes!("../../../baseline/expected/moe_idioms.txt"),
        include_bytes!("../../../baseline/expected/moe_mini.txt")];
    for source in cases {
        let canonical=parse(source,TxtProfile::CanonicalV1,&Limits::default()).unwrap();
        let legacy=parse(source,TxtProfile::LegacyBodySpanV1,&Limits::default()).unwrap();
        assert_eq!(canonical.len(),legacy.len());
        for (c,l) in canonical.iter().zip(&legacy) {assert_eq!(c.key,l.key);assert_eq!(format!("{}\n",c.text),l.text);}
        assert_eq!(render(&canonical,TxtProfile::CanonicalV1,&Limits::default()).unwrap(),source);
        assert_eq!(render(&legacy,TxtProfile::LegacyBodySpanV1,&Limits::default()).unwrap(),source);
    }
}

#[test]
fn crlf_bom_blank_body_and_final_delimiter_without_lf_have_explicit_semantics() {
    let bytes="\u{feff}字\r\nfirst\r\n\r\n</>".as_bytes();
    let canonical=parse(bytes,TxtProfile::CanonicalV1,&Limits::default()).unwrap();
    let legacy=parse(bytes,TxtProfile::LegacyBodySpanV1,&Limits::default()).unwrap();
    assert_eq!(canonical[0].text,"first\n");assert_eq!(legacy[0].text,"first\r\n\r\n");
    let blank=parse(b"empty\n\n</>\n",TxtProfile::CanonicalV1,&Limits::default()).unwrap();assert_eq!(blank[0].text,"");
    assert_eq!(render(&blank,TxtProfile::CanonicalV1,&Limits::default()).unwrap(),b"empty\n\n</>\n");
}

#[test]
fn malformed_or_invalid_utf8_source_never_returns_a_partial_import() {
    for bytes in [b"".as_slice(),b"a\nbody\n",b"\nbody\n</>\n",b"a\n</>\n",b"a\nbody\rX\n</>\n",b"a\nbody\n</>\ntrailing",b"a\nzero\0x\n</>\n"] {
        assert_eq!(parse(bytes,TxtProfile::CanonicalV1,&Limits::default()).unwrap_err().code,ErrorCode::MalformedSource);
    }
    assert_eq!(parse(b"a\n\xff\n</>\n",TxtProfile::CanonicalV1,&Limits::default()).unwrap_err().code,ErrorCode::InvalidEncoding);
}

#[test]
fn unrepresentable_exports_are_refused_instead_of_silently_normalized() {
    for text in ["foo\n</>\nbar","zero\0x","body\r\n"] {
        assert_eq!(render(&[Entry {key:"a".into(),text:text.into()}],TxtProfile::CanonicalV1,&Limits::default()).unwrap_err().code,ErrorCode::UnrepresentableSource);
    }
    for text in ["body",""] {
        assert_eq!(render(&[Entry {key:"a".into(),text:text.into()}],TxtProfile::LegacyBodySpanV1,&Limits::default()).unwrap_err().code,ErrorCode::UnrepresentableSource);
    }
}

#[test]
fn text_count_line_and_payload_budgets_are_enforced() {
    let mut limits=Limits::default();limits.max_source_lines=2;
    assert_eq!(parse(b"a\nbody\n</>\n",TxtProfile::CanonicalV1,&limits).unwrap_err().code,ErrorCode::LimitExceeded);
    limits=Limits::default();limits.max_entries=1;
    assert_eq!(parse(b"a\nx\n</>\na\ny\n</>\n",TxtProfile::CanonicalV1,&limits).unwrap_err().code,ErrorCode::LimitExceeded);
    limits=Limits::default();limits.max_entry_bytes=1;
    assert_eq!(parse(b"a\nbody\n</>\n",TxtProfile::CanonicalV1,&limits).unwrap_err().code,ErrorCode::LimitExceeded);
}

#[test]
fn parser_checks_cancellation_within_a_long_definition() {
    let source=format!("a\n{}</>\n","line\n".repeat(300));let token=CancellationToken::default();
    let mut sink=|p:Progress|if p.phase==Phase::Parsing&&p.completed>100 {token.cancel();};
    assert_eq!(parse_txt(source.as_bytes(),TxtProfile::CanonicalV1,&Limits::default(),&mut JobContext::new(&token,&mut sink)).unwrap_err().code,ErrorCode::Cancelled);
}

#[test]
fn text_export_cancellation_and_commit_race_leave_existing_data_untouched() {
    for race in [false,true] {
        let dir=tempfile::tempdir().unwrap();let path=dir.path().join("out.txt");let token=CancellationToken::default();
        let mut acted=false;
        let mut sink=|p:Progress|if p.phase==Phase::Verifying&&!acted {
            if race {fs::write(&path,b"other job").unwrap();}else{token.cancel();}acted=true;
        };
        let result=write_txt(&[Entry {key:"a".into(),text:"body".into()}],&path,TxtProfile::CanonicalV1,&Limits::default(),&mut JobContext::new(&token,&mut sink));
        assert_eq!(result.unwrap_err().code,if race {ErrorCode::DestinationExists}else{ErrorCode::Cancelled});
        if race {assert_eq!(fs::read(&path).unwrap(),b"other job");}else{assert!(!path.exists());}
        assert_eq!(fs::read_dir(dir.path()).unwrap().count(),if race {1}else{0});
    }
}

#[test]
fn txt_pack_dictionary_export_roundtrips_profiles_and_both_mdx_encodings() {
    let source="a\nfirst\n\nlast\n</>\na\nsecond\n</>\nalias\n@@@LINK=a\n</>\n字\n中文\n</>\n";
    for profile in [TxtProfile::CanonicalV1,TxtProfile::LegacyBodySpanV1] {
        for encoding in [Encoding::Utf8,Encoding::Utf16] {
            let dir=tempfile::tempdir().unwrap();let mdx=dir.path().join("out.mdx");let txt=dir.path().join("out.txt");
            let limits=Limits::default();let token=CancellationToken::default();let mut sink=|_|{};
            let rows=parse(source.as_bytes(),profile,&limits).unwrap();
            let request=PackRequest {title:"TXT".into(),description:"Roundtrip".into(),encoding,entries:rows.clone()};
            pack_mdx(&request,&mdx,&limits,&mut JobContext::new(&token,&mut sink)).unwrap();
            let dict=Dictionary::open_studio_output(&mdx,&limits,&mut JobContext::new(&token,&mut sink)).unwrap();
            dict.export_txt(&txt,profile,&mut JobContext::new(&token,&mut sink)).unwrap();
            assert_eq!(parse(&fs::read(&txt).unwrap(),profile,&limits).unwrap(),rows);
        }
    }
}

#[test]
fn rust_cedict_matches_the_captured_original_output_bytes() {
    let fixture:serde_json::Value=serde_json::from_str(include_str!("../../../baseline/cases.json")).unwrap();
    let converted=convert(fixture["cedict"].as_str().unwrap().as_bytes(),&Limits::default()).unwrap();
    assert_eq!(converted.txt_profile,TxtProfile::CanonicalV1);
    assert_eq!(converted.primary_entries,5);assert_eq!(converted.traditional_entries,2);assert_eq!(converted.skipped_lines,1);
    assert_eq!(converted.comments.len(),1);
    assert_eq!(render(&converted.entries,TxtProfile::CanonicalV1,&Limits::default()).unwrap(),include_bytes!("../../../baseline/expected/cc_cedict.txt"));
}

#[test]
fn pinyin_tone_placement_and_legacy_case_neutral_quirks_are_preserved() {
    assert_eq!(cedict_pinyin("nu:3 lu:4 hao3 ma5").unwrap(),"nǚ lǜ hǎo ma");
    assert_eq!(cedict_pinyin("LU:4 NV5 MA0 OU3 LIU2").unwrap(),"lǜ nv MA ǒu liú");
    assert_eq!(cedict_pinyin("  nu:3  ").unwrap(),"  nǚ  ");
    assert_eq!(cedict_pinyin("ma٢").unwrap_err().code,ErrorCode::UnsupportedPolicy);
}

#[test]
fn cedict_comments_duplicates_xrefs_tags_and_skips_have_stable_order() {
    let converted=convert("# comment\n傳 传 [chuan2] /see 傳|传[Zhuan4] (old) CL: 個|个[ge4]/\n字 字 [zi4] /one/\n字 字 [zi4] /two/\nbad line\n".as_bytes(),&Limits::default()).unwrap();
    assert_eq!(converted.entries.iter().map(|e|e.key.as_str()).collect::<Vec<_>>(),vec!["传","傳","字","字"]);
    let text=&converted.entries[0].text;
    assert!(text.contains("entry://傳"));assert!(text.contains("<span class=\"cc_tag\">(old)</span>"));
    assert!(text.contains("<span class=\"cc_ie\">CL</span> :"));assert!(text.contains("</font></p>"));
    assert_eq!(converted.skipped_lines,1);
}

#[test]
fn empty_invalid_and_cancelled_cedict_do_not_produce_entries() {
    assert_eq!(convert(b"# comments only\ninvalid\n",&Limits::default()).unwrap_err().code,ErrorCode::MalformedSource);
    assert_eq!(convert(b"\xff",&Limits::default()).unwrap_err().code,ErrorCode::InvalidEncoding);
    let token=CancellationToken::default();token.cancel();let mut sink=|_|{};
    assert_eq!(convert_cedict_utf8(b"a a [a1] /a/\n",&Limits::default(),&mut JobContext::new(&token,&mut sink)).unwrap_err().code,ErrorCode::Cancelled);
}
