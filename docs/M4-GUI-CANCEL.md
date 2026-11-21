# GUI database cancellation check

The prior native report passed import/rebuild cancellation, existing destinations,
invalid files and recovery. This step exercises the desktop Cancel button.
No GUI or backend behavior changes are included. The Database submit handler
already navigates to Jobs, whose Cancel button calls the shared native handler.

Prepare a synthetic input from the updated project root:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m4_gui_cancel.py prepare
```

This creates `m4-database-out-gui-cancel/` with a closed SQLite database containing
100,000 short-key records and less than 32 MiB decoded text. It stays within
the existing record, file and writer planning limits. Generated fixture/output
folders are excluded from project ZIPs. It uses no real dictionary data.

Start the app using the usual command in the desktop directory if needed:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1/m3/desktop
npm run tauri dev
```

Close/release Dictionary Tools readers and dismiss completed Jobs if needed.
In Database, select **SQLite → MDX** and use:

- Source: `m4-database-out-gui-cancel/gui-cancel-source.db`
- Save as: `m4-database-out-gui-cancel/results/cancelled-rebuild.mdx`

Both paths are relative to the project root; preparation prints absolute paths
for pasting into the GUI. Click Convert, then **Cancel** when Jobs appears.
Wait for **Cancelled** before checking files:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m4_gui_cancel.py check
```

Expected file-check status: `filesystem_checks_passed_GUI_state_pending`.
The checker hashes the source, requires the destination and staging files to be
absent, and refuses leftover SQLite sidecars. It does not infer GUI cancellation
from file absence alone. Send the generated `gui-cancel-check-report.json`
and confirm that Jobs showed **Cancelled** (a screenshot is useful).

If the job completes before Cancel, preserve the successful output and retry
with a fresh folder, for example `--folder m4-database-out-gui-cancel-2` on
both prepare and check commands. The test input improves the opportunity to
click Cancel but cannot guarantee a timing window on every Mac. A failed job
or a completed job is not cancellation evidence. Do not raise limits or add
artificial publication delays to make this test pass.

After a successful cancellation, dismiss that terminal job and try a normal
small conversion to a new destination. Confirm success to check GUI recovery.
This first GUI check covers SQLite → MDX; native tests cover both directions.
