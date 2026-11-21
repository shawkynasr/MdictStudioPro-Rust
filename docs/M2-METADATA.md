# Metadata and stylesheet preservation: metadata-only rebuild

Offline qualification accepted 2026-11-02. All 36 commands completed as expected:
14 successful rebuild comparisons, 18 expected refusals, two seed commands and
the artifact refresh/Rust test commands. Metadata values, unchanged binary
sections, physical records, cancellation cleanup and no-overwrite checks passed.
Both five-entry native controls passed independent Python marker expansion.
All 121 protected and 18 current source identities match; the 61-package graph
and returned dependency lock bytes are unchanged.

The unchanged report and source snapshots are retained under
`docs/evidence/m2-metadata-user-run`. Generated dictionary bytes, successful logs
and individual actual JSON were not attached separately; these results describe
assertions completed by the fingerprinted runner.

Native checklist accepted by user confirmation on 2026-11-02: “Yes, Confirming
all five entries work, no crashes.” This responds to the preceding request to
test both encodings in MDict and GoldenDict, including styling and restart.
The scoped attestation and the requested output hashes/checklist are retained
under `docs/evidence/m2-metadata-native-user-confirmation`. Individual reader/file
combinations, colors and restart observations were not separately itemized;
no screenshot or trace evidence is claimed. This does not qualify general
native handling of XML character references in title/description metadata.
No further rerun is requested for these controls. M2 area 2 remains open for
metadata-aware new-entry packing and background publication integration.

Authored 2026-11-02. The first Mac run passed Rust tests and the first rebuild
command. Its Python source-record comparison then failed while parsing numeric
newline references in the input fixture's stylesheet. The unchanged report and
18 source snapshots are retained under `docs/evidence/m2-metadata-first-user-run`.
No complete process case or native-reader qualification is claimed from that run.

The corrected oracle uses a private source copy with only StyleSheet cleared,
asserts every binary section byte is unchanged, and reads raw records from that
copy. Original source/header values remain untouched and are still compared
directly with rebuilt metadata. The rebuilt output still goes through the
unmodified Python reader with its actual stylesheet. A regression test models
the numeric-reference parser failure and checks copy cleanup and input identity.
Rust sources and all locks are unchanged by this retry. M2 area 2 stays open.

This first subgate adds `studio_v2_import::application::metadata::rebuild` for
existing unencrypted UTF-8/UTF-16 v2 MDX/MDD. It creates a new file with a
serialized header and copies all original key/record sections byte-for-byte.
It does not repack entries, change encoding/key flags, normalize headwords,
resolve redirects in definitions or rewrite HTML. It is a metadata-preserving
rebuild/export route, not a general entry-editing writer or a new TXT format.

Preserve `.venv`, prepared v6 `vendor`, real inputs and previous outputs.
The accepted command was:

```sh
.venv/bin/python scripts/m2_metadata.py --output m2-metadata-out-v2
```

The accepted report is `m2-metadata-out-v2/m2-metadata-report.json`. No pip
update or batch rerun is requested. The Rust test command included the existing
reader and import-worker tests.

Use `m2-metadata-out-v2/native/metadata-utf8.mdx` and
`m2-metadata-out-v2/native/metadata-utf16.mdx` as standalone controls for MDict
and GoldenDict.
Test one file at a time: `inline-red` and `marker-red` must show STYLE_ONE_OK in
red/bold with a border; `inline-blue` and `marker-blue` must show STYLE_TWO_OK in
blue and underlined; `plain` shows PLAIN_CONTROL_OK. All five entries must exist
after restart. No MDD is needed. The batch checks raw definitions and independent
Python stylesheet expansion before these controls reach native testing.

## Declared metadata profile

`mdict-v2-metadata-v1` preserves all imported supported header values and unknown
ASCII, non-namespaced attributes. Attribute order and quoting become
deterministic; original raw XML bytes are not claimed to survive a rebuild.
Original header snapshots remain available through the unchanged import API.
Non-ASCII/namespaced attribute names are refused in this rebuild profile rather
than dropped. Version, encoding, encryption, format, case/strip flags and all
other structural attributes cannot be edited through this API.

