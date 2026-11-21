# SQLite → JSONL export

Database conversion now offers **SQLite → JSONL**. It exports every stored row,
in physical rowid order, as one UTF-8 JSON object containing `key` and `text`,
followed by LF. Duplicate keys remain separate records. Empty bodies, embedded
newlines/CRLF, quotes, backslashes, NUL characters, numeric style controls and
literal TXT delimiter lines survive JSON decoding unchanged. There is no
trimming, sorting, stylesheet expansion or redirect resolution.

This operation exports the complete source database, not the current browse
filter. JSONL contains definition rows only. MDX header metadata remains in the
database and is included in the job receipt, not embedded into the JSONL stream.
The receipt retains the input DB snapshot SHA-256, row digest, count, output bytes,
database profile and stored TXT profile. The TXT profile is provenance and does
not control JSONL encoding. MDD resources are separate.

The existing source snapshot/schema/row validation is reused. Each selected row
is encoded and written to a private file beside the destination; no whole-body
array or giant IPC reply is required. Before publication, the stage is reparsed
with bounded lines and its row count and framed row digest must exactly match
the validated snapshot. The final operation uses the existing no-clobber commit.
Cancellation, failure and a destination race remove private staging and preserve
existing files. Publication success wins over cancellation that arrives later.

All existing input, record, decoded-row, key/body and output caps remain: 128 MiB
files, 100,000 rows, 32 MiB decoded text, 4 KiB keys and 1 MiB bodies. JSON escaping
can make an output exceed 128 MiB even when the database fits; this is refused.
One encoded/verification line is bounded by `6 × (body cap + key cap) + 128`
bytes. This export does not use the 2 MiB browse reply envelope for row data.
The existing 60-second cooperative backend job budget applies through copying,
encoding, verification and commit checks.

The command runs through shared publication admission, progress, cancellation,
receipts and shutdown. Starting a Database conversion closes its browse snapshot
first. Dictionary Tools readers still need releasing. The save dialog selects
`.jsonl`, and suffix handling preserves an already-entered `.JSONL` extension.
English, Chinese and Arabic labels/hints are included. No accepted M2 source,
lock or dependency is changed.

## Automated Mac gate

The preceding wildcard feature passed its Mac gate and all seven user GUI
screenshots. Its scoped report and visual confirmation are retained in
`evidence/m4-database-pattern-qualified`; that does not qualify JSONL export.

Close the app, merge updated project files, and run:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m4_database_jsonl.py --output m4-database-out-jsonl
```

Use a fresh output name for retries. This single command runs the full desktop
gate, then builds the M4 CLI with `--offline --locked` and exports two synthetic
fixtures: a legacy two-column DB and a revision-2 DB with metadata. Python's
SQLite and JSON readers independently compare every row and digest, controls,
duplicates, empty bodies, output size, metadata receipt and no-clobber behavior.
It verifies that protected M2 sources, qualification sources and the M4 lock stay
unchanged. The synthetic revision-2 header is not an external MDX reader test.

Native tests also cover deterministic cancellation in snapshot/export/verification/
commit phases, stage cleanup, lowered output caps, destination races, corrupted
stage rows, shared reader admission and late cancellation after successful
publication. The Python verifier has tamper tests for changed/reordered/missing
duplicates, invalid object fields, duplicate JSON fields, malformed text and
incomplete lines. Native execution remains pending until the new Mac report.

Upload `m4-database-out-jsonl/report.json`. The expected status is
`database_jsonl_native_and_oracle_passed_GUI_pending`. The nested desktop report
and logs are retained under `m4-database-out-jsonl/m3-shell-out` if troubleshooting
is needed.

## GUI and real-file verification

After the automated gate passes, start the app with `npm run tauri dev` from
`m3/desktop`. Choose Database → SQLite → JSONL, select a supported DB and a fresh
output, convert, then collect its receipt. Verify the output against that DB:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/verify_database_jsonl.py --database /Users/shawky/Downloads/prefix-test.db --jsonl /Users/shawky/Downloads/prefix-test.jsonl
```

Use your actual selected paths. Expect eight records for the known prefix-test
fixture, or five for dictionary22.db. A repeated export to the same destination
must fail without replacing it. The receipt's operation is `db_to_jsonl`.
