# Selected entry deletion into a new database

Browse a database and select a row. Choose **Delete entry**, review its headword and source row ID, then choose **Save copy without this entry**. Choose a new output filename. Canceling the file dialog keeps the selection and snapshot; selecting another row/page discards the deletion panel. Load the saved copy to see the result. A search returning one match can still delete that row when other entries exist in the database.

Only that exact physical source row is omitted. Other definitions with the same headword stay separate. Remaining keys, definition source (including large bodies), order, stored TXT profile and dictionary metadata are preserved. Sequential output row IDs may change; the receipt has `source_rowid` and no `output_rowid` because the row no longer exists. The source file is preserved. This database profile requires at least one entry; attempting to remove the only row fails without publishing an output.

The new background request is `kind=database`, `operation=db_delete_entry`, with source, destination, expected_source_sha256 and rowid (a canonical signed i64 string). It contains no definition text, replacement key or arbitrary SQL. The worker uses the existing validated private snapshot, shared serial admission lease and cancellation token, then creates and verifies the new database before no-clobber publication. Source hash mismatch, missing/invalid IDs, existing destinations and cancellation before commit leave the source untouched and no new copy published. Cancellation after publication cannot undo success. Existing file, record, decoded-text, command and stored-body caps, locks and protected M2 sources stay unchanged. An unchanged stylesheet may retain rules unused by the remaining definitions.

Close the app before updating. From the project root on the Rust-enabled Mac, use a fresh output directory:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m4_database_delete.py --output m4-database-out-delete
```

The runner requires the full desktop gate and new backend/runtime/adapter deletion tests. Independent Python checks compare every remaining row and metadata for UTF-8/UTF-16 fixtures and sparse legacy IDs, first/last-row deletion, unchanged destinations, stale/missing/bad IDs, large bodies and refusal to delete the only row. Native tests check cancellation and destination races; the runtime test rebuilds and reimports MDX to verify surviving entries and sorting. The synthetic metadata fixture does not itself claim an MDX decode. Native compilation and GUI checks remain pending until the Mac run.

For the GUI check, open `m4-database-out-delete/utf16-source.db`, select duplicate **#3**, choose **Delete entry**, and save to `/Users/shawky/Downloads/delete-gui-edited.db`. Load the copy: expect **six** records, the first `duplicate` definition still blue, the second bold definition absent, and all other entries and metadata preserved. Output row #3 is now the former empty row #4.

```sh
.venv/bin/python scripts/verify_database_delete.py --source m4-database-out-delete/utf16-source.db --copy /Users/shawky/Downloads/delete-gui-edited.db --rowid 3
```

Send the gate report and GUI verifier result or saved copy. This step does not add entries, overwrite sources or qualify complete M4.
