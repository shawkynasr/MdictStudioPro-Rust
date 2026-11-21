# M2 TXT I/O and the first Rust converter

The TXT/CC-CEDICT slice passed on the user's Intel Mac (macOS 15.8.2) on
2026-10-29: 38 commands succeeded and five controlled refusals had the required
error codes. Twelve golden file/profile cases, four 13-record MDX pipelines,
7-record baseline and 23-record extended CC-CEDICT outputs, and ten pinyin probes
all passed their independent checks. The report and 32 matching source/data
snapshots are retained in `docs/evidence/m2-text-user-run`. Individual user-run
test logs were not supplied; no Rust test count is inferred. No rerun is due.
The earlier MDX/MDD slices
remain qualified at their retained source snapshots; M2 is still partial.
No M1/native/corpus rerun is requested.

## Explicit TXT profiles

TXT input is strict UTF-8, optionally with one UTF-8 BOM. LF and CRLF record
lines are supported; lone CR, NUL, empty keys, incomplete records and missing
body lines are errors. A standalone `</>` closes a record; it is not valid
definition content. Imports return all records or an error, never a partial list.
Keys are not trimmed, entries are not sorted, and duplicates/redirect source
strings are not merged or resolved.

| Profile | Imported body | Export contract |
| --- | --- | --- |
| `canonical_v1` | Normalize CRLF body newlines to LF, remove exactly one structural LF before the delimiter | Add that structural LF; preserve actual body trailing LFs. Empty body uses one blank line. Reject CR rather than silently change content. |
| `legacy_body_span_v1` | Keep raw body bytes decoded as UTF-8, including its final LF/CRLF before the delimiter | Require the body to end in LF/CRLF; write it directly before the delimiter. Reject an unrepresentable body rather than append a new definition byte. |

The legacy profile follows the raw-span comparison contract used in M1 fresh
packing. The old minimal probe's newline grammar remains unchanged; the new
explicit profile names prevent treating the two contracts as interchangeable.
Exports emit LF key/delimiter lines and no BOM; the legacy profile preserves its
body line endings. They do not promise byte-identical preservation of whole-file
BOM, key/delimiter CRLF or absent final delimiter LF. A literal BOM as the first
headword is refused on export because it would be ambiguous on reimport.

`parse_txt`, `read_txt`, `render_txt` and `write_txt` compose with the existing
packing API. `Dictionary.export_txt` exports stored physical order. Canonical
profile round trips any supported LF body, including empty/multiple blank lines;
legacy export deliberately refuses ordinary MDX definitions without a trailing
LF. Neither profile silently changes a definition to make it fit.

File export validates entries, writes a sibling temporary file, syncs and
reparses the actual file with the selected profile, compares every entry, then
publishes without replacement. Cancellation before commit removes the temporary
file. Publication after a destination appears must fail without overwriting it.
As with the other core APIs, power-loss directory durability and process-kill
orphan cleanup remain later application work.

## CC-CEDICT UTF-8 converter port

`convert_cedict_utf8` and `convert_cedict_file` return entries, comments and
primary/traditional/skipped-line counters. `cedict_pinyin` exposes the tone
conversion helper. The implementation uses the frozen Unicode16 lowercase data
and the captured Python16 whitespace set; no Python subprocess or new dependency
is needed in the application. Development tests still use the original Python
plugin as an independent oracle.

ConversionResult identifies `txt_profile=canonical_v1`: its entry strings do not
include the framing newline. To reproduce the original converter-TXT-loader-MDX
body bytes, serialize with that profile and import with `legacy_body_span_v1`.
Directly packing canonical converter entries is a different body contract and
must not be labelled legacy raw-span parity.

The port preserves simplified-first/traditional-second order, repeated headwords,
pinyin vowel priorities, the original neutral/invalid-tone case quirks, generated
HTML and stylesheet reference, greedy cross-reference behavior and longest-first
tag replacements. Raw HTML is not escaped or sanitized, matching the converter;
safe preview isolation remains separate application work.

This first port supports UTF-8 without BOM and ASCII tone suffix digits. It
rejects non-ASCII numeric suffixes explicitly, rather than claim general Python
isdigit/int equivalence. Big5/GB18030 converter input and spreadsheet converters
are not ported by this slice. A source with no valid records is rejected; the
old plugin could write an empty output for a nonempty comments/invalid-only
file. That is an intentional strict application-boundary difference, not a
claim of total legacy behavior equivalence.

Original source-adjacent timing log side effects are not reproduced. The new
converter leaves input files alone and reports comments/counters through the
result; the CLI publishes only the explicitly selected TXT destination.

## Budgets and cancellation

Existing core defaults still apply: 1,000 entries, 8 MiB decoded data, 1 MiB
definition/resource bytes, 4 KiB keys and 16 MiB file size. A new configurable
`max_source_lines` defaults to 1,000,000. CC-CEDICT also caps a pinyin field at
4 KiB and comment count at the entry-count limit. These are bounded first-slice
APIs, not a production-scale dictionary/converter memory guarantee.

Source reads are capped, UTF-8 decoding is strict, and parsing/conversion checks
cancellation at each line. Progress is coalesced every 256 lines, plus start/end
and export record checkpoints. A single line/format operation and filesystem
calls remain synchronous, so the future GUI must run jobs off its event thread.

## Reproduce only when needed

Update the ZIP in place, retaining .venv/vendor and outputs:

```sh
cd "$HOME/Downloads/mdict-studio-m0-m1"
.venv/bin/python scripts/m2_text.py --output m2-text-out
```

This uses the same Python Unicode16 environment and pinned mdict-utils. It runs
the changed M2 workspace tests, then checks:

- All six captured converter TXT outputs in both profiles, with exact re-export.
- BOM/CRLF boundaries, blank lines, duplicates, redirects and Unicode.
- Four TXT -> MDX -> TXT pipelines (two profiles times two MDX encodings), with
  independent Python rows, wire audit and separate CLI processes.
- The CC-CEDICT baseline plus an extended fixture against the actual original
  plugin, byte-for-byte, including comments/counters and ten pinyin probes.
- Correct typed refusals for malformed/invalid input, unrepresentable legacy
  output, existing destinations and unsupported pinyin suffixes.

The six captured TXT files qualify I/O interoperability; only CC-CEDICT is a Rust
converter port. No XLSX/MOE converter implementation or broad real-corpus
conversion is implied. The original plugin runs only on copies inside this run's
oracle folders; baseline sources and real dictionaries are never modified.

Return `m2-text-out/m2-text-report.json`, plus a named failure log or `*-diff.json`
file. The first-byte difference file helps diagnose parity errors without asking
for another full run. Do not import these automation fixtures into native readers.

## CLI additions

| Command | Input/output |
| --- | --- |
| `txt-read FILE PROFILE` | JSON rows from strict TXT import |
| `txt-write ROWS.json OUTPUT PROFILE` | JSON array of key/text objects to new TXT file |
| `txt-pack FILE OUTPUT.mdx PROFILE utf8\|utf16` | Import, then pack with the selected source/body contract |
| `txt-export FILE.mdx OUTPUT.txt PROFILE` | Strict Studio reopen, then physical-order export |
| `cedict INPUT.u8 OUTPUT.txt` | UTF-8 CC-CEDICT conversion with structured counters |
| `cedict-pinyin WORDS.json` | JSON string array to pinyin helper results |

M2 remains open after this slice for spreadsheet converter ports, larger indexes,
general import/metadata contracts and application job/Tauri integration.
