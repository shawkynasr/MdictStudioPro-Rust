# Full CC-CEDICT packing — qualified on Mac

The accepted report and 24 exact qualified source snapshots are retained under
`docs/evidence/m2-cc-pack-user-run`. All four native commands passed: five library
tests, 39 runtime tests and two release builds. No rerun is required for this gate.

The complete previously selected CC-CEDICT MDX has 202,884 records,
75,162,810 decoded key/payload bytes and an 84,130,038-byte generated JSONL
manifest. It exceeded the old 100,000-record / 32 MiB decoded / 16 MiB plan
profile. That successful limit refusal remains valid evidence for the old profile.

This slice adds `m2/cc-pack-io` and `m2/cc-pack-runtime`. All 300 previously
qualified source identities stay unchanged. The graph adds one local packer to
the accepted package set, with a renamed local runtime facade: 69 packages total,
no registry version changes. The already-present miniz_oxide 0.9.1 is now a direct
compression dependency of the new library. The old IO library is also a direct
dependency for the test oracle; its sources and limits remain unchanged.

## Explicit profile

The new request kind is `cc_packing`, distinct from the existing `dictionary`
packing request. It permits MDX only, with explicit UTF-8 or UTF-16 encoding.
The native library accepts no MDD or export operations under this profile.

| Bound | New profile |
| --- | ---: |
| Records | 250,000 |
| Decoded key/body bytes | 96 MiB |
| Per-entry UTF-8 body | 1 MiB |
| Key UTF-8 bytes | 4 KiB |
| Descriptor plan charge | 48 MiB |
| Input and output files | 128 MiB each |
| Key block target | 16 KiB |
| Record block target | 64 KiB |
| Key or record blocks | 8,192 each |
| Block-index data | 16 MiB |
| Compressed block or key-index envelope | 8 MiB |
| Shared memory reservation | 384 MiB, exclusive |
| Shared temporary reservation | 3 GiB |
| Observed process RSS target | 384 MiB, unchanged |

Tighten options may lower record, decoded, plan and output ceilings only. No
other job or reader may overlap an admitted CC pack, because its memory charge
consumes the full shared 384 MiB budget. Reservations and descriptor charges are
accounting, not allocator or OS memory guarantees. Native measurement is required.

## Block-spooled implementation

The new library derives its source snapshot, strict JSONL parser, metadata
validation, frozen Unicode16 lowercase sort, stable duplicate ordering and
complete staged-record verification from the accepted IO implementation. Only
the new library has larger record/decoded/plan ceilings. The descriptor vector
remains bounded in memory, and UTF-8 payloads are spooled on disk; this is not an
external sort or an unlimited-size writer.

The new MDX encoder reads each sorted payload once, encodes one entry, and
collects a bounded key block and record block. Records never split across blocks;
an individually larger entry is placed in its own bounded block. Each zlib block
is checksummed and written immediately to a private file. Only block indexes and
current buffers remain in memory; there is no complete encoded-body collection,
all-block collection or final-file Vec. Summary lengths use encoding units,
record offsets include body terminators, and plaintext v2 checksum/terminator
conventions match the existing native format.

After block spooling, the encoder assembles header, key section and record section
using 64 KiB copies under the file cap. The accepted metadata rewrite and strict
full reopen verify every key, duplicate ordinal and body against the original
spool before no-clobber commit. Reader locators remain disabled. A successful
commit is followed only by movement of prepared metadata and a notification;
no new cancellation check or hashing can turn that success into an ordinary
failed publication. Caught panics retain explicit publication uncertainty.

The resulting profile is `cc-mdx-block-spool-v1`: plaintext MDX v2, zlib, literal
No/No flags and the existing canonical metadata rules. It adds no v3, encryption,
legacy encoding or expanded MDD capability.

## Native qualification and reproduction

