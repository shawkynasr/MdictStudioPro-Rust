# Add one entry into a new database copy

Load a database snapshot, then choose **Add entry**, enter a headword and definition source, and choose **Save copy with new entry**. The Add button is available even when a search returns no results. A new entry is appended after all source rows, regardless of the current search, selection or page. Existing headwords are allowed and create another independent definition. Existing rows, their order, dictionary metadata and stored TXT profile remain unchanged. Empty definition text is allowed. The draft is plain source; the preview continues to show the saved selection until a copy is loaded. Canceling the save dialog keeps the draft and snapshot. Changing the row or page discards the draft.

This extends the shared background worker with `kind=database`, `operation=db_add_entry`, source, destination, expected_source_sha256, key and text. There is no source row ID. The worker validates a private source snapshot against its expected SHA-256, preserves all rows, appends one entry and verifies the rebuilt copy before no-clobber publication. The receipt includes the new `output_rowid` (sequential decimal string) and no `source_rowid`. Sparse or negative old row IDs become sequential in the copy. Rebuilding MDX uses the existing writer sort and preserves duplicate definition order.

Headword: nonempty, at most 4096 UTF-8 bytes, no NUL/CR/LF and not exactly `</>`. Spaces, punctuation and Unicode are literal. Definition: up to 8192 UTF-8 bytes, including empty text. The backend preserves provided CR/LF, NUL and TXT delimiters in bodies; textarea editing follows browser LF behavior. Numeric markers in active compact HTML dictionaries must use stored rules. The complete command remains capped at 64 KiB. Source rows can have larger stored bodies; they are not copied into the editor command or truncated.

Existing 100,000-record, 32 MiB decoded-text, 128 MiB file and 1 MiB stored-body limits remain unchanged. An addition exceeding the record or aggregate decoded-text cap is refused before publication. Source overwrite and existing destinations remain disallowed. Stale snapshots, invalid input and cancellation before publication create no output and preserve the source; cancellation after publication cannot undo success. This is adding to an existing validated database, not creating an empty dictionary or changing lookup flags.

Close the app, update the project, and use a fresh output directory on the Rust-enabled Mac:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m4_database_add.py --output m4-database-out-add
```

The runner requires the full desktop gate plus backend/runtime/adapter addition tests. Independent Python oracles check UTF-8/UTF-16 metadata fixtures and sparse legacy rows, duplicate additions, literal empty definitions, exact key/body boundaries, invalid keys, stale snapshots, unknown stylesheet rules and no-clobber behavior. Native tests check cancellation, publication races, unchanged large source definitions and the record cap. The runtime test rebuilds and reimports MDX to verify sort and duplicate ordering. Synthetic metadata fixtures do not themselves claim an MDX decode. Native compilation and GUI checks remain pending until run on the Mac. Protected M2 sources and locks remain unchanged; full M4 is not qualified by this slice.

For the GUI check, open `m4-database-out-add/utf16-source.db`, choose **Add entry**, set headword `duplicate`, and enter exactly:

```text
`1`ADDED_DUPLICATE_BOLD
```

Save to `/Users/shawky/Downloads/add-gui-edited.db`. Load the copy: expect **eight** records, both original duplicate definitions unchanged and the added bold definition at **#8**. Metadata and UTF-16 encoding remain unchanged. Verify from the project root:

```sh
.venv/bin/python scripts/verify_database_add.py --source m4-database-out-add/utf16-source.db --copy /Users/shawky/Downloads/add-gui-edited.db --key 'duplicate' --text '`1`ADDED_DUPLICATE_BOLD'
```

Keep the single quotes around text containing backticks. Send the Mac gate report and GUI verifier result or saved copy.
