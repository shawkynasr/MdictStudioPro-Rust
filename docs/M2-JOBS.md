# Background conversion jobs and GUI polling

The background conversion job layer passed its bounded batch on the user's Mac
on 2026-10-30. M1 remains complete within its scoped engine decision. M2 remains
partial. No rerun of this batch is needed.

Both command steps passed: the Rust workspace tests and the background batch.
Twelve successful jobs matched original-plugin content/metrics and the exact
output hashes from the already qualified application API. All five expected
failed jobs retained their typed errors and destination-preservation checks.
The batch reports 50 delivered events; its terminal identity/revision/state
comparisons passed. This is the observed count for that run, not a fixed event
count for later runs, since intermediate updates may coalesce differently.

All twelve source/lock hashes, 90 protected source identities and the unchanged
60-package joint dependency receipt matched. The original report and exact
source snapshots are retained in `docs/evidence/m2-jobs-user-run`. The successful
Rust log and event transcript were not separately attached; no individual test
counts or independent event trace are inferred from them. Background MDX/MDD
operations, Tauri wiring, real-corpus scale and full M2 completion remain separate.

## Reproducing the accepted batch (not requested)

Update the existing folder from the project ZIP, keeping `.venv`, prepared v6
`vendor`, real corpus files and previous outputs. Run only the new batch:

```sh
.venv/bin/python scripts/m2_jobs.py --output m2-jobs-out
```

Return `m2-jobs-out/m2-jobs-report.json`. Unexpected failed-command output is
embedded in the report. A content/event mismatch may also require
`background-actual.json` or a named Python TXT file. The output directory must
be new. No package installation, dependency update, previous batch or native
reader test is requested.

## Public API and execution

`studio_application::runner::Runner` owns one named native thread. `submit`
accepts an owned `PublishRequest` and `Limits`, returning a session-local job ID.
The worker calls the qualified shared `convert_to_txt` API; file reading,
conversion, common TXT validation and publication run off the submitting thread.
Jobs execute serially in admission order. This is not a general-purpose thread
pool, Python plugin bridge, Tauri command layer or MDX/MDD job scheduler yet.

The default queue allows four pending jobs and one active job, with up to 32
retained records including queued, active and completed work. Configuration
permits 1..128 pending jobs and pending+1..256 retained records. Admission returns
typed `queue_full`, `retention_full`, `closed` or input errors rather than growing
unboundedly. No completed record is evicted automatically. `forget` explicitly
removes a terminal record; unfinished jobs cannot be forgotten.

Only one line, `pub mod runner;`, extends the qualified application facade file.
The body of that facade and all earlier qualified core/reader/converter files
stay exact. The new runner, tests and qualification client are separate files.
No registry dependency or lock changes are introduced.

## Polling and event semantics

`snapshot(id)` and `snapshots()` read current state. `drain_events()` returns at
most one changed snapshot per retained job and clears its dirty marker. There is
no unbounded event channel. Snapshots contain job ID, monotonic per-job revision,
state, cancellation request flag, latest application progress and a small output
summary or typed failure. Output summaries contain counts, bytes and destination,
not rendered entries or the converter's potentially large comment list. The
synchronous conversion API still exposes comments unchanged.

Intermediate state/progress updates can coalesce, including stage transitions.
This is a polling mailbox, not a complete event/audit log. Terminal state remains
queryable until explicit `forget`, even after draining events. A GUI should use
the latest revision per job and resynchronize from snapshots after reconnecting.
The GUI adapter must serialize access to draining events if there are multiple
consumers. There is one mailbox per runner, not per subscription.

States are `queued`, `running`, `succeeded`, `failed` and `cancelled`. Cancellation
is a separate request flag; it does not prematurely change a running job's state.
An active job may finish successfully after a late cancellation request because
publication already committed. Per-phase progress counters preserve the shared
API's units and do not form a global percentage.

## Cancellation, errors and shutdown

`cancel(id)` immediately removes queued work and records terminal cancellation.
For running work it sets that job's existing token and returns promptly. Tokens
are independent between jobs. Repeated requests and already finished jobs have
explicit outcomes. Normal conversion errors retain their application error code;
failure messages are bounded to 4 KiB at a UTF-8 boundary.

Job execution catches unwinding panics, reports an internal failure and allows
later jobs to run. A panic outcome marks `publication_uncertain=true`, because an
unexpected panic may occur around commit; it must not trigger automatic retries
or claim that no output exists. This does not recover from panic-abort builds,
allocation aborts, SIGKILL or process/system failure. Ordinary application errors
and cooperative cancellation retain the existing staged publication guarantees.

`shutdown()` stops admission, cancels queued work and requests cancellation of the
active job without joining. Dropping the runner does the same and detaches its
thread handle, so GUI teardown does not wait for an uninterruptible engine call.
The worker exits after active work returns. Explicit `join()` waits and belongs
on a shutdown worker or CLI thread. `wait_for_terminal` is likewise a blocking
CLI/test helper with a timeout; GUI handlers should poll snapshots/events instead.
No restart persistence or global cross-session job ID uniqueness is implied.

The mutex protects only small queue/record operations; file/conversion work runs
outside it. These are bounded accepted workloads and event storage, not a hard
RSS, latency, streaming or forced-termination guarantee. Existing converter and
XLSX format/size restrictions remain unchanged.

## Authored verification

Six deterministic internal runner tests use gates, not sleeps, to exercise serial
execution, queue/retention limits, queued and active cancellation, independent
tokens, late success, 10,000 coalesced progress updates, explicit forgetting,
typed failure, panic recovery, shutdown, timeout and nonblocking drop. Two real
worker integration tests check exact Mini TXT bytes, retained terminal delivery,
existing destination preservation and successful work after a failed job.

The existing application integration tests remain in the Rust workspace batch.
The new qualification client submits 17 real jobs: twelve baseline/extended
cases spanning all six converters and five expected per-job failures. Python
compares content/metrics with original plugins, verifies output summaries and
matches terminal events to retained state. A failed job is data in a successful
batch result; it does not crash the qualification client or stop later jobs.

The runner verifies 90 source identities, allowing only the exact public module
export in the previous facade, plus the unchanged 60-package dependency graph.
Two new Python contract tests pass in this authoring environment. The Rust test
command and real-job batch passed on the user's Mac; no local Rust toolchain is
available here. This is not yet a GUI integration or M2 closeout.
