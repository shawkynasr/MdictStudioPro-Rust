# MDX to SQLite with decoded header preservation

This adds MDX → SQLite to Database's conversion selector. The preceding
browsing GUI was confirmed by screenshots: five records at offsets 0/2/4,
two separate `字` matches, and zero matches for `missing`. The latest native
report for that updated browser has not been supplied. This step's new Rust
and Svelte changes also require native verification; M4 is not complete.

## Data and boundaries

The M3 route accepts a source MDX and a new destination DB only. It reuses the
accepted bounded v2 MDX exporter to write and verify a private JSONL spool.
It decodes that spool without an intermediate TXT representation, checks
record counts and key/body byte totals against the verified export, and
passes the rows and header into the staged database writer. Duplicates,
physical order, decoded HTML, numeric markers, redirect bodies, blank lines
and empty definitions are retained. It does not resolve redirects or expand
numeric stylesheet markers during import.

The existing exclusive 384 MiB logical / 3 GiB temporary reservation covers
the whole conversion. Limits remain 100,000 records, 32 MiB decoded rows,
128 MiB input/output, 4 KiB keys, 1 MiB definitions, 256 header attributes and
64 KiB aggregate decoded header key/value bytes. JSON escaping is allowed a
separate bounded storage envelope. This is unencrypted v2 import under the
existing MDX reader profile, not v3, a larger-file route or OS hard containment.
Empty dictionaries and keys containing NUL/newlines or equal to `</>` are
refused by this database profile. MDD resources stay in their separate files.

MDX-derived databases have application ID MDSP, SQLite user_version 2 and
profile `studio-sqlite-mdx-v1`. The same `mdx` two-column table holds the rows.
The five existing Studio metadata fields are joined by `mdx_header_json` and
`mdx_header_sha256`. The source SHA-256 is the original verified MDX snapshot,
not the private JSONL. All decoded header attributes—including Title,
Description, StyleSheet, encoding and lookup flags—are retained. They describe
the source dictionary; SQLite text is stored as Unicode. Raw XML formatting,
compressed bytes and original archive block layout are not retained.

The database is closed, reopened and checked for exact row and metadata
agreement before its no-clobber commit. Cancellation before commit publishes
no DB. Existing destinations are refused before exporting the MDX; temporary
spools/stages are privately owned. Old plain Studio databases remain revision
1, and legacy uncompressed two-column databases remain readable. Earlier app
versions reject the new revision rather than silently discard its metadata.

Browsing a revision-2 database returns its decoded dictionary metadata, shown
in a collapsible section. Both this metadata and definition source are escaped
text in the GUI. SQL/header tampering is detected by consistency checks, not
cryptographic authentication. DB → TXT still exports entries only; dictionary
metadata is retained in the DB and receipt, not embedded in the TXT file.

## Verification on Mac

Merge the updated sources into the existing project, preserving caches and
all real input/output files. No new dependency is added.

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
python3 scripts/m3_shell.py --output m3-shell-out-v20
cd m3/desktop
npm run tauri dev
```

1. Close/release Dictionary Tools readers. Select Database → MDX → SQLite.
2. Choose the five-record MDX built earlier, then a new destination such as
   `/Users/shawky/Downloads/mdx-copy.db`. Convert and collect the Jobs receipt.
   Expect five records and operation `mdx_to_db`.
3. Browse the new DB. Confirm five rows, the two distinct `字` definitions and
   the empty definition. Expand Dictionary metadata and check Title,
   Description and StyleSheet against the original MDX.
4. Optionally use SQLite → TXT with a new destination and compare its records.
   Definitions containing standalone TXT delimiters may be stored in the DB
   but correctly refused on TXT export; they are not silently rewritten.
5. Repeat an existing DB destination and check that it stays unchanged. Test
   cancellation with a sufficiently large supported input if needed.

`scripts/verify_mdx_database.py` is the independent comparison command. It
uses the existing `.venv` mdict-utils reader with `substyle=False`, preserving
numeric style markers while comparing rows. It also verifies the original
header through independent XML/checksum decoding and SQLite through Python's
read-only sqlite3 connection. Supply the actual source path:

```sh
.venv/bin/python scripts/verify_mdx_database.py --mdx "/actual/source.mdx" --database "/Users/shawky/Downloads/mdx-copy.db"
```

Send the shell report and verification result, or attach the small source MDX
and resulting DB for comparison. Native tests cover UTF-8/UTF-16 MDX input,
stylesheets, duplicate bodies, long Unicode metadata, malformed input,
overwrite refusal and cancellation during decoding/precommit. SQLite → MDX,
persistent readers, rendered DB previews and MDD import remain later work.
