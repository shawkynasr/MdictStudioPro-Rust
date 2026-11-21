# M2 isolated XLSX reader and normalization boundary

The common-cell XLSX reader passed on the user's Intel Mac (macOS 15.8.2) on
2026-10-29. All 12 supported cases matched the original helper's headers/rows;
all seven controlled refusals had the right error code. Dependency resolution
and the Rust workspace tests passed, for 14 successful commands and seven
expected error exits in this first run. The report, exact generated lock and 32
matching source/data snapshots are retained in `docs/evidence/m2-xlsx-user-run`.
All 35 protected core/oracle/lock identities matched. Individual test logs were
not supplied; no Rust test count or cross-platform acceptance is inferred.
No rerun is requested. M1 remains complete and the
qualified MDX, MDD, TXT and CC-CEDICT code/locks remain unchanged. This step does
not port the five MOE converters or complete M2.

## API and dependency isolation

`m2/xlsx-reader` is an independent workspace/package, `studio-xlsx`. Its library
exposes `read_xlsx`, `read_xlsx_bytes`, `Table`, `Limits`, `ReadControl` and typed
errors. Its output is an ordered vector of string dictionaries suitable for the
MOE converter ports. It is not yet a dependency of studio-core or the GUI.

Direct dependencies are exact-pinned: calamine 0.31.0, quick-xml 0.38.3, zip
4.6.1, serde 1.0.229 and serde_json 1.0.154. The first Mac run creates only this
new workspace's Cargo.lock, then uses --locked. That generated lock has now been
reviewed and retained in this package, so normal future builds use it directly.
It contains 39 packages; the 18 shared registry name/version/checksum identities
match the qualified core graph. The original report includes the complete lock receipt.
Existing root/M1/M2 dictionary workspaces and their locked graphs are protected
before and after verification. No cache patching or old lock regeneration occurs.

## Original helper contract

The reference remains the unchanged `baseline/legacy/excel_utils.py`, using
openpyxl 3.1.5 with read_only=True and data_only=True. Default selection means
the active sheet, not necessarily the first sheet. Named selection is explicit.
Row one supplies headers, including leading missing columns. Headers use
str(value).strip(); missing headers use col_N. Duplicate normalized headers
overwrite left to right. Only rows with every original value None are skipped;
an empty/whitespace string can retain a blank-looking row.

Body cells follow the original helper: None becomes empty string, booleans use
True/False, integral floats have no .0, integer lexemes remain exact, and other
scalar strings are stripped using the frozen Python whitespace set. Numeric
headers differ: a float 1.0 stays the header `1.0`, whereas an integer header
becomes `1`. Scientific notation uses Python thresholds/padded exponents.

## Why the OOXML scalar sidecar is necessary

Calamine validates and loads the selected worksheet range. The sidecar reads
the immutable package snapshot to preserve details needed by the original
helper: activeTab and relationship selection, declared dimensions/leading blanks,
raw numeric type lexemes, missing formula caches versus empty strings, and raw
inline/shared text. Values are normalized from those scalar records while
Calamine's cell classification rejects date/duration values outside this profile.

The sidecar deliberately preserves literal `_x000D_` text when openpyxl does;
Calamine's Excel-escape decoding is not silently substituted. Shared-string
`x005F_` handling follows the original openpyxl reader. Rich string runs are
joined and phonetic runs excluded. Formulas are never evaluated: cached values
are used and an absent/empty cache is None, matching data_only behavior.

Integer XML values beyond f64's exact integer precision use their raw decimal
lexemes. Whole floating values use their actual f64 integer value; fractional
values use shortest digits with explicit Python notation rules. This is a tested
numeric sample contract, not exhaustive proof over every IEEE-754 value.

## Supported scope and limits

The initial profile supports standard UTF-8 XML 1.0 XLSX parts with explicit A1
coordinates and dimensions: strings, booleans, numbers, errors and cached/missing
formula values. Dates, durations, ISO dates and nonfinite floats are explicit
unsupported-cell errors. Missing dimensions, external worksheet relationships
and cells outside declared geometry are refused. No lossy fallback selects a
different sheet, discards a cell or returns a partial table.

Defaults: 16 MiB input, 64 MiB total advertised ZIP uncompressed size, 16 MiB per
part, 2,048 parts, 10,000 rows, 256 columns and at most 1,000,000 cells in the
declared rectangle; individual values are capped at 1 MiB and decoded data at
16 MiB. Size/coordinate preflight occurs before loading Calamine's worksheet
range. ZIP entries are read in memory, never extracted to disk. DTD declarations
in inspected XML parts are refused. Both readers use the same byte snapshot.

Calamine still materializes the range. ZIP metadata, sidecar records, backend
cells and normalized output all consume memory beyond value-byte counters.
These are conservative work budgets, not hard process memory or streaming
guarantees. Large MOE spreadsheets need measured limits/index/streaming work
before increasing caps. Cancellation is checked at ZIP/XML/row checkpoints;
the individual Calamine range call remains synchronous and cannot be interrupted.

## Reproduce only when needed

Update the project ZIP in place, retaining .venv, vendor and all prior outputs:

```sh
cd "$HOME/Downloads/mdict-studio-m0-m1"
.venv/bin/python scripts/m2_xlsx.py --output m2-xlsx-out
```

The first run may download new reader dependencies and generate its isolated
lockfile. The script verifies direct pins and package checksums, then runs only
the new XLSX workspace tests. It generates 19 synthetic cases and compares 12
supported cases against the original helper, including active/named worksheets,
leading blanks, duplicate/numeric headers, rich/shared/inline strings and Excel
escape text, cached/uncached formulas, numeric precision/scientific samples,
captured MOE source rows, empty sheets and a 2,000-row table. Seven controlled
refusals cover dates, duration, missing sheets/dimensions, huge sparse geometry,
external relationships and malformed ZIP input.

Bundled synthetic unit fixtures and expected rows are fingerprinted in
`baseline/xlsx-reader-kit/manifest.json`. No real spreadsheet or dictionary data
is included. Unit tests exercise parity, unsupported types, pre-allocation shape
refusal, decoded budgets and cancellation. The user-run Rust workspace test
command passed on macOS. Rust was not executed in the authoring environment,
where Rust/Cargo remain unavailable.

Return `m2-xlsx-out/m2-xlsx-report.json`, plus any named log or expected/actual
JSON files on failure. The report includes the generated Cargo.lock; no second
upload is required for that dependency receipt. No M1/native reader/old converter
or real-corpus batch is requested. The Python helper remains a development oracle,
not an application runtime dependency.

The reader's common-cell output and exact dependency graph have passed review;
the five MOE ports are now authored using this input boundary; see `M2-MOE.md`
for the new runtime qualification batch. Date/calendar handling and larger worksheet qualification remain
explicit subsequent contracts, not implied by a common-cell pass.

## Sources

- Captured project implementation: `baseline/legacy/excel_utils.py`.
- [Pinned Calamine API/dependency documentation](https://docs.rs/crate/calamine/0.31.0).
- [Calamine release history, including Excel string escape behavior](https://github.com/tafia/calamine/releases).
- [quick-xml release/API changes](https://github.com/tafia/quick-xml/blob/master/Changelog.md).
- [Cargo lockfile and yanked-version behavior](https://doc.rust-lang.org/stable/book/ch14-02-publishing-to-crates-io.html).
