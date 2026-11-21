//! Application-owned dictionary API. This first slice handles bounded Studio
//! MDX output; it is not yet an arbitrary-dictionary or hard-memory-limit API.
mod casing;
mod engine;
mod error;
mod job;
mod model;

pub use engine::{pack_mdx, Dictionary};
pub use error::{Error, ErrorCode, Result};
pub use job::{CancellationToken, JobContext, Phase, Progress};
pub use model::{Encoding, Entry, Limits, PackRequest, PackSummary, POLICY_ID, POLICY_SHA256};
