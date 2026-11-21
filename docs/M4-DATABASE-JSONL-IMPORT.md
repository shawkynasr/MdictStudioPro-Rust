# JSONL → SQLite qualification

This additive operation imports row-only UTF-8 JSONL into a new Studio text database. Each line must be an object with exactly two string fields, `key` and `text`, and end with LF (CRLF is also accepted). Blank lines, missing/extra/duplicate fields, BOMs, invalid UTF-8, non-string values and incomplete final lines are refused. Headwords must be nonempty, at most 4 KiB, contain no NUL/CR/LF, and differ from `</>`. Definition text retains empty strings, line endings, NUL, literal TXT delimiters and numeric style markers.

The source is privately snapshotted and hashed. Bounded parsing retains at most 100,000 rows and 32 MiB of decoded key/body bytes; each body is at most 1 MiB. The existing 128 MiB input/output and 60-second cooperative work budgets remain. The existing database writer inserts in input order, checks the staged database by readback, and publishes without replacing an existing destination. Cancellation before commit leaves no published output. Successful publication wins a later cancellation.

JSONL carries no dictionary metadata. Import creates the existing `studio-sqlite-text-v1` revision 1 profile, stores the JSONL source hash and framed row digest, and defaults subsequent TXT export to canonical format. Stored HTML is previewable; numeric style markers remain literal without a stored stylesheet. No metadata is inferred or copied from another database.

Close the app, update the project, then run from the project root on the Rust-enabled Mac:

```sh
.venv/bin/python scripts/m4_database_jsonl_import.py --output m4-database-out-jsonl-import
```

Use a fresh output directory. This runs the full desktop gate, native backend/runtime/adapter tests, and independent Python SQLite/JSONL checks for order, duplicates, controls, origin hash, absent metadata, byte-identical re-export, malformed inputs, aggregate limits and no-clobber behavior. Reports remain GUI-pending until manual confirmation. Rust/Tauri compilation cannot run in the Linux delivery workspace.

For the GUI check, launch from `m3/desktop` with `npm run tauri dev`, select Database → JSONL → SQLite, choose the previously exported `prefix-test.jsonl`, and save to a new `prefix-test-imported.db`. Expect 8 records with both apple definitions and unchanged Chinese/Arabic text. Browse the database, then independently compare every row:

```sh
.venv/bin/python scripts/verify_database_jsonl.py --database /Users/shawky/Downloads/prefix-test-imported.db --jsonl /Users/shawky/Downloads/prefix-test.jsonl
```

The expected row digest remains `28b954eb69af2807d5f1901b98f71700cc1ce1c3a324b42fbca97f7fa368db2c`. The database source hash in this comparison is newly computed and need not match the original database file. Check cancellation with a larger fixture and retry to a fresh destination; selecting an existing destination must preserve it.
