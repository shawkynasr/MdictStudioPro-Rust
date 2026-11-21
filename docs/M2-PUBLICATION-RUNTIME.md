# Shared larger publication runtime: first integration gate

Accepted first Mac gate 2026-11-05 after the one-line reader test constructor
correction. All five Rust test/build/seed command receipts and both controller
scenarios passed. The 13 registered source-bound Rust tests cover deterministic
cancellation/shutdown/panic ordering; successful individual test stdout was not
attached. Source-bound report and nine exact snapshots:
`docs/evidence/m2-publication-runtime-user-run`. The original E0223 compile failure
and its sources remain under `m2-publication-runtime-first-user-run`.

Review checked 3,331 controller exchanges: nine publications, eight expected job
failures, 16 precancelled jobs and six expected API refusals. Reported recipe
digests for 196,608 physical records, four export hashes and four extracted-file
hashes were independently recomputed. Reader-plus-packing and reader-plus-export
admission was observed in both scenarios, with correct distinct weights. All final
shared reservations, reader handles and retained reader reply bytes were zero.
Maximum observed RSS was 108,470,272 bytes (103.45 MiB rounded).

Actual dictionary/export/extracted files and successful test stdout were not
attached. Full wire decoding, no-clobber output, input identity and staging cleanup
were checked by the exact-source-bound Mac harness; review separately checked
reported recipes/hashes, controller transitions and ledger arithmetic. All 190
protected source identities and the 66-package graph match; no registry version
changed. Runtime sources were unchanged by the fixture correction.

