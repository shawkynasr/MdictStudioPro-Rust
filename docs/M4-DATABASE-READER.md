# Persistent SQLite reader: native foundation

This slice adds an owned `Reader` in `m4/database`. Its native foundation passed
the uploaded Mac report (see `evidence/m4-database-reader-qualified`). The next
slice connects it to the GUI; see `M4-DATABASE-READER-GUI.md` for that separate
qualification. No application restart is required for this backend runner; closing
the app first keeps the test workflow consistent.

`Reader::open(path, job)` uses the existing bounded copy, SQLite schema checks,
integrity checks, metadata checks and complete row validation. It retains the
read-only connection and private temporary file. `info()` returns the opening
source SHA-256, row digest, record count, database profile and optional MDX header.

`page(ReaderQuery::{All, Exact, Prefix}, offset, limit, job)` reuses that snapshot.
It does not reopen, recopy, or revalidate the original path. Edits, replacement,
or removal of that path do not change an open reader. Close and reopen to see
new source data. Exact and prefix queries remain case-sensitive and literal;
duplicates retain their physical row identities and order.

Each page takes a fresh `Job`. Its SQLite progress hook resets cancellation,
deadline and instruction accounting, including after a cancelled or failed page.
Opening checks cancellation again at `database_reader_ready`, before handing
ownership to the caller. `close()` is idempotent; subsequent info/page calls
return `closed`. Close and ordinary drop close the connection before unlinking
the snapshot. Abnormal process termination cleanup is not qualified here.

Existing limits are unchanged: input 128 MiB, 100,000 records, decoded rows
32 MiB, body 1 MiB, key 4 KiB, reply 2 MiB, offset at most 100,000, and per-job
60-second / approximately 50-million SQLite instruction budgets. Persistent
pages require 1–128 rows; existing one-shot zero-limit behavior is unchanged.
WAL, shared-memory and journal sidecars remain unsupported.

The caller must own and close its reader. The backend API itself has no global pool or session persistence across restarts.
The GUI adds one managed handle with shared admission in the subsequent slice.
Desktop integration must coordinate admission, operation cancellation, source
switches, stale replies, explicit close and app shutdown before exposing handles.

## Mac qualification

From the project root, use the existing prepared dependencies and a fresh output
directory:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m4_database_reader.py --output m4-database-out-reader
```

The runner uses only `cargo --offline --locked` with the isolated M4 lock. It runs
all backend library tests (including the persistent reader tests), then a standalone
example. Python independently verifies the original SQLite rows, Studio metadata,
digests, all/exact/prefix pages, duplicates, offsets, one opening validation,
queries after source deletion and closed-reader responses. Native tests also
cover source edits, cancellation recovery, expired jobs, limits, response overflow,
close/drop removal and invalid inputs. Outputs are synthetic; existing folders
are refused rather than overwritten.

Expected status:
`persistent_reader_backend_passed_GUI_integration_pending`.
Send `m4-database-out-reader/report.json` after running. For a retry use a fresh
name, for example `--output m4-database-out-reader-2`.

## Validation scope

Python oracle tests can run in the packaging environment. Rust/Cargo is not
available there; native compilation, tests and the example remain pending until
the Mac report is checked. Earlier database preview evidence qualifies the
previous frontend slice only, not this reader API.
