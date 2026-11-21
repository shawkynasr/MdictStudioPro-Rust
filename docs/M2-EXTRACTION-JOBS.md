# Background extraction and shared reader admission

Accepted first gate 2026-11-05. Mac Rust test/build commands and all three process
scenarios passed. Review recomputed 4,101 reported file hashes and examined 1,166
controller exchanges. They cover three successful publications, twelve expected
job failures (three admission refusals plus nine ordinary extraction failures),
24 pre-cancelled jobs and nine expected API refusals. Three reader page replies
remained correct while the composition performed extraction work.

All scenarios observed one reader and one extraction sharing the budget after
release of the second reader, then ended with zero active operations, retained
reader handles and retained reader reply bytes. All 171 prior source identities
and the 65-package graph match. Original report, provenance and nine exact source
snapshots are retained under `docs/evidence/m2-extraction-jobs-user-run`.
No rerun is requested.

| Scenario | Extracted files | Observed peak RSS bytes |
| --- | ---: | ---: |
| Cross-block resource | 2 | 5,300,224 |
| 32 MiB-plus resource | 3 | 5,316,608 |
| Many files | 4,096 | 6,664,192 |

Maximum reported RSS was about 6.36 MiB. This is an observation for these layouts,
not a hard memory bound. Individual successful Rust test stdout and actual output
trees were not attached: deterministic unit-test acceptance uses the exact-source-
bound successful command receipt, and file cleanup/preservation uses the bound
harness checks. The reviewer recomputed the reported hashes and logical state
without reading the user's actual output files. Full ceilings, older packing/
converter integration, real inputs and M2 completion remain unqualified.

The
isolated `m2/extraction-jobs` workspace composes the accepted session and streaming
extractor APIs. All 171 previous source identities and prior locks are guarded
unchanged. The graph contains 65 packages: the existing session/extractor graphs
plus one local facade, with no new registry dependency or version.

Keep `.venv`, prepared v6 `vendor`, private inputs and old output directories.
For reproduction only, choose a fresh output directory and run:

```sh
.venv/bin/python scripts/m2_extraction_jobs.py --output m2-extraction-jobs-out
```

Return `m2-extraction-jobs-out/m2-extraction-jobs-report.json`. It embeds compiler
failures, controller exchanges, receipts, file hashes, admission observations and
RSS. No native-reader tests, font setup or accepted-batch rerun are needed.
The first offline test may canonicalize only this new lock; its complete bytes
and package identities are recorded. Later build commands are locked and offline.

## Application composition

`Runtime` owns one serial extraction publisher, one accepted persistent-session
pool and one shared active-operation budget. `open_reader` returns a managed
reader handle. Its `session()` accessor supplies the existing page-job API.
`extraction().submit` returns an extraction job ID immediately; snapshot, progress,
cancel, result transfer, forget and wait follow the existing lifecycle vocabulary.

Extraction request metadata contains source/destination paths only. Each path is
bounded to 16 KiB; the operation uses the accepted fixed extraction ceilings.
The input is not opened until the worker acquires shared admission. A queued
job holds only bounded request/metadata slots. If admission is unavailable when
dispatched, the job fails with `limit_exceeded` / `resource_admission`, produces
no destination and requires an explicit later resubmission. It does not busy-wait,
silently evict a reader or retry a publication automatically.

The worker reuses the qualified `extract_mdd` implementation. It retains thin
publication receipts, not output resource bodies. Queues default to two pending
requests and eight retained jobs, with the same 1..4 / pending+1..8 configurable
bounds as earlier workers. Events coalesce to one latest snapshot per retained
job. `take_result` moves a receipt once; `forget` frees terminal metadata and an
untaken receipt. The thin receipt shape is fixed/bounded, so successful commit
does not depend on a later serialization or response-budget check.

## Commit and failure semantics

Before execution, a cancelled token stops the job without admission or input I/O.
Queued cancellation removes the request immediately. The extractor performs its
own final precommit cancellation checkpoint, then exclusively publishes the
verified directory. **No token check follows successful execution in the worker.**
Cancellation or shutdown after directory commit therefore preserves Succeeded
and its receipt, even when `cancel_requested` is true during result bookkeeping.

Ordinary extraction errors remain typed, preserve engine limit name/value/max
when present, and set `publication_uncertain=false`. Unwinding panics set
`publication_uncertain=true`; a caller must inspect the destination before retrying.
The worker does not delete an uncertain destination. The shared lease drops on
normal return and unwinding. Process abort, power loss, blocking filesystem calls
and allocation aborts are outside cooperative cleanup/cancellation guarantees.

