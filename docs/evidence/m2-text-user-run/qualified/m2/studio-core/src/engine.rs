use crate::{casing::Casing, CancellationToken, Encoding, Entry, Error, ErrorCode,
    JobContext, Limits, PackRequest, PackSummary, Phase, Result, POLICY_ID, POLICY_SHA256};
use mdictlib::{ChecksumPolicy, LegacySort, MdxBuilder, MdxFile, OpenOptions,
    WriteEncoding, WriteOptions};
use std::{collections::BTreeMap, fs, path::Path};

fn invalid(message: &str) -> Error { Error::new(ErrorCode::InvalidInput, message) }
fn limit(message: &str) -> Error { Error::new(ErrorCode::LimitExceeded, message) }
fn sum(left: usize, right: usize) -> Result<usize> {
    left.checked_add(right).ok_or_else(||limit("Byte counter overflow"))
}
fn policy() -> Result<Casing> {
    Casing::pinned16().map_err(|error| Error::new(ErrorCode::Internal, error.to_string()))
}
fn key(key: &str, limits: &Limits) -> Result<()> {
    if key.is_empty() || key.contains(['\0', '\r', '\n']) {
        return Err(invalid("Expected a nonempty key without NUL or line breaks"));
    }
    if key.len() > limits.max_key_bytes { return Err(limit("Key byte budget exceeded")); }
    Ok(())
}
fn row(entry: &Entry, limits: &Limits) -> Result<usize> {
    key(&entry.key, limits)?;
    if entry.text.contains('\0') { return Err(invalid("Definition contains NUL")); }
    if entry.text.len() > limits.max_entry_bytes { return Err(limit("Definition byte budget exceeded")); }
    sum(entry.key.len(), entry.text.len())
}
fn metadata(request: &PackRequest, limits: &Limits) -> Result<()> {
    if sum(request.title.len(), request.description.len())? > limits.max_metadata_bytes {
        return Err(limit("Metadata byte budget exceeded"));
    }
    for text in [&request.title, &request.description] {
        // Multiline/general XML metadata serialization is a later contract.
        if text.chars().any(|c| c.is_control() || matches!(c, '\u{fffe}' | '\u{ffff}')) {
            return Err(invalid("This slice accepts single-line metadata without control characters"));
        }
    }
    Ok(())
}

