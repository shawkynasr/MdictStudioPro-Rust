# Persistent disk index and paged lookup: first implementation gate

Accepted first gate 2026-11-03. The Mac Rust test and build commands succeeded.
All 55 process cases passed: 12 builds, 20 query runs and 23 expected refusals.
The report embeds 180 page results, all recomputed during review against the
fixture records, including duplicate ordinals and the explicit Unicode16 scalar.
All 142 previous source identities and the 62-package graph match. Original
report, provenance and 11 exact source snapshots are retained under
`docs/evidence/m2-index-user-run`. No rerun is requested.

| Larger fixture | Entries | Artifact bytes | Build peak RSS bytes | Query peak RSS bytes |
| --- | ---: | ---: | ---: | ---: |
| UTF-8 MDX | 65,536 | 3,543,040 | 6,189,056 | 5,414,912 |
| Binary MDD | 65,536 | 3,543,040 | 6,029,312 | 5,267,456 |

Maximum observed process RSS was 6,189,056 bytes (about 5.90 MiB); no query
allocated a global locator. These synthetic-layout observations do not qualify
the full source/cache ceilings or other application paths. Successful Rust test
stdout was not attached; its acceptance uses the exact-source-bound command
receipt. Build/query responses and actual page values are embedded. No separate
input/cache binaries or native-reader checks were supplied or requested.

The following sections describe the qualified matrix and its explicit limits.
The earlier sizing gate remains accepted and all 142 previous source identities
and previous locks remain guarded unchanged. This step adds an isolated
`m2/indexed-engine` workspace; the accepted reader is copied exactly as its base,
with new index/hash modules appended. It adds no registry package or version.
The 62-package graph substitutes one new local package for the bounded-reader
package, with the same direct dependencies. Consolidating the reader after
qualification remains separate work.

Keep `.venv`, v6 `vendor`, private inputs and earlier outputs. For reproduction
only, use a fresh output directory:

```sh
.venv/bin/python scripts/m2_index.py --output m2-index-out
```

Return `m2-index-out/m2-index-report.json`. The batch uses the existing Python
3.14 / Unicode16 environment and mdict-utils installation. No pip upgrade,
vendor regeneration, accepted-batch rerun or MDict/GoldenDict checks are needed.
Local Python contracts verify fixture wire framing, page-oracle behavior,
damage probes and unchanged source/dependency inventories. They do not execute
Rust. A failed Rust command is embedded in the report with its log tail.

## Contract and integration scope

`index::Index::build` writes a new caller-selected cache artifact exclusively.
`Index::open` returns a source-bound borrowed session. `Index::page` returns
the full match count, selected match basis, requested offset, next offset and
at most 128 physical rows, materializing only those definitions/resources.
Zero-length pages report totals without materializing bodies. An offset beyond
the total gives an empty page; large offsets cannot overflow into other keys.
Offsets are explicit API parameters, not portable opaque cursors. The query,
policy and source stay bound to the open session; callers must preserve their
query when requesting the next offset.

Policies preserve the accepted semantics:

| Policy | Selection |
| --- | --- |
| `raw_exact` | Exact spelling only; also the required MDD policy |
| `header_ascii_v1` | All exact rows first; only when none exist, frozen Unicode16 lowercase if the header is case-insensitive, then ASCII punctuation/whitespace removal if StripKey is Yes |

Header policy requires explicit case/strip flags. Exact matches take precedence
even when their normalized token is empty. An absent query that normalizes to
empty is refused. Physical ordinal breaks duplicate ties, including normalized
groups; duplicate rows never collapse. Redirect bodies remain raw strings in
this index API. Existing small-reader redirect resolution remains unchanged;
larger redirect/session/application integration is not claimed.

The index is an application format, not an MDX/MDD wire format or an
mdictlib-native index. The native API exposes header-controlled normalization
and source metadata stamps; this gate keeps application normalization explicit
and uses full content binding. Its frozen lowercase module is included from
the unchanged qualified core. There is no compiler-provided `to_lowercase` in
the new lookup path. Future parser/table/format changes must revise the cache
identity; native-index interoperability is not claimed.

## Artifact and verification

The single-file `STIDX001` artifact contains a fixed 4096-byte header, two
16-byte-per-entry descriptor tables (exact and normalized), UTF-8 key tokens,
and a 32-byte SHA-256 footer. Descriptors contain absolute offset, token length
and physical ordinal. There are no definitions, resource bytes or executable
content in this file. The manifest binds format/policy revision, engine patch
revision, exact Unicode16 table SHA-256, dictionary kind, header flags, record
count and SHA-256 of the complete private source snapshot, including metadata
and bodies. Length/mtime alone cannot make another dictionary reuse this cache.
Identical source bytes can reuse it across locations and processes.