The passing library tests compare output bytes with the old qualified writer for both
encodings, using repeated keys, Greek/Arabic/supplementary Unicode, an empty body,
stylesheet markers, multiple blocks and a body larger than the block target.
They also cover cancellation during snapshot/load/entry encoding/compression,
assembly, reopen verification and precommit; reduced limits, forbidden growth,
overwrite preservation and rejection of non-MDX operations.

Runtime tests add reader exclusion and retry, one-transfer results, exclusive
charges, queue limits, cancellation before/after commit, panic uncertainty and
lease release. Existing converter, reader, packing and index tests remain in the
new runtime as regressions. The serial runner, index adapter and converter modules
are byte-identical copies of the accepted implementation.

The full-data reference is metadata only. It reuses the complete accepted source
inventory and independently computes the frozen sorted scan:
202,884 records, 1,630,651 key bytes, 73,532,159 payload bytes,
FNV64 `54170a8a8de5cfea`. For this particular source the frozen order already
matches its physical order; the batch still derives and checks the sorted order.
The cryptographic per-record SHA digest remains the accepted preflight reference.
No dictionary definitions or original source files are bundled.

For reproduction only, merge the update into your existing directory. Keep `.venv`, `vendor`, previous
outputs and the original `real-corpus-inputs/CC-CEDICT 092026.mdx`:

```bash
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m2_cc_pack.py --inputs real-corpus-inputs --output m2-cc-pack-out
```

The batch runs locked offline library and runtime tests and two release builds.
It prepares all source records independently, proves an admitted reader blocks
the new pack, checks old-cap refusals and pre-cancellation, then packs both complete
encodings. Independent wire decoding must match every sorted key/body digest and
metadata field. Each output is indexed and strictly reopened through the accepted
separate verifier; its complete ordinal scan must match the sorted reference.
Overwrite attempts must preserve outputs, late cancellation must preserve success,
and shutdown must leave no reservations, retained readers or private residue.
The long-lived controller and separate verifiers must stay below 384 MiB RSS.

The reproduction report is `m2-cc-pack-out/m2-cc-pack-report.json`. No new report
or rerun is needed. Failures retain stage and diagnostic
logs; full outputs and private inputs remain in the excluded local output folder.
Native code was compiled and run on the user's Mac; the local editing environment
has no Rust toolchain. Local Python checks independently review the source-bound
receipt; they do not remeasure native output bytes or process RSS.

## Accepted full-data result

Both encodings contain all 202,884 entries and match the complete independent
stable-sort key/body digest. They preserve metadata under the existing literal
No/No profile and pass complete strict source/index reopening. The UTF-8 file is
9,211,594 bytes, SHA-256
`1aa87a504a2e0cdedb8f008bd5240a399c0e106dc5385159c9e8d5d0bfff9d39`;
the UTF-16 file is 11,150,121 bytes, SHA-256
`e7bc680ccaa58a9412335c6edc5dbb6289a777c7f39d565bc4690cc5bceab10c`.

Runtime peak RSS was 60,010,496 bytes (57.23 MiB), below the unchanged 384 MiB
target. Separate verifier peaks were 3,256,320 and 3,592,192 bytes. The review
checked 1,273 controller exchanges, 324 unique previous/new source identities,
and the exact 69-package graph. None of the 300 previously qualified sources
changed. Small-fixture native tests establish byte-for-byte equality with the
old qualified writer in both encodings; full files are compared through an
independent wire decoder and strict reader/index reopen, not a capped old-writer
full rebuild.

The transcript binds 13 publication jobs, their terminal snapshots, five
one-transfer successful results, typed old-cap/growth/pre-cancel refusals, reader
exclusion, overwrite preservation, late cancellation and final shutdown. Final
reservations and reader retention were zero. Input/cache identity, exact expected
output set and private cleanup are assertions in the exact Mac harness. No
source definitions or full dictionary outputs are bundled with the evidence.
No independent reader-app visual test was requested as part of this native gate.

The old bounded packing profile still refuses this source, as it should; the new
explicit block-spooled profile is qualified separately. M2 is not yet marked
complete. Final M2 scope/evidence closeout review is the next step.
