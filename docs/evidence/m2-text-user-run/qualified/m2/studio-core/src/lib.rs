//! Application-owned dictionary/resource API for bounded Studio MDX/MDD.
//! This is not yet an arbitrary-dictionary or hard-memory-limit API.
mod casing;
mod engine;
mod error;
mod job;
mod model;
mod resources;
mod resource_paths;
mod safe_fs;
mod text;
mod cedict;

pub use engine::{pack_mdx, Dictionary};
pub use error::{Error, ErrorCode, Result};
pub use job::{CancellationToken, JobContext, Phase, Progress};
pub use model::{Encoding, Entry, Limits, PackRequest, PackSummary, POLICY_ID, POLICY_SHA256};
pub use resources::{pack_mdd, ResourceArchive};
pub use resource_paths::resource_relative_path;
pub use model::{Resource, ResourcePackRequest, ExtractionSummary, RESOURCE_POLICY_ID};
pub use model::{TxtProfile, TextSummary, ConversionResult};
pub use text::{parse_txt, read_txt, render_txt, write_txt};
pub use cedict::{convert_cedict_utf8, convert_cedict_file, cedict_pinyin};
