# Shared Rust application conversion API

The shared conversion API passed its bounded integration batch on the user's
Intel Mac on 2026-10-30. M1 remains complete within its reviewed scope. M2 remains
partial. No rerun of this batch is needed.

All 49 command outcomes matched expectations: 39 successes and ten controlled
refusals. Twelve baseline/extended cases across six converters matched original
plugin content, TXT publication, shared progress and repeats. Active/named
workbook boundaries matched. Three cases differed from raw Python bytes only in
the previously documented set-derived reference/alias ordering. The Rust test
command, including the cancellation/publication integration suite, passed.

All nine application source/lock hashes, 81 protected source identities and the
60-package joint dependency receipt matched. The original report and nine source
snapshots are retained under `docs/evidence/m2-application-user-run`. The final
successful test log was not attached, so no individual Rust test counts are
inferred from it. This pass does not establish real-corpus scale, GUI integration
or completion of M2.

## Reproducing the accepted batch (not requested)

From the existing project folder after updating the ZIP:

```sh
.venv/bin/python scripts/m2_application.py --output m2-application-out
```

Return `m2-application-out/m2-application-report.json`. Unexpected failed-command
output is embedded in the report, limited to its last 64,000 characters. Named
actual/expected files may still be needed for a content mismatch. The output
directory must be new. Keep `.venv`, the prepared v6 `vendor` directory, real
corpora and all previous outputs. No pip update, dependency upgrade, old batch
rerun or native-reader check is requested.

## Public surface

`m2/application` is a separate workspace exposing `studio_application`:

- `read_workbook` returns the existing normalized `Table` with the shared job
  and error interface.
- `convert` dispatches a typed `ConverterId` to UTF-8 CC-CEDICT or any of the
  five qualified MOE converters. It returns core `Entry` values, canonical TXT
  profile, consistent metrics and retained CC-CEDICT comments.
- `convert_to_txt` converts and publishes through the already qualified staged
  core TXT writer. The destination must not exist. Its result includes record
  count, file bytes, converter identity, metrics and comments.

There is no Python runtime or intermediate subprocess in this application API.
Python in the runner is solely the independent original-plugin oracle.
The earlier qualified core, XLSX reader and converter code remain unchanged.
This new facade combines them through path dependencies. The future Tauri layer
can depend on it directly; no GUI, IPC commands or worker scheduler are included
in this slice. Existing MDX/MDD APIs stay in `studio-core`.

Requests use native Rust paths. JSON CLI requests require serializable UTF-8
paths, reject unknown fields, and are limited to 32 KiB. All six converter IDs
are stable snake-case names, e.g. `cc_cedict` and `moe_revised_wfg`. An optional
worksheet is supported for MOE XLSX inputs. Supplying it for CC-CEDICT is an
explicit `invalid_input` error.

## Jobs and errors

One `JobContext` supplies a caller-defined job ID, the existing cloneable
`CancellationToken`, and a common `Progress` callback. Progress stages are
`reading_workbook`, `converting`, `validating_output` and `publishing`. The
underlying phase name and local completed/total counters are preserved. These
counters have different units across phases and are not one global percentage.
Callbacks run synchronously on the calling worker. A UI integration owns worker
execution and event delivery to its UI thread.

The same token reaches the reader, converter, common TXT validator and publisher.
Cooperative cancellation before commit returns an error and no published output.
The core writer removes its temporary file on ordinary cancellation/failure.
Cancellation triggered by the final `published` callback occurs after commit and
returns success. There is no check after successful commit that could misreport
an already published output as cancelled. Callback panic recovery, SIGKILL,
power-loss durability and hard real-time interruption are outside this slice.

One serialized `ErrorCode` enum preserves all existing core errors and adds
`malformed_workbook`, `unsupported_workbook`, `unsupported_cell` and
`sheet_not_found`. All current XLSX/MOE string error codes map explicitly;
unknown future codes fail closed as `internal` with their diagnostic retained.
This does not change the underlying crates' public error types.

## Limits and parity

`Limits` contains dictionary, workbook and MOE budgets. The smaller core/MOE
entry-count, key, definition and decoded-output limits govern MOE conversion.
All converter results then pass common canonical TXT grammar and byte/line
budgets before success. Validation renders bounded TXT bytes and discards them;
publication renders again through the verified writer. This adds bounded
allocation/work and is not a streaming or hard-RSS claim.

The existing qualified format restrictions remain: dates/durations unsupported,
MOE ASCII marker/numeric syntax profile, first-seen set-derived ordering, UTF-8
CC-CEDICT input, no escaping/redirect resolution or external asset copying.
Whole real MOE corpus, production indexing/decompression limits and arbitrary
dictionary imports remain separate work. See `M2-MOE.md` and `M2-XLSX.md`.

## Dependency integration

The application lock is a deterministic joint seed from the two qualified lock
graphs. It has 60 package records: the union, with the unused `studio-cli`
package replaced by `studio-application`. Registry versions and checksums are
unchanged. Ambiguous `syn` references are explicitly version-qualified using the
original graph. `scripts/application_lock.py` reproduces and validates this
joint graph; no resolver refresh or new registry dependency is authorized by
the runner. Both original locks and every protected source stay unchanged.

The Mac batch uses Cargo `--locked`. If Cargo requires any lock adjustment, the
runner stops and returns the diagnostic for review rather than updating it.
The joint lock passed Cargo `--locked` on the user's Mac and matches the joint
qualified registry identities without dependency upgrades.

## Authored verification

The Rust integration tests cover one job ID across all stages, staged TXT bytes,
existing destination refusal, cancellation during reading, validation, writing
and strict reopen, successful late cancellation, common output budgets, input
error mapping, CC-CEDICT metrics/comments and unknown backend error handling.

The command runner compares twelve baseline/extended cases across all six
converters against actual original Python plugins. Each is converted, published
and repeated through the new API, with progress schema/order/commit checks. It
also checks active/named workbook access, inherited input refusals, unsupported
options, unknown converter IDs and preservation of an existing output. All old
qualified source identities and both old lock graphs are verified before/after.

Three new Python contract checks pass locally. Rust compilation, the integration
test command and the command matrix passed on the user's Mac. Background job
execution, worker event delivery and Tauri routing remain subsequent application
work. Do not mark M2 complete from this bounded integration pass alone.
