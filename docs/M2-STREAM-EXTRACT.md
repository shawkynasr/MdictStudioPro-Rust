# Streaming MDD extraction: first staged-output gate

Accepted first gate 2026-11-05. The corrected Mac Rust test/build commands and
all 30 process cases passed: four successful extractions and 26 expected
refusals. Review recomputed the 4,105 reported file hashes and aggregate resource
digests from the independent byte recipes. All 161 previous source identities and
the 62-package graph match. Original successful report, provenance and ten exact
source snapshots are retained in `docs/evidence/m2-stream-extract-user-run`.
No rerun is requested.

| Case | Files | Largest resource bytes | Record blocks | Observed peak RSS bytes |
| --- | ---: | ---: | ---: | ---: |
| Cross-block resource | 3 | 200,000 | 4 | 2,932,736 |
| Large resource | 3 | 33,554,439 | 513 | 3,489,792 |
| Uncompressed blocks | 3 | 8,388,611 | 129 | 3,620,864 |
| Many files | 4,096 | 256 | 16 | 4,792,320 |

Every success reported zero locator bytes and zero materialized-record limit.
Maximum observed process RSS was about 4.57 MiB, with maximum parser-accounted
peak 381,562 bytes. These measurements apply to the generated layouts and
payload recipes, not all combinations within the candidate ceilings. Successful
Rust test stdout and actual output directories were not attached; acceptance
uses the exact-source-bound test receipt and harness output-tree/cleanup checks.
The reviewer recomputed reported hashes without inspecting user output files.
Background integration, full ceilings, real inputs and M2 completion remain open.

The first Mac run stopped at Rust E0308 in the new
`core_error` adapter: the core and application ErrorCode enums are distinct.
No Rust tests or extraction process cases ran. The adapter now maps every core
variant explicitly, preserving its serialized application code and message;
a Rust regression exercises all variants and an actual unsafe-path refusal.
Original report and ten source snapshots are preserved under
`docs/evidence/m2-stream-extract-first-user-run`. All earlier sources are unchanged.
The corrected retry above passed. This
adds the isolated `m2/stream-extract` workspace and a standalone typed
`extract_mdd` API. All 161 earlier qualified source identities and earlier locks
remain guarded unchanged. The new graph has 62 package records: the accepted
61-package v2-import graph plus one local extractor package, with no new
registry dependency or version. Existing session/index workspaces are preserved.

Keep `.venv`, v6 `vendor`, private inputs and previous outputs. For reproduction
only, choose a fresh output directory and run:

```sh
.venv/bin/python scripts/m2_stream_extract.py --output m2-stream-extract-out-v2
```

Return `m2-stream-extract-out-v2/m2-stream-extract-report.json`. It embeds failure
logs, exact source and lock identities, extraction summaries, per-file byte/SHA-256
comparisons and process RSS. No native-reader tests, real dictionaries, font
installation, vendor regeneration or old-batch rerun are requested. The first
offline test may canonicalize only this new lock; the complete result is recorded.
Later builds are locked and offline. Rust is unavailable in the authoring runtime.

## Operation and compatibility

The extractor reuses the unchanged qualified ordinary-v2 header parser by source
inclusion, and copies the accepted typed-error, parser-limit and cooperative-job
definitions into its independent facade. It admits the existing unencrypted v2
MDD profile. Source bytes are copied into a capped private snapshot and SHA-256
binds the receipt to those complete bytes. Reader/index/session APIs and their
small materialization budgets remain unchanged.

This path opens `MddFile` with Verify, explicit parser ceilings, locator limits
of zero and **materialized-record limit zero**. It uses `span_at` and span
`copy_to`; it never calls `resource_at`, `resources` or span `read`. Resource
lengths and keys come from source-bound spans. The engine still decodes bounded
record blocks, which is different from allocating a complete resource payload.
The new write sink accepts at most 64 KiB per write call and retains only a
fixed-size SHA-256 state. A resource may cross many record blocks.

Before creating output staging, the extractor visits all physical key ordinals,
checks span lengths, sums output bytes and plans every filesystem path. Planning
retains keys, paths and sizes, not resource data. A bounded copy then creates
each staged file, hashes bytes actually written, flushes/syncs it and rereads
the owned file descriptor in 64 KiB chunks to verify length and SHA-256. Empty
resources create zero-length files and participate in verification.

The thin receipt includes source SHA-256, counts, output bytes, largest resource,
plan charge, node count, engine memory counters and an aggregate resource digest.
That digest is SHA-256 of concatenated frames, in physical ordinal order:
`ordinal_u64le || key_UTF8_length_u64le || key_UTF8 || payload_length_u64le ||
payload_sha256_32bytes`. It covers raw archive-key spelling, duplicate identity
and exact payload bytes without retaining those payloads. Source, file and framed
hashes are checked independently with Python hashlib in the authored batch.

The SHA-256 implementation is included from the unchanged, already tested index
module. Its standard-vector Rust test is included again in this workspace.
The span API signatures follow the previously reviewed mdictlib 0.2.8 interface;
current documentation retrieval was unavailable during this implementation, so
the corrected Mac run compiled against the pinned local crate successfully.

## Path planning and publication

