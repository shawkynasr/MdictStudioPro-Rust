use serde::Serialize;
use std::fmt;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCode {
    InvalidInput, UnsupportedPolicy, LimitExceeded, Cancelled,
    DestinationExists, Integrity, Io, Engine, Internal,
}

#[derive(Debug, Serialize)]
pub struct Error { pub code: ErrorCode, pub message: String }
pub type Result<T> = std::result::Result<T, Error>;

impl Error {
    pub(crate) fn new(code: ErrorCode, message: impl Into<String>) -> Self {
        Self { code, message: message.into() }
    }
}
impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result { write!(f, "{:?}: {}", self.code, self.message) }
}
impl std::error::Error for Error {}
impl From<std::io::Error> for Error {
    fn from(error: std::io::Error) -> Self {
        let code = if error.kind() == std::io::ErrorKind::AlreadyExists {
            ErrorCode::DestinationExists
        } else { ErrorCode::Io };
        Self::new(code, error.to_string())
    }
}
impl From<mdictlib::Error> for Error {
    fn from(error: mdictlib::Error) -> Self {
        let code = if matches!(&error, mdictlib::Error::ChecksumMismatch { .. }) {
            ErrorCode::Integrity
        } else { ErrorCode::Engine };
        Self::new(code, error.to_string())
    }
}
