# Selected definition editing into a new database

Browse a database, select a row, choose **Edit definition**, change the definition source, and choose **Save edited entry in a database copy**. The headword is read-only. Blank text intentionally clears the definition. The existing preview shows the saved selection until the copy is loaded; the draft is plain source, not executed HTML. Canceling the save dialog keeps the draft and snapshot. Changing the row or page discards the draft.

This first editor accepts at most 8 KiB of UTF-8 replacement text within the unchanged 64 KiB complete command boundary. Larger existing definitions are never truncated: oversized drafts are refused before closing the snapshot. The backend preserves the exact provided body, including empty text, CR/LF, NUL and TXT delimiters. Browser textarea editing follows browser LF behavior. Existing 128 MiB file, 100,000-row, 32 MiB decoded-row and 1 MiB stored-body caps remain unchanged.

Background request: `kind=database`, `operation=db_edit_entry`, with source, new destination, expected_source_sha256, rowid (a signed canonical decimal string), and text. The worker validates a private source snapshot and requires its SHA-256 to match the opened snapshot. It selects the exact physical row ID, not a headword or a rounded JavaScript number. Duplicate names remain separate. The standard writer creates a new Studio database, updates origin/row/count digests, verifies by readback, and publishes without replacing an existing destination. Cancellation before commit leaves no published copy; later cancellation cannot undo successful publication.

Keys, row order, unselected bodies, stored TXT export format and decoded MDX metadata are preserved. The copy has canonical sequential row IDs; sparse or negative source IDs may be reassigned. Receipts include source_rowid and output_rowid. The copy's source_sha256 identifies source database bytes. Legacy inputs receive the existing Studio text profile. For active HTML numeric styles (`Format=Html`, `Compact=Yes` or `1`), replacement numeric markers must have stored stylesheet rules. Stylesheet and structural flags remain unchanged.

Close the app and update the project. Run from the project root on the Mac:

```sh
.venv/bin/python scripts/m4_database_entry.py --output m4-database-out-entry
```

Use a fresh directory. The runner executes the full desktop gate, requires the new backend/runtime/adapter tests, and independently checks every row for synthetic UTF-8/UTF-16 metadata databases and legacy input with sparse IDs. It checks clearing, stale input, invalid or absent IDs, edit limits, unknown numeric rules and existing destinations. Runtime tests also rebuild a selected-entry copy to MDX. Synthetic metadata fixtures do not claim an MDX decode. Native compilation and GUI checks remain pending until run on the Mac. M2 sources, locks and caps stay unchanged.

For the GUI check, browse `m4-database-out-entry/utf8-source.db`, select duplicate row **#3**, choose **Edit definition**, and replace its source with exactly:

```text
`1`Edited second duplicate.
```

Save to `/Users/shawky/Downloads/entry-gui-edited.db`. Browse the copy: expect seven records, unchanged blue DUPLICATE_ONE_BLUE at #2, and the new bold text at #3. Title, description, encoding and stylesheet must remain unchanged. From the project root:

```sh
.venv/bin/python scripts/verify_database_entry.py --source m4-database-out-entry/utf8-source.db --copy /Users/shawky/Downloads/entry-gui-edited.db --rowid 3 --text '`1`Edited second duplicate.'
```

Single quotes keep shell backticks literal. Send the JSON result or saved database for independent verification. This slice does not add, delete or rename entries, overwrite sources, raise caps, enable arbitrary SQL or qualify full M4 completion.

The later selected-headword extension is documented in [M4-DATABASE-RENAME.md](M4-DATABASE-RENAME.md). The read-only-headword description above records the original definition-only slice.