Edits are optional title, description and stylesheet strings. Missing edits
preserve their imported values. An empty title/description is an explicit empty
value. A nonempty stylesheet derives `Compact="Yes"` and requires HTML MDX;
this one derived attribute change is visible in the returned header. Clearing
a stylesheet does not automatically change Compact. MDD stylesheets must be
empty; resource bytes are never interpreted as HTML or stylesheet markers.

XML metacharacters are escaped once. Literal ampersand sequences such as
`&amp;` or `&#10;` remain literal data after one decode; they are not decoded
twice. Only XML 1.0 characters are accepted. Title, description and other
non-stylesheet attributes encode LF/CR/tab as numeric character references, so
standard XML and the Rust importer preserve their exact values, including CRLF
and tabs. The old Python reader does not fully decode numeric character
references in metadata; this operation does not claim otherwise. Its raw record
reader remains useful as a definition/resource oracle.

The stylesheet uses the MDict/native-tested literal-LF convention: repeated
ID/prefix/suffix triplets, with a final LF. It escapes metacharacters but retains
literal LF separators. Standard XML parsers normalize these literal attribute
line breaks; their normalized stylesheet value is deliberately not used as the
preservation oracle. Raw wire decoding and the Rust importer must agree exactly.
The old ten metadata failures remain historical; this profile does not relabel
them or claim universal XML attribute semantics for MDict stylesheets.

Stylesheet IDs must be unique ASCII decimal strings of at most 32 bytes. Prefix
and suffix may be empty, but cannot contain tab or CR. CRLF, missing final LF,
incomplete triplets and duplicate IDs are refused, with no silent repair.
Numeric definition markers must reference an existing rule. Their text remains
unchanged, including redirect bodies and definition line endings. A stylesheet
cannot be cleared while numeric markers still reference it. Non-numeric
backtick text is preserved literally. No HTML rendering or script execution is
performed by the rebuild API.

## Publication and current limits

The source is copied into a private bounded snapshot. Header parsing and full
physical record verification use that immutable snapshot; the unchanged binary
sections are copied from it into a temporary file in the destination directory.
The staged file is flushed/synced, reopened under strict checksum verification
and compared against every original physical row/resource and expected header
value/raw byte. Publication uses `persist_noclobber` only after those checks.
Existing destinations, including symlinks, are not replaced. Source and
destination being the same path is an explicit destination-exists error.

Cancellation is checked during snapshotting, marker checks, section copying and
immediately before exclusive publication. Failed/cancelled stages are removed.
After publication commits, a later cancellation does not remove the output.
No callback is invoked after commit. File sync plus exclusive publication is
not a filesystem power-loss/directory durability guarantee.

This is currently synchronous and must be called from a non-UI worker. The
accepted read-only import runner is not reused for file publication: its panic
contract explicitly assumes no file output. A metadata publication worker and
new-entry packing with this metadata policy need separate integration. This
subgate therefore does not close all of area 2.

Limits remain the qualified 16 MiB file, 1,000 records, 8 MiB decoded data and
64 KiB wire-header envelope. Several private snapshots and original/verified
owned dictionaries may coexist. No production RSS/pre-decompression guarantee
is added. Serialized attribute expansion is bounded before output publication.

## Authored evidence checks

Two new Rust unit tests cover serializer escaping and stylesheet/marker grammar.
Four integration tests cover metadata/raw sections/duplicates, malformed styles
and invalid controls, copy/commit cancellation and no-overwrite cleanup, and MDD
metadata with duplicate/empty binary resources and a foreign attribute.

The process batch checks the eight UTF-8/UTF-16 case/strip combinations, both
missing-flag raw-import cases, MDD
metadata, foreign extension attributes, multiline/CRLF/tab/Unicode/literal-entity
values, unchanged binary sections and independent Python/wire records. Refusals
cover missing LF/CRLF/incomplete/duplicate rules, dangling or cleared markers,
invalid XML characters, edit/escaped-XML/UTF-16 wire-header budgets, corrupt source records, styles on
Text/MDD, existing/same-path destinations and three cancellation phases. Two
native controls are seeded through the unchanged qualified core writer, rebuilt
with the stylesheet bytes from the successful M1 reference, and checked by
Python numeric-marker expansion against inline controls.

All 121 prior source identities are guarded. The accepted `application.rs`
changes only by appending `pub mod metadata;`; reader implementation, read-only
worker, original tests/CLIs, previous scripts and all locks remain unchanged.
No new dependency or v1/v3/encryption support is added.
