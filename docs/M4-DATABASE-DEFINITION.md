# Stored definition text search

The database browser adds **Definition text contains**. It searches the stored `paraphrase` string, including HTML source and numeric stylesheet markers. It does not strip tags, resolve links or search rendered DOM text. Headwords are excluded. The result includes the complete original row, so two definitions under the same headword remain separate results.

The query is a literal substring; `?`, `*`, `%`, `_` and backslash have no wildcard meaning. A nonempty query of at most 4 KiB is required; NUL is refused. Case-sensitive matching uses the original text. Unicode lowercase matching applies the existing pinned Unicode 16 root-lower algorithm separately to the entire body and entire query before testing containment. This includes contextual Greek final sigma; it is not casefolding, accent normalization or tokenized full-text search.

Search uses the existing validated private read-only snapshot. Every query scans in physical rowid order to count all matching rows; only the requested page is retained. No index or source changes are made. Existing 100,000-row, 32 MiB decoded-text, 1 MiB body, 128-row page, 2 MiB serialized-reply and 60-second cooperative budgets remain. A body operation is bounded by the existing body cap; cancellation/deadline checks occur between rows, with progress every 256 rows and at scan completion. An interrupted or oversized page can be followed by another query on the same snapshot. Closing and reopening is required to observe source changes.

Protocol additions: `ReaderQuery::Definition/LowerDefinition`; the managed query's optional `definition` boolean defaults to false. Definition, prefix and wildcard flags are mutually exclusive. Existing queries retain their behavior. The standalone qualification CLI adds `definition_lookup` with optional `lower` (default false). The GUI supports English, Chinese and Arabic labels and reuses the current matching selector, pagination, previews and cancellation controls.

Close the app and update the project. From the project root on the Mac:

```sh
.venv/bin/python scripts/m4_database_definition.py --output m4-database-out-definition
```

Use a fresh output directory. The runner executes the full desktop gate (backend, runtime and adapter tests, frontend checks and native compilation), then independently checks native CLI results against explicit row identities and complete fixture text. It also verifies source and protected M2 identities and the M4 dependency lock. Native compilation cannot run in the delivery workspace.

After the gate passes, launch the app from `m3/desktop` with `npm run tauri dev`. Browse `m4-database-out-definition/definitions.db`, choose **Definition text contains**, and set 2 entries per page.

| Query | Letter matching | Expected rows |
| --- | --- | --- |
| `needle` | Case-sensitive | #3 application |
| `nEeDlE` | Unicode lowercase | #1 and #2 apple; next page #3 application |
| `中文` | Case-sensitive | #5 and #6 字 |
| `أهلاً` | Case-sensitive | #7 مرحبا |
| `<div` | Case-sensitive | #1 apple and #7 مرحبا |
| `? * % _` | Case-sensitive | #4 literal |
| `missing` | Case-sensitive | 0 |

The headword `needle` (#10) must not match a definition search for needle. Switching to exact headword search should find #10. Original/Split previews must retain stored source text and duplicate definitions. Native tests cover cancellation and retry, pinned snapshots, Unicode edge cases, invalid flag combinations, and page overflow. A passing runner report remains GUI-pending until the manual behavior is confirmed. This slice does not qualify full M4 completion or additional MDX rebuild lookup policies.
