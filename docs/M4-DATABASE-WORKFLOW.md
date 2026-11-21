# Combined database workflow checkpoint

This is the first of the three proposed Database closeout checkpoints: combined workflow/readers, real dictionary sizing/performance, and final regression/evidence closeout. The accepted single-operation editor features are unchanged. This checkpoint adds a native adapter example and an independent qualification runner, not new production operations or raised limits.

The example uses the same adapter publication jobs as the GUI. For each UTF-8/UTF-16 fixture it packs a real source MDX, imports SQLite, updates title/description, edits one duplicate, renames an inline entry, appends a third duplicate, deletes another entry, rebuilds MDX and reimports it. Before each mutation it opens a fresh validated snapshot and closes it before submitting the publication job. Every stage writes a separate file and preserves previous stages. Existing caps, locks, M2 identities and publication policies remain unchanged.

Close the app and update the project. From the Mac project root, use a fresh output directory:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m4_database_workflow.py --output m4-database-out-workflow
```

This runs the full desktop gate and requires the existing edit/rename/add/delete runtime tests. The new native example executes nine publication jobs per encoding. The independent mdict-utils reader reads both original and rebuilt MDX without expanding numeric markers; Python SQLite oracles compare every intermediate copy, metadata, source hashes, receipt counts/IDs, duplicate order and the final reimport. Original fixture rows and metadata are checked before mutation expectations are applied. Verification itself must not change any artifact. Python unit tests tamper stage rows, metadata and receipt IDs, regenerate database digests, and alter rebuilt duplicate/sort order to verify detection. These local oracle tests do not qualify Rust compilation or reader rendering.

Expected automated status: `database_workflow_native_and_oracle_passed_readers_pending`. Upload `m4-database-out-workflow/report.json`. Rust compilation/native jobs remain pending until this report passes; actual reader checks remain separate.

The generated files to open in **both MDict and GoldenDict** are:

```text
m4-database-out-workflow/native/utf8/rebuilt.mdx
m4-database-out-workflow/native/utf16/rebuilt.mdx
```

Disable overlapping test dictionaries so absent keys cannot match another dictionary. Each rebuilt file contains **seven records** and **five distinct headwords**. The dictionary title is `Combined database workflow · UTF-8` or `Combined database workflow · UTF-16`. Its description is exactly `Edit, rename, add and delete into database copies.`

| Headword | Expected display |
| --- | --- |
| `combined` | Blue inline-blue and marker-blue; bold marker-bold. |
| `duplicate` | Three definitions, in order: blue DUPLICATE_ONE_BLUE, bold EDITED_DUPLICATE_BOLD, blue ADDED_DUPLICATE_BLUE. |
| `renamed 字` | Blue INLINE_BLUE_OK; this was the old `inline` entry. |
| `multilingual` | English, Chinese and Arabic, plus blue MULTILINGUAL_BLUE_OK. |
| `empty` | A valid entry with an empty definition. |
| `inline` | Absent after renaming. |
| `marker` | Absent after deletion. |

No raw numeric markers should appear. No MDD is needed. The same checklist is written to `reader-checks.txt` in the result directory. The original MDX intentionally differs from the rebuilt one because it retains pre-edit contents and metadata. Send the report first, then confirm both rebuilt encodings in both readers. This checkpoint is complete only after automated and reader evidence are reviewed.
