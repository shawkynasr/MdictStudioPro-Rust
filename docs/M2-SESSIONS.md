# Persistent application sessions and background page jobs

Accepted first gate 2026-11-05. The Mac Rust test/build commands and all five
process scenarios passed. Review recomputed all 37 page replies (32 primary
pages and five pages after public source/cache replacement), and the logical
retention ledger across 497 controller exchanges. The transcript contains 87
successful jobs, ten cancelled jobs and 25 expected API refusals. Every scenario
ended with zero live-reader, retained-handle and retained-reply reservations.
Original report, provenance and eight exact source snapshots are retained under
`docs/evidence/m2-sessions-user-run`. No rerun is requested.

| Scenario | Records | Observed peak RSS bytes |
| --- | ---: | ---: |
| UTF-8 case/strip fixture | 416 | 4,202,496 |
| UTF-16 case/strip fixture | 416 | 3,969,024 |
| Binary MDD | 100 | 3,887,104 |
| Larger MDX | 65,536 | 6,017,024 |
| Larger MDD | 65,536 | 6,262,784 |

Maximum reported peak RSS was about 5.97 MiB. These observations apply to the
synthetic fixture layouts and one pool per controller process. Successful Rust
test stdout was not attached; lifecycle-test acceptance uses the exact-source-
bound successful command receipt. Input/cache binaries and standalone file
cleanup logs were not attached; normal-exit cleanup and source restoration were
checked by the bound harness. Full ceilings, other application workers, GUI
integration and M2 completion remain unqualified.

Earlier sizing and disk-index gates remain accepted. This step adds
the isolated `m2/sessions` workspace, with one local facade package and the same
accepted registry versions: 63 package records total. All 153 previously accepted
source identities and all prior locks are guarded unchanged. No engine patch,
registry version change or accepted-batch rerun is introduced.

Keep `.venv`, prepared v6 `vendor`, private real inputs and previous outputs.
For reproduction only, choose a fresh output directory and run:

```sh
.venv/bin/python scripts/m2_sessions.py --output m2-sessions-out
```

Return `m2-sessions-out/m2-sessions-report.json`. Use the existing Python 3.14 /
Unicode16 venv. The report embeds failed compiler/test log tails, successful
page responses, controller exchanges, source/lock identities and RSS observations.
No native-reader test or real input is needed for this synthetic lifecycle gate.
The first offline test may canonicalize only the new lock; its complete bytes
are returned. Later build commands are locked and offline.

## Application API and ownership

`Pool::open` returns a session handle immediately, with a background open-job ID.
The actor validates a private dictionary snapshot, attaches the verified disk
index, and publishes an `Opened` manifest. Open-job success and session Ready
become visible under one lock. A client that consumes/forgets the open job can
immediately submit page requests without racing an unfinished readiness update.

Each actor holds the reader and borrowing `Index` together on its worker stack.
The index never outlives the reader. No unsafe lifetime conversion, leaked reader
or self-referential owning struct is used. Each session has one serial worker;
the existing index implementation performs exact-first/frozen16 matching.
Repeated pages reuse the verified session; source/cache validation is not
repeated per query. Initial open still performs the full accepted validation.

`submit_page` accepts a query, explicit offset and up to 128 rows. Open and page
jobs expose revisioned snapshots, typed failures, a coalesced latest-progress
value and a dirty event flag. `drain_events` returns at most one latest snapshot
per retained job; it does not retain an unbounded event history or payload copies.

`take_result` moves a terminal reply out once, then releases its retained-byte
reservation. A second take returns no result. `forget` removes a terminal job,
discarding an untaken reply and releasing both its byte and metadata slots.
Taking a reply alone does not free its job slot. Running jobs cannot be forgotten
or collected. Payloads are serialized by reference for byte measurement; polling
snapshots contain no definitions or binary resources.

## Lifecycle and cancellation

Session states are Opening, Ready, Closing, Closed and Failed. Jobs use Queued,
Running, Succeeded, Failed and Cancelled. These are separate lifecycles: an
individual page failure does not automatically invalidate an otherwise usable
read-only session. Startup failure or actor panic terminates the session.

`cancel(job)` cancels queued pages immediately, removing their requests from the
queue. Running work observes the same cooperative token as the accepted reader
and index. Before retaining a completed read-only response, the actor checks
close/cancellation again. Thus an observed cancellation after materialization can
discard the complete page. A committed successful job remains successful if
cancel is called afterward. A pre-cancelled caller-supplied token can cancel an
open or page request before execution. Externally shared token updates are
cooperative; the serialized cancel API and result commit share the session lock.

`close` is nonblocking, stops new submissions, cancels pending/running work and
wakes the actor. Closing remains visible while cleanup is in progress. The actor
unwinds/drops its private index and reader, releases its live-reader admission,
and only then marks the session Closed/Failed. `wait_closed` acknowledges that
resource barrier. Previously completed replies can still be taken/forgotten
after closure; closing a reader does not silently discard those results.

