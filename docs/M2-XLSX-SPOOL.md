# Revised/WFG input memory: disk-backed normalized row gate

2026-11-07. The scoped native row-normalization gate passed on Mac. This gate normalizes worksheet rows only. Revised/WFG dictionary
rendering, grouping and publication are not yet integrated or qualified by it.
M2 remains partial. All 241 accepted source identities stay unchanged.

## Accepted Mac gate

All 163,909 rows and 2,950,362 normalized fields matched both the fresh Mac helper
pass and the independent complete local Python reference. Review checked all 27
process receipts (10 successes, 17 expected refusals), both successful native command
receipts, 241 protected plus twelve new source identities and the exact 52-package
registry subset. Nine common-cell cases also matched existing original goldens.

Independent acceptance-time recomputation repeated every source row with the
captured helper and verified 615,738 shared strings / 41,823,579 shared text bytes,
102,800,416 exact compact JSONL bytes and 175,812,245 bytes of private files total.
These matched the native receipt. Used shared-index bytes were 9,851,808; reserved
index capacity was 16,777,216 bytes. Report, review oracles, provenance and twelve
source snapshots are retained under `docs/evidence/m2-xlsx-spool-user-run`.

The complete release-build process reported 159,842,304 bytes RSS (152.44 MiB).
The maximum across all cases was 164,052,992 bytes (156.45 MiB), below the provisional
192 MiB observation target. Native reopen parity, source preservation and private
cleanup are assertions in the exact matching harness; actual native files are not
attached. No Rust execution occurred locally during review. No routine rerun needed.

This qualifies normalized input rows only. Revised/WFG grouping, rendering and
publication, application admission/worker integration and reader concurrency remain
unqualified. XML parts are still materialized under a cap; this is not a hard RSS
limit or all-input memory proof. M2 remains partial.

## Allocation change

The qualified XLSX reader holds the raw cell map, calamine range, shared strings
and normalized whole-table maps concurrently. Raising its limits for the full
Revised workbook would retain those duplicate layers.

The isolated `m2/xlsx-spool` reader copies the source to a private immutable snapshot,
validates ZIP member sizes and selected worksheet relationships, and spools shared
string bytes to disk with an offset index. It then normalizes one worksheet row
at a time into a private JSONL file. After flushing, it reopens every row, recomputes
the complete framed digest and returns an owning `Spool`; dropping the owner removes
the private files. The diagnostic CLI drops that owner before reporting success.

One XML part is still materialized at a time under a 96 MiB part ceiling. This is
not a streaming XML parser or a hard process memory bound. Shared-string values
are read by offset rather than retained in a whole string table. There is no full
raw-cell map, calamine range or normalized whole-table allocation. The receipt
reports both used and reserved offset-index bytes and actual private file bytes.

## Compatibility contract

This explicit profile is `moe-disk-rows-general-numeric-v1`. It preserves the captured
header/value normalization, missing versus empty strings, duplicate-header last
assignment, original row order and blank-row rules. Qualified numeric normalization,
Unicode whitespace and XML helpers are reused without modifying their source.
Active or explicit sheet selection and safe internal worksheet relationships remain.
The output digest includes each complete normalized dictionary row, not a sample.

The new path requires explicit geometry, ordered row/cell coordinates and General
numeric formats. ISO dates, date/time/duration and other styled numerics are explicit
refusals. This is a narrower MOE input profile, not a replacement for every workbook
the existing reader accepts. The selected official Revised workbook uses General
numeric formats and primitive/string/cache cells supported by this profile.

Full independent Python reference:

| Measurement | Expected |
| --- | ---: |
| Data rows retained | 163,909 |
| Header columns | 18 |
| Stored XML cells including header | 1,530,428 |
| Declared rectangle including header | 2,950,380 cells |
| Normalized row-map pairs | 2,950,362 |
| Row-map value bytes | 44,384,638 |
| Row-map key bytes | 40,321,614 |
| Normalization byte charge including headers | 84,706,498 |
| Shared-string entries | 615,738 |

The complete source hash, original helper identity, header list and framed digest
are retained in `docs/evidence/revised-row-source-reference`. No source dictionary,
workbook contents or row spool is bundled. A fresh Mac Python pass must match this
reference, and native rows must match both Python results exactly.

## Bounds and staged next step

The reader permits a 32 MiB input snapshot, 128 MiB advertised ZIP expansion,
96 MiB individual XML parts, 200,000 row coordinates, 64 columns, 3,200,000 cells,
1,000,000 shared strings / 96 MiB shared text, 1 MiB individual scalar values,
8 MiB rows, a 128 MiB normalization charge and 192 MiB row-spool file. Overrides
only lower limits. A successful full gate must also observe <=512 MiB total private
files and <=32 MiB reserved shared-string offset index.

The provisional native process RSS target is 192 MiB. Full process probes use a
release build; native tests use a debug build. This is an observed-workload gate,
not an OS-enforced limit or an app admission/reader-concurrency qualification.
The 52-package isolated lock is an exact reachable subset of the accepted CC graph,
with no registry version/checksum upgrades. Existing native profiles remain intact.

After row parity and memory are accepted, group the verified private rows by
headword and feed one bounded group into the existing Revised/WFG layouts, with
bounded output and atomic publication. That integration and both complete output
comparisons are separate remaining work. A reader-only pass does not establish
native Revised/WFG dictionary output parity.

## Retained reproduction command (already passed)

Merge the package into the existing project. Keep `.venv`, `vendor`, private inputs
and prior outputs. Keep the exact attached ZIP in Downloads:
`dict_revised_2015_20260929.zip`. Only the main workbook is extracted; the extra
field-explanation workbook is ignored.

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m2_xlsx_spool.py --archives /Users/shawky/Downloads --output m2-xlsx-spool-out
```

Use `--archives` for another ZIP location. The output folder must be new; retries
use a new name beginning `m2-xlsx-spool-out`.

The script tests/builds the isolated reader, compares the existing nine common-cell
Python golden cases, checks malformed/unsupported inputs, five cancellation phases,
forbidden ceiling increases, old full-source caps and cleanup, then compares all
163,909 Revised rows against the captured helper and independent full reference.
Both stream-written and reopened native row digests must agree. Failures embed
native responses/build diagnostics. No dictionary-reader app check is requested.

Return only `m2-xlsx-spool-out/m2-xlsx-spool-report.json`. The report contains counts,
headers and hashes, not definitions. Private native spools are removed on normal
success/failure; the extracted source remains under the excluded output prefix.
Do not rerun accepted CC-CEDICT, Concise, Mini/Idioms or M1 batches.
