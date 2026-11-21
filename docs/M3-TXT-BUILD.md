# M3: build MDX directly from dictionary TXT

2026-11-12. Authored for native qualification; M3 is not complete.

Build now defaults to dictionary TXT (UTF-8), with JSONL retained as an advanced
source format in More options. The newline profile is explicit. Source encoding
and MDX output encoding are separate: strict UTF-8 input with optional UTF-8 BOM
can produce UTF-8 or UTF-16 MDX. UTF-16 TXT input is refused with an encoding
message, rather than guessed or decoded lossily. MDD packing is unchanged.

## Check on the Mac

Merge into the existing project, keeping `.venv`, vendor, node_modules, targets,
inputs and existing dictionaries/indexes. From the project root:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
python3 scripts/m3_shell.py --output m3-shell-out-v8
```

Use a fresh report name if that directory exists. No reinstall is needed with
previous dependencies cached. The runner normalizes only the new M3 locks,
checks registry identities against the accepted graph, runs TXT runtime and
adapter tests, then frontend tests/build and desktop check. On failure return
that output directory's m3-shell-report.json and failing step log.

Launch:

```sh
cd m3/desktop
npm run tauri dev
```

1. Close both readers in Dictionary Tools first. TXT builds have an exclusive
   reservation covering preparation and packing; the UI and native admission
   enforce this rather than closing readers silently.
2. In Build select `m3/fixtures/build-source.txt`. The card should say Dictionary
   source TXT · UTF-8. Enter a title, select a NEW MDX destination, leave Standard
   newline handling and click Build dictionary.
3. Jobs should show ONE build across TXT preparation and packing. Collect its
   receipt: expect 5 records and source_format txt_utf8.
4. Index/open the resulting MDX in Tools. Look up apple, 字 (two definitions),
   مرحبا and empty (an empty definition). The first 字 body preserves its extra
   trailing blank line. Check HTML source as well as rendered display.
5. Close the reader; repeat with UTF-16 MDX output and a NEW destination, then
   with Block spool and a new output. No old external reader batches are needed.
6. Try a TXT missing its final </>: expect a line-numbered failure and no MDX.
   Retry an existing destination: it must remain unchanged.
7. Test cancellation using a larger representative TXT; no destination should
   exist before commit. A success remains successful if Cancel arrives late.
8. Under More options choose JSONL entries (advanced), select the existing
   m3/fixtures/entries.jsonl and a new destination to check the older route.

Converter TXT output can now be selected directly in Build. No manual JSONL
conversion is needed. Original source files are never rewritten.

## TXT grammar

Each record has a nonempty headword, at least one definition line and </> on a
line by itself. For an empty definition put a blank line between headword and
</>. Blank lines BETWEEN complete records are rejected as empty headwords. A
final delimiter may end at EOF without LF. LF and CRLF are accepted, including
mixed endings; lone CR, NUL, invalid UTF-8 and incomplete records are refused.

Standard (canonical_v1) normalizes definition CRLF to LF, then removes exactly
ONE separator LF before </>. Other whitespace is preserved. This matches the
current converters' and exporter's canonical TXT. Legacy (legacy_body_span_v1)
retains the raw body span, including the delimiter-preceding LF/CRLF. Both keep
duplicate headwords, HTML, Unicode and blank body lines. This choice is visible
rather than inferred. Output MDX encoding does not alter the source grammar.

## Integration and bounds

The additive m3/txt-runtime coordinator derives from the accepted M2 coordinator.
Existing queue, reader, converter, index and packing modules are reused by path;
its reservation implementation and reader lifecycle remain byte-identical. Only
the TXT request/response route is added. The native adapter dependency alias
points at this M3 coordinator. No accepted M1/M2 source or lock is changed.
Native regression testing is still necessary for this new integration.

TXT gets the existing exclusive block-packing reservation (384 MiB logical
memory and 3 GiB temporary space) throughout preparation AND packing, including
when Bounded output is selected. It uses the SAME queue, one job ID, one token
and one receipt. No extra uncoordinated preparation worker is created. These
logical reservations are conservative accounting, not hard OS memory limits.

Preparation reads once through a 64 KiB buffer, hashes the bytes actually read
(including BOM/CRLF), validates one record at a time and creates a private bounded
JSONL spool. It never materializes all entries or a whole input string. The
selected existing packer snapshots the spool and handles validation, stable
sorting, writing, reopening and atomic no-clobber publication. RAII temporary
files are removed on success, failure or cancellation.

Caps: original TXT 128 MiB; prepared JSONL 128 MiB; 8 million source lines;
headwords 4 KiB; definitions 1 MiB. Bounded: 100,000 records and 32 MiB decoded
entries. Block: 250,000 records and 96 MiB decoded entries. JSON escaping can hit
the prepared-spool cap before decoded-size caps. Existing metadata, engine,
command and output limits still apply. No automatic fallback or cap widening.

The outer receipt describes original TXT digest/bytes, newline profile and
record count. Its nested packer receipt describes the prepared JSONL and its
hash, not the original TXT hash. Hashes bind integrity, not authenticity.
Cancellation checks occur between chunks/records and at the accepted packer's
commit boundary. No fallible validation/cancellation is added after commit.

## Verification scope

Authored Rust tests compare streaming preparation with the accepted core parser
for BOM, CRLF, duplicates, blank/empty bodies and final-delimiter-at-EOF. They
exercise both packers and output encodings via pack/export, metadata, no-clobber,
malformed/oversized inputs, prepare/precommit and late cancellation, and shared
reader admission. Inherited coordinator regression tests are reused unchanged.

Rust tests and this new Svelte template have NOT run in the authoring environment:
Rust is absent and npm registry access was blocked. Local Node/Python checks are
reported separately from native build/GUI qualification.

## Version 125: automatic dictionary output extensions

The user reports all five TXT-built records working in MDict and GoldenDict,
including UTF-16 MDX output. This is user reader-compatibility evidence for the
reported fixtures; it does not establish every cancellation/resource-limit test.

Build's Save dialog now filters for MDX or MDD, suggests dictionary.mdx or
dictionary.mdd, and normalizes the returned path. The same normalization runs
before submitting a build, covering manually typed paths. Existing matching
extensions are preserved case-insensitively; switching MDX/MDD replaces the archive
suffix; names such as dictionary.v2 get the selected suffix appended. Directory
paths are left for native validation. The resulting filename is visible in Save
to and the output inspector. Atomic no-clobber behavior and engine code are unchanged.

Merge and let Vite reload, or restart npm run tauri dev. Reuse the same TXT sample.
Choose a new basename without an extension and verify Save to shows .mdx, then
build it. Check MDD naming when selecting that format. No fixture regeneration,
old M1/M2 test batch or dependency reinstall is required. Native dialog behavior
and the updated Svelte template need this brief Mac check.


Version 126 adds direct folder MDD building. See M3-FOLDER-MDD.md for the latest
check command. Existing TXT routes/caps remain unchanged.
