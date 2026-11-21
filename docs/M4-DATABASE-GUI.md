# Database GUI integration

The standalone SQLite backend passed all eight native Rust tests and six
independent oracle checks on the user's Mac. The source-bound report is kept
in `docs/evidence/m4-database-qualified/m4-database-report.json`.
This conversion integration passed native adapter/Svelte compilation and an
independently checked five-record GUI round trip. Its scoped evidence is in
`docs/evidence/m4-database-gui-qualified/`. The following read-only browsing
step is described in `M4-DATABASE-BROWSE.md`; its native checks are pending.
M3 and the whole Database feature remain incomplete.

## What is connected

Database now offers TXT → SQLite and SQLite → TXT. Paths have native pickers
and editable fields. Save dialogs append `.db` or `.txt` when needed. TXT
import explicitly selects canonical or legacy body-span input. Export uses
the stored profile, or canonical TXT for supported legacy databases.
All labels are provided in English, Chinese, and Arabic, using the existing
app theme and RTL layout. The page clears paths when changing direction.

The adapter submits a `database` request into the existing serial publication
worker. Poll, progress, cancel, result collection, retention, dismissal and
shutdown use existing jobs. A database conversion takes the full existing
384 MiB logical memory and 3 GiB temporary reservation, so open reader leases
must be released first. Backend limits remain 100,000 records, 32 MiB decoded
text, 128 MiB files, 4 KiB keys and 1 MiB definitions. These are logical caps,
not OS-enforced hard memory limits. The backend's cooperative time/VM work
budget also remains unchanged.

The wrapper accepts only the two publication operations; it exposes no lookup,
SQL or runtime cap overrides. Errors map into the shared job codes, retaining
the original database error code in the message. Publication remains staged,
verified, cancellable before commit, and refuses existing destinations.

## Dependencies

Only the additive M3 runtime now depends on `studio-database`. The accepted M2
source and lockfiles remain unchanged. M3 runtime/adapter seed locks add the
ten SQLite registry packages from the qualified backend lock, recorded exactly
in `m4/sqlite-registry.json`; their checksums and versions are checked before
native compilation. No existing M2 registry package can be upgraded through
this allowlist. Cargo may normalize path/development edges in the M3 locks.
The standalone backend lock remains unchanged. The Tauri graph is resolved by
its existing desktop check; a frozen production desktop lock remains later work.

## Run on the Mac

Update project sources while retaining `.venv`, `vendor`, `node_modules`,
`target`, real inputs and existing output folders. SQLite crates were already
fetched for the passed backend test, so start without reinstalling:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
python3 scripts/m3_shell.py --output m3-shell-out-v17
cd m3/desktop
npm run tauri dev
```

If a dependency is missing, rerun the shell check with `--install` and a fresh
output name. The first command writes `m3-shell-report.json`; please retain it.

1. Close/release any Dictionary Tools readers. Open Database.
2. Select TXT → SQLite, Standard TXT, and `m3/fixtures/build-source.txt`.
   Save to a new `studio-database-test.db` in Downloads. Convert, then collect
   its receipt in Jobs. Expect five records.
3. Return to Database and select SQLite → TXT. Select the new DB and save to
   a new `studio-database-roundtrip.txt` in Downloads. Expect five records.
4. Independently compare the exported entries:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
python3 scripts/verify_gui_extraction.py entries --source m3/fixtures/build-source.txt --txt /Users/shawky/Downloads/studio-database-roundtrip.txt
```

Expected status: `passed`, with five expected and actual records. Existing
files must remain unchanged on a repeated destination; malformed TXT must
leave no new DB. Cancel before commit using a larger input if the fixture
finishes too quickly. Cancellation after publication does not undo a success.

Database lookup/persistent sessions, MDX ↔ DB, BLOB/compressed definitions,
live WAL snapshots, resource databases and larger profiles remain deferred.
