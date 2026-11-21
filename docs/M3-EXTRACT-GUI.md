# Extract GUI: MDX exports and MDD resource extraction

Version 128, 2026-11-12. Native qualification pending; M3 remains incomplete.

The existing native extraction routes were already connected. This revision makes
the GUI destination workflow explicit, adds filename suffix handling and adds
a dedicated larger export profile for dictionaries built with Block spool.

## Update and check

Merge into the existing project while retaining caches, vendor, inputs, outputs
and indexes. From the project root:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
python3 scripts/m3_shell.py --output m3-shell-out-v11
```

Use a new report name if that output already exists. The runner checks runtime,
adapter and frontend tests, Svelte/TypeScript/Vite, and desktop compilation.
It does not claim a native window was launched. On failure send its
m3-shell-report.json and the failing step log. No dependency reinstall is needed
with the previous caches. All accepted M2 source/lock identities remain unchanged.

On success:

```sh
cd m3/desktop
npm run tauri dev
```

## MDX to TXT and JSONL

Close readers in Dictionary Tools for these checks. Extract defaults to the
Large MDX export profile: 250,000 records, 96 MiB decoded keys/definitions. More
options also exposes Bounded: 100,000 records, 32 MiB decoded. The Large choice
uses a dedicated M3 export-only profile derived from the accepted M2 streaming
export implementation. Its 96 MiB/250,000 caps are new profile bounds requiring
native qualification; accepted M2 code and limits are unchanged.

1. Use the five-record MDX previously built from m3/fixtures/build-source.txt
   with Standard newline handling. In Extract choose the MDX and MDX → TXT.
2. Choose a fresh output, for example entries.txt. An entered basename gets .txt
   automatically; the final path is visible before running. Click Export entries.
3. In Jobs collect the receipt; expect 5 records. Repeat with MDX → JSONL and
   entries.jsonl. The .jsonl suffix is automatic. Both exports are UTF-8, even
   when the source MDX uses UTF-16.
4. Verify the exports against their original source. For example, if you saved
   them inside m3-shell-out-gui-extract (create that parent folder first):

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
python3 scripts/verify_gui_extraction.py entries --source m3/fixtures/build-source.txt --txt m3-shell-out-gui-extract/entries.txt --jsonl m3-shell-out-gui-extract/entries.jsonl
```

Expect status passed for both, expected_records 5 and actual_records 5. The
comparison checks record multiplicity, exact definition text and order within
duplicate headwords. Different physical ordering between different headwords is
allowed, because packing sorts entries. Blank bodies and extra body newlines are
checked, not trimmed. For a source built using Legacy newline handling, add
--source-profile legacy_body_span_v1. The exported TXT is always parsed using
its canonical export grammar.

The same verifier can compare a representative CC-CEDICT export against the
canonical converter TXT used to build it. This is an optional larger case; the
new Large profile is intended to avoid the smaller 32 MiB export ceiling.
Dictionary title, description, numeric StyleSheet and other header attributes
are present in the collected native receipt, NOT in the TXT/JSONL entry file.
Numeric markers stay as stored source; exported entries are not rendered HTML.
Do not assume a rebuilt dictionary automatically recovers metadata from TXT.

If TXT reports unrepresentable_source (for example a stored definition contains
a standalone </> line or literal CR), choose JSONL. The job refuses lossy TXT
output; it does not strip or rewrite those definitions to force success.

## MDD to a new resource folder

1. Select the fixture preview.mdd, or a folder-built copy made from the exact
   m3-shell-out-preview-fixture/assets directory. Selecting .mdd automatically
   chooses MDD extraction; selecting .mdx restores MDX export.
2. The source folder supplies an initial parent and suggested *_resources name.
   Change Parent folder if desired and enter one NEW folder name. The full
   destination is shown read-only in Save to. No folder is created by the GUI.
3. Click Extract resources. Collect the receipt: the original preview asset
   archive should have 2 resources. Its staged files are verified before commit.
4. Compare extracted bytes and paths with the actual original resources:

```sh
python3 scripts/verify_gui_extraction.py resources --original m3-shell-out-preview-fixture/assets --extracted m3-shell-out-gui-extract/resources
```

Replace the extracted path with your selected parent/name. Compare a CC-CEDICT
MDD with the folder actually used to build it, rather than the unrelated preview
assets. Expect status passed, matching file counts and no changed_bytes_paths.
The verifier hashes files through 64 KiB buffers, compares relative filenames,
keeps empty files, ignores the same macOS metadata names as folder packing and
rejects observed symlinks. Empty directories are ignored because MDD does not
represent them. Run verification after jobs finish and avoid editing folders
while it reads them; it is a comparison tool, not an atomic filesystem snapshot.

## Failure and cancellation checks

- Repeat export to an existing file or extraction to an existing folder, even
  an empty folder: destination_exists; previously published output stays intact.
- A filename helper does not create or replace files. Both the dialog and typed
  export paths are normalized; native atomic no-clobber remains authoritative.
