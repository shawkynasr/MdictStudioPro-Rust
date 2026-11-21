use serde::{Deserialize, Serialize};

pub const POLICY_ID: &str = "unicode16-literal-v1";
pub const POLICY_SHA256: &str = "f69d2e55d6b8c8d5fe33f764cc47b829bccc6d73aaff1791e1216328a1c24071";

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Entry { pub key: String, pub text: String }

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Encoding { Utf8, Utf16 }

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PackRequest {
    pub title: String,
    pub description: String,
    pub encoding: Encoding,
    pub entries: Vec<Entry>,
}

/// Application work budgets, not a bound on allocator RSS or engine expansion.
/// The first release intentionally retains the qualification size envelope.
#[derive(Clone, Debug)]
pub struct Limits {
    pub max_entries: usize,
    pub max_decoded_bytes: usize,
    pub max_key_bytes: usize,
    pub max_entry_bytes: usize,
    pub max_file_bytes: u64,
    pub max_metadata_bytes: usize,
    pub max_result_entries: usize,
    pub max_result_bytes: usize,
    pub max_source_lines: usize,
}
impl Default for Limits {
    fn default() -> Self {
        Self { max_entries: 1000, max_decoded_bytes: 8*1024*1024,
            max_key_bytes: 4096, max_entry_bytes: 1024*1024,
            max_file_bytes: 16*1024*1024, max_metadata_bytes: 64*1024,
            max_result_entries: 256, max_result_bytes: 2*1024*1024,
            max_source_lines: 1_000_000 }
    }
}

#[derive(Debug, Serialize)]
pub struct PackSummary {
    pub entries: usize, pub file_bytes: u64, pub policy: &'static str,
}

pub const RESOURCE_POLICY_ID: &str = "unicode16-resources-v1";

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Resource { pub key: String, pub bytes: Vec<u8> }

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResourcePackRequest {
    pub title: String, pub description: String, pub resources: Vec<Resource>,
}

#[derive(Debug, Serialize)]
pub struct ExtractionSummary { pub resources: usize, pub payload_bytes: usize }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all="snake_case")]
pub enum TxtProfile {
    /// One LF before the delimiter is structural, not definition content.
    CanonicalV1,
    /// Retain the raw body span, including its delimiter-preceding LF/CRLF.
    LegacyBodySpanV1,
}

#[derive(Debug, Serialize)]
pub struct TextSummary { pub entries: usize, pub file_bytes: usize, pub profile: TxtProfile }

#[derive(Debug, Serialize)]
pub struct ConversionResult {
    pub entries: Vec<Entry>, pub txt_profile: TxtProfile, pub comments: Vec<String>,
    pub primary_entries: usize, pub traditional_entries: usize, pub skipped_lines: usize,
}
