use std::fs;
use studio_core::*;

fn request(encoding: Encoding) -> PackRequest {
    PackRequest { title: "قاموس & 字".into(), description: "Literal <HTML> metadata".into(), encoding,
        entries: vec![Entry { key: "ΟΣ".into(), text: "first\n\nlast\n".into() },
            Entry { key: "ος".into(), text: "other".into() },
            Entry { key: "ΟΣ".into(), text: "second".into() },
            Entry { key: "A꟎Σ".into(), text: "frozen16".into() }] }
}
fn pack(request: &PackRequest, path: &std::path::Path, limits: &Limits) -> Result<PackSummary> {
    let token = CancellationToken::default(); let mut sink = |_| {};
    pack_mdx(request, path, limits, &mut JobContext::new(&token, &mut sink))
}
fn open(path: &std::path::Path, limits: &Limits) -> Result<Dictionary> {
    let token = CancellationToken::default(); let mut sink = |_| {};
    Dictionary::open_studio_output(path, limits, &mut JobContext::new(&token, &mut sink))
}

#[test]
fn both_encodings_reopen_with_exact_duplicates_context_and_unmodified_text() {
    for encoding in [Encoding::Utf8, Encoding::Utf16] {
        let dir = tempfile::tempdir().unwrap(); let path = dir.path().join("output.mdx");
        let input = request(encoding); let limits = Limits::default(); let token = CancellationToken::default();
        assert_eq!(pack(&input, &path, &limits).unwrap().entries, 4);
        let dictionary = open(&path, &limits).unwrap();
        assert_eq!(dictionary.title(), input.title);
        assert_eq!(dictionary.description(), input.description);
        let exact = dictionary.lookup("ΟΣ", &token).unwrap();
        assert_eq!(exact, vec![input.entries[0].clone(), input.entries[2].clone()]);
        assert_eq!(dictionary.lookup("Ος", &token).unwrap(), vec![input.entries[0].clone(), input.entries[1].clone(), input.entries[2].clone()]);
        assert!(dictionary.lookup("a꟏Σ", &token).unwrap().is_empty());
        assert!(dictionary.lookup("missing", &token).unwrap().is_empty());
    }
}

#[test]
fn invalid_and_oversized_requests_leave_no_temporary_files() {
    let dir = tempfile::tempdir().unwrap(); let path = dir.path().join("output.mdx");
    let mut limits = Limits::default(); limits.max_entries = 1;
    assert_eq!(pack(&request(Encoding::Utf8), &path, &limits).unwrap_err().code, ErrorCode::LimitExceeded);
    let mut input = request(Encoding::Utf8); input.entries[0].key = "bad\0key".into();
    assert_eq!(pack(&input, &path, &Limits::default()).unwrap_err().code, ErrorCode::InvalidInput);
    input = request(Encoding::Utf8); input.description = "multiline\nmetadata".into();
    assert_eq!(pack(&input, &path, &Limits::default()).unwrap_err().code, ErrorCode::InvalidInput);
    assert_eq!(fs::read_dir(dir.path()).unwrap().count(), 0);
}

#[test]
fn cancellation_before_start_and_during_verification_never_publishes() {
    for during_verification in [false, true] {
        let dir = tempfile::tempdir().unwrap(); let path = dir.path().join("output.mdx");
        let token = CancellationToken::default();
        if !during_verification { token.cancel(); }
        let mut sink = |p: Progress| { if p.phase == Phase::Verifying { token.cancel(); } };
        let result = pack_mdx(&request(Encoding::Utf8), &path, &Limits::default(), &mut JobContext::new(&token, &mut sink));
        assert_eq!(result.unwrap_err().code, ErrorCode::Cancelled);
        assert_eq!(fs::read_dir(dir.path()).unwrap().count(), 0);
    }
}