The publishing worker deliberately uses different late-cancel semantics from a
read-only page worker, which may discard a completed but uncommitted response.
Earlier worker implementations and their tests are unchanged.

## Shared admission and managed close

| Profile | Memory reservation | Private-file reservation |
| --- | ---: | ---: |
| Live persistent reader | 96 MiB | 768 MiB |
| Running streaming extraction | 96 MiB | 3 GiB |
| Default runtime total | 192 MiB | 4 GiB |

At most two operations are active. Consequently, two readers fit, and one reader
plus one extraction fits (3.75 GiB reserved private-file space). Two extraction
profiles do not fit the temporary-space budget. A runtime may lower these caps,
not raise them. Reader reservation precedes underlying session creation and stays
held through Opening, Ready and Closing. Extraction reservation is acquired at
dispatch and released after the extractor returns/unwinds, before terminal job
acknowledgement. These are conservative logical admission allowances, not kernel
memory/disk quotas or measured RSS. The accepted extractor's per-file/output,
path-plan and parser limits continue to apply independently.

A dedicated reader monitor starts before any managed reader can be admitted.
It observes the accepted session's terminal cleanup barrier, releases its shared
lease, and notifies managed waiters. With active readers it checks at bounded
20 ms intervals; with none it waits on a condition variable. The monitor has no
user callback. The tracked set is bounded by the shared two-operation cap.

`Reader::close` requests cancellation without joining. `Reader::wait_closed`
acknowledges both the underlying private-reader cleanup and shared lease release.
Use this managed barrier, rather than the underlying session's wait, before
relying on new shared admission. `Reader::join` is a blocking disposal helper:
after the managed barrier, it joins the underlying actor and frees its metadata.
Dropping a reader requests close; the monitor keeps its reservation until cleanup
is acknowledged. Completed page replies remain available on retained closed
reader handles through the accepted session API.

Runtime shutdown closes shared admission, requests all readers to close and
cancels unfinished extraction work. `Runtime::join`, reader join and job waits
belong off a UI event handler. Runtime Drop requests shutdown and detaches its
service join handles; shared ownership keeps reservations alive through cleanup.

The accepted reader pool still bounds eight retained handles, eight jobs per
session and 8 MiB of retained serialized replies. Extraction retains at most
eight fixed-shape receipts plus bounded failure metadata. These retention ledgers
are separate from the shared active-operation gate; no postcommit global reply
allocation check can reverse a successful publication. Taken replies become
caller-owned memory outside retention accounting.

Use one Runtime for cooperating operations in this composition. Creating separate
runtimes creates separate budgets. Earlier converter, packing and metadata workers
do not yet participate in this gate, and there is no claim of a process-wide
reservation across those workers or arbitrary caller-owned memory.

## Authored qualification

Seven Rust tests cover profile arithmetic, real reader/extractor contention,
resource release after close/drop, late cancellation plus shutdown after actual
commit, bounded queues/retention, queued and mid-copy cancellation, panic before
and after actual commit, failure recovery and pre-cancelled requests. Test-only
executor gates run outside metadata locks; production requests contain no test
phase override. The Mac test command passed; individual successful test output
is not embedded in the report. Rust was not executed in the authoring runtime.

The Python batch uses the bounded Rust-only diagnostic controller and records
three process scenarios: a cross-block archive, a 32 MiB-plus-seven-byte resource,
and 4,096 files. For each it opens two readers, checks extraction admission failure,
closes/releases one reader, retries successfully while the other remains usable,
compares every output file and receipt, tests ordinary failures and pre-cancellation,
fills retention, then closes/shuts down. All final shared reservations and reader
retention must be zero. The instantaneous overlap snapshot is an observation;
the source-bound Rust contention test supplies the deterministic lifecycle check.

The harness checks unchanged source/cache bytes, existing-output preservation and
absence of normal-exit staging/private snapshot residue. It embeds successful
page replies, publication receipts, per-file hashes and controller exchanges.
`/usr/bin/time` measures the built runtime controller process, excluding Cargo,
the seed index builder and Python fixture generation. The provisional observed
RSS threshold remains 384 MiB; it is not an OS limit.

Local Python checks validate pinned identities, admission arithmetic and report
comparison behavior; they do not execute Rust. M2 remains partial. Larger packing
and converter paths, representative real-corpus qualification, remaining common
admission integration and final backend closeout are still outstanding.
