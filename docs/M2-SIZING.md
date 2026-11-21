# Production sizing: first bounded-reader gate

Accepted first gate 2026-11-03. The corrected Mac run passed all three setup,
Rust test and build commands, then all 29 process cases: eight successful
scan/query cases and 21 expected refusals. All 133 prior source identities and
the 62-package graph match. The original report and nine exact source snapshots
are retained in `docs/evidence/m2-sizing-user-run`.

| Larger fixture | Records | Logical payload bytes | Peak RSS bytes |
| --- | ---: | ---: | ---: |
| UTF-8 MDX | 262,144 | 67,108,864 | 4,677,632 |
| UTF-16 MDX | 65,536 | 16,777,216 | 4,222,976 |
| Binary MDD | 65,536 | 16,776,960 | 3,719,168 |

All successful scans retained zero locator bytes. Maximum reported parser
accounting was 371,375 bytes, distinct from process RSS. These observations
apply to the generated block layouts and payload recipes; full profile ceilings,
real input diversity, indexes and larger application paths remain unqualified.
The successful test command's stdout and individual query values were not
attached; acceptance uses the exact-source-bound harness receipt. No separate
logs, screenshots or native-reader checks were supplied or requested. No rerun
is needed. M2 area 3 stays open.

The first Mac run compiled successfully: the reused header
unit and two integration tests passed; three integration tests failed because
their shared MDX builder fixture omitted the required `Format=Html` declaration.
The unchanged header policy rejected it before the intended limit checks. Only
the test fixture is corrected. Original report and nine source snapshots are
retained in `docs/evidence/m2-sizing-first-user-run`. The corrected retry above
completed the large-fixture and Mac memory measurements.

This step adds an isolated `m2/bounded-engine` workspace. It does not raise the
qualified application, converter, packing or extraction budgets. It is the
reader building block for subsequent larger-path integration, not a production
readiness decision. Three overall M2 areas still remain.

Keep `.venv`, prepared v6 `vendor`, real inputs and all prior output directories.
For reproduction only, use a fresh output directory and run:

```sh
.venv/bin/python scripts/m2_sizing.py --output m2-sizing-out-v2
```

Return `m2-sizing-out-v2/m2-sizing-report.json`. The report records source identities,
the complete lock, failing compiler output or Python traceback, parser memory
accounting, input identities and process peak RSS. A data failure may also need
the named log or actual JSON. This generates larger synthetic inputs locally;
the fixtures are excluded from the downloadable package. No pip update, engine
vendor regeneration, old-batch rerun or MDict/GoldenDict testing is requested.

## Audit finding and selected strategy

The pinned mdictlib 0.2.8 already supplies parser limits and lazy record access.
The existing adapters used its finite defaults, then applied their own smaller
owned-row limits. This new route selects explicit engine ceilings and avoids
the full owned `Vec<Entry>`/resource collection and lifetime lookup locator.
It uses the engine's existing mechanisms rather than a new decompression parser.

The API is `studio_bounded_engine::Dictionary::open_v2`. It first copies a capped
source into a private snapshot, reusing the unchanged qualified header parser
by source inclusion. The parser admits the existing unencrypted UTF-8/UTF-16 v2
MDX/MDD profile. Engine open uses Verify and explicit Limits. Before returning a
reader, a sequential pass validates every physical record/resource, checks
ordinal continuity, counts decoded bytes and computes a framed diagnostic
fingerprint. Entries are dropped between iterations; no complete body collection
is retained. A failure or cancellation returns no usable reader.

`lookup_exact` scans keys and materializes only matching rows. It preserves raw
key spelling, physical ordinal and duplicate order. It returns all matches or an
error on count/byte overflow. It does not use implicit header normalization,
resolve redirects or allocate an engine locator. This is an explicit new
`raw-exact-bounded-scan-v1` policy, not a change to the earlier application's
qualified exact-first/frozen-normalized policy. Its O(n) lookup is a deliberate
first gate, not the final fast interactive lookup design.

The engine's persistent-index API was also identified during the audit, but no
index is built or published in this step. Its normalization and artifact binding
must be integrated with the application's frozen policy and cache lifecycle
in a subsequent subgate. MDD streaming spans and larger publication/extraction
paths, cross-worker aggregate admission and XLSX sizing also remain open.

## Provisional profile ceilings

These are candidate ceilings to measure, not a promise that every combination
within them succeeds. Aggregate limits may reject an operation sooner.

| Counter | Candidate ceiling |
| --- | ---: |
| Source snapshot | 512 MiB per open reader |
| Physical records | 500,000 |
| Cumulative decoded scan, keys plus payloads | 2 GiB |
| Wire header / XML budget | 64 KiB; at most 256 attributes |
| Keyword / record index | 16 MiB each |
| Retained block metadata | 16 MiB |
| Compressed / decompressed individual block | 8 MiB each |
| Entries declared in one key block | 65,536 |
| Materialized record / application decoded record | 2 MiB |
| Aggregate engine working-memory accounting | 64 MiB per open reader |
| Engine locator entries and bytes | Zero: locator operations disabled |
| Exact query key | 4 KiB UTF-8 |
| Returned matches / raw query bytes | 256 / 2 MiB |
| CLI request / complete serialized reply | 64 KiB / 2 MiB |

