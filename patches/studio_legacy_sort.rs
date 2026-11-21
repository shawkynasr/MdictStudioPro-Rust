//! Experimental compatibility profiles for the Python writer under LC_COLLATE=C.
//! Physical order only; this module never changes reader lookup normalization.
use std::cmp::Ordering;

/// Optional legacy physical ordering. Upstream behavior remains the default.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LegacySort {
    /// Python Unicode lowercase and its legacy punctuation regex, C locale.
    MdictUtilsC,
    /// ASCII A-Z folding and the legacy punctuation regex, C locale.
    MdxBuilderC,
}

fn comparison_key(word: &str, profile: LegacySort, is_mdd: bool) -> String {
    let folded = match profile {
        LegacySort::MdictUtilsC => word.to_lowercase(),
        LegacySort::MdxBuilderC => word.to_ascii_lowercase(),
    };
    if is_mdd {
        return folded;
    }
    // Deliberately preserve '\\': the legacy unescaped character class omits it.
    // Only ASCII space is removed; tabs and other Unicode whitespace survive.
    folded.chars().filter(|c| {
        *c != ' ' && (!c.is_ascii_punctuation() || *c == '\\')
    }).collect()
}

pub(super) fn compare(profile: LegacySort, is_mdd: bool, left: &str, right: &str) -> Ordering {
    // UTF-8 string order matches Unicode scalar order and our Python C-locale
    // oracle for valid scalar strings. Stable caller sort preserves tied input.
    comparison_key(left, profile, is_mdd).cmp(&comparison_key(right, profile, is_mdd))
}
