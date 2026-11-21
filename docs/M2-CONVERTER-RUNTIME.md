# Larger owned converters and shared admission: first gate

Accepted first Mac gate 2026-11-06 after moving the crate documentation comment
above module declarations. The original E0753 failure and exact sources remain
retained. All five Rust test/build/seed command receipts and six controller
scenarios passed. The 17 registered source-bound Rust tests are represented by
the successful test command; individual successful test stdout was not attached.

Report, eleven exact source snapshots and independently generated local Python
oracle receipts: `docs/evidence/m2-converter-runtime-user-run`.

Review independently regenerated the full fixture files and ran all six original
Python plugins, recomputing 68,000 normalized records. It checked 2,964 controller
exchanges, six successful conversions, 35 expected failures, 48 pre-cancelled jobs,
18 expected API refusals and six correct reader pages. Reader/converter overlap
was observed in every scenario with the correct 352 MiB combined logical memory
weight. Final shared reservations, retained reader handles and reader reply bytes
were zero. Maximum process RSS was 192,593,920 bytes (183.67 MiB rounded).

Raw bytes matched for CC-CEDICT, WFG, Idioms and Mini. Revised and Concise matched
under the already documented narrow Python set-order comparison; other HTML,
whitespace, duplicate order and metrics remain exact. All 199 prior source
identities, eleven new source identities and 66 package identities match.

Actual user output files and successful Rust test stdout were not attached. Full
Mac XLSX/Python parity, snapshot/source identity, publication and cleanup were
checked by the exact-source-bound harness. Review separately ran local full
Python oracles and checked reported hashes/digests, state transitions and ledger
arithmetic. Those local oracle receipts are retained with source bindings.

No rerun is needed. Keep `.venv`, `vendor`, private inputs and prior outputs. The
accepted command is retained for reproduction only; choose a new output folder
if a rerun is requested:

```sh
.venv/bin/python scripts/m2_converter_runtime.py --output m2-converter-runtime-out-v2
```

A reproduction returns that folder's `m2-converter-runtime-report.json`, including
on failure. No pip upgrade, vendor preparation or native dictionary-reader
visual test is needed for this converter profile.

## Implementation

The isolated `m2/converter-runtime` workspace preserves the accepted publication
runtime as a source-bound artifact and adds a conversion request variant to a
new instance of that runtime. CC-CEDICT and all five MOE converters call the
qualified `studio_application::convert_to_txt` implementation with explicit
larger limits. Existing defaults and the converter algorithms are not edited.

Each conversion privately snapshots its selected regular input through a 64 KiB
buffer, caps growth, hashes the exact snapshot and runs the native converter on
that private file. The suffix remains .txt or .xlsx as appropriate. It retains
worksheet selection and the existing scalar normalization, HTML, duplicate and
alias behavior. This does not add streaming XLSX reading: the qualified reader
still constructs worksheet/cell/table values, and converters own their entries.

Results are thin: converter/profile, entry and file counts, metrics, comment count
and input snapshot SHA-256. Complete entries and CC-CEDICT comment strings are
not retained in the worker result or sent over the controller protocol. The
legacy Python converters run only as explicit test oracles, outside the Rust
runtime and its RSS measurement; no Python plugin is launched by the runtime.
The CC-CEDICT oracle receives an exact-byte copy in the oracle folder because
the legacy plugin writes an input-adjacent log; the selected input tree stays
unchanged. Local original-Python sizing checks fit the proposed decoded limits
for all six recipes. They do not establish Rust parity or process memory usage.

The qualified canonical TXT writer still renders owned bytes, reopens the private
output, strictly reparses every record, compares entries/bytes and publishes a
new file exclusively. Larger conversion therefore includes multiple bounded
owned collections during conversion/publication. It is not a streaming pipeline
or a guarantee that process RSS equals the logical reservation.

## Candidate ceilings

| Budget | Larger profile |
| --- | ---: |
| Converter source snapshot | 32 MiB |
| Converted entries | 100,000 |
| Decoded key/body bytes | 32 MiB |
| Published canonical TXT bytes | 64 MiB |
| Key / individual body | 4 KiB / 1 MiB |
| Source/output text lines | 4,000,000 |
| Workbook rows / columns | 32,000 / 64 |
| Workbook cells | 512,000 |
| Workbook decoded scalar bytes | 32 MiB |
| Workbook ZIP advertised uncompressed total / part | 128 MiB / 32 MiB |
| MOE row count | 32,000 |
| MOE input charge including repeated header names | 48 MiB |
| MOE decoded output | 32 MiB |