The public `Limits.dictionary` reuses the old core type only for the snapshot's
file/header counters; its other small-core fields do not control this new scan.
The new scan counters and engine limits above are explicit. Configuration may
lower these ceilings, not raise them or enable a locator. Data-derived engine
limit failures keep the engine's limit name, requested value and ceiling, with
the application's shared `limit_exceeded` error code. Allocation failure has a
distinct detail; checksum, decoding, I/O and cancellation errors remain typed.

Engine accounting is not RSS and excludes returned caller-owned values. The
adapter also owns a header snapshot, one returned record, bounded query vectors
and JSON structures. UTF-16 decoding can expand UTF-8 output, so decoded record
size is checked separately after engine materialization. A large binary JSON
reply can have structure overhead before serialization is counted. Several
readers opened concurrently would need an application-wide reservation policy;
this first CLI opens one at a time. No hard process-memory guarantee follows.

The process batch records `/usr/bin/time -l` maximum RSS in bytes on macOS
(Linux time -v is parsed in KiB and converted). It runs the built reader binary
directly; compiler/Cargo memory is not confused with reader RSS. A provisional
384 MiB observed-RSS threshold fails the test if exceeded. This is a benchmark
acceptance threshold, not a kernel memory limit or a predictive global budget.
No multi-gigabyte readiness claim is made.

## Fixture and failure evidence authored

A stdlib Python writer streams synthetic keys/record blocks to temporary files;
it does not call either Rust writer or retain all rows. Small UTF-8, UTF-16,
binary MDD and plain-block files are checked with the independent wire auditor
and legacy Python reader before Rust comparison. Larger cases include 65,536
UTF-16 rows, 262,144 UTF-8 rows with approximately 64 MiB logical bodies, and
65,536 MDD resources. Actual file/decoded sizes and observed RSS are returned.
The profile's full 500,000-row / 512 MiB / 2 GiB ceilings are not exercised by
this first matrix and remain unqualified as complete size targets.

Whole-scan counts, key/payload bytes and an ordinal/length-framed FNV-1a-64 value
are compared with the independently generated recipe. FNV is a regression
fingerprint, not a cryptographic identity or proof against chosen collisions.
Source SHA-256 binds every tested file; engine Verify checks source checksums.
Small files also get independent Python physical-row comparisons. Duplicate,
missing, upper-case-different, Chinese and supplementary-key query results are
checked exactly, including empty binary payloads.

Probes lower individual valid-file budgets, reject an oversized real record,
alter huge header/index/block declarations, change key/record checksums and
truncate data. Structural refusals can precede a limit check when the declared
extent is impossible; those probes must still fail without partial output.
The valid-file lowered-limit probes specifically require limit_exceeded.
Cancellation is tested at snapshot, full-scan and lookup phases. A private
per-process TMPDIR must be empty afterward; every source SHA-256 must stay
unchanged. Cancellation is cooperative between bounded block/record operations;
engine work is not preempted mid-codec call. Abort/power-loss cleanup is not
claimed by normal RAII checks.

Five Rust integration tests cover full scan/no-locator duplicate lookup, typed
engine caps, cancellation, cumulative/materialization/count limits, binary/empty
MDD records and refusal to enable a locator. The reused header module's unit
regression also runs. The corrected Mac test command passed; individual
successful test output is not embedded in the submitted report.

## Dependencies and follow-on work

All 133 previous source identities and every previous lock are guarded unchanged.
The new workspace adds one local package to the accepted 61-package graph.
Its direct dependencies were already present at the same versions/checksums.
The first offline test may canonicalize only the new lock; its complete bytes
and all 62 package identities are returned for review. Later commands are locked
and offline. No engine patch or package upgrade is introduced.

After this gate passes, choose revised measured targets, qualify persistent
index/paged matching with the frozen lookup policy, streaming resource output,
larger packing/converter paths and shared resource admission. Representative
real-input qualification and final backend closeout still follow area 3.

API audit references (published documentation displayed version 0.2.8, reviewed
2026-11-03; compilation against the checksum-pinned local crate is still required):

- [Limits](https://docs.rs/mdictlib/latest/mdictlib/struct.Limits.html)
- [MemoryUsage](https://docs.rs/mdictlib/latest/mdictlib/struct.MemoryUsage.html)
- [MdxFile lazy entries and key-index APIs](https://docs.rs/mdictlib/latest/mdictlib/struct.MdxFile.html)
- [MddFile resources and spans](https://docs.rs/mdictlib/latest/mdictlib/struct.MddFile.html)
