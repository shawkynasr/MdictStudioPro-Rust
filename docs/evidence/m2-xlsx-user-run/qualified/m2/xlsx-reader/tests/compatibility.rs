use std::{cell::Cell,path::PathBuf};
use studio_xlsx::{read_xlsx,read_xlsx_bytes,Limits,Progress,ReadControl};

fn kit()->PathBuf {PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../baseline/xlsx-reader-kit")}
fn read(name:&str,sheet:Option<&str>)->studio_xlsx::Result<studio_xlsx::Table> {
    let cancelled=||false;let mut progress=|_|{};
    read_xlsx(&kit().join(name),sheet,&Limits::default(),&mut ReadControl::new(&cancelled,&mut progress))
}

#[test]
fn common_scalar_sheet_and_blank_row_cases_match_original_python_golden_rows() {
    let expected:serde_json::Value=serde_json::from_slice(&std::fs::read(kit().join("expected.json")).unwrap()).unwrap();
    for (name,case) in expected.as_object().unwrap() {
        let actual=read(case["file"].as_str().unwrap(),case["sheet"].as_str()).unwrap();
        assert_eq!(actual.sheet_name,case["sheet_name"].as_str().unwrap(),"{name}");
        assert_eq!(serde_json::to_value(actual.headers).unwrap(),case["headers"],"{name}");
        assert_eq!(serde_json::to_value(actual.rows).unwrap(),case["rows"],"{name}");
    }
}

#[test]
fn active_sheet_and_explicit_sheet_name_are_distinct() {
    assert_eq!(read("active.xlsx",None).unwrap().sheet_name,"العربية & 字");
    assert_eq!(read("active.xlsx",Some("First")).unwrap().sheet_name,"First");
    assert_eq!(read("active.xlsx",Some("missing")).unwrap_err().code,"sheet_not_found");
}

#[test]
fn unsupported_dates_and_malformed_or_external_layouts_fail_explicitly() {
    for (file,code) in [("date.xlsx","unsupported_cell"),("duration.xlsx","unsupported_cell"),
        ("no-dimension.xlsx","unsupported_workbook"),("external.xlsx","unsupported_workbook"),("invalid.xlsx","malformed_workbook")] {
        assert_eq!(read(file,None).unwrap_err().code,code,"{file}");
    }
}

#[test]
fn oversized_geometry_is_rejected_before_calamine_range_allocation() {
    let reached=Cell::new(false);let cancelled=||false;
    let mut progress=|p:Progress|if p.phase=="calamine_range" {reached.set(true);};
    let result=read_xlsx(&kit().join("oversized.xlsx"),None,&Limits::default(),&mut ReadControl::new(&cancelled,&mut progress));
    assert_eq!(result.unwrap_err().code,"limit_exceeded");assert!(!reached.get());
}

#[test]
fn cancellation_before_read_and_at_normalization_returns_no_partial_table() {
    let bytes=std::fs::read(kit().join("normalization.xlsx")).unwrap();
    let cancelled=||true;let mut sink=|_|{};
    assert_eq!(read_xlsx_bytes(&bytes,None,&Limits::default(),&mut ReadControl::new(&cancelled,&mut sink)).unwrap_err().code,"cancelled");
    let flag=Cell::new(false);let cancelled=||flag.get();
    let mut progress=|p:Progress|if p.phase=="normalization" {flag.set(true);};
    assert_eq!(read_xlsx_bytes(&bytes,None,&Limits::default(),&mut ReadControl::new(&cancelled,&mut progress)).unwrap_err().code,"cancelled");
}

#[test]
fn decoded_budget_does_not_return_a_truncated_success() {
    let mut limits=Limits::default();limits.max_decoded_bytes=1;
    let cancelled=||false;let mut sink=|_|{};
    assert_eq!(read_xlsx(&kit().join("normalization.xlsx"),None,&limits,&mut ReadControl::new(&cancelled,&mut sink)).unwrap_err().code,"limit_exceeded");
}