Opening privately copies a capped cache, verifies the complete SHA-256 footer,
then compares every descriptor to the corresponding source key under the chosen
policy. It proves sorted `(token, ordinal)` order and complete one-to-one ordinal
coverage in both tables with a bounded bitset. Blob extents must be contiguous,
nonoverlapping and within bounds; unknown manifests, stale policy/source/revision,
missing/duplicate ordinals and unrelated trailing bytes are refused. This also
rejects semantically wrong tokens even when a corruption probe recomputes a
valid checksum. The digest is integrity/content binding, not authentication.

The new fixed-buffer SHA-256 implementation has Rust standard-vector tests,
including segmented, multi-block and million-byte messages. The Mac test command
passed and the harness also compared source digests against Python hashlib.
Local Python tests alone do not qualify that Rust implementation.

No caller-visible cache is changed on a query or failed attachment. Missing or
damaged caches return a typed failure; no automatic delete/overwrite/retry is
performed. A source-bound session owns a private cache copy and borrows a reader
with a private dictionary snapshot, so later public-file changes cannot change
the in-flight session's data. Source copy consistency under concurrent external
mutation and adversarial control of an output parent are not newly qualified.

## Bounded work and publication

Construction externally sorts exact and normalized keys in separate passes.
Each run retains at most 8192 tuples and 2 MiB serialized key/ordinal data;
`sort_unstable` sorts in place. Merge fan-in is eight, with at most eight run
readers and one output, and at most 8192 run paths. Tokens are capped at 12 KiB,
source keys at the inherited 4 KiB. Each serialized sort section is capped at
64 MiB, and the final artifact at 128 MiB. Limits may reject a long-key input
before the inherited 500,000-row candidate ceiling. Temporary run files can
overlap during a merge; the serialized runs for one section require at most
about 128 MiB, in addition to the staged/private cache and source snapshots.
These are logical bounds; no global filesystem quota or OS memory limit is set.

Before publication, the complete staged artifact is reopened and semantically
verified. Scratch is removed, the artifact is flushed/synced, and cancellation
is checked immediately before `persist_noclobber`. Existing paths are never
replaced. There is no cancellation check after commit, and build requests return
only a thin receipt. Queries require a separate reopen request, so a later page
error cannot relabel a committed build as failed. Crash/power-loss durability,
parent-directory fsync and recovery of interrupted temporary files are not
qualified by this normal-exit batch. Automatic eviction and concurrent rebuild
coordination remain future application work.

Each page has a 128-row / 2 MiB raw key+payload cap; overflow returns no page.
The CLI bounds requests at 64 KiB / 16 queries and the complete serialized reply
at 2 MiB. It retains only the requested pages. JSON structures and the casing
table have caller-owned overhead beyond engine accounting. The unchanged parser
has a 64 MiB accounting budget and its global locator remains disabled. There
is no global reservation across concurrent sessions or workers yet.

## Qualification matrix and practical limits

The authored Mac batch builds and reopens caches in separate processes. It tests
UTF-8/UTF-16, all four case/strip flag combinations, exact-first duplicates,
Greek final sigma, dotted I, a Unicode16 addition, Chinese, Arabic, supplementary
characters, punctuation, empty-normalized queries and raw redirect text.
It pages all 400 duplicate rows in physical order, checks count-only and
out-of-range windows, and separately builds/queries 65,536-entry MDX and MDD
fixtures. Binary resource duplicates are covered by Rust tests; the Python MDD
matrix also checks an empty trailing resource.

Negative probes include changed source metadata with the old mtime, wrong
policy/revision, footer damage, truncation, recomputed-checksum wrong tokens,
ordinals and extents, page count/byte and sort-run limits, an existing output,
missing cache, and cancellation during sort runs, merge, semantic verification,
precommit, cache attachment and lookup. Sources/caches must remain unchanged
on refusals and no normal-exit scratch may remain. The report records observed
process RSS separately from parser counters; the earlier provisional 384 MiB
RSS observation threshold is reused, not enforced by the OS. Compiler RSS is
excluded. A successful case's actual page values are embedded for review.

Within a verified session, equal-range search is logarithmic in table entries
plus page payload reads. Startup is deliberately still linear: full dictionary
validation, full source hashing, cache copying/hashing and semantic key-space
verification all run again. Timings separate validated open, verified attachment
and warm page calls. This gate makes no fast-startup claim and does not certify
the 128 MiB cache ceiling or all 500,000-row source combinations.

M2 area 3 stays open. Larger application/session routing, stream extraction,
packing/converter budgets and aggregate admission still follow. Representative
real-input qualification and final regression/closeout remain separate work.

API audit references (documentation displayed mdictlib 0.2.8):

- https://docs.rs/mdictlib/latest/mdictlib/struct.MdxFile.html
- https://docs.rs/mdictlib/latest/mdictlib/struct.KeyIndexSourceIdentity.html
- https://docs.rs/mdictlib/latest/mdictlib/struct.KeyOrdinal.html