`studio_core::resource_relative_path` supplies the unchanged path grammar: one
optional archive-root separator, slash/backslash conversion, at most 32 validated
components, and refusals for traversal, repeated leading separators, ambiguous
components, reserved device names, control characters and nonportable punctuation.
The new bounded planner uses the unchanged frozen Unicode16 lowercase table for
component-prefix collision checks. It rejects duplicate leaves, case aliases and
file/directory prefix conflicts before output staging. It does not rename or merge
colliding resources. Unsafe archive keys remain inspectable by earlier raw-reader
APIs but cannot be extracted by this operation.

Staging is a private TempDir under the selected output parent. Directory traversal
uses owned directory descriptors, `mkdirat`, and `openat` with `O_NOFOLLOW`.
Leaves require `O_EXCL` and never replace existing files. A second logical name
that aliases a filesystem name is refused on that filesystem. This catches aliases
not covered by the portable lowercase check without silently combining output.

After all files are verified, the receipt and engine-accounting checks are
completed before commit. The final progress/cancellation checkpoint precedes
exclusive directory publication using the same macOS `renamex_np(RENAME_EXCL)` /
Linux `renameat2(RENAME_NOREPLACE)` pattern as the accepted core extractor.
A destination appearing at commit must remain untouched. No fallible verification
or cancellation callback occurs after publication. The caller receives success
once the whole verified directory has been published.

Any ordinary precommit failure drops staging and returns no destination. This
uses the same caller-owned, stable output-parent boundary as the earlier core;
it does not qualify malicious ancestor-directory replacement. Unexpected staged
symlinks are explicitly tested. Source/private-stage cleanup is checked on normal
exit. Power-loss durability, interrupted-process recovery, hostile filesystem
behavior and parent-directory fsync are not part of this gate. Linux code is
present; the requested qualification target is the user's Mac. Windows returns
UnsupportedPlatform and has no path-following publication fallback.

## Candidate ceilings

| Counter | Ceiling |
| --- | ---: |
| Source snapshot | 512 MiB |
| Resource count | 100,000 |
| Individual resource | 256 MiB |
| Total output payload | 2 GiB |
| Path-plan charge | 16 MiB |
| Path-prefix nodes | 200,000 |
| Raw key / path component count | 4 KiB / 32 |
| Parser-accounted working memory | 64 MiB |
| Compressed / decoded individual block | 8 MiB each |
| Retained key index / record index / block metadata | 16 MiB each |
| Locator entries/bytes; materialized-record bytes | Zero |
| Copy/verify application buffer | 64 KiB |

All extraction counters can be lowered, not raised. Engine counters reuse the
earlier bounded profile's ceilings. Path charge includes conservative row-vector
growth, retained key/path bytes, canonical prefix strings, directory-prefix
tracking and per-node allowances. It is an admission estimate, not allocator RSS.
Some combinations below the count/size ceilings will fail the plan or parser
budget sooner. The full ceilings are unqualified until corresponding tests pass.

Disk use includes the private source snapshot and hidden staged output at once.
The 2 GiB output counter bounds logical resource bytes, not filesystem allocation,
directory metadata or a kernel quota. This operation runs alone in its CLI; it
does not yet share admission with persistent sessions or existing packing workers.
No process-wide hard-memory or free-disk guarantee follows from these counters.

## Authored qualification

Local Python contracts pass for independent block-spanning fixture generation,
wire corruption detection, exact output-tree comparison and protected identities.
These tests do not compile Rust. The Rust command includes new tests for large
and empty resources, mid-copy cancellation, unsafe/alias paths, preflight budgets,
destination appearance at commit and staged symlink refusal, plus the reused
header and SHA regressions.

The Mac process batch has four successful-output candidates:

- A nonaligned resource crossing multiple zlib record blocks.
- A resource of 32 MiB plus seven bytes, after a 17-byte prefix resource.
- An 8 MiB plus three-byte resource in uncompressed record blocks.
- 4,096 separately created files, beyond the old 1,000-entry envelope.

Unicode filenames, an archive-root marker and empty tail resources are included.
The stdlib writer streams payload recipes into independent key/record spool files
and splits record blocks inside resource payloads. A separate wire auditor checks
the generated dictionaries. Output verification compares every path, directory,
size and SHA-256, including the absence of extra files or symlinks.

Negative cases cover traversal/device/UNC names, duplicate/case/prefix conflicts,
individual/aggregate/count/plan/node/file/parser/block limits, cancellation during
snapshot/planning/mid-copy/verification/precommit, checksum damage, oversized block
declarations, truncation, v3/encryption refusal and an existing output. Every failed
case must preserve existing output and leave no new destination or staging entry.
The batch records the built extractor process's RSS separately from Cargo and
Python fixture/auditor memory. Its provisional observed-RSS threshold is 384 MiB;
this is a measurement gate, not an OS limit. The corrected run passed this
matrix; the full candidate ceilings remain unqualified.

M2 area 3 remains open. This first gate expands resource extraction only.
Background publication routing/admission, larger packing/converter paths,
representative real inputs and final backend closeout still follow. MDX v3,
encryption, GUI adapters and Chinese/English/Arabic UI work are outside this gate.
