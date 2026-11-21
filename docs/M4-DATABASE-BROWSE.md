# Read-only database browsing and lookup

The preceding GUI conversion slice compiled successfully on the Mac and its
five-record DB/TXT outputs passed independent comparison. Its scoped native
receipt and output digests are retained under
`docs/evidence/m4-database-gui-qualified/`. The uploaded report also inventoried
an extra unpacked project; only the 94 matching delivered source identities
are copied into the scoped receipt, with the original report digest retained.

## This slice

Database now includes Browse database below the conversion controls. Select
a SQLite file, choose All entries or Exact headword, and load a page. Page
sizes are 2, 16 or 32. Previous/next navigation follows physical rowid order;
duplicates remain separate and row IDs travel as strings. Empty definitions
remain empty. Exact matching is case-sensitive and treats whitespace,
punctuation, `%`, `_` and `?` literally. There is no wildcard or substring search.
Definitions are escaped source text, never injected into the application DOM.
The existing light/dark theme and English/Chinese/Arabic labels apply.

Each query snapshots and validates the entire closed database, then returns
one bounded page. This intentionally has an O(database size) validation cost
per page. There is no persistent SQLite reader or background open connection.
Later pages supply the preceding database SHA-256; a changed file fails with
an integrity error instead of mixing snapshots. Restart with Load entries to
accept a newly validated file. This detects changed content, not merely a
changed filename. SQLite inputs remain read-only; no output path is accepted.

The `database_page` request runs in the existing serial worker and takes its
full 384 MiB logical / 3 GiB temporary reservation. Dictionary Tools readers
must be closed and released first. Limits are unchanged: 100,000 records,
32 MiB decoded data, 128 MiB input, 4 KiB keys, 1 MiB definitions, and a 2 MiB
serialized page. The native boundary allows up to 128 records per page, while
the GUI offers the smaller sizes above. Large definitions can still exceed a
requested page's byte budget; reduce the page size rather than truncating it.
The cooperative SQLite work/time and cancellation checks remain active.

The GUI automatically collects/forgets its completed page jobs. Source/query
changes invalidate the displayed page and late results. Conversion receipts
remain manually collected in Jobs. Shutdown uses the existing worker join.
Read-only jobs have no destination; the M3 request accessor now returns an
optional path. The inherited M2 publication tests are copied into M3 with
only `.destination().unwrap()` adaptations and corrected relative fixture
paths; their assertions are retained.
Accepted M2 source and locks are unchanged. No new dependency is introduced.

## Mac verification

Update the project sources while preserving caches, dictionaries and outputs.

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
python3 scripts/m3_shell.py --output m3-shell-out-v18
cd m3/desktop
npm run tauri dev
```

The shell check now also executes the standalone database Rust tests, including
the new browsing checks, before the shared runtime and adapter tests. Rust
and Svelte execution for this slice remain pending until that report passes.

1. Close/release Dictionary Tools readers and open Database → Browse database.
2. Choose your previously verified `dictionary.db`, All entries, page size 2.
   Load entries: total 5. Navigate through three pages and back. Expect keys
   in order: `apple`, `字`, `字`, `مرحبا`, `empty`.
3. Select both `字` entries separately. Their first/second definitions differ;
   `empty` has a blank definition. HTML is shown as literal source text.
4. Choose Exact headword and search `字`: two distinct records. Search
   `missing`: zero records. `Apple` also returns zero for this raw exact policy.
5. Page jobs should disappear from Jobs after collection. Your input DB must
   remain unchanged. Send `m3-shell-out-v18/m3-shell-report.json` and confirm
   the displayed totals/order/definitions.

Persistent readers, rendered database previews, prefix/fuzzy search, database
editing, MDX ↔ DB, BLOB definitions, live WAL imports and larger profiles remain
later work. This slice is not full M4 completion.