/// Owned, bounded index for Studio outputs. Does not call the library locator.
/// Input file/block decoding is not yet protected by a hard allocation limit.
pub struct Dictionary {
    rows: Vec<Entry>,
    exact: BTreeMap<String, Vec<usize>>,
    normalized: BTreeMap<String, Vec<usize>>,
    policy: Casing,
    limits: Limits,
    title: String,
    description: String,
}
impl Dictionary {
    pub fn open_studio_output(path: &Path, limits: &Limits, job: &mut JobContext<'_>) -> Result<Self> {
        Self::open(path, limits, job, Phase::Indexing)
    }
    fn open(path: &Path, limits: &Limits, job: &mut JobContext<'_>, phase: Phase) -> Result<Self> {
        job.checkpoint(phase, 0, 0)?;
        if fs::metadata(path)?.len() > limits.max_file_bytes { return Err(limit("Input file byte budget exceeded")); }
        let options = OpenOptions::new().with_checksum_policy(ChecksumPolicy::Verify);
        let file = MdxFile::open_with_options(path, &options)?;
        let attrs: BTreeMap<String,String> = file.header().attributes().map(|(k,v)|(k.to_owned(),v.to_owned())).collect();
        for (name, expected) in [("GeneratedByEngineVersion", "2.0"), ("StudioCasingPolicy", POLICY_ID),
            ("StudioCasingDataSha256", POLICY_SHA256), ("StripKey", "No"), ("KeyCaseSensitive", "No"),
            ("Format", "Html"), ("StyleSheet", "")] {
            if attrs.get(name).map(String::as_str) != Some(expected) {
                return Err(Error::new(ErrorCode::UnsupportedPolicy, format!("Unsupported or missing {name}")));
            }
        }
        if !["No", "no", "0", ""].contains(&attrs.get("Encrypted").map(String::as_str).unwrap_or("No")) {
            return Err(Error::new(ErrorCode::UnsupportedPolicy, "Encrypted dictionaries are outside this slice"));
        }
        if !matches!(attrs.get("Encoding").map(String::as_str), Some("UTF-8" | "UTF-16")) {
            return Err(Error::new(ErrorCode::UnsupportedPolicy, "Only UTF-8 and UTF-16 Studio outputs are supported"));
        }
        let declared = usize::try_from(file.len()).map_err(|_|limit("Entry count overflow"))?;
        if declared == 0 { return Err(invalid("Empty dictionary")); }
        if declared > limits.max_entries { return Err(limit("Entry count budget exceeded")); }
        let mut result = Self { rows: Vec::new(), exact: BTreeMap::new(), normalized: BTreeMap::new(),
            policy: policy()?, limits: limits.clone(),
            title: attrs.get("Title").cloned().unwrap_or_default(),
            description: attrs.get("Description").cloned().unwrap_or_default() };
        let mut bytes = 0;
        let mut previous: Option<String> = None;
        for physical in file.keys() {
            job.checkpoint(phase, result.rows.len(), declared)?;
            let physical = physical?;
            key(physical.key(), limits)?;
            // Record decoding occurs inside the engine before our byte check.
            let value = file.entry_at(physical.ordinal())?.ok_or_else(||Error::new(ErrorCode::Integrity, "Missing physical record"))?;
            if value.text().len() > limits.max_entry_bytes { return Err(limit("Definition byte budget exceeded")); }
            if value.text().contains('\0') { return Err(invalid("Definition contains NUL")); }
            // Refuse over-budget data before making the adapter's owned copy.
            bytes = sum(bytes, sum(physical.key().len(), value.text().len())?)?;
            if bytes > limits.max_decoded_bytes || result.rows.len() >= limits.max_entries {
                return Err(limit("Decoded dictionary budget exceeded"));
            }
            let entry = Entry { key: physical.key().to_owned(), text: value.text().to_owned() };
            let normalized = result.policy.lower(&entry.key);
            if previous.as_ref().is_some_and(|p|p > &normalized) {
                return Err(Error::new(ErrorCode::Integrity, "Physical keys violate the persisted casing policy"));
            }
            previous = Some(normalized.clone());
            let ordinal = result.rows.len();
            result.exact.entry(entry.key.clone()).or_default().push(ordinal);
            result.normalized.entry(normalized).or_default().push(ordinal);
            result.rows.push(entry);
        }
        if result.rows.len() != declared { return Err(Error::new(ErrorCode::Integrity, "Incomplete physical scan")); }
        job.checkpoint(phase, declared, declared)?;
        Ok(result)
    }

    pub fn len(&self) -> usize { self.rows.len() }
    pub fn is_empty(&self) -> bool { self.rows.is_empty() }
    pub fn title(&self) -> &str { &self.title }
    pub fn description(&self) -> &str { &self.description }
    pub fn export_txt(&self,destination:&Path,profile:crate::TxtProfile,job:&mut JobContext<'_>)->Result<crate::TextSummary> {
        crate::write_txt(&self.rows,destination,profile,&self.limits,job)
    }

    /// All matches or a budget error; never silently drops duplicate payloads.
    pub fn lookup(&self, query: &str, cancellation: &CancellationToken) -> Result<Vec<Entry>> {
        if cancellation.is_cancelled() { return Err(Error::new(ErrorCode::Cancelled, "Lookup cancelled")); }
        key(query, &self.limits)?;
        let normalized = self.policy.lower(query);
        let selected = self.exact.get(query).or_else(||self.normalized.get(&normalized));
        let Some(selected) = selected else { return Ok(Vec::new()); };
        if selected.len() > self.limits.max_result_entries { return Err(limit("Result count budget exceeded")); }
        let mut bytes = 0;
        for ordinal in selected {
            if cancellation.is_cancelled() { return Err(Error::new(ErrorCode::Cancelled, "Lookup cancelled")); }
            let entry = &self.rows[*ordinal];
            bytes = sum(bytes, sum(entry.key.len(), entry.text.len())?)?;
            if bytes > self.limits.max_result_bytes { return Err(limit("Result byte budget exceeded")); }
        }
        let mut rows = Vec::new();
        for ordinal in selected {
            if cancellation.is_cancelled() { return Err(Error::new(ErrorCode::Cancelled, "Lookup cancelled")); }
            rows.push(self.rows[*ordinal].clone());
        }
        Ok(rows)
    }
}

