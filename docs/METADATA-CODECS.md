# Metadata and storage codecs: completed revision-3 result

The latest user run completed all 111 observations: 91 passed, 10 failed,
2 unsupported and 8 blocked. All 28 Rust observations passed. UTF-16 records,
duplicates and reverse metadata now pass through both engines under both sort
profiles. The separate UTF-8 interoperability suite also passed 14/14.
Original report and log: `docs/evidence/metadata-v3-completed-user-run`.

All ten failures are standard-XML StyleSheet comparisons. Rust and Python
return the exact multiline attribute; the standard XML parser returns spaces.
This is a parser-contract disagreement, not evidence of missing raw newlines.
It remains unresolved; none of these assertions has been weakened or removed.

Both unsupported observations are legacy Python GB18030 writer rejections.
The eight dependent checks were correctly blocked. Rust GB18030 self reads and
Rust-to-Python records passed; reverse GB18030 remains unproven. No check that
was unsupported or blocked is counted as a pass.

No further identical rerun is needed. The next useful evidence is dictionary
stylesheet rendering in independent reader applications and a representative
real dictionary corpus. Metadata parser semantics need an explicit decision
before this gate is closed. M1 and engine selection remain incomplete.

The earlier blocked run is preserved separately in `docs/evidence/v3-user-run`.
Harness revision 3 fixed command-argument shadowing; it changed no writer code
or dependencies. There are 22 passing local Python tests (six baseline and
sixteen harness tests). No Rust execution was performed in this environment.

## Historical revision-2 result and preparation

The user's Intel Mac run completed 111 observations: 77 passed and 34 failed.
All 28 Rust observations passed. The original report and log are retained under
`docs/evidence/metadata-v1-user-run`; they are never rewritten to match fixes.

## What the failures mean

| Count | Cause | Treatment |
|---|---|---|
| 10 | Standard XML turns literal StyleSheet newlines into spaces | Unresolved parser contract; exact assertions retained |
| 4 | Python reader treats UTF-16LE header as one-byte key units | Isolated v3 candidate emits UTF-16 label |
| 4 | Legacy writer rejects utf-16le and gb18030 API arguments | Request utf16 for UTF-16; report explicit GB18030 rejection as unsupported |
| 16 | Readers run after the writer failed to create output | Corrected harness blocks these dependent observations |

The 34 failures are not 34 independent dictionary engine defects. The first
harness mixed Python byte-codec names with the legacy writer's narrower API,
and attempted reads of nonexistent outputs. These are harness errors.

UTF-8, Big5 and GBK record interoperability passed for the samples. GB18030
Rust self reads and Rust-to-Python records passed, but reverse GB18030 remains
unproven because the installed legacy writer rejected that encoding. Unicode
MDD resource names and exact binary data passed. All Rust metadata, rejection,
duplicate lookup and multiblock observations passed.

## Reproduction commands

Extract the updated package into a separate folder, or update the project
sources while retaining earlier reports. From the updated project root:

```sh
cargo fetch --locked
python3 scripts/prepare_sort_experiment.py --revision 3 --reuse
python3 -m venv .venv
.venv/bin/python -m pip install mdict-utils==1.3.14
.venv/bin/python scripts/patched_interop.py --writer-revision 3 --output interop-out-v3
.venv/bin/python scripts/metadata_codecs.py --writer-revision 3 --output codec-out-v2
```

An existing .venv with mdict-utils 1.3.14 can be reused. The preparation creates
`vendor/mdictlib-0.2.8-studio-sort-v3`, preserving v1/v2. If v3 already exists,
`--reuse` compares every generated member with the checksum-verified crate and
the reproducible patch before accepting it. It never overwrites existing source.

The old default remains revision 2. Revision 3 is selected explicitly through
Cargo's command-line patch path override; the experiment manifest and both
uploaded lockfiles remain unchanged. The harness confirms the built candidate
revision. It also reverses the one expected label substitution in memory and
verifies that the rest of the writer matches the passing v2 source fingerprint.

Send `interop-out-v3/interop-report.json` and
`codec-out-v2/metadata-codec-report.json`, plus the corresponding log on failure.
Output directories must be new. Retain the original codec-out as evidence.

Revision 3 changes only the writer's UTF-16 wire label from UTF-16LE to UTF-16.
Key/body encoding remains explicitly little endian with no BOM. It does not
change sorting, header case/strip flags, compression, records or either reader.
The UTF-8 interop regression and record-codec subset passed on the user's Mac.
Rust/Cargo remain unavailable in this environment.

## Stylesheet contract remains open

The report shows exact multiline StyleSheet values in Rust and in the Python
reader where construction succeeded. The standard XML parser instead returns
spaces. This is not evidence that the raw binary header lost the newlines.

Escaping newlines as XML character references can preserve their meaning in
standard XML, but the legacy Python reader only decodes a small set of named
entities. A blind serializer change would introduce another compatibility
failure. No newline normalization, entity replacement, skipped assertion or
reader monkey-patch has been added to make this gate appear green.

The next run is therefore expected to keep the ten standard-XML stylesheet
comparisons failing if it reaches them. Rejected GB18030 writes are recorded as
unsupported and dependent checks as blocked; neither is counted as a pass.
The suite remains failed until the metadata contract is resolved. Do not mark
M1 complete or use this candidate as a production engine selection.

## Scope

The fixture still covers five MDX storage codecs, both C-locale sort profiles,
duplicate payloads, representability rejection, Unicode resource keys, binary
zeros, Title/Description/StyleSheet/Format and independent header framing.
There are 28 Rust and 83 Python observations. Reverse bodies use binary sources
and explicit encoded NUL terminators, bypassing TXT newline policy. Reverse
stylesheet output is not claimed: the original writer constructor does not
expose that argument. MDD resource names are always UTF-16LE.

Source TXT/CSV decoding, all-codepoint codec mapping equivalence, native reader
apps, stylesheet rendering, large files, encryption/LZO input and non-C locales
remain separate gates. GUI language selection is a later implementation task.
