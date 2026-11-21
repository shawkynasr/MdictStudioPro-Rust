# Full CC-CEDICT: exclusive admission and chunked TXT publication

2026-11-07. Native test/build receipts and complete-source parity passed review. M2 is partial. Accepted native sources and
profiles stay unchanged; 229 prior source identities are checked before/after.

## Accepted Mac gate

The full 203,362-entry canonical TXT (76,339,785 bytes) matched both fresh Mac Python
and the independent complete local reference exactly. The receipt reported 125,369
primary entries, 77,993 traditional entries, 30 source comments and no skipped
nonempty source lines. Comments remain counted separately from exported TXT.

Review replayed all 1,440 controller exchanges. The old entry/decoded/output limits
refused the full source; attempted ceiling increases, pre-cancellation, overwrite,
wrong-converter and worksheet options were refused. One full publication, single
receipt transfer and late-cancellation behavior passed. Final reservations and
reader retention were zero. Exact source/lock/legacy bindings were checked; report,
provenance and twelve exact source snapshots are retained under
`docs/evidence/m2-cc-full-user-run`. No routine rerun is needed.

Peak reported native process RSS was 240,029,696 bytes (228.91 MiB), below the
provisional 384 MiB observation target. Full-data ledgers showed one CC conversion
reserving all 384 MiB, with no other active operation. Reader contention is covered
by the source-bound native test/build receipts; this full-source controller run
did not open readers. This is an observed workload qualification, not OS-enforced
memory isolation or proof for every input up to a ceiling.

Review rehashed the complete independent local Python output. Native output/source/
temporary files are private: their whole-output hash comparison and preservation/
cleanup are assertions of the exact-source-bound Mac harness. No Rust was executed
locally during review. Revised/WFG and M2 closeout remain pending.

## Why this follows Concise

The accepted Concise process reached 326.64 MiB while carrying a 256 MiB logical
conversion charge. That charge does not enforce a process memory ceiling. Large
owned conversions need a conservative admission policy and fewer simultaneous
output copies before extending concurrency or dataset claims.

`m2/cc-runtime` is an isolated facade based on the accepted converter runtime.
Its `cc-cedict-owned-chunked-txt-v1` conversion profile accepts only CC-CEDICT with
no worksheet selector. It preserves the qualified CC parser, frozen Unicode16
pinyin policy and HTML through `studio_application::convert`. That function still
owns all entries and briefly allocates canonical bytes for validation. This is
not an end-to-end streaming converter or an OS-enforced memory ceiling.

The new private publisher validates canonical record/aggregate limits, writes in
bounded chunks, syncs, reopens, and compares every byte against the validated
canonical entry sequence, including duplicate order, empty bodies and final body
newlines. Verification uses fixed buffers and an EOF check; it does not load the
whole file or build a second entries vector. Cancellation is checked through the
last precommit checkpoint. Exclusive publication preserves an existing file, and
committed success survives a later cancellation.

## Explicit profile and admission

| Limit | Accepted general converter profile | New CC-only profile |
| --- | ---: | ---: |
| Source snapshot | 32 MiB | 32 MiB |
| Output entries | 100,000 | 250,000 |
| Decoded output including source comments | 32 MiB | 96 MiB |
| Canonical TXT file | 64 MiB | 128 MiB |
| Key / body per record | 4 KiB / 1 MiB | Unchanged |
| Source/output line count | 4,000,000 | Unchanged |
| Logical conversion memory charge | 256 MiB | 384 MiB |
| Logical temporary charge | 768 MiB | Unchanged |
| Shared memory / temporary ceiling | 384 MiB / 4 GiB | Unchanged |

The new charge takes the entire shared memory budget. An existing reader blocks
a CC conversion, and a CC reservation blocks a new reader; the worker keeps its
serial publication order. This conservatism is explicit and isolated. It does not
change the already accepted general or Concise runtime, or qualify their full-size
reader overlap. Registry package versions/checksums remain identical in a separate
66-package lock; only the local facade identity changes. Ceiling overrides only
lower limits. Other converter ids and worksheet options are refused.

The full-source provisional observation threshold remains 384 MiB for the native
child process, including allocator/runtime overhead. It is not a hard limit.
A failure must drive more allocation work, not a silent threshold increase.

## Full source and Python oracle

The attached `cedict_1_0_ts_utf-8_mdbg.zip` contains the exact SHA-bound
`cedict_ts.u8` (9,871,744 bytes). Full Python conversion produces:

- 125,369 primary and 77,993 traditional entries: 203,362 total, in original order.
- 30 source comments and no skipped nonempty lines; comments are counted in the
  receipt and are not silently inserted into the canonical TXT.
- 75,119,613 decoded key/body bytes and a 76,339,785-byte canonical TXT.

The raw output hash and full framed record digest are retained in
`docs/evidence/cc-full-source-reference`. The Mac batch runs the captured Python
plugin again on an exact private oracle-side input copy (the legacy plugin writes
a log beside its input). Native TXT must match both that fresh Mac output and the
independent full local reference exactly. No reference-field normalization applies
to CC-CEDICT. The archive/source data and converted dictionary are not bundled.

## Retained reproduction command (already passed)

Merge the updated package into the current project; retain `.venv`, `vendor`,
private inputs and previous outputs. Keep this exact ZIP in Downloads:
`cedict_1_0_ts_utf-8_mdbg.zip`.

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m2_cc_full.py --archives /Users/shawky/Downloads --output m2-cc-full-out
```

Change `--archives` if the ZIP is elsewhere. Extraction checks exact archive,
allowlisted member, size and SHA-256 automatically. Use a new output folder for
retries, with the same `m2-cc-full-out` prefix.

The script tests/builds only the isolated new workspace with locked offline
packages, then checks the original entry/decoded/output caps refuse the full
source, ceiling increases are refused, pre-cancellation produces no output, invalid
MOE/worksheet requests fail, full output matches both Python references, a second
receipt cannot be taken, late cancellation retains success, an existing output is
preserved and normal shutdown releases reservations/private snapshots. Native
tests additionally cover reader contention in both admission directions, cancellation
before/after commit, fixed-buffer publication corruption detection and canonical
framing. No repeat of accepted M1 or earlier converter batches is requested.

Return only `m2-cc-full-out/m2-cc-full-report.json`. The report embeds failure
logs/diagnostics and hashes/counts, not definitions. Private source/TXT files and
legacy oracle logs stay under the excluded output prefix. Passing this batch would
qualify this full CC workload; it would not close M2.

## Remaining work

Revised and Revised WFG still need worksheet-memory architecture and measured
full-data qualification. Their 163,909 rows, 2,950,380-cell rectangle, large XML
parts and >100 MiB output are not admitted by this CC profile. No new XLSX caps
are raised here. Full real packing workflows, index-build shared admission and
backend closeout also remain open.
