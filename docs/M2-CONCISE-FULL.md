# Full MOE Concise: explicit worksheet geometry profile

2026-11-06. Authored for the complete attached official Concise workbook. The Mac native test/build receipts and full-output comparison passed review.
M2 remains partial. No accepted source or existing profile is modified.

## Accepted Mac gate

The source-bound report passed: all 45,178 data rows yielded 44,445 entries,
24,826,583 decoded key/body bytes and 25,093,253 canonical TXT bytes. The complete
normalized record digest matches both independent original-Python runs. Native
and Mac Python raw hashes differ; the matching Mac harness compared every record
using only the already accepted set-order rule for reference fields. It preserves
keys, entry order, multiplicity, definitions and other HTML.

Review replayed all 893 controller exchanges: one full publication, six expected
job refusals (old row limit, old rectangle limit, two attempted ceiling increases,
pre-cancellation and existing destination), plus the wrong-converter API refusal.
Receipt transfer, late cancellation, worker recovery and final zero reservations/
reader retention passed. Both native test/build command receipts returned zero.
Report, provenance and twelve exact source snapshots are retained under
`docs/evidence/m2-concise-full-user-run`. Actual native output files are private;
file preservation and private scratch cleanup are assertions of the bound harness.
No routine rerun is needed. M2 remains partial.

Peak reported process RSS was 342,503,424 bytes (326.64 MiB), below the provisional
384 MiB observation target. It exceeds the 256 MiB logical conversion charge.
The reservation accounting is not an OS memory limit; a full-size simultaneous
reader/converter workload remains unqualified. Revisit admission sizing or reduce
owned allocations before extending the production concurrency claim. This gate
qualifies the tested single-conversion workload, not a hard memory ceiling.

## What changed and why

The workbook contains 45,178 data rows (45,179 with header), 15 columns, 499,518
stored cells and a 677,685-cell rectangle. Both the reader and converter have row
ceilings, and the reader budgets rectangle allocation separately from stored cells.
The original profile therefore refuses the complete workbook.

`m2/concise-runtime` is an isolated facade based on the accepted converter runtime.
Conversion requests accept only `moe_concise`, with receipt profile
`moe-concise-owned-v1`. It reuses the qualified application, XLSX normalization,
MOE layout, canonical TXT verifier and no-clobber publisher. Registry packages,
versions and checksums are identical; only the local facade name changes in its
separate lock. All 217 accepted source identities stay unchanged.

| Ceiling | Accepted general profile | Explicit Concise profile |
| --- | ---: | ---: |
| Worksheet coordinate rows, including header | 32,000 | 50,000 |
| MOE table rows | 32,000 | 50,000 |
| Worksheet rectangle/stored cells | 512,000 | 750,000 |
| Output entries | 100,000 | 100,000 |
| Decoded key/body output | 32 MiB | 32 MiB |
| Canonical TXT file | 64 MiB | 64 MiB |
| Source snapshot / individual XLSX part | 32 MiB | 32 MiB |
| Worksheet normalized values | 32 MiB | 32 MiB |
| Advertised ZIP expansion | 128 MiB | 128 MiB |
| Shared conversion memory / temporary charge | 256 / 768 MiB | 256 / 768 MiB |

Other limits also stay unchanged. Request overrides may only lower ceilings.
The implementation remains an owned worksheet/converter path. Its logical charge
is not a process memory limit; the full-run RSS observation threshold is 384 MiB.
This batch does not establish real reader/converter overlap or index-build admission.

## Full-source oracle

The captured Python converter produces 44,445 entries, 24,826,583 decoded key/body
bytes and a 25,093,253-byte canonical TXT. Its set-valued reference fields can have
different order between Python processes. An independent full conversion with
`PYTHONHASHSEED=17` produced different raw bytes but the same accepted normalized
record digest as the first complete conversion. Both receipts are retained in
`docs/evidence/concise-full-source-reference` with source and Python code identities.
No definitions or original datasets are bundled.

The Mac batch compares every native entry against a fresh original-Python result.
Only the previously qualified reference-field set ordering is normalized. Keys,
entry order, duplicate multiplicity, definitions and other HTML stay exact. The
same full normalized digest must also equal the independent local reference.
Raw output hashes and whether raw bytes match remain visible in the report.

## Retained reproduction instructions (already passed)

Merge the updated package into the existing project. Keep `.venv`, `vendor`,
private inputs and all earlier outputs. Keep this exact uploaded ZIP in Downloads:
`dict_concised_2014_20260929.zip`.

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m2_concise_full.py --archives /Users/shawky/Downloads --output m2-concise-full-out
```

Change `--archives` if needed; extraction is automatic and checks exact archive,
member and workbook SHA-256. The output directory must be new. For a retry, use
a new name beginning `m2-concise-full-out`.

The script builds/tests only the new isolated workspace with locked offline
dependencies, then runs the complete workbook. Native tests cover shared runtime
behavior and conversion cancellation before commit versus success after commit,
new profile restrictions and lowering-only ceilings. The full-source controller
batch checks the old row and rectangle limits independently refuse the source,
requests cannot grow the new ceilings, a different converter is refused,
pre-cancellation produces no output, failure leaves the worker usable, the complete
output matches the original Python/reference digest, an existing output is kept,
and all reservations/private snapshots are released on normal shutdown.
It captures failure logs and controller diagnostics; no request samples/truncates
or writes original source files. The exact extracted source is rehashed at the end.

Return only `m2-concise-full-out/m2-concise-full-report.json`. Private source and TXT
files remain in the excluded output directory. Do not rerun accepted Mini/Idioms,
reader or M1 batches. Passing this gate qualifies only full Concise in this profile;
CC-CEDICT, Revised/WFG scaling, real packing workflows, index-build shared admission
and final M2 closeout remain.