pub fn pack_mdx(request: &PackRequest, destination: &Path, limits: &Limits,
    job: &mut JobContext<'_>) -> Result<PackSummary> {
    job.checkpoint(Phase::Preparing, 0, request.entries.len())?;
    if fs::symlink_metadata(destination).is_ok() {
        return Err(Error::new(ErrorCode::DestinationExists, "Destination already exists"));
    }
    if request.entries.is_empty() { return Err(invalid("No entries supplied")); }
    if request.entries.len() > limits.max_entries { return Err(limit("Entry count budget exceeded")); }
    metadata(request, limits)?;
    let casing = policy()?;
    let mut bytes = 0;
    let mut ordered = Vec::new();
    for (index, entry) in request.entries.iter().enumerate() {
        job.checkpoint(Phase::Preparing, index, request.entries.len())?;
        bytes = sum(bytes, row(entry, limits)?)?;
        if bytes > limits.max_decoded_bytes { return Err(limit("Decoded input budget exceeded")); }
        ordered.push((casing.lower(&entry.key), entry));
    }
    ordered.sort_by(|left, right|left.0.cmp(&right.0));
    job.checkpoint(Phase::Writing, 0, ordered.len())?;
    let encoding = match request.encoding { Encoding::Utf8 => WriteEncoding::Utf8, Encoding::Utf16 => WriteEncoding::Utf16Le };
    let options = WriteOptions::new().with_encoding(encoding).with_legacy_sort(LegacySort::PreserveInput)
        .with_key_block_target_bytes(16*1024).with_record_block_target_bytes(64*1024);
    let mut builder = MdxBuilder::with_options(options);
    for (name, value) in [("Title", request.title.as_str()), ("Description", request.description.as_str()),
        ("Format", "Html"), ("Compact", "No"), ("Compat", "Yes"), ("StyleSheet", ""),
        ("RegisterBy", ""), ("StudioCasingPolicy", POLICY_ID), ("StudioCasingDataSha256", POLICY_SHA256)] {
        builder.header_attribute(name, value)?;
    }
    for (index, (_, entry)) in ordered.iter().enumerate() {
        job.checkpoint(Phase::Writing, index, ordered.len())?;
        builder.add_entry(&entry.key, &entry.text)?;
    }
    let parent = destination.parent().filter(|p|!p.as_os_str().is_empty()).unwrap_or(Path::new("."));
    // Sibling temporary file keeps publication on the same filesystem.
    let mut temporary = tempfile::NamedTempFile::new_in(parent)?;
    builder.finish(temporary.as_file_mut())?;
    temporary.as_file().sync_all()?;
    let file_bytes = temporary.as_file().metadata()?.len();
    if file_bytes > limits.max_file_bytes { return Err(limit("Output file byte budget exceeded")); }
    let verified = Dictionary::open(temporary.path(), limits, job, Phase::Verifying)?;
    if verified.rows.len() != ordered.len() || verified.rows.iter().zip(&ordered).any(|(a,(_,b))|a != *b)
        || verified.title != request.title || verified.description != request.description {
        return Err(Error::new(ErrorCode::Integrity, "Output rows or duplicate order differ"));
    }
    // Publish without replacing any destination that appeared during the job.
    // No rollback is attempted after this commit succeeds.
    job.check()?;
    temporary.persist_noclobber(destination).map_err(|error|Error::from(error.error))?;
    job.published(ordered.len());
    Ok(PackSummary { entries: ordered.len(), file_bytes, policy: POLICY_ID })
}
