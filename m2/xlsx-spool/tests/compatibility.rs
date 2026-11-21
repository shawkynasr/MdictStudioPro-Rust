use std::{cell::Cell,collections::BTreeMap,path::{Path,PathBuf}};
use studio_xlsx_spool::{read_to_spool,Limits,ReadControl};
fn kit()->PathBuf {PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../baseline/xlsx-reader-kit")}
fn rows(path:&Path)->Vec<BTreeMap<String,String>> {std::fs::read_to_string(path).unwrap().lines().map(|line|serde_json::from_str(line).unwrap()).collect()}
#[test]fn existing_python_golden_rows_match_disk_spool() {
 let cases:serde_json::Value=serde_json::from_slice(&std::fs::read(kit().join("expected.json")).unwrap()).unwrap();
 for(name,case)in cases.as_object().unwrap() {let no=||false;let mut cb=|_|{};let control=ReadControl::new(&no,&mut cb);let spool=read_to_spool(&kit().join(case["file"].as_str().unwrap()),case["sheet"].as_str(),&Limits::default(),&control).unwrap();assert_eq!(serde_json::to_value(&spool.receipt.headers).unwrap(),case["headers"],"{name}");assert_eq!(serde_json::to_value(rows(spool.rows_path())).unwrap(),case["rows"],"{name}");assert_eq!(spool.receipt.worksheet,case["sheet_name"].as_str().unwrap());let private=spool.private_path().to_owned();drop(spool);assert!(!private.exists());}
}
#[test]fn legacy_calamine_table_and_new_rows_agree_on_common_profile() {
 let no=||false;let mut old_progress=|_|{};let old=studio_xlsx::read_xlsx(&kit().join("normalization.xlsx"),None,&studio_xlsx::Limits::default(),&mut studio_xlsx::ReadControl::new(&no,&mut old_progress)).unwrap();
 let mut cb=|_|{};let spool=read_to_spool(&kit().join("normalization.xlsx"),None,&Limits::default(),&ReadControl::new(&no,&mut cb)).unwrap();assert_eq!(spool.receipt.headers,old.headers);assert_eq!(rows(spool.rows_path()),old.rows);
}
#[test]fn unsupported_layouts_dates_and_duration_refuse_cleanly() {
 for(file,code)in [("date.xlsx","unsupported_cell"),("duration.xlsx","unsupported_cell"),("no-dimension.xlsx","unsupported_workbook"),("external.xlsx","unsupported_workbook"),("invalid.xlsx","malformed_workbook")] {let no=||false;let mut cb=|_|{};let result=read_to_spool(&kit().join(file),None,&Limits::default(),&ReadControl::new(&no,&mut cb));assert_eq!(result.err().unwrap().code,code,"{file}");}
}
#[test]fn cancellation_at_normalization_and_reopen_and_lowered_geometry_refuse() {
 for phase in ["snapshot","shared_strings","normalize_rows","verify_rows","complete"] {let flag=Cell::new(false);let cancelled=||flag.get();let mut cb=|p:studio_xlsx_spool::Progress|if p.phase==phase {flag.set(true);};let result=read_to_spool(&kit().join("normalization.xlsx"),None,&Limits::default(),&ReadControl::new(&cancelled,&mut cb));assert_eq!(result.err().unwrap().code,"cancelled");}
 let no=||false;let mut cb=|_|{};let mut limits=Limits::default();limits.cells=1;assert_eq!(read_to_spool(&kit().join("normalization.xlsx"),None,&limits,&ReadControl::new(&no,&mut cb)).err().unwrap().code,"limit_exceeded");
}
#[test]fn public_rust_api_cannot_grow_profile_ceilings() {
 let no=||false;let mut cb=|_|{};let mut limits=Limits::default();limits.rows+=1;
 assert_eq!(read_to_spool(&kit().join("normalization.xlsx"),None,&limits,&ReadControl::new(&no,&mut cb)).err().unwrap().code,"invalid_input");
}
