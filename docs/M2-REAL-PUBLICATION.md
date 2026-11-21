# Real bounded packing and shared index-build admission — qualified on Mac

The accepted Mac report is retained under `docs/evidence/m2-real-publication-user-run`
with 18 exact source snapshots and provenance. No rerun is required.

The isolated workspace is `m2/real-publication-runtime`. All 282 prior source
identities accepted by the full-converter gate remain unchanged. The dependency
graph is the same 68 packages with the facade renamed; the existing indexed
engine moves from a development dependency to a runtime dependency. No registry
versions or accepted engine/packing limits change.

## Qualified scope

| Selected original dictionary | Complete records | Packing | Shared index build |
| --- | ---: | --- | --- |
| CC-CEDICT MDX | 202,884 | Expected bounded refusal | Complete original source |
| CC-CEDICT MDD | 17 | Complete binary resource pack | Complete original source |
| Almaany MDX | 82,812 | Complete UTF-8 and UTF-16 packs | Complete original source |
| Chinese idioms MDX | 10,414 | Complete UTF-8 and UTF-16 packs | Complete original source |

The unchanged packer permits at most 100,000 records, 32 MiB decoded key/payload
bytes, 1 MiB per payload, 16 MiB descriptor plan and 128 MiB input/output files.
Independent complete local preparation confirms the MDD and two smaller MDX
files fit. CC-CEDICT has 75,162,810 decoded key/payload bytes and exceeds the
record and plan caps too. It is not sampled, truncated or presented as a successful
pack: the complete prepared manifest must produce a typed limit refusal and no
output. Scaling that packer remains a later gate, so this does not close M2.

Index builds use a new explicit `kind: index` publication request with source,
destination, MDX/MDD kind, policy and optional lower sort-run limits. The adapter
calls the existing complete bounded reader and index builder unchanged. It uses
an exclusive reservation of 384 MiB memory and 3 GiB temporary capacity under the
existing shared 384 MiB / 4 GiB ledger. Index builds cannot overlap readers,
conversion, packing or extraction. Reservations are accounting, not OS limits;
measured controller RSS must remain below 384 MiB.

Successful builds return the existing thin index receipt. No query or definition
is materialized by the build command. A notification after the commit enables
late-cancellation tests without adding a new cancellation check after publication.
Build errors preserve typed codes/limits; panics retain publication uncertainty.
The shared serial runner and all accepted converter modules are byte-identical
copies in this isolated workspace. Packing retains its existing 192 MiB charge;
a single admitted reader (96 MiB) may remain open while packing. That overlap is
measured by the real-data batch, not assumed from reservation numbers.

## Independent preparation and comparisons

The local preflight used the complete four previously attached dictionaries.
Only source identities, sizes, counts, limits, metadata and record digests are
included under `docs/evidence/real-publication-preflight`. No definitions, resource
bytes or original dictionaries are bundled.

The oracle independently decodes physical v2 records using the accepted stdlib
wire decoder. SQLite holds records and payloads on disk; its sort key is the
frozen Unicode16 lowercase mapping, with original ordinal as the duplicate tie
break. Sorting uses binary UTF-8 comparison, not the host Unicode version or
SQLite NOCASE. MDD resources are copied to safe ordinal filenames in a private
root; their original dictionary keys remain unchanged. Generated JSONL manifests
are complete, strictly UTF-8 and LF-terminated. The Mac batch must reproduce the
complete preflight identities/digests before using them.

Each successful packed dictionary is independently decoded in full. Key order,
duplicate order and every payload must match the stable sorted source digest.
Title, description, stylesheet and nonstructural extra metadata are compared.
Structural flags use the packer's existing literal No/No lookup profile, zlib,
and v2 format; this is logical record preservation under that profile, not a
byte-identical rebuild or preservation of every original structural flag. External
CSS/font companions for MDX files are not newly bundled. Native-reader visual
checks are a separate follow-up if needed.

## Native lifecycle checks and batch

Three new deterministic Rust tests cover reader contention then retry and strict
cache reopen; cancellation at sort runs, merge, precommit and postcommit; queue
overflow and queued cancellation; exclusive reservation charges; panic uncertainty
and lease release; and recovery after an ordinary source failure. Existing 33
native tests are retained. All 36 native tests and the two release builds passed on Mac. Native execution
was not performed locally; this editing environment has no Rust toolchain.

For reproduction only, merge the update into the existing project on Mac. Keep `.venv`, `vendor`, the
four previously qualified dictionaries in `real-corpus-inputs`, and older outputs.

```bash
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m2_real_publication.py --inputs real-corpus-inputs --output m2-real-publication-out
```

The batch runs locked offline native tests and two release builds, then for each
original source:

1. Independently prepares the complete source and checks its accepted identity.
2. Builds an index as an admitted background job, transfers its thin receipt once
   and opens a managed reader using that cache.
3. Refuses a second index build while the reader holds capacity.
4. Packs the eligible complete source while that reader remains admitted, or
   records the complete CC-CEDICT limit refusal. Successful outputs are fully
   decoded and compared; overwrite attempts must preserve them.
5. Closes/releases the reader, tests index overwrite refusal and pre-cancellation,
   and checks final shutdown, reservations, result retention, input identity and
   private cleanup.
6. Strictly reopens the index through the accepted separate verifier and compares
   the complete original scan, with an empty query list to keep definitions out
   of the report. Its process RSS must also remain below 384 MiB.

The reproduction report is `m2-real-publication-out/m2-real-publication-report.json`.
No new report or rerun is needed for the accepted gate. A failed command
or case retains stage and diagnostics. Output folders use the excluded prefix;
private source preparation is removed after successful cases. Generated rebuilt
dictionaries and indexes stay in your local output directory. No source file is
modified and no overwrite is authorized by this batch.

## Accepted receipt review

The Mac receipt passed review of all 925 controller exchanges, 300 unique
previous/new source identities, the exact 68-package graph and three successful
native commands. The five complete packed outputs matched the locally computed
independent stable-sort record digests, including every duplicate and payload.
Metadata and UTF-8/UTF-16 encodings matched the defined No/No packing profile.
All four admitted original-source indexes matched their source identities/counts
and passed a separate strict cache reopen plus complete source scan against the
previous independent real-reader scan. The separate verifier requested no pages,
so no definition bodies entered the report.

Reported controller peak RSS was 20,377,600 bytes for CC-CEDICT MDX (its packing
refusal and successful index), 7,331,840 for the MDD, 177,405,952 for Almaany and
59,703,296 for idioms. The maximum was 169.19 MiB, below the unchanged 384 MiB
threshold. Maximum separate index-verifier RSS was 4,055,040 bytes. These are Mac
process measurements recorded by the exact source-bound harness, not a hard OS
memory guarantee or a claim for larger inputs.

The receipt and transcripts bind index builds, reader/index contention refusals,
real reader/packer overlap, successful packing, overwrite preservation,
pre-cancellation, late cancellation, one-transfer results and final shutdown with
zero reservations and reader retention. Complete source identity, native scratch
cleanup and removal of private oracle preparation are assertions in the exact
harness. The review did not independently rerun native binaries or materialize
output dictionary bytes; it checked the independent reference digests, receipt
identities and source-bound execution evidence. The accepted package bundles no
private dictionary/resource data or rebuilt outputs.

The CC-CEDICT MDX pack remains a controlled refusal, not a qualified full pack.
Its original index covers all 202,884 entries. Full CC-CEDICT packing capacity and
final M2 closeout remain open. No independent reader-app visual test was part of
this gate, and no new MDX/MDD format version is claimed.
