# Unicode lowercase database matching

Database exact and prefix searches now offer **Letter matching**:

| Mode | Behavior |
| --- | --- |
| Case-sensitive (default) | Existing literal, binary matching |
| Unicode lowercase | Lowercase the complete key and query with the reviewed Unicode 16 root-lower policy, then compare exactly or by prefix |

The second mode reuses the accepted casing implementation and frozen table by
path. No accepted M2 source, table, lock or dependency is changed. It is distinct
from full Unicode case folding: `Straße` and `STRASSE` remain different, as do
`i` and `İ` (the latter lowercases to `i` plus combining dot). Contextual Greek
sigma follows the lowercase rule: `ΟΣ` matches `ος`, while `οσ` remains distinct.
There is no accent removal, Unicode normalization, locale-specific casing,
punctuation stripping, wildcard expansion, or redirect resolution. In particular,
prefix comparison occurs after lowercasing each whole string; contextual casing
can affect its boundary. This profile does not reproduce every reader app's search.

Rows retain their original keys, definitions, row IDs, duplicate multiplicity and
physical order. Changing the mode clears the displayed results and keeps the open
snapshot. All-record browsing ignores the matching mode. Stored MDX lookup flags
and SQLite → MDX rebuild eligibility are unchanged.

The persistent reader exposes `LowerExact` and `LowerPrefix`. The managed
`database_query` request accepts optional `matching: "literal"` (default) or
`"unicode16_lower"`; unknown profiles are refused. Legacy one-shot database
requests remain literal. GUI labels/hints cover English, Chinese and Arabic.

Unicode lowercase queries scan validated snapshot rows in rowid order, without
creating a second dictionary index or copying all bodies into memory. The
reviewed casing policy is cached once. Each scan checks cancellation/deadline per
row, emits `database_case_scan` progress, and retains only the requested page.
The existing SQLite instruction budget and all source/row/cell/reply limits still
apply. Full totals require scanning all rows, so these queries can be slower than
literal queries. A failed/cancelled scan retains the snapshot for a retry.

## Validation

The earlier persistent reader GUI slice passed its Mac native/frontend/desktop
gate, duplicate pagination screenshots, and the user's close/reopen and normal
shutdown confirmation. Source-bound evidence is in
`evidence/m4-database-reader-gui-qualified`. It does not qualify this new mode.

New native tests cover accented Latin, contextual sigma, dotted İ, German ß,
non-BMP Deseret letters, Chinese/Arabic, literal `%`/`_`, duplicate pagination,
unchanged default matching, unchanged source bytes, scan cancellation, reply
overflow/recovery, and profile switching on one managed snapshot. Adapter and
frontend tests cover transmitting the new profile. Native tests and Svelte/Tauri
compilation require a fresh Mac run.

Close the app, update project files, then run from the project root:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_shell.py --output m3-shell-out-database-case
```

Upload `m3-shell-out-database-case/m3-shell-report.json`. Choose a fresh output
name if that folder already exists. After the build passes, start the app from
`m3/desktop` with `npm run tauri dev`.

In `prefix-test.db`, use prefix `aPp`, page size 2. Case-sensitive should return
zero rows. Unicode lowercase should return four rows across two pages: IDs 1/2,
then 3/4. Exact `aPpLe` should return IDs 1/3/4 in Unicode lowercase mode. Switching
back to Case-sensitive should return zero again while the snapshot remains open.
Both modes still treat `a%` and `a_` literally. Confirm existing previews work.