#[test]
fn destination_created_during_validation_is_never_overwritten() {
    let dir = tempfile::tempdir().unwrap(); let path = dir.path().join("output.mdx");
    let token = CancellationToken::default(); let mut appeared = false;
    let mut sink = |p: Progress| {
        if p.phase == Phase::Verifying && !appeared { fs::write(&path, b"other job").unwrap(); appeared = true; }
    };
    let result = pack_mdx(&request(Encoding::Utf8), &path, &Limits::default(), &mut JobContext::new(&token, &mut sink));
    assert_eq!(result.unwrap_err().code, ErrorCode::DestinationExists);
    assert_eq!(fs::read(&path).unwrap(), b"other job");
    assert_eq!(fs::read_dir(dir.path()).unwrap().count(), 1);
}

#[test]
fn cancellation_after_commit_keeps_success_and_published_file() {
    let dir = tempfile::tempdir().unwrap(); let path = dir.path().join("output.mdx");
    let token = CancellationToken::default();
    let mut sink = |p: Progress| { if p.phase == Phase::Published { token.cancel(); } };
    assert!(pack_mdx(&request(Encoding::Utf8), &path, &Limits::default(), &mut JobContext::new(&token, &mut sink)).is_ok());
    assert!(path.is_file()); assert!(token.is_cancelled());
}

#[test]
fn lookup_budget_errors_do_not_silently_truncate_duplicates() {
    let dir = tempfile::tempdir().unwrap(); let path = dir.path().join("output.mdx");
    pack(&request(Encoding::Utf8), &path, &Limits::default()).unwrap();
    let mut limits = Limits::default(); limits.max_result_entries = 1;
    let dictionary = open(&path, &limits).unwrap(); let token = CancellationToken::default();
    assert_eq!(dictionary.lookup("ΟΣ", &token).unwrap_err().code, ErrorCode::LimitExceeded);
    let mut limits = Limits::default(); limits.max_result_bytes = 1;
    let dictionary = open(&path, &limits).unwrap();
    assert_eq!(dictionary.lookup("ΟΣ", &token).unwrap_err().code, ErrorCode::LimitExceeded);
    token.cancel(); assert_eq!(dictionary.lookup("missing", &token).unwrap_err().code, ErrorCode::Cancelled);
}

#[test]
fn strict_reopen_reports_header_checksum_corruption() {
    let dir = tempfile::tempdir().unwrap(); let path = dir.path().join("output.mdx");
    pack(&request(Encoding::Utf8), &path, &Limits::default()).unwrap();
    let mut bytes = fs::read(&path).unwrap();
    let header_len = u32::from_be_bytes(bytes[..4].try_into().unwrap()) as usize;
    bytes[4 + header_len] ^= 1; fs::write(&path, bytes).unwrap();
    let error = match open(&path, &Limits::default()) { Ok(_) => panic!("corrupt file accepted"), Err(e) => e };
    assert_eq!(error.code, ErrorCode::Integrity);
}

#[test]
fn complete_output_budget_is_checked_before_commit() {
    let dir = tempfile::tempdir().unwrap(); let path = dir.path().join("output.mdx");
    let mut limits = Limits::default(); limits.max_file_bytes = 1;
    assert_eq!(pack(&request(Encoding::Utf8), &path, &limits).unwrap_err().code, ErrorCode::LimitExceeded);
    assert_eq!(fs::read_dir(dir.path()).unwrap().count(), 0);
}

#[test]
fn unversioned_foreign_dictionary_is_refused_before_index_use() {
    let dir = tempfile::tempdir().unwrap(); let path = dir.path().join("foreign.mdx");
    let mut builder = mdictlib::MdxBuilder::new();
    builder.add_entry("word", "body").unwrap();
    builder.finish(fs::File::create(&path).unwrap()).unwrap();
    let error = match open(&path, &Limits::default()) { Ok(_) => panic!("unversioned file accepted"), Err(e) => e };
    assert_eq!(error.code, ErrorCode::UnsupportedPolicy);
}
