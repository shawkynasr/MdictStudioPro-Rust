# Ordinary v2 import application composition and background jobs

Accepted 2026-11-01 on the user's Mac. All 56 commands passed: artifact refresh,
Rust tests and 27 cases through both sync/background routes. Fifteen successful
case pairs matched the qualified oracles, and twelve failure pairs returned the
expected typed errors without partial results. Positive cases checked 420 MDX
lookup/redirect results and four MDD resource queries per route. Reply transfer,
coalesced events, byte accounting, forgetting and terminal cancellation checks
passed. All 114 protected and 15 current source hashes match; the 61-package
dependency graph and complete lock bytes remain unchanged. M2 is not complete.

The unchanged report and source snapshots are retained under
`docs/evidence/m2-import-jobs-user-run`. Passing command logs and individual
actual JSON were not separately attached. Deterministic cancellation/queue/
shutdown/panic tests passed through the fingerprinted Rust test command; no
separate trace evidence is claimed. The bounded ordinary-v2 import-routing area
is accepted. Metadata/stylesheet preservation is next. No rerun is requested.

The preceding synchronous reader passed 26 qualification cases. This step adds
an explicit application request/reply API and an import-specific background
worker in `studio_v2_import::application`. The reader already depends on
`studio-application` for shared types. Keeping composition here avoids a circular
dependency; it does not change the converter/packing facade or its qualified
worker. No new dependency or lockfile change is introduced.

Preserve `.venv`, prepared v6 `vendor`, real inputs and previous outputs.
The accepted command was:

```sh
.venv/bin/python scripts/m2_import_jobs.py --output m2-import-jobs-out
```

The report is `m2-import-jobs-out/m2-import-jobs-report.json`. It includes source
hashes, the dependency lock, a failing command's output tail and Python exception
tracebacks. A comparison failure may also need the named `*-actual.json` file.
The output directory must be new. No pip update, native-reader check or old batch
rerun is requested. The new test command includes the existing importer tests.

## Explicit import requests and replies

`Request` requires a source path and either MDX with an explicit lookup policy
or MDD. Each action is typed: MDX `lookup`/`resolve` or MDD `resource`. Unsupported
action/source combinations are rejected before file work. Unknown JSON fields
are rejected. Admission checks at most 64 actions, 4 KiB per query, an 8 KiB path
and 64 KiB serialized request metadata; they never open a dictionary on the
caller thread.

`execute` opens and fully validates one dictionary, runs the ordered actions and
drops the dictionary before returning. Its response contains unchanged header
metadata, the declared policy, the physical record count and typed per-action
results. It does not return a full record dump, cache a live dictionary or publish
files. Opening a source is always the ordinary-v2 API; there is no fallback that
weakens the separate Studio export verifier. Persistent reader sessions and a
Tauri command adapter remain later work.

Open/integrity/cancellation failures and aggregate reply-budget failures return
no partial reply. Expected per-query failures retain their shared error code and
import-specific detail (for example `redirect_cycle`), allowing the remaining
actions to be inspected. Cancellation is always a job failure, never an embedded
query error. Raw HTML, scripts and numeric stylesheet markers are returned as
data and never rendered or executed here.

Requests can lower entry/result/hop limits, but cannot raise the qualified
defaults. The whole serialized response has a default and ceiling of 2 MiB,
checked using a counting writer without allocating a JSON copy. It is checked
after each action and again before the background result is retained. Existing
per-query and input caps still apply. This is a reply-retention bound, not a
hard RSS or engine pre-decompression bound. Temporary query allocations and
owned Rust structure overhead remain outside that serialized byte counter.

## Import worker ownership and lifecycle

The import runner reuses the shared `CancellationToken`, `Progress`, `Stage`,
job `State`, admission error types and cancellation outcomes. It owns one serial
worker and a coalescing polling mailbox. Defaults allow two pending requests and
eight retained job records; configuration permits 1..4 pending and at most eight
retained records, with an extra slot beyond the pending capacity for an active
job. Admission is bounded and never evicts terminal jobs automatically.

This worker is separate from the existing conversion/packing worker. They do not
share global ordering or a combined memory semaphore. An eventual app may run
both concurrently; no claim of one serial queue across every operation is made.
The prior worker and all its behavior remain unchanged.

Snapshots contain progress, lifecycle state, a bounded failure message and reply
availability/byte counts. They contain no payload copy. `take_result` moves the
reply out once and releases the runner's ownership; subsequent calls return
`None`. `forget` releases a terminal record and any uncollected reply. Unknown
IDs and attempts to collect/forget unfinished jobs have typed errors. Collected
reply memory becomes the caller's responsibility.

Queued cancellation drops the request before file work; active cancellation is
cooperative through the shared token, including between actions. Success commits
after the final cancellation check; a racing late cancellation does not roll
back a completed read-only reply. Completed cancellation requests return
`already_finished`. Shutdown closes admission and requests cancellation without
waiting. Drop detaches after requesting cancellation. Explicit `join` and
`wait_for_terminal` are for CLI/tests or a non-UI shutdown task. Worker panics
become typed internal failures and the next job can run. No filesystem output is
published by these import operations.

## Qualification authored

Six deterministic worker unit tests use a gated executor to cover queued/active
cancellation and recovery, queue and retained-record limits, single result
transfer, coalesced events, panic recovery, shutdown/closed admission, nonblocking
drop, unknown IDs, invalid requests/configuration and aggregate reply limits.
Four new integration tests exercise real dictionary operations, sync/background
reply equality, duplicate lookup/redirect results, action-phase cancellation,
typed open failure with recovery, reply caps and binary MDD resources. Existing
reader tests still run in the same Rust command.

The process batch reuses the unchanged qualified Python/wire fixture generator
and oracles. It compares sync/background results for all 26 reader cases, plus
one whole-reply-cap failure: 27 cases executed by both routes, after the artifact
refresh and Rust test command (56 commands total when successful). Positive
cases check raw headers, physical counts, exact lookup/redirect oracles and MDD
bytes. Background cases also check state, progress job IDs, one coalesced event,
reply byte accounting, single collection, explicit forgetting, late cancellation
and absence of partial failed replies. Detailed cancellation/queue/panic ordering
is exercised by the gated Rust tests, not inferred from timing of the process
batch.

All 114 previously qualified source identities are guarded. The accepted reader
`lib.rs` changes only by appending `pub mod application;`; its implementation,
header parser, lookup code, tests, original CLI, scripts and lock stay unchanged.
Their accepted snapshots and reports remain intact. Only the new module, new
worker/tests/CLI and qualification script implement this step.

No GUI, real-input qualification, metadata rebuild serialization, production
sizing or v1/v3/encryption support is added by this batch. This accepted batch
closes the application-routing subgate of M2 area 1 within the stated bounded
one-shot profile.
