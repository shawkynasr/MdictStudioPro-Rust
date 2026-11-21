# M2 larger packing and export: first gate

Accepted first Mac gate 2026-11-05. The Rust test/build receipts and all 47 process
cases passed: 16 publications and 31 expected refusals. Report/source snapshots:
`docs/evidence/m2-large-io-user-run`. Review recomputed recipe digests for 327,681
reported physical records and seven export file hashes, and checked pipeline
hash links, metadata, audit counters and typed errors. All 180 prior source
identities and ten new sources match; the 62-package lock changed ordering only
during Cargo canonicalization. No routine rerun is needed. This does not close M2.

Maximum observed packing RSS was 105,115,648 bytes (100.25 MiB rounded); export
maximum was 4,231,168 bytes (4.04 MiB rounded). Actual output files and successful
Rust test stdout were not attached. Full wire checks, staging cleanup and output
publication were checked by the exact-source-bound Mac harness; review separately
recomputed its reported recipe digests and export hashes.

The accepted batch used the command below. It is retained for reproduction only;
keep `.venv`, `vendor`, private inputs and earlier outputs:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m2_large_io.py --output m2-large-io-out
```

For a requested rerun, return the report including on failure and choose a new
output folder. The batch uses the cached dependencies and prepared v6 vendor
tree; it does not reinstall Python packages or rebuild the vendor experiment.
No new MDict/GoldenDict visual check is requested for this gate: it retains the
already qualified v2 wire options and metadata serializer. Independent structural
and complete physical-record checks run before any compatibility claim expands.

## Implemented boundary

The isolated `m2/large-io` workspace accepts a small request JSON file. Fresh MDX
packing reads strict UTF-8 JSONL records `{"key":"word","text":"definition"}`.
MDD packing reads `{"key":"resource key","file":"relative/file.bin"}` plus an
explicit resource directory. MDD file references use the existing portable path
grammar and Unix directory-relative descriptors with no symlink following.
Empty binary resources are retained. The JSONL manifest is privately snapshotted;
individual resource contents are copied into a private payload spool as read.
This does not promise an atomic snapshot of an externally changing directory.
The manifest hash identifies the JSONL bytes; the record digest also binds every
resource payload and its position.

Packing spools decoded payloads to disk and retains a capped descriptor plan.
It sorts by frozen Unicode16 whole-string lowercase and original ordinal, then
adds each record to the existing owned builder using PreserveInput. There is no
second complete owned source collection. **The builder still owns its records**
and may allocate additional buffers during encoding. This is a larger bounded
owned-builder experiment, not a streaming writer or a hard process memory limit.

MDX output supports UTF-8 and UTF-16; MDD resource bytes remain binary. Writer
options remain zlib, 16 KiB key and 64 KiB record block targets, and generated
literal No/No case/strip flags. Titles, descriptions, unknown nonreserved
attributes and LF numeric stylesheet triplets use the qualified serializer.
Structural overrides and undefined numeric style markers are refused.

After encoding, metadata is serialized and binary sections copied with a fixed
buffer. Before publication, a strict checksum reader reopens the private output
and compares every physical key and raw definition/resource byte against the
spool, with locators disabled. Header attributes and raw serialized header must
also match. Only then is a new file published exclusively.

Exports open an ordinary supported unencrypted v2 UTF-8/UTF-16 MDX snapshot and
iterate one bounded record at a time. JSONL retains physical order, duplicate
keys, raw numeric style markers and definition whitespace. The thin receipt
contains source header attributes; the record file itself is not a complete
imported-profile rebuild manifest. Repacking deliberately uses the fresh No/No
profile, not arbitrary imported case/strip flags.

Canonical TXT uses `key LF body LF </> LF`, including an explicit blank body
line for an empty definition. It refuses keys containing CR/LF, a delimiter key,
a BOM at the start of the first key, CR in a body and standalone delimiter body
lines. It never silently rewrites those records; JSONL can represent them.
Definitions containing NUL remain outside this first profile. Staged exports
are strictly reparsed and their complete framed digest compared before commit.

## Explicit ceilings

| Budget | First profile |
| --- | ---: |
| Decoded key plus payload bytes | 32 MiB aggregate |
| Records | 100,000 |
| Payload per record | 1 MiB |
| Key UTF-8 bytes | 4 KiB |
| Descriptor plan charge | 16 MiB estimate, including sort scratch allowance |
| JSONL input / published file | 128 MiB each |
| Input JSONL physical line | 8 MiB |
| Source dictionary snapshot for export | 512 MiB |
| Header XML | 64 KiB |
| Parser working-memory accounting | 64 MiB |
| Decoded/compressed block | 8 MiB each |
| Materialized encoded record | 4 MiB |
| Locator entries / bytes | 0 / 0 |
| Staged TXT lines | 2,000,000 |

Budgets can only be lowered. The encoded-record ceiling accommodates a 1 MiB
UTF-8 body encoded as UTF-16 plus its terminator; it does not alter the older
reader's 2 MiB ceiling. The descriptor charge is an estimate, not measured RSS.
32 MiB input can expand while encoding or inside the owned builder. Peak scratch
files are bounded by the individual caps; concurrent jobs are not admitted here.
For example, export can hold a 512 MiB input snapshot and a 128 MiB staged output.
There is no disk-free-space reservation or operating-system RSS enforcement.

Cancellation is checked during input copying, row ingestion, builder population,
binary-section copying, verification, export and immediately before publication.
The existing builder's synchronous `finish` call is not interruptible internally;
cancellation there takes effect on return, before publishing. Once publication
succeeds, no further cancellation checkpoint discards that committed success.

## Qualification batch

Five Rust tests cover larger duplicate-aware packing/export, cancellation at
publication phases, lowered ceilings/no overwrite, numeric styles/TXT refusals,
and descriptor-relative binary resource reads with traversal/symlink refusals.
The Python batch runs the workspace tests and builds the CLI. It then exercises:

- 65,536 MDX records in both encodings, JSONL and TXT exports, and export/repack.
- 65,536 MDD resources including an empty payload, and a 1 MiB UTF-16 definition.
- Stable duplicate/case/punctuation/Arabic/Chinese/supplementary/Greek records.
- Complete independent stdlib wire decoding using SQLite offsets and a payload
  spool, plus the existing separate structural checksum auditor.
- Byte-for-byte export comparison to deterministic recipes, complete framed
  SHA-256 digests, metadata equality, expected typed failures, cancellation,
  no destination overwrite and no private staging residue.

Framing hashes each ordinal (u64 LE), UTF-8 key length (u64 LE), key bytes,
payload length (u64 LE), and SHA-256 of the raw decoded/binary payload. It excludes
compressed dictionary bytes, which are hashed separately. The same recipe is
checked independently in Python and Rust.

Process RSS uses `/usr/bin/time` on the built CLI, excluding Python fixture
generation and the compiler. 384 MiB is a provisional observed-RSS threshold,
not a guarantee for every input admitted by the caps. Larger entropy, varied
resource sizes and application concurrency remain separate qualification work.

The batch preserves all 180 prior source identities, pins the existing 61-package
import dependency graph plus one local crate, embeds exact lock contents and
records per-process requests, replies, RSS and independent digest/audit results.
No package upgrade or old runtime change is included.

## Still open

The accepted first run does not qualify all cap combinations, an unbounded dictionary writer, real
corpus workflows, converter production sizing or M2 closeout. Routing this new
packing/export path through the shared session/extraction admission runtime is
also still pending. Existing small publication workers retain their old limits.
