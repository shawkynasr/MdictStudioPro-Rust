use crate::{casing::Casing, Error, ErrorCode, Limits, Resource, Result};
use std::{collections::BTreeMap, path::PathBuf};

fn unsafe_path(message: &str) -> Error { Error::new(ErrorCode::UnsafePath, message) }
fn collision() -> Error { Error::new(ErrorCode::PathCollision, "Resource paths alias or conflict as files/directories") }

/// Convert an archive key to a relative filesystem path, never an OS root.
/// One leading separator is the MDD archive-root marker; two are refused.
pub fn resource_relative_path(key: &str) -> Result<PathBuf> {
    if key.is_empty() || key.len() > 4096 { return Err(unsafe_path("Empty or oversized resource key")); }
    let normalized = key.replace('\\', "/");
    if normalized.starts_with("//") { return Err(unsafe_path("UNC or repeated leading separator")); }
    let relative = normalized.strip_prefix('/').unwrap_or(&normalized);
    let parts: Vec<_> = relative.split('/').collect();
    if parts.len() > 32 { return Err(unsafe_path("Resource path exceeds 32 components")); }
    for part in &parts {
        if part.is_empty() || *part == "." || *part == ".." || part.len() > 255
            || part.ends_with([' ', '.'])
            || part.chars().any(|c|c.is_control() || "<>:\"|?*".contains(c)) {
            return Err(unsafe_path("Resource path contains traversal, ambiguous or nonportable components"));
        }
        let base = part.split('.').next().unwrap_or("").trim_end_matches([' ', '.']).to_ascii_uppercase();
        let device = matches!(base.as_str(), "CON" | "PRN" | "AUX" | "NUL" | "CONIN$" | "CONOUT$")
            || ["COM", "LPT"].iter().any(|prefix|base.strip_prefix(*prefix).is_some_and(|n|
                matches!(n, "1"|"2"|"3"|"4"|"5"|"6"|"7"|"8"|"9"|"¹"|"²"|"³")));
        if device { return Err(unsafe_path("Reserved filesystem device name")); }
    }
    Ok(PathBuf::from(relative))
}

pub(crate) struct PlannedPath { pub parts: Vec<String> }

pub(crate) fn plan(resources: &[Resource], limits: &Limits) -> Result<Vec<PlannedPath>> {
    let casing = Casing::pinned16().map_err(|e|Error::new(ErrorCode::Internal,e.to_string()))?;
    // Track every directory prefix as well as each leaf. Equal directory
    // prefixes may be shared; aliases, duplicate leaves and prefix files may not.
    let mut nodes: BTreeMap<String, (String, bool)> = BTreeMap::new();
    let mut paths = Vec::new();
    for resource in resources {
        if resource.key.len() > limits.max_key_bytes {
            return Err(Error::new(ErrorCode::LimitExceeded,"Resource key byte budget exceeded"));
        }
        let relative = resource_relative_path(&resource.key)?;
        let parts: Vec<String> = relative.iter().map(|s|s.to_string_lossy().into_owned()).collect();
        let mut folded = String::new(); let mut raw = String::new();
        for (index, part) in parts.iter().enumerate() {
            if index != 0 { folded.push('/'); raw.push('/'); }
            folded.push_str(&casing.lower(part)); raw.push_str(part);
            let leaf = index + 1 == parts.len();
            if let Some((old_raw, old_leaf)) = nodes.get(&folded) {
                if old_raw != &raw || *old_leaf || leaf { return Err(collision()); }
            } else { nodes.insert(folded.clone(), (raw.clone(), leaf)); }
        }
        paths.push(PlannedPath { parts });
    }
    Ok(paths)
}
