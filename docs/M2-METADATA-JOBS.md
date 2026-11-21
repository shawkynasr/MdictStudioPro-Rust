# Metadata-aware new-entry packing and publication jobs

Offline qualification accepted 2026-11-03. The Rust test command and both process
batches passed. All 56 job outcomes matched expectations: ten successful
publications and eighteen expected refusals per route. Both routes preserved
metadata, stable physical order, duplicates, payloads and rebuild sections;
no-clobber and no-staging-residue checks passed. Each background batch reused
one worker across failures and recovery. The native five-entry controls passed
independent Python marker expansion. All 126 protected and 23 current source
hashes match; the 61-package graph and complete lock bytes remain unchanged.

The unchanged report and matching sources are retained under
`docs/evidence/m2-metadata-jobs-user-run`. Passing Rust logs, actual batch JSON
and generated files were not separately attached. These are assertions completed
by the fingerprinted runner, not independent execution here. The earlier failed
reports remain unchanged. No CLI rerun or project update is needed for the next
reader checks.

Native checklist accepted by user confirmation on 2026-11-03: “All five entries
correct, no crashes or missing entries.” This responds to the requested two-file
MDict/GoldenDict checklist, including styling and restart. The attestation and
exact requested output hashes are retained in
`docs/evidence/m2-metadata-jobs-native-user-confirmation`. Individual combinations
and restart observations were not separately itemized; no screenshot or trace
evidence is claimed. M2 area 2 is accepted within the bounded declared v2
metadata profile. Arbitrary native XML metadata behavior, production memory/
size limits and representative real-corpus qualification are not implied.
No further rerun is requested. Production sizing/indexing/resource limits are next.

The first Mac attempt stopped while compiling `tests/publication.rs`: comparing
`Vec<u8>` with an untyped empty array was ambiguous because both ordinary and
serde_json numeric comparisons were available. The assertion now uses
`bytes.is_empty()`. Only the integration test changed; packing/publication code,
workers, serializer, publisher and locks are unchanged. The original report and
23 source snapshots are retained under
`docs/evidence/m2-metadata-jobs-first-user-run`. No process case ran in that
attempt, and no Rust test-suite pass or native qualification is inferred.

The second Mac attempt compiled successfully and passed 30 tests (all 16 unit
tests, four application tests, six importer tests and four metadata tests).
All four new packing integration tests then failed at the same initialization
error: the engine refuses `header_attribute("KeyCaseSensitive", ...)`, because
it owns that field. The old setter also attempted StripKey next. Both calls are
removed; fresh packing now checks the builder-generated No/No declarations and
refuses an unexpected policy before composing metadata. Earlier qualified MDX
and MDD wire reports confirm those defaults. The serializer, publisher, worker,
sort order, options and lock remain unchanged. The report and 23 source
snapshots are retained under `docs/evidence/m2-metadata-jobs-second-user-run`.
No process case ran in that attempt. The subsequent successful batch above
qualifies the corrected fresh-packing path offline.

The metadata-only rebuild already passed offline and the user's native-reader
checklist. This slice adds fresh MDX/MDD packing with the same metadata policy,
and a separate serial worker for file publication. The qualified reader,
conversion/packing worker, read-only import worker and metadata-only publisher
implementations remain unchanged. All earlier evidence remains historical.

Keep `.venv`, prepared v6 `vendor`, real inputs and previous output directories.
The accepted command was:

```sh
.venv/bin/python scripts/m2_metadata_jobs.py --output m2-metadata-jobs-out-v3
```

The accepted report is `m2-metadata-jobs-out-v3/m2-metadata-jobs-report.json`.
No pip update or batch rerun is requested. The Cargo test command included
existing importer, metadata and read-only-worker tests.

Now test these two files one at a time in both MDict and GoldenDict:
`m2-metadata-jobs-out-v3/background/native-utf8.mdx` and
`m2-metadata-jobs-out-v3/background/native-utf16.mdx`. Check all five entries:
inline-red/marker-red show red, bold, bordered STYLE_ONE_OK; inline-blue/
marker-blue show blue, underlined STYLE_TWO_OK; plain shows PLAIN_CONTROL_OK.
Restart each reader and repeat, checking for crashes or missing entries. No MDD
is needed. Earlier native confirmation for the metadata-only rebuild files
does not substitute for these freshly packed file hashes.

## Request and metadata policy

The new API is `studio_v2_import::application::metadata::publication`. `Request`
is explicitly `pack_mdx`, `pack_mdd` or `rebuild`. Fresh requests carry owned
entries/resources and `Metadata` (title, description, stylesheet, optional extra
attributes); a rebuild wraps the existing source/destination/edit request.
All input is data. No Python, HTML or script code is executed by this API.

Fresh MDX selects UTF-8 or UTF-16 and writes v2, zlib, HTML, case-insensitive
literal keys with `StripKey=No`. Physical rows are stably sorted by the pinned
Unicode16 whole-string lowercase profile, preserving input order within equal
sort keys, including duplicates. A fresh pack does not inherit arbitrary
case/strip flags from another dictionary. Existing metadata-only rebuilds keep
their original flags and all binary sections.