Pool shutdown marks admission closed and requests close on every active session.
It does not block a UI caller. Dropping a session requests close and detaches the
join handle; dropping the pool requests shutdown. `wait_job`, `wait_closed` and
`join` are blocking controller/test helpers and belong off a UI event handler.
Cooperative cancellation cannot preempt a blocking filesystem call or a codec
operation in its middle; no immediate hard-stop latency is promised.

The actor boundary catches unwinding panics, fails unfinished jobs, drops all
reader/index locals and releases admission. It does not recover from process
abort, power loss or an allocator that aborts. Those outcomes are outside the
normal-exit cleanup claim. Failure messages are truncated at a UTF-8 boundary
to 4 KiB.

## Admission and retained data

| Resource | This pool's limit |
| --- | ---: |
| Live actors, including opening/closing readers | Default 2; configurable down to 1 |
| Retained session handles, including closed metadata | 8 |
| Pending page requests per session | Default 2; configurable 1..4 |
| Retained jobs per session | Default 8; pending+1..8 |
| Serialized individual response | At most 2 MiB; may be lowered |
| Retained serialized reply bytes across all sessions | 8 MiB |
| Logical memory reservation per live reader | 96 MiB |
| Logical private-file reservation per live reader | 768 MiB |

An open is admitted only while live-reader and handle slots are available.
The pool reports both live and retained-handle counts. Live reservations remain
held through close cleanup, and release on startup failure, panic and shutdown.
Closed handles remain charged to the handle cap until their last internal/caller
reference drops. Pool bookkeeping uses weak actor references, preventing an
ownership cycle. The maximum live reservation is 192 MiB memory plus 1.5 GiB
private files. The reader still uses its inherited 64 MiB parser accounting cap,
512 MiB source cap and 128 MiB cache cap. The additional reservation is a
provisional admission allowance, not measured allocator accounting.

Response byte admission uses the complete serialized `Response`, including tags
and JSON escaping. An individual or global retained-byte overflow fails the
whole job without retaining its reply. Taking/forgetting/dropping results releases
that accounting; moved values belong to the caller and are outside pool retention.
Bookkeeping bounds do not establish an OS RSS or filesystem quota. A caller can
own additional memory after taking replies; there is no process-wide reservation
shared with the earlier packing/conversion workers yet.

## Authored qualification

Nine Rust tests exercise real reader/index actors, including:

- Repeated pages after replacing the public source and cache; one-time transfer.
- Close while opening, with a gate proving admission stays held until cleanup.
- Queued/running cancellation, queue/retention admission and pool shutdown.
- Cancellation after a complete payload exists but before reply commit.
- Actor panic and release of its reader reservation.
- The global 8 MiB retained-byte cap, transfer release and drop release.
- Pre-cancelled open/page requests and per-response overflow recovery.
- The eight-handle cap even when all corresponding actors are already closed.

Deterministic gates are compiled only in Rust unit tests. They run outside the
metadata locks; production API requests do not contain test phase overrides.
The Mac test command passed against the pinned engine; individual successful
test logs were not embedded. Rust has not been executed in the authoring
environment.

The Python batch uses a Rust-only diagnostic controller speaking bounded
line-delimited JSON over stdin/stdout. It runs no Python plugin. Each command
line is bounded before deserialization; controller responses include the measured
session payload plus a small diagnostic envelope. `serde_json::Value` conversion
in this test controller has caller-owned overhead beyond session retention.
It has at most eight handle entries and joins workers on normal EOF. This
diagnostic protocol is not the future Python-plugin IPC protocol.

Five process scenarios cover UTF-8/UTF-16 case/strip-aware dictionaries, binary
MDD, and 65,536-row MDX/MDD. Each builds its matching index with the already
accepted builder, then opens a persistent session, pages repeatedly, checks
physical results, transfers once, cancels a pre-cancelled job, replaces/restores
only its generated public fixtures, checks concurrent reader admission, fills
job retention, closes, reopens with cancellation and shuts down. Source/cache
bytes must be restored and no normal-exit private snapshots may remain.

The report embeds successful page values and controller transcripts for review.
`/usr/bin/time` measures the built session controller process, excluding Cargo
and index-builder RSS. The provisional 384 MiB observed-RSS threshold is reused;
it is not an OS memory limit. The matrix does not test full source/cache ceilings,
all cross-platform filesystem behavior or GUI event-loop integration.

M2 area 3 remains open. This facade connects persistent readers to application
session/page jobs. Index construction is still an explicit separate operation;
the existing converter/packing/publication runners are unchanged. A combined
global queue, larger packing/converter/extraction paths, representative real
inputs and final regression/closeout remain outstanding. Tauri/GUI adapters,
Chinese/English/Arabic localization, redirects across large sessions and v3
support are not part of this gate.
