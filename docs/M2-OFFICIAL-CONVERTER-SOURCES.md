# Full official converter sources: inspection and next native gate

2026-11-06. All four attached MOE text-database ZIPs and CC-CEDICT were fully
inspected locally. The captured original Python plugins converted all six complete
datasets. The subsequent full Mini/Idioms native gate passed on Mac; the other four
converter cases remain held for scaling.
The 214 accepted source identities, dependency locks and native limits are unchanged.

| Converter | Source data rows | Python output records | Decoded key/body bytes | Current native blockers |
| --- | ---: | ---: | ---: | --- |
| CC-CEDICT | 125,369 matching lines | 203,362 | 75,119,613 | Entries, decoded output, TXT bytes |
| MOE Mini | 4,719 | 4,311 | 13,240,798 | Passed full native comparison |
| MOE Idioms | 5,489 | 5,489 | 20,243,661 | Passed full native comparison |
| MOE Concise | 45,178 | 44,445 | 24,826,583 | Worksheet rows and rectangle cells |
| MOE Revised | 163,909 | 162,636 | 124,361,971 | Output counts/bytes, worksheet rows/cells, part/value bytes |
| MOE Revised WFG | 163,909 | 161,182 | 103,410,785 | Output counts/bytes, worksheet rows/cells, part/value bytes |

Concise has 499,518 stored cells but a 677,685-cell rectangle including the header.
The native reader caps both at 512,000. Preflight now reports this distinction.
Revised has a 2,950,380-cell rectangle and a 74,152,456-byte worksheet XML part.
The additional Revised field-explanation workbook is documentation, not input.
Mini and Idioms need no source splitting or native limit changes.

## Accepted full Mini and Idioms gate

The attached Mac report passed review: 9,800 total entries, exact full-output SHA
agreement with both fresh Mac and independent local original-Python references,
732 controller exchanges, successful one-transfer receipts, unchanged qualified
source/lock identities and zero final reservations/retained replies. Mini peak RSS
was 125,456,384 bytes (119.64 MiB); Idioms was 202,477,568 bytes (193.10 MiB).
The report and three exact source snapshots are retained in
`docs/evidence/m2-official-converters-user-run` with provenance and review summary.
Native output files remain private: their byte comparisons, input preservation
and private scratch cleanup are assertions in the matching Mac harness. Review
rehashed the independently produced local Python outputs and checked every
controller exchange; it did not execute Rust or reread native output files.
No routine rerun is needed. M2 remains partial.

## Retained reproduction command (already passed)

Merge this package into the existing project. Keep `.venv`, `vendor`, private
inputs and earlier outputs. Keep these two exact uploaded ZIPs in Downloads:

- `dict_mini_2019_20260929.zip`
- `dict_idioms_2020_20260929.zip`

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m2_official_mini_idioms.py --archives /Users/shawky/Downloads --output m2-official-converters-out
```

Use a new output name with the same prefix for a retry. If the ZIPs are elsewhere,
change `--archives`. The script checks archive/member SHA-256 and sizes, extracts
only the two exact workbook members, builds the unchanged qualified runtime and
runs both complete datasets. It compares native TXT bytes with both a fresh Mac
original-Python conversion and the full local reference, checks receipts/counts,
source preservation, admission cleanup, cancellation after completion and RSS.
It records diagnostic receipts and hashes on failure. No reader/converter overlap
or new index-build admission qualification is claimed by this batch.

Return only `m2-official-converters-out/m2-official-converters-report.json`.
The report contains metadata and fingerprints, not dictionary definitions.
Extracted workbooks and both output sets remain under the excluded output prefix.
The application ZIP contains only sizing metadata, never these source datasets or
converted dictionary content. No dependencies or Rust tests need routine reruns.

## Evidence and remaining work

`docs/evidence/official-converter-input-inspection/measurements.json` binds archive
and source hashes, full worksheet scans, output measurements, captured Python code
and the 214 accepted sources. Its provenance distinguishes Python-only inspection
allowances from the unchanged native profile: 250,000 scan rows, 5,000,000 cells,
128 MiB per part and 256 MiB decoded/ZIP were used only to measure complete sources.
These are not supported native limits. Revised/Concise Python set ordering is not
asserted as a portable raw-byte contract; Mini/Idioms references are exact.

Next, scale Concise with an explicit measured profile and qualify
CC-CEDICT/Revised/WFG through appropriately bounded larger-input work. Do not
truncate data or silently lift caps. Full real packing workflows, index-build
shared admission and final backend closeout also remain. M2 is partial.