The workbook row ceiling includes the reader's coordinate/header accounting.
Other qualified value/part-count checks remain in force. Comments count toward
CC-CEDICT's decoded budget as in the original Rust converter. Lower-only request
overrides cover source bytes, entries, decoded output, TXT bytes, workbook rows,
cells and decoded scalar bytes; unsupported increases fail explicitly. The
native dictionary byte limit also applies when it reads the snapshotted CC-CEDICT
source, so lowering TXT bytes can cause an earlier source-read refusal.

## Shared worker and cancellation

Conversion uses the same serial publication queue as MDX/MDD packing, JSONL/TXT
export and streaming MDD extraction in this new runtime. The active reservation
is acquired at dispatch before snapshot I/O. A converter reserves a logical
256 MiB memory weight and 768 MiB temporary-file weight. The existing two active
slots, 384 MiB memory weight cap and 4 GiB temporary weight cap remain. Reader
plus conversion reserves 352 MiB / 1.5 GiB; two readers block conversion before
it runs. Weights schedule work and are not operating-system quotas.

The queue retains two pending requests by default and at most eight jobs/results.
Input/destination paths and worksheet selectors are bounded; row data is read
from the selected file, not embedded in queued requests. Reader actors keep their
existing page workers and cleanup/release barrier.

The original cancellation token and progress callbacks flow through snapshotting,
reading, conversion, validation and publication. Calamine/library calls and some
owned parsing/rendering operations have no internal interruption hook; cancellation
takes effect at the next qualified checkpoint before commit. Once native TXT
publication succeeds, receipt construction only moves prepared fields and counts
comments; it performs no new hashing, serialization or token check that could
discard committed success. Worker panic outcomes remain conservatively uncertain
and release reservations. Shutdown and blocking join behavior are unchanged.

## Qualification batch

The workspace has 17 registered Rust tests: the 13 inherited publication/reader
ordering tests, three conversion tests and the included SHA-256 vector test.
New conversion tests check the distinct reservation, two-reader contention and
recovery, thin results, mid-conversion cancellation with a queued packing job,
postcommit cancellation/shutdown and lowered entry caps followed by success.
Condition-variable gates make cancellation ordering deterministic.

The Mac batch builds/tests the runtime and seeds a small indexed reader. It then
runs six controller scenarios. CC-CEDICT has 16,000 input lines plus a comment,
producing 32,000 simplified/traditional records. The shared MOE workbook has
12,000 data rows in two-row polyphone groups, numeric cells, Chinese/Arabic text,
references, aliases and image markers. Each MOE converter produces thousands of
records and uses a row count above the previous 10,000-row default.

For every converter, the captured original Python plugin is executed explicitly.
All records, duplicate order, HTML and metrics are compared. The existing narrow
MOE comparator accounts only for documented Python set iteration in reference
values/alias groups; it does not broadly normalize whitespace or HTML. A normalized
framed digest and both raw file hashes are recorded, with raw equality stated
separately. Canonical TXT parsing in the new fixture helper is linear in file size.

Each scenario opens two readers, confirms admission refusal, releases one and
converts while requesting an indexed page. It checks metrics, complete output
parity, snapshot identity, no overwrite, lower limits, pre-cancellation, retention,
single-transfer receipts, late cancellation, shutdown refusal, input/cache identity,
temporary cleanup and final zero reservations/reader retention. Workbook, malformed
source, bad UTF-8 and worksheet selector refusals are included. Full controller
transcripts and exact lock contents are embedded in the report.

Controller process RSS excludes Python/openpyxl oracle work and the compiler.
384 MiB remains a provisional observation threshold, not proof for all admitted
cap combinations. Larger formulas, varied cell shapes and real dictionaries or
spreadsheets are outside this synthetic batch. Active overlaps are sampled; Rust
gates establish ordering even if a process finishes between observations.

All 199 prior qualified source identities remain protected. The lock keeps the
same 66 package identities/registry checksums, replacing only the local facade;
no dependency update is requested. Representative real inputs, full ceiling
qualification, index-build admission, further platforms/GUI routing and final M2
closeout remain open even after a successful first converter run.
