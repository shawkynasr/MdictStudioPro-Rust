# Isolate lookup policy before further native imports

The uploaded v4 native-wire report passes all sixteen structural/header checks,
with encoded NULs in every record of all eight MDX files. It also reports
successful Rust tests, fixture builds and interop. Its metadata inventory stays
91 passed, 10 failed (stylesheet/XML line normalization), 2 unsupported and
8 blocked. This aggregate report is retained unchanged; the nested reports and
runtime logs were not attached. It does not demonstrate a fixed native crash.

## Revision 5: a separate diagnostic ordering profile

The legacy profiles remove ASCII punctuation and spaces for MDX ordering while
the builder declares StripKey=No. The optional new HeaderLiteralC profile keeps
punctuation and whitespace and compares Unicode scalar lowercase strings under
C-style lexical ordering. This matches the declared comparison policy tested
here, without changing reader normalization or the two legacy profiles.

This is a candidate profile, not a decision to replace the app's historical
sorting options. It does not prove the native reader uses exactly this
collation. Python and Rust Unicode lowercase equivalence is tested only for
these fixture keys, not every Unicode scalar or full Unicode case folding.

V5 retains v4 writer bytes for record/header generation; the only engine source
addition is the optional comparator variant. Preparation creates a new vendor
directory, never edits v4, and verifies the published crate checksum. Source
verification reverses the exact additions back to the passing v2 source hashes.
The original Cargo.lock and legacy-sort/Cargo.lock remain unchanged. The new
workspace lock copies the pinned dependency graph, changing only its own root
package name; it is run with --locked.

## Run offline

Update the project files while keeping .venv and existing vendor directories.
Keep both readers closed and use a project directory outside their search
folders. From the project root run:

```sh
.venv/bin/python scripts/minimal_reader_controls.py --output minimal-out
```

The driver prepares v5, reruns the legacy experiment's tests with v5 selected,
then builds six MDX files (three controls in UTF-8 and UTF-16):

| Control | Coverage |
|---|---|
| 01-plain | Six ordinary lowercase Latin keys and plain text |
| 02-punctuation | Spaces, punctuation, case variants, duplicates, missing keys |
| 03-multilingual | Arabic, Chinese including supplementary CJK, accented case |

All controls have an empty StyleSheet, no numeric style markers, no redirects,
no scripts, no MDD and no external resources. Tiny key-block targets exercise
cross-block lookup. Python independently checks exact physical key/text order;
Rust exercises exact-first lookup, duplicate retention, case fallback and absent
queries. The structural auditor checks all block lengths/checksums, key summary
boundaries and offsets. The v4 wire contract still applies. A file list and
SHA-256 identities are included; raw Rust observations and logs stay alongside.

Return **minimal-out/minimal-controls-report.json**, and the referenced log if
any step fails. No dependency upgrade is required. Use a new output directory
for a repeat run.

## Native testing remains a separate step

The driver never opens MDict or GoldenDict. Its successful status is
offline_controls_passed_native_untested; its reader-results.csv starts NOT_RUN.
Keep generated files outside all reader scan folders pending report review.

After that review, test one plain UTF-8 MDX by itself first, then punctuation
and multilingual controls, and finally the corresponding UTF-16 files. Keep
the previously crashing pairs out. A native startup failure stops that reader's
sequence; successful enumeration must also be followed by actual key lookups.
Stylesheets and MDD resources return only after the minimal controls work.
No native crash fix, stylesheet fix, resource rendering, production qualification
or M1 completion is claimed by this experiment.

Rust/Cargo remain unavailable in the authoring environment. The new Rust
workspace must compile and pass its runtime checks on the user's machine.
