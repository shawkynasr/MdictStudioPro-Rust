# Revised/WFG grouping, rendering and bounded TXT publication

2026-11-07. Both complete standalone converter gates passed on Mac. M2 is partial. Application background/admission integration
is not claimed. All 253 previously accepted source identities remain unchanged.

## Accepted Mac gate

Both full outputs matched their original Python references: Revised had 162,636
entries / 1,454 redirects under the qualified reference-field/alias ordering rule;
WFG had 161,182 entries with exact raw TXT equality. The bound harness streamed
through every output record. Review checked all 30 process cases (six publications,
24 expected refusals) and both successful native command receipts. Small outputs
were independently regenerated with the captured Python plugins during review.

The entire source was also normalized again to recompute its group plan:
161,182 groups from 163,909 rows, no skipped headwords, largest group six rows /
11,220 normalized key/value bytes, index charge 54,397,924 bytes. All agreed with
native receipts. Full source row receipts matched the previously accepted reader.
Revised used 168,136,704 bytes RSS (160.35 MiB), WFG 164,143,104 (156.54 MiB).
These release-process observations are below the provisional 256 MiB target.

The exact report, review oracles, provenance and twelve source snapshots are
retained in `docs/evidence/m2-revised-render-user-run`. Actual native TXT files
are private. Native strict-reopen/record comparison, source preservation, no-clobber
and private cleanup are assertions of the exact matching Mac harness; no native
execution occurred locally. No routine rerun is needed. This is standalone TXT
conversion parity, not shared background/admission or real MDX packing qualification.
M2 remains partial.

## Resulting pipeline

The new isolated `m2/revised-render` facade consumes the accepted disk-backed row
spool. It validates every row with the existing MOE profile rules, including rows
without headwords, and builds a first-seen headword index of row offsets. Every
nonempty row is accounted for. It loads one bounded headword group, in original
row order, and invokes the unchanged qualified `studio_xlsx::moe` layout converter.

There is no complete normalized table or output entries vector in this path.
The in-memory group index and one group remain owned. Numeric/whitespace/XML/layout
helpers retain their qualified source. First-seen group order, polyphone sorting,
reference fields, per-head alias deduplication and aliases shared by different
headwords retain the original semantics. The input reader still materializes one
bounded XML part at a time and uses its narrower General-numeric MOE profile.

TXT records are appended to a private file under explicit aggregate limits. Before
publication the source row files are closed/removed, the complete TXT is reopened
through a bounded canonical parser, and byte counts, raw SHA-256 and ordered framed
record hashes must match. Publication refuses existing destinations and checks
cancellation through the last precommit checkpoint. A cancellation from the
published callback keeps success. Prepared receipt fields require no fallible
validation after commit. No partial dictionary file is published on a normal error.

## Full-source expectations and comparison

| Converter | Primary headwords | Alias redirects | Entries | Canonical TXT bytes |
| --- | ---: | ---: | ---: | ---: |
| Revised | 161,182 | 1,454 | 162,636 | 125,337,787 |
| Revised WFG | 161,182 | 0 | 161,182 | 104,377,877 |

Both use all 163,909 verified source rows. Independent complete Python references
are retained in `docs/evidence/revised-render-source-reference`. Revised was also
converted again under `PYTHONHASHSEED=17`: raw hashes changed, but the full normalized
record digest matched. Only the previously accepted reference-field set ordering
and alias ordering within each primary entry are normalized. Keys, definitions,
HTML elsewhere, entry order and multiplicity remain exact. WFG requires exact raw
TXT bytes. No original dataset or output definitions are included in this ZIP.

The Mac batch runs both complete captured Python converters again. Streaming
iterators compare every normalized native/Python record, and both results must
match the independent reference digest. The native raw file/record hashes are also
recomputed separately from the published output and checked against its receipt.

## Explicit bounds

The profile is `moe-grouped-disk-rows-txt-v1`; it accepts only Revised and WFG.
The accepted row-reader limits stay unchanged. Group index accounting has a fixed
64 KiB base, 256 bytes plus twice the headword UTF-8 bytes per group, and 64 bytes per
row reference, capped at 64 MiB. This is a conservative plan charge, not a measured
allocator or OS guarantee. Groups/entries are capped at 200,000, per-group rows at
4,096, group normalized input at 16 MiB and group output at 8 MiB. Individual keys/
bodies remain 4 KiB / 1 MiB, total decoded output 128 MiB, TXT 160 MiB and output
lines 4,000,000. Combined private source/output file bytes must stay <=512 MiB.
All Rust/JSON ceiling overrides only lower the profile; the row API independently
checks its own fixed limits. Layout construction still owns the bounded group and
uses the existing layout implementation; no all-input hard RSS claim is made.

The provisional native release-process observation target is 256 MiB. Native tests
use debug builds. This is a standalone converter/library gate, not a shared runtime
worker/admission or concurrent reader qualification. Registry versions/checksums
remain an exact accepted subset: the isolated graph has 53 packages. The row library's
dev-only XLSX dependency is now a normal dependency of this new rendering facade;
existing locks and source code are unchanged.

## Retained reproduction command (already passed)

Merge the updated ZIP into the existing project and keep `.venv`, `vendor`, private
inputs and all earlier outputs. Keep the exact source archive in Downloads:
`dict_revised_2015_20260929.zip`. Only the main workbook is extracted automatically.

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m2_revised_render.py --archives /Users/shawky/Downloads --output m2-revised-render-out
```

Change `--archives` if needed. Output must be a new directory; retry with another
name beginning `m2-revised-render-out`.

The new native tests compare grouped output bytes against the existing whole-table
layout for interleaved heads, polyphones, duplicate aliases and blank heads. They
cover bounded groups/index/output, precommit cancellation, postcommit success,
overwrite preservation and corruption before reopen. The process batch compares
small outputs against the original Python plugins, runs both complete conversions,
and checks cancellation checkpoints, ceiling refusal, cleanup and source identity.
No accepted earlier gate or external dictionary-reader app test needs a rerun.

Return only `m2-revised-render-out/m2-revised-render-report.json`. The report contains
counts, hashes, receipts and failure diagnostics, not definitions. Full source and
output TXT files remain under the excluded output prefix. This gate does not pack
MDX/MDD; real fresh-packing workflows, application integration/admission, index-build
shared admission and M2 closeout remain afterward.
