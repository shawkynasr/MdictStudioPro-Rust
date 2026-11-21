# SQLite to MDX v2 rebuilding

This adds SQLite → MDX to Database. The preceding MDX → SQLite native report
passed ten database tests, 63 runtime tests, 15 adapter tests, Svelte build and
Tauri compilation. The uploaded `dictionary22.db` also passed integrity, row
count, row digest and metadata digest checks. It contains five records and
decoded Title `dict22` / Description `hi new world`, with an empty stylesheet.
Its original MDX was not uploaded for independent source comparison. A scoped
source-bound native report is retained in `docs/evidence/m4-mdx-import-qualified/`.
This new rebuild slice requires its own native and reader-app verification.

## Behavior

The source DB is privately snapshotted, validated and read in rowid order in
one operation. The accepted bounded MDX writer sorts keys using its pinned
Unicode-16 lowercase ordering and preserves the relative order of duplicate
definitions. Global row order may therefore change when rebuilding an unsorted
TXT/legacy database. Definitions, duplicate multiplicity, empty bodies,
numeric style markers and redirects are retained; redirects are not resolved.
No intermediate TXT representation is used.

For MDX-derived revision-2 databases, all supported decoded header attributes
are restored exactly, including title, description, stylesheet, original
UTF-8/UTF-16 encoding and extra attributes. The metadata serializer remains
the existing native-qualified ASCII attribute-name / LF stylesheet-triplet
profile, with its 64 KiB serialized UTF-16 header ceiling. Unsupported headers
or definitions are refused rather than normalized or dropped. This profile
requires explicit false/No values for KeyCaseSensitive and StripKey. Other
lookup profiles are deferred. Nonempty numeric stylesheets require HTML and
Compact=Yes. Encryption and MDX v3 are not written.

Plain Studio TXT and supported legacy two-column databases rebuild as UTF-8,
with the database filename stem as title, blank description/stylesheet, and
the existing writer's literal No/No header. Bodies containing NUL or undefined
numeric stylesheet controls remain outside this writer profile. The DB is not
modified. MDD resources are separate and are not rebuilt or renamed here.

## Verification and publication

The accepted writer first produces a private MDX. The stored header is then
serialized onto a private final stage. That stage is independently reopened
through the existing bounded MDX reader/exporter; every decoded key/body and
each key's ordered duplicate definitions are compared with the DB snapshot.
Header attributes and file extent must agree exactly before a no-clobber
commit. The result is a new MDX, not a byte-identical archive reconstruction.

One shared serial job covers the entire operation: 384 MiB logical memory /
3 GiB temporary reservation, cancellation, progress, receipts, dismissal and
shutdown. Dictionary Tools reader leases must first be released. Existing
limits remain: 100,000 records, 32 MiB decoded data, 1 MiB definitions, 4 KiB
keys, and 128 MiB source/output/private JSONL files. The backend DB validation
deadline remains cooperative; this is not OS hard memory/time containment.
Final stages live in a private directory beside the chosen destination.
Cancellation before final commit or a destination race publishes no new MDX.
Successful publication wins over a later cancellation.

The receipt records the input DB snapshot SHA-256 and its original row-order
digest, plus the output size, encoding, sort profile and decoded header. The
row digest is input provenance, not the sorted output's physical-row digest.
No new dependency, accepted M2 source or M2 lockfile is changed.

## Mac test

Merge the updated project files, preserving caches, dictionaries and outputs.

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
python3 scripts/m3_shell.py --output m3-shell-out-v21
cd m3/desktop
npm run tauri dev
```

1. Close/release Dictionary Tools readers. Choose Database → SQLite → MDX.
2. Select `/Users/shawky/Downloads/dictionary22.db` and a new destination
   `/Users/shawky/Downloads/dict22-rebuilt.mdx`. The save suffix is automatic.
3. Convert and collect the receipt. Expect five records, operation `db_to_mdx`,
   title `dict22`, description `hi new world` and UTF-8 encoding.
4. Test the new MDX by itself in MDict and GoldenDict. Confirm all five records,
   both `字` definitions, the empty entry, title and description.
5. Independently verify it using the existing Python environment:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/verify_database_mdx.py --database /Users/shawky/Downloads/dictionary22.db --mdx /Users/shawky/Downloads/dict22-rebuilt.mdx
```

Expected status is `passed`. This compares ordered duplicate definitions and
decoded headers through Python sqlite3 and mdict-utils (`substyle=False`), and
checks the input DB stayed unchanged. Send that output, the shell report and
the rebuilt MDX. Existing-destination refusal and cancellation are covered by
new native tests; the GUI can also be checked with a larger supported input.

Native tests additionally cover original UTF-8 and UTF-16 metadata/stylesheet
round trips, plain DB sorting, preserved duplicates, unsupported header flags,
precommit cancellation and destination races. Independent application rendering
of a rebuilt nonempty numeric stylesheet still needs a separate visual test;
the user's uploaded DB has no stylesheet. Persistent readers, larger profiles,
additional lookup policies and full M4 completion remain later work.