Fresh MDD uses the same stable Unicode16 order and retains exact resource key
strings and bytes, including duplicates and zero-byte records. Resource keys
are archive data: this route does not extract files or interpret paths. Raw keys
such as `../raw.bin` may be stored, but cannot create filesystem files here.
The older safe-path MDD pack/extract API is not replaced or relaxed.

`mdict-v2-metadata-v1` is reused without changing its serializer or stylesheet
grammar. Titles/descriptions and other non-stylesheet whitespace use XML numeric
character references; stylesheets use the accepted literal-LF triplets with a
final LF. Numeric markers must reference existing rules and stay raw. Nonempty
styles derive Compact=Yes and are forbidden on MDD. Raw HTML, definition line
endings and redirects remain unchanged. Unknown ASCII non-namespaced extension
attributes are retained. Extra fields cannot override structural/profile fields
or namespace bindings, and cannot assert Studio policy tags.

## Verification and commit

The engine first packs into a private staging file using PreserveInput after
the explicit frozen sort. The importer reopens that file with checksum
verification and compares every physical row/resource with the sorted request.
The accepted serializer then writes the requested metadata into another private
input, retaining every data-section byte; the imported attributes must match
the request. Finally, the unchanged metadata-only publisher snapshots this input,
verifies all records/metadata again, and commits an exclusively published file
in the destination directory. No existing destination is overwritten.

Metadata-aware pack output uses the ordinary import API for verification; it
is not silently passed to the older Studio-only export verifier. The actual
file bytes and metadata are checked against independent Python/wire oracles in
the process batch. Summary results contain path, operation, record count, size
and profile, without copying the full dictionary into the GUI mailbox.

Cancellation is cooperative while adding entries/resources, after engine
encoding, during header copying, and through the publisher's pre-commit check.
Encoding itself is not preempted inside the engine. Private stages are dropped
on failure/cancellation. Successful execution means publication committed; the
worker performs no cancellation check or fallible result accounting afterward.
A cancellation racing after commit therefore keeps success and the output.

Panics are caught by the publication worker and reported as an internal failure
with `publication_uncertain=true`. It does not delete a possibly committed file
or retry automatically. Callers must inspect the destination. Ordinary typed
failures have `publication_uncertain=false`, meaning this operation did not
commit a new file; an existing destination may still be present and untouched.
Process abort, OOM and power-loss recovery are not provided by catch_unwind.

## Queue, ownership and size envelope

The dedicated worker reuses shared cancellation/progress/lifecycle/error types,
with defaults of two pending jobs and eight retained records; configurable
ceilings are four pending and eight retained, with room beyond pending capacity
for an active job. Events coalesce to one dirty snapshot per retained job.
Summary collection transfers ownership once; forgetting a terminal job releases
its retained state. Failed jobs retain no success summary. Shutdown requests
cancellation without waiting; join/wait helpers are for non-UI code. Drop requests
cancellation and detaches. Other workers remain separate: no global ordering or
combined memory semaphore across conversion, import and publication is claimed.

Admission validates and measures the request on the caller thread. It scans
bounded owned input and is not constant-time; a future GUI adapter must prepare
large requests off its UI thread. Requests are at most 16 MiB serialized, with
1..1000 rows, 4 KiB keys, 1 MiB per body/resource and 8 MiB total decoded row data.
Metadata and its UTF-16 wire header are capped at 64 KiB. Existing 16 MiB file
caps remain. More than one staged file, decoded index and owned request can
coexist; serialized and decoded caps are not hard RSS or pre-decompression
allocation guarantees. Production sizing remains the next M2 work area.

## Authored qualification

Seven gated worker tests cover queued/active cancellation and recovery,
queue/retention/mailbox/collection bounds, cancellation through the real runner
API after a simulated commit, panic after a simulated file publication and
recovery, shutdown/closed admission, nonblocking drop, unknown IDs and invalid
configuration/structural overrides. Four integration tests use real packing for
both encodings, metadata/duplicates/markers/redirect lookup, raw MDD duplicates
and empty bytes, cancellation at three stages, no-clobber, background rebuild
and typed failed-job recovery. The Mac Rust test command passed; individual
passing test logs were not attached separately.

The process batch executes 28 requests through each route: ten successful
publications and eighteen expected refusals per route (56 job outcomes).
Each route uses one process batch; background jobs reuse one long-lived runner,
so successful recovery after typed failure is checked through real file output. Independent Python/
wire readers check stable physical order, duplicate bytes, metadata, unchanged
rebuild sections, checksums and marker expansion. Refusals cover destination
protection, structural overrides, XML/style errors, NUL definitions, key/body/
count/header budgets, missing source and clearing live styles. The batch asserts
no partial outputs or staging residues remain. It runs four external commands
when successful: package artifact refresh, Rust tests and the two CLI batches.

The two new controls at `background/native-utf8.mdx` and
`background/native-utf16.mdx` contain the same five red/blue/plain entries as the
accepted metadata-only controls, but use fresh entry packing. Their exact hashes
and Python expansion checks are recorded for later native review. Earlier native
confirmation is not reused as evidence for these new file bytes.

All 126 prior source identities are guarded. The accepted `metadata.rs` only
appends `pub mod publication;`. New code lives in the child publication module,
worker, tests and CLI. All existing implementations, older scripts and locks are
unchanged; no dependencies were added. There is no Tauri integration, persistent
reader session, v1/v3/encryption support or production-corpus qualification here.