No rerun is needed. Keep `.venv`, `vendor`, private corpora and all previous
outputs. The accepted command below is retained for reproduction only:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m2_publication_runtime.py --output m2-publication-runtime-out-v2
```

For any requested reproduction, return the report including on failure and choose
a new output folder. No Python install, vendor
preparation or new MDict/GoldenDict visual check is needed for this integration.

## Composition

The isolated `m2/publication-runtime` workspace composes the accepted larger
`studio-large-io` operations and `studio-stream-extract` extraction function with
managed `studio-sessions` readers. It preserves previous runtimes as qualified
artifacts; this new runtime replaces neither their source files nor defaults.

One serial publication worker handles all five operations: MDX packing, MDD
packing, JSONL export, canonical TXT export and streaming MDD extraction. Default
queue capacity is two pending requests and eight retained jobs, including running,
queued and terminal jobs. Callers must forget terminal jobs to free retention.
Results transfer once and contain thin receipts, never dictionary body vectors.
Tagged responses distinguish dictionary-file receipts from extraction receipts.

Requests contain paths and small metadata only; aggregate path/metadata lengths
are capped at 64 KiB, individual paths at 16 KiB and extra attributes at 256.
The diagnostic controller separately caps each JSONL command at 64 KiB before
parsing. Snapshot errors retain at most 4 KiB of message text and progress is
coalesced to the latest value. Retained receipt metadata is bounded by the
qualified header serializer and the eight-job count. These bounds are separate
from active-operation logical reservations.

The serial queue prevents simultaneous publication jobs. Persistent readers have
their existing separate actor threads, so an admitted reader can serve pages
while publication runs. Reader close acknowledgement still waits for the original
reader/index cleanup and release of the new shared reservation. Blocking join
helpers belong off the GUI thread; the controller is only a Rust diagnostic tool.

## Logical admission

Every reader reserves before opening its dictionary/index. Every publication
reserves at dispatch, before its executor reads source files or stages output.
Reservations share one ledger and release through RAII after normal success,
ordinary error, cancellation or panic.

| Operation | Memory weight | Temporary-file weight |
| --- | ---: | ---: |
| Persistent reader | 96 MiB | 768 MiB |
| MDX or MDD packing | 192 MiB | 768 MiB |
| JSONL or TXT export | 96 MiB | 768 MiB |
| Streaming MDD extraction | 96 MiB | 3 GiB |

The new profile admits at most two active operations, 384 MiB total logical memory
weight and 4 GiB total logical temporary-file weight. Limits may only be lowered.
Packing's weight is higher than export's because the qualified writer still owns
its inputs; the prior isolated packing run peaked at about 100.25 MiB. That
measurement is not proof of a 192 MiB allocator ceiling for every admitted input.
The profile is a scheduling model, not operating-system memory/disk enforcement.
Actual RSS is measured separately against a provisional 384 MiB observation
threshold for the process; retained requests/results and caller allocations are
not allocator-metered by the ledger.

Two live readers occupy both active slots, so a publication submitted then fails
with `limit_exceeded` / `resource_admission` before executing. It is not left
waiting for a reader to close. After one reader is closed and released, the caller
can submit another job. Reader plus packing reserves 288 MiB memory and 1.5 GiB
temporary space; reader plus export reserves 192 MiB / 1.5 GiB. Reader plus
extraction reserves 192 MiB / 3.75 GiB. Only one publication is active at a time.

Packing retains its 32 MiB decoded-input / 100,000-row candidate caps and owned
builder. Export retains its per-record bounded traversal and strict staged
reparse. Extraction retains its streaming span writer and path preflight. None
of those operation limits is raised by this integration. Index construction,
converters and earlier small workers still use separate scheduling.

## Publication and cancellation

Native operation tokens and progress callbacks are adapted directly; raw
dictionary payloads do not pass through the controller protocol. Engine limit
details are preserved when adapting extraction errors to the common failure
shape. The original errors remain typed, and internal panic messages are bounded.

Queued cancellation drops the request without running it. Running cancellation
uses each accepted operation's checkpoints, including its final precommit check.
The owned builder's synchronous `finish` call remains internally uninterruptible;
its next checkpoint handles cancellation before publication. Shutdown closes new
admission, closes readers and cancels queued/running publication jobs.

Once an executor returns success after publication, the worker stores that
success without an additional token check or fallible reply-size calculation.
A late cancellation or shutdown cannot relabel a committed success as cancelled.
An executor panic is conservatively marked `publication_uncertain=true`, whether
it occurred before or after commit; inspect the destination before retrying.
RAII releases the active reservation in either case.

## Mac qualification batch

Thirteen Rust tests include the extraction/reader integration cases and add
distinct packing/export charges, lowered admission budgets, reader contention,
mixed-operation queue/retention limits, mid-pack cancellation and recovery,
mid-export cancellation, precommit shutdown, postcommit success, and dictionary
panic handling. Condition-variable gates make these ordering tests deterministic.

The process batch starts two controllers, one per MDX encoding. Each opens two
readers, verifies admission refusal, closes one reader, and then packs 65,536
entries while requesting an indexed reader page. It exports the result as JSONL
and canonical TXT and runs streaming extraction through the same queue. The
UTF-8 scenario additionally packs a 65,536-resource MDD from selected-root files.

Independent stdlib decoding checks every packed record and metadata; exports
are compared byte-for-byte to recipes; extracted files are hashed independently.
The batch also checks malformed/missing inputs, no overwrite, pre-cancellation,
retention refusal, single-transfer receipts, late cancellation, shutdown refusal,
input/cache/resource identity, private staging cleanup and final zero shared
reservations/reader reply retention. Full controller exchanges and receipts are
embedded in the report. Active ledger observations are recorded when sampled;
the deterministic Rust tests establish ordering even if a fast process finishes
between observations.

All 190 prior source identities are checked unchanged. The isolated lock has
66 package records: the union of accepted extraction/session and larger-IO
dependencies with the unused old facade removed and the new local facade added.
Registry versions and checksums do not change. Compiler RSS and Python oracle
memory are excluded from the controller RSS measurement.

Acceptance is scoped to these source-bound tests. Converter sizing/admission,
representative real-input workflows, full candidate ceiling combinations,
operating-system resource enforcement, additional platforms, GUI routing and
final M2 closeout remain open. This gate does not implement MDX v3 or encryption.
