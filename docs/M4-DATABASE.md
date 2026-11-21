# Database backend qualification

This document describes the qualified standalone SQLite backend.
The subsequent Database GUI integration is described in `M4-DATABASE-GUI.md`.
`m4/database` is an isolated Rust workspace. The standalone qualification is isolated from desktop builds. The subsequent M3
integration adds the qualified SQLite dependencies to M3 only; accepted M2
graphs remain unchanged. This is not whole Database feature completion.

## Scope and format

Commands are TXT → DB, DB → TXT, read-only exact lookup, and all-record browsing
with pagination. The browsing extension is described in `M4-DATABASE-BROWSE.md`.
The backend uses pinned rusqlite 0.43.0 with bundled SQLite, hooks and runtime
limits. Bundled SQLite avoids selecting an unknown system SQLite version.
The separate `m4/database/Cargo.lock` is retained exactly from the first Mac
resolution receipt, with its SHA-256 verified before inclusion. Each run records
all selected registry checksums and exact lock text in its report, and uses
`--locked --offline` for tests/builds. A C compiler is needed for
the bundled engine. The desktop's current lockfiles are protected, not upgraded.

The original GUI exposed mdict-utils `--txt-db`. Its upstream text schema uses
`mdx(entry TEXT NOT NULL, paraphrase TEXT NOT NULL)` and an entry index; the
legacy TXT parser strips lines and blank lines. This backend accepts that
uncompressed two-column schema for read-only import, but uses the existing
Studio parser/renderer for TXT so stored whitespace, duplicate order, empty
bodies and blank body lines are preserved. It does not reproduce irreversible
legacy trimming or restore whitespace that was already lost in an old DB.

New Studio databases use the same two-column `mdx` table plus `studio_meta`,
application ID 1296323408 (`MDSP`), user_version 1, source text profile, source
SHA-256, record count and framed row SHA-256. An index on entry uses binary
collation. There is no unique key constraint: duplicates remain separate rows.
`rowid` ordering defines stored record order. Lookup is raw exact, without
case folding, wildcard interpretation or redirect resolution. Row IDs in JSON
are strings to preserve full integer precision.

Canonical and legacy body-span TXT profiles are explicit during import and
stored in Studio metadata. Export uses that profile and reparses the result
before publishing. Legacy body-span mode preserves the raw body span; it does
not promise byte-identical headword/delimiter line endings. Standalone `</>`
inside a stored definition, NUL controls or an incompatible TXT body are
rejected as unrepresentable instead of silently rewritten. Later JSONL export
can provide an escape route, but is not part of this step.

## Input and publication boundary

Each operation copies and hashes a regular source into a private snapshot.
Database inputs must be closed rollback-journal SQLite 3 files: WAL, SHM and
journal sidecars, WAL header mode, compressed/BLOB definitions, MDD tables,
views, triggers, virtual tables and unknown schemas are refused. Do not use
this initial importer against a live writer. Switch WAL files to
`PRAGMA journal_mode=DELETE`, close/checkpoint them, and ensure sidecars are
gone before importing. No existing database is edited.

Database reads use a read-only connection to the snapshot, defensive mode,
disabled views/triggers, trusted_schema OFF, no enabled extension-loading
feature, fixed SQL and parameter binding. The reader validates supported
schema/column types, SQLite quick_check, every row and the Studio digest/count
when present. Externally edited Studio rows fail integrity until an explicit
editing profile is added. This is not an arbitrary SQL console.

Creation uses a transaction in a private destination-adjacent directory,
closes the connection, reopens/validates a snapshot of the staged DB, then
publishes via exclusive no-clobber file publication. TXT export is also staged
and revalidated. Existing destinations, malformed inputs, statement failures
and cancellation do not publish a new file. The private directory also owns
SQLite journals so failure cleanup does not leave public temporary sidecars.
Successful publication wins over cancellation arriving afterwards.

Fixed first-profile ceilings: 128 MiB source/output, 100,000 rows, 32 MiB
decoded keys+bodies, 4 KiB key, 1 MiB body, 128 matches per page and 2 MiB raw
and serialized lookup response. SQL length/columns/expression depth/attached
DB/variable limits, a 4 MiB page cache, disabled mmap and a progress hook are
configured. Each connection has an approximate 50-million-VM-instruction
budget; each Job has a cooperative 60-second deadline. These are application
work limits, not an OS-enforced bound on RSS, disk I/O or wall-clock time.

Qualification commands deliberately reopen, snapshot and validate the DB on
each call. A future GUI reader will need to retain the validated connection
under coordinated admission for repeated fast queries. The current GUI
integration connects conversions only through the shared publication queue;
see `M4-DATABASE-GUI.md`.

## Run on Mac

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
python3 scripts/m4_database.py --install --output m4-database-out
```

Keep `.venv`, vendor, desktop caches and existing dictionaries. `--install`
only creates the new database lock if absent and fetches that locked graph;
it does not install Python packages or rewrite the desktop locks. Later runs
can omit `--install` and use a new output folder, for example
`--output m4-database-out-v2`.

The script runs Rust unit tests and the CLI, then independently opens the
Rust-created DB using Python's sqlite3. It checks the five-record fixture,
physical row order, duplicates, definition bodies, metadata hashes, paginated
lookup, legacy DB import, no-clobber and malformed/compressed-input refusal.
Rust tests add cancellation at snapshot/insertion/commit, publication races,
legacy CRLF bodies, invalid schemas, changed-row detection and page overflow.

Expected report status: `backend_subset_passed`. Native Rust compilation/tests
are not available in the authoring environment. Local Python oracle tests do
not qualify the Rust backend. The report records native source hashes and
asserts accepted M2 and desktop M3 sources/locks stayed unchanged throughout.

The result folder contains `dictionary.db`, `roundtrip.txt`, a Python-created
`legacy.db`, test requests/logs and `m4-database-report.json`. The negative
fixtures deliberately include malformed or unsupported inputs; they are not
output dictionaries to import into MDict.

## References consulted

- [mdict-utils writer: txt2db/db2txt](https://github.com/liuyug/mdict-utils/blob/master/mdict_utils/writer.py)
- [rusqlite pinned release](https://docs.rs/crate/rusqlite/0.43.0)
- [rusqlite Connection API](https://docs.rs/rusqlite/latest/rusqlite/struct.Connection.html)
- [runtime SQLite limits](https://docs.rs/rusqlite/latest/rusqlite/limits/enum.Limit.html)
