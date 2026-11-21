# Persistent database browsing

The Database page now opens one validated SQLite snapshot on a dedicated native
worker. Load entries, exact/prefix searches and Previous/Next reuse it. Source
edits or removal do not affect the open snapshot. Choose **Close snapshot**, then
Load entries to read a changed file. Choosing or typing another source closes the
old snapshot before the next open. Changing a query or page size clears results
while retaining the snapshot. English, Chinese and Arabic labels are included.

The frontend serializes reader ownership changes and drains accepted open/page
jobs even when an older request finishes after a source/query change. It discards
stale results. Cancel remains available while opening or loading a page. A page
cancellation preserves the snapshot for another query; an open cancellation
releases it. Rendered/Split/HTML previews and metadata use the returned page.

The actor admits one reader and one retained open/page job. Each operation uses a
fresh backend Job and its original work limits. Close cancels active work, clears
queued work/results, drops the connection and temporary file, then releases the
shared reservation before exposing `closed`. Stale reader IDs cannot close a new
reader. App shutdown closes and joins this actor through the existing native
shutdown path.

Admission remains conservative: the existing exclusive database charge (384 MiB
logical memory / 3 GiB logical temporary reservation) remains held while the
snapshot is idle as well as busy. Other readers and publications are refused
until it closes. Database conversion and opening Dictionary Tools automatically
close the database snapshot first. Other publication workflows require using
Close snapshot before starting. Reservations are accounting, not OS memory limits.
All existing file, row, decoded text, cell and page caps remain unchanged.

New bounded adapter commands: `database_open`, `database_query`, `database_poll`,
`database_cancel`, `database_take`, `database_forget`, `database_close`. They use
the same main-window-only Tauri boundary. Native polling exposes one small job
snapshot; dictionary work runs outside the adapter mutex. Existing one-shot
`database_page` publication requests remain compatible but the GUI uses the new
reader commands.

## Mac checks

Close the app and update project files from the ZIP. From the project root:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_shell.py --output m3-shell-out-database-reader
```

Use a fresh output name for retries. This gate runs the backend, runtime and
adapter tests, frontend Node tests, Svelte checks, frontend build and desktop
compile. Upload `m3-shell-out-database-reader/m3-shell-report.json`. Native checks are
pending until this report is reviewed; the retained earlier reader report
qualifies only the backend foundation.

Then start the app:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1/m3/desktop
npm run tauri dev
```

Browse `prefix-test.db` with page size 2. Prefix `app` should give three records
across two pages, including both apple definitions. Try `App`, `a%`, `a_`, `字`
and `مر`; exact `app` should give no results. Confirm previews still work.
Change the query several times and confirm the snapshot-open notice remains.
Close snapshot: results and notice should clear; Load entries should open again.
Switch to another database and verify its rows/metadata replace the first.
Cancel an opening/page request if it is long enough to observe, then retry.
Finally quit with a snapshot open and confirm normal shutdown. Report the GUI
results separately from the automated gate.
