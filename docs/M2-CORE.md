# M2 first implementation slice: studio-core

This document records the earlier foundation slice. Current MDD, converter and
background job work has passed its bounded batches; see `M2-REMAINING.md` for
the reviewed five-area closeout ledger. Historical statements below about work
not yet present refer to this foundation snapshot, not the current whole project.

Current addition: TXT I/O and the UTF-8 CC-CEDICT port passed the Mac batch;
see `M2-TEXT-CONVERTERS.md`. Earlier snapshots remain unchanged.

Latest extension: MDD APIs and staged extraction passed the user-run Mac batch.
See `M2-RESOURCES.md`. The MDX qualification below describes the
earlier preserved source snapshot and remains valid for that tested slice.

M1 is complete and unchanged. This first M2 slice passed Rust workspace tests,
both encodings and separate-process reopen on the user's Intel Mac on 2026-10-29.
The unchanged report and matching source snapshots are retained under
`docs/evidence/m2-foundation-user-run`. Ten commands returned zero; each output
had all 15 records preserved by independent Python and passed the wire audit.
Individual test logs were not supplied; no new test counts are inferred from
the process-level report. No rerun is requested. It is not the entire M2 or a
production-ready replacement for the original application.

## What is implemented

`m2/` is a separate two-crate workspace. It does not alter the original workspace,
locks, qualified source or completed evidence. Its lock reuses the exact external
package records from the qualified real-rebuild graph; only the application
package records change. The checked-in lock must be accepted by Cargo --locked;
if it is rejected, return the failure rather than update dependencies silently.

`studio-core` exposes PackRequest, Entry, Encoding, Limits, Error/ErrorCode,
CancellationToken, JobContext/Progress, pack_mdx and Dictionary. Engine types stay
private. Core errors have stable serialized codes for the eventual UI.

Packing validates owned input, stable-sorts with the frozen Unicode16 policy,
writes UTF-8 or UTF-16 v2 MDX with explicit headers, syncs a sibling temporary file,
strictly reopens every key/body, compares exact output rows and metadata, then
publishes using tempfile's no-clobber persistence. A destination created during
validation must be preserved. Ordinary failures/cancellation drop the temporary
file. Publication is the commit point: cancellation after it does not relabel a
successful write as failure. Parent-directory power-loss durability and crash
orphan cleanup are not yet a complete application contract.

Opening handles Studio-tagged outputs only and rejects missing/wrong policy,
flags, encoding and nonempty embedded stylesheet. Explicit Verify, full physical
scan, declared-count checks and monotonic normalized order precede returning the
owned exact/normalized index. Raw exact matches win; duplicates retain source
order. Lookup returns the complete selected group or a result-budget error; it
does not silently truncate duplicates or use the library locator.

Progress/cancellation is cooperative at entry and phase checkpoints. Sorting,
engine finish and individual decompression calls are not interruptible from this
API. Callers must keep progress callbacks non-panicking and run the synchronous
API in their job worker, not the eventual UI event thread. There is no background
job scheduler or GUI command routing yet.

## Limits and scope

Defaults retain 1,000 entries, 8 MiB decoded input/index rows and 16 MiB file size.
Additional caps: 4 KiB keys, 1 MiB definitions, 64 KiB metadata, 256 results and
2 MiB result payload. These bound accepted work, not engine peak allocation/RSS.
Header/block decompression happens before adapter checks; owned requests are
already allocated by the caller. Do not expose this as a hardened arbitrary-file
importer. Limits can be supplied explicitly; higher values need measurement.

This first slice uses empty embedded stylesheet and single-line title/description;
general metadata/stylesheet serialization stays deferred. Raising the probe cap,
adding a disk-backed/streaming index, general import and MDD support, converters,
redirects and preview isolation are subsequent M2/application work. Chinese,
English and Arabic GUI localization/RTL remain planned, not implemented here.

The casing implementation is extracted from the qualified M1 implementation;
its frozen baseline data and contextual FinalSigma algorithm are retained.
There is no production Python casing or conversion subprocess.

## Reproduce this slice only when needed

Update the ZIP in place, retaining .venv and vendor, then run:

```sh
cd "$HOME/Downloads/mdict-studio-m0-m1"
.venv/bin/python scripts/m2_foundation.py --output m2-core-out
```

The runner verifies the existing v6 source, exact dependency reuse and pinned
casing data; runs the new Rust workspace tests; packs two tiny synthetic MDX
files; checks bytes/duplicate order with independent Python and the wire auditor;
then checks lookup from separate processes. It does not rerun M1, build real
corpus/stress files, install dependencies or ask for native-reader tests.

Rust workflow tests cover both encodings, exact/fallback lookup and payload
preservation, invalid inputs, budgets, pre-start and verification cancellation,
the destination-creation race, cancellation after commit, duplicate result caps,
strict checksum errors and output-limit cleanup. The Mac report confirms the
Rust workspace test command passed. Rust was not executed in the authoring
environment, where Cargo/rustc remain unavailable.

Return m2-core-out/m2-foundation-report.json and the named log if any step fails.
A pass qualifies this slice; it does not complete M2.

The CLI also accepts `pack REQUEST.json OUTPUT.mdx` and `lookup FILE.mdx QUERY`.
Request fields are title, description, encoding (`utf8`/`utf16`) and entries
(`key`/`text`). Stdout contains one result JSON; stderr carries structured errors
and progress. This CLI is not the future Python plugin IPC protocol.
