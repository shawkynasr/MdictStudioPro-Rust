# Header and lookup policy qualification

## Resume the received batch

The user's report passed both 77-record literal candidates, 142 lookups, both
alias spelling checks and the flag/order negative control. Each 12-definition
duplicate group occupied 12 separate key blocks. The final conflict log says:

```
ERROR: invalid data: conflicting aliases for header attribute StripKey
```

The engine rejected the conflict during open, before the probe's own boolean
resolver ran. The old Python assertion accepted only that resolver's different
wording. This was a checker false failure, not evidence of an accepted conflict.
The checker now accepts either exact known conflict diagnostic with exit 1 and
no stdout. Unrelated parse/checksum errors, panics and emitted rows remain failures.
Rust code and the candidate engine are unchanged by this correction.

After updating in place, retaining the existing header-out folder, run:

```sh
.venv/bin/python scripts/finalize_header_lookup.py --output header-out
```

This accepts only the received failed report and hash-matched qualified sources.
It verifies the existing candidate hashes, their small independent audits and
saved observations, then uses a cached Cargo build and reruns only the conflicting
fixture refusal. It does not regenerate dictionaries or repeat the Rust lookup
matrix. The old report is retained as header-lookup-report.before-finalize.json;
success updates header-lookup-report.json and creates native-candidates plus
native-checklist.csv. Existing native output is never overwritten.

Once this command reports success, test only the two native-candidates files:
UTF-8 alone first, then UTF-16 alone, in MDict and GoldenDict. Check the punctuation
spellings individually; a?b and missing should have no entry. Check aPpLe, the
first/last edge keys, Chinese, Arabic and the supplementary character. For duplicate,
verify that all DUP_01 through DUP_12 definitions are accessible. Record case-group
differences as actual reader behavior; the studio exact-first API is distinct.
Restart each reader and confirm entries still open. Keep all other header-out
MDX files outside reader scan folders. Return the finalized report and native
observations; if finalization fails, return its terminal error and recheck log.

## Original batch design

The fresh-pack report proved physical records/resources and Title/Description,
not full export-header or native lookup parity. Its legacy-ordered Rust files
still declared StripKey=No. Changing that flag alone is insufficient: physical
order, header normalization and the consuming reader must agree.

## Run

Update the project in place, keeping .venv, vendor, your corpus and reports.
The dependencies installed for the preceding fresh-pack batch are sufficient.

```sh
.venv/bin/python scripts/header_lookup.py --output header-out
```

Return header-out/header-lookup-report.json and any log named in an error.
No real dictionary, font, large stress fixture or native app is needed for this
offline batch. Existing directories are refused; use another --output for retry.
New Rust code is uncompiled in the authoring environment. The driver runs the
Rust workspace tests and must compile successfully on the user's Mac.

## Candidate and diagnostics

The candidate is an explicit punctuation-preserving export profile, separate from
the original app's legacy modes. It uses the already qualified HeaderLiteralC
comparator with canonical StripKey=No and KeyCaseSensitive=No, plus Format=Html,
Compact=No, Compat=Yes, empty StyleSheet, Title/Description and ancillary fields.
It writes both UTF-8 and UTF-16 using the existing version-6 candidate engine.
The engine version and dependency graph are unchanged.

Every key and definition is preserved verbatim. No aliases or redirects are
automatically generated, and no Unicode normalization or accent removal is added.
Both original legacy comparators remain unchanged and separately selectable in
their existing probes. The name mdxbuilder denotes the original application's
ASCII-folding mode, not an exact official MdxBuilder Wide/Narrow implementation.

The upstream writer reserves its StripKey attribute. For the two diagnostic
legacy files only, the qualification wrapper changes the generated XML flag to
canonical StripKey=Yes and regenerates prefix length/ADLER32. Every key/record
section byte is retained, and the whole resulting dictionary is strictly scanned.
This is explicitly a diagnostic overlay, not a new general header serializer or
a claim of production compatibility. The literal candidate uses the builder's
canonical No header directly, with no flag overlay.

## What must pass

The fixture has 77 physical records: punctuation/case variants, Arabic, Chinese,
non-BMP characters, boundary keys and 12 distinct definitions with the identical
headword duplicate. Small key/record targets force multiple blocks. An independent
block walk requires that duplicate's group to occupy at least three key blocks.

Every literal raw-exact query must return all and only its exact duplicate rows;
only a query without raw-exact rows uses lowercase fallback. This is the studio
API's exact-first contract. Both a?b and missing must return no rows under No.
Case-only aPpLe returns all four Apple/apple/APPLE rows; exact apple returns its
two lowercase rows. The independent Python reader must return every physical row
with exact order and payload. The independent v2 auditor checks wire structure,
checksums and all encoded definition terminators. Rust uses Verify throughout.

The driver creates lowercase Stripkey spelling copies of a No and a Yes file,
holding all non-header bytes identical. Their rows and lookups must match their
canonical counterparts. A boolean resolver validates Yes/No/1/0 flags and rejects
conflicting StripKey/Stripkey values before rows or queries are emitted. If an
engine path fails the alias-equivalence check, that is a failure; native candidates
are withheld. The resolver is in this probe, not yet integrated into all future
app imports.

A negative control changes only the flag on literal-ordered data. The fixture
includes aa between normalized ab candidates, so the resulting physical sequence
is demonstrably nonmonotonic under the tested strip normalization. The driver
must catch that mismatch, proving a flag-only edit is not accepted as a fix.

Legacy diagnostic files must keep their original app physical order and exact
payloads. Their fallback differences and ordering under a separate strip lookup
oracle are recorded honestly. These observations do not qualify those modes for
native export. In particular, the app's historical backslash regex behavior is
not silently changed to match a different reader normalization rule.

The independent lowercase oracle is scoped to the fixture characters. It does
not qualify all contextual Greek lowercase, Unicode versions, official builder
mapping tables, or encoded-byte comparators. Generic multiline StyleSheet XML
serialization also remains a separate open issue.

## After report review

Only complete offline success creates native-candidates with two files:
07-header-literal-utf8.mdx and 07-header-literal-utf16.mdx. Keep every diagnostic,
alias-conflict and flag-mismatch file out of native reader scan folders.

The generated native-checklist.csv records the studio API expectations and blank
columns for actual MDict/GoldenDict observations. A native reader can group case
variants differently from the studio exact-first API; record its actual grouping
rather than treating that API policy as an externally standardized requirement.
All distinct stored definitions must remain accessible, especially the 12 duplicate
definitions. Native test instructions follow review of the uploaded report.

Success is literal_header_lookup_offline_passed_legacy_diagnostics_recorded_native_pending.
It qualifies the bounded literal candidate offline only. Both native readers,
legacy export policy, broader Unicode mappings, production integration and M1
completion remain open.
