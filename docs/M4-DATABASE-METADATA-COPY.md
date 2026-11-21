# Save a database metadata copy

The browser adds **Save database metadata copy** for databases with stored MDX metadata. Select the title and/or description checkbox, edit that field, and choose a new `.db` destination. Selecting an empty field intentionally clears its value. Canceling the save dialog leaves the open snapshot and drafts intact. A submitted copy releases the browse snapshot first and runs on the shared background publication worker.

The operation creates a new database through the existing verified writer. It preserves every key and definition in row order, duplicate definitions, empty bodies, the stored TXT export profile, and all unselected header attributes (including encoding, stylesheet, compact flags and lookup flags). It neither edits the input nor replaces an existing destination. The copy's `source_sha256` records the source database bytes, and its metadata and row digests are regenerated and verified. The imported MDX origin hash is not presented as the origin of this changed copy.

The request must carry the SHA-256 from the opened browser snapshot. The worker privately snapshots the current source and compares that hash before reading rows or creating an output. A changed or replaced source is refused with `integrity`; close and reload before trying again. Invalid externally modified Studio digests remain refused by normal validation. Native source changes after the private copy do not alter the job's pinned input.

Only title and description edits are accepted. Title is at most 4 KiB UTF-8, description 8 KiB; XML-forbidden controls are refused. Aggregate decoded metadata remains capped at 64 KiB/256 attributes. The adapter's complete JSON command remains at most 64 KiB; the frontend checks the encoded command before releasing the reader. Existing file, decoded-row, record, body, page, memory-admission and work budgets remain unchanged. Databases without stored MDX metadata have no editor in this slice.

Protocol: background `kind=database`, `operation=db_edit_metadata`, with `source`, `destination`, `expected_source_sha256`, and `edits` containing optional `title` and `description`. Missing edit fields preserve values; at least one replacement is required. Native tests cover stale-source refusal, cancellation at several stages, clean recovery, final destination races, field bounds, source immutability and rebuilding an MDX that retains the edited metadata. Successful publication retains the established rule that a later cancellation cannot undo it.

Close the app and extract the update, then run from the Mac project root:

```sh
.venv/bin/python scripts/m4_database_metadata.py --output m4-database-out-metadata
```

The fresh-output runner executes the full desktop gate and independent Python comparisons for synthetic UTF-8/UTF-16 metadata databases. It verifies seven stylesheet fixture records, both duplicate definitions, exact source/copy rows, edited and unselected attributes, digests, origin hash, blank selected values, bounds, stale-source rejection and no-clobber behavior. Synthetic source metadata has an explicit placeholder origin hash; the runner does not claim an MDX decode for those inputs. Native runtime tests separately cover MDX rebuilding. Rust/Tauri compilation remains pending until the user-run gate passes.

For GUI checks, open `m4-database-out-metadata/utf8-source.db` in Browse database. Expand **Save database metadata copy**, select title and description, set title `dict22 edited` and description `hi new world`, and save to a new `metadata-gui-edited.db`. Expect a successful background job. Browse the new file and inspect Dictionary metadata; expect all seven records, both duplicate definitions and the original numeric stylesheet.

From the project root, compare the actual GUI output:

```sh
.venv/bin/python scripts/verify_database_metadata.py --source m4-database-out-metadata/utf8-source.db --copy /Users/shawky/Downloads/metadata-gui-edited.db --title 'dict22 edited' --description 'hi new world'
```

A same-destination attempt must leave the existing file unchanged. No screenshot is required for the source/copy oracle. Rebuilding the edited database to MDX remains the existing separate operation; reader apps can additionally confirm the new title and unchanged styled definitions. This feature does not enable entry editing, stylesheet editing, arbitrary SQL, or full M4 completion.

The later additive stylesheet replacement is documented separately in `M4-DATABASE-STYLESHEET-COPY.md`; the earlier title/description evidence remains scoped to its accepted version.
