use crate::{Error, ErrorCode, Result};
use serde::Serialize;
use std::sync::{Arc, atomic::{AtomicBool, Ordering}};

#[derive(Clone, Default)]
pub struct CancellationToken(Arc<AtomicBool>);
impl CancellationToken {
    pub fn cancel(&self) { self.0.store(true, Ordering::Relaxed); }
    pub fn is_cancelled(&self) -> bool { self.0.load(Ordering::Relaxed) }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Phase { Preparing, Writing, Verifying, Indexing, Extracting, Parsing, Converting, Published }

#[derive(Clone, Debug, Serialize)]
pub struct Progress { pub phase: Phase, pub completed: usize, pub total: usize }

pub struct JobContext<'a> {
    cancellation: &'a CancellationToken,
    progress: &'a mut dyn FnMut(Progress),
}
impl<'a> JobContext<'a> {
    pub fn new(cancellation: &'a CancellationToken, progress: &'a mut dyn FnMut(Progress)) -> Self {
        Self { cancellation, progress }
    }
    pub(crate) fn check(&self) -> Result<()> {
        if self.cancellation.is_cancelled() {
            Err(Error::new(ErrorCode::Cancelled, "Job cancelled before commit"))
        } else { Ok(()) }
    }
    pub(crate) fn checkpoint(&mut self, phase: Phase, completed: usize, total: usize) -> Result<()> {
        self.check()?;
        (self.progress)(Progress { phase, completed, total });
        self.check()
    }
    pub(crate) fn published(&mut self, total: usize) {
        // Commit has succeeded. A late cancellation cannot turn it into failure.
        (self.progress)(Progress { phase: Phase::Published, completed: total, total });
    }
}
