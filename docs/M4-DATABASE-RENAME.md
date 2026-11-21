# Selected headword editing into a new database

Browse a database, select a row, choose **Edit entry**, and check **Rename** to enable its headword field. The checkbox starts unchecked. Saving without it preserves the original key. Definitions can also be edited in the same copy. Canceling the save dialog keeps the draft; choosing a different row or page discards it. Load the saved copy to see the result.

Only the selected physical row changes. Duplicate names stay separate even when the replacement already exists. SQLite row order, all unselected rows, definition text, stored text profile and dictionary metadata are preserved. Output row IDs are sequential; sparse source IDs may be reassigned. The receipt identifies both source and output IDs. Rebuilding MDX uses the existing writer sort and preserves duplicate definition order.

Optional `key` extends `db_edit_entry`; omitted or null means preserve the original. An explicit key is nonempty, at most 4096 UTF-8 bytes, contains no NUL/CR/LF and cannot equal the TXT delimiter `</>`. Spaces, case, punctuation and Unicode are literal. Existing definition-editor and complete-command caps remain 8 KiB and 64 KiB. A large existing definition is refused without truncation before releasing the snapshot, including rename-only saves. No source overwrite, add/delete, new lookup flags, dependency changes or cap increases.

The source SHA-256, exact signed row ID, private snapshot validation, numeric marker checks, cancellation, verified readback and no-clobber publication remain required. Cancellation before publication leaves no output. Existing destinations are preserved. Rust/native and GUI checks must run on the Mac; local Python/Node checks alone do not qualify them.

Close the app, update the project, then run from its root using a fresh output directory:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m4_database_rename.py --output m4-database-out-rename
```

The runner requires backend, runtime and adapter rename tests and the full desktop gate. Independent Python oracles check synthetic UTF-8, UTF-16 and sparse legacy sources, unchanged definitions/metadata, name collisions, clearing, invalid keys, stale snapshots and no-clobber behavior. The runtime test rebuilds to MDX and reimports to verify sorting after renaming. The synthetic metadata fixture itself does not claim an MDX decode.

For the GUI check, open `m4-database-out-rename/utf16-source.db`, select duplicate **#3**, choose **Edit entry**, check **Rename**, and enter `renamed 字`. Leave its definition unchanged: `` `1`DUPLICATE_TWO_BOLD ``. Save to `/Users/shawky/Downloads/rename-gui-edited.db`. Load the copy: expect seven records, unchanged first duplicate at #2 and the renamed bold entry at #3. Then run:

```sh
.venv/bin/python scripts/verify_database_entry.py --source m4-database-out-rename/utf16-source.db --copy /Users/shawky/Downloads/rename-gui-edited.db --rowid 3 --text '`1`DUPLICATE_TWO_BOLD' --key 'renamed 字'
```

Send the gate report and GUI verifier result. Keep single quotes around text containing backticks.