- A new resource folder name must be one component, not a path. Traversal,
  reserved names/characters, trailing dot/space and oversized UTF-8 names are
  refused. Archive-internal paths still undergo native validation independently.
- Cancel a representative job before commit: terminal Cancelled and no newly
  published destination. Late cancellation after commit retains success.
- Use Jobs → Dismiss finished jobs if retained history is full. Output files
  remain. Receipt collection and dismissal keep their existing explicit behavior.

These are GUI checks for this revision, not a request to repeat old independent
M1/M2 reader batches. Extraction of an existing source requires no new index.

## Native routing, reservations and existing limits

Bounded MDX exports retain dictionary/export_txt or export_jsonl. The explicit
large_export request translates txt/jsonl to studio-export-io, an export-only M3
profile derived from studio-large-io streaming code, with explicit 96 MiB and
250,000 record bounds. It does not call the packing-only studio-cc-pack-io. The coordinator gives it the existing
exclusive block-packing reservation (384 MiB logical memory, 3 GiB temporary
space). The GUI asks you to close readers before Large export; native admission
also enforces that condition. The new profile needs native qualification; accepted I/O code remains unchanged.

MDD extraction retains the existing extraction request and streamed resource
backend. It uses its existing 96 MiB logical reservation and 3 GiB temporary
allowance; tests are simplest with both readers closed. All jobs use the same
publication queue/token/progress, one-transfer receipts and cleanup barriers.
No new worker pool, plugin permission or arbitrary filesystem command is added.

MDX input remains the supported unencrypted v2 UTF-8/UTF-16 profile, with the
existing 512 MiB input, 1 MiB per exported definition, 128 MiB exported-file and
canonical TXT line-count/grammar ceilings. Bounded decoded/count caps are 32 MiB
and 100,000; Large caps are 96 MiB and 250,000. No automatic widening or fallback.
MDD extraction retains its existing profile: <=100,000 resources, <=256 MiB per
resource, <=2 GiB extracted payload, plus source/parser/block/path-plan bounds.
Logical reservations and verifier input caps are not hard OS memory guarantees.

The native extractor stages in a private sibling directory, validates paths and
case aliases, streams and hashes bytes, then publishes the whole new directory
without overwriting. Cancellation/failure removes staging. MDX exports stage,
reparse and verify their output before no-clobber publication. No new fallible
validation or cancellation check is added after a successful native commit.

The standalone Python verifier is read-only and has its own bounded comparison
profile: 128 MiB per entry input, 8 MiB per input line, 4 MiB per definition,
500,000 records, 200,000 visited resource paths, 100,000 files, 256 MiB per file
and 2 GiB total resource bytes. It does not run inside app admission accounting
or prove app memory ceilings. Content is never evaluated or executed.

## Verification evidence

Seven Node helper/security tests and Python verifier/structure tests run locally.
Native adapter tests now exercise both export profiles and suffix-independent
file content, duplicate/blank-body preservation, metadata receipts, exact nested
binary/empty-resource extraction, output refusal, wrong-kind input refusal and
TXT-unrepresentable/JSONL-preserved content. The existing real-reader test also
checks Large export admission refusal while a reader holds its lease. Runtime
lifecycle, extraction and cancellation regressions remain enabled.

Rust/Svelte compilation and native GUI tests for this revision have NOT run in
the authoring environment (Rust absent; npm registry access blocked). Local checks
and earlier native successes are not substituted for that qualification.

## Version 128 routing correction

The first native v127 run passed all 50 coordinator/runtime tests and 7 of 9
adapter tests. Both new export tests failed: Large export returned
unsupported_policy, because studio-cc-pack-io explicitly accepts MDX packing
only. Its public enum also names exports, but its execute guard denies them.
The earlier v127 description incorrectly treated that as an available exporter.
This was a routing error, not a dependency-installation or input-file problem.
Frontend build steps were not reached; they still need the normal check.

The correction adds the dedicated export-only M3 profile described above. Its I/O
module is the accepted M2 streaming I/O source with exactly two policy changes:
the 96 MiB/250,000 ceilings and an export-only execution guard. Shared header,
casing and SHA modules are included from unchanged M2 files. Native tests check
the export-only guard, lowered-limit refusals, cancellation and a real 33 MiB
payload export above the old 32 MiB ceiling. The runner runs those tests before
the runtime/adapter and frontend checks. Existing adapter expectations are kept:
TXT must produce unrepresentable_source for unrepresentable bodies, and JSONL
must preserve those same bodies. Tests are not skipped or changed to accept the
incorrect unsupported_policy result.

The failure receipt, matching failing route/test sources and scoped evidence are
retained under docs/evidence/m3-extract-first-native-run. No reinstall or old
M1/M2 reader batch is required. Re-run the normal script with output v11; it may
spend longer in export-io-tests because of the new 33 MiB boundary case. New Rust
execution remains pending in the authoring environment.
