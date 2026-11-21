# Literal headword prefix search

Browse database now offers **Headword prefix** alongside All entries and Exact
headword. `app` matches `apple` and `application`; `App` matches `Apple`.
Matching is case-sensitive and literal, including spaces, `%`, `_`, `?`, and
quotes. Chinese and Arabic prefixes are supported. This does not introduce
wildcard expansion, case folding or full-text search.

The SQLite predicate uses a bound query and `substr` with binary comparison,
not LIKE or interpolated SQL. Results remain in physical row order and preserve
duplicate definitions, pagination, source identity checking, response budgets,
shared admission and cancellation. Existing requests without the optional
`prefix` field keep exact behavior. The standalone backend adds `prefix_lookup`.

Limits remain 100,000 records / 32 MiB decoded text / 128 MiB files. This change
does not enable full CC-CEDICT database conversion. Every page still opens a
validated read-only snapshot; persistent readers are a later step.

## Native verification on Mac

Merge the update while preserving vendor and existing caches, then run:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_shell.py --output m3-shell-out-prefix
```

Use a fresh output suffix if it exists. This runs the database, runtime and
adapter suites plus frontend checks/build and desktop compilation. New native
tests cover literal punctuation, multilingual prefixes, case, duplicate order,
pagination, cancellation, default compatibility and shared job routing. Local
Python tests compare the actual SQLite predicates with Python `startswith` and
exact matching, including SQL-looking literal input. Rust and Svelte compilation
are not available in the preparation environment, so the Mac gate is required.

## GUI check

Start the updated app from `m3/desktop` with `npm run tauri dev`.
In Database, first convert `m3/fixtures/database-prefix.txt` using **TXT → SQLite**
to a new `prefix-test.db` file. It contains eight records. Then use Browse
database with that database and **Headword prefix**. Select two entries per page.

| Query | Expected |
| --- | --- |
| `app` | 3 results: apple, application, apple; pages of 2 then 1 |
| `App` | 1 result: Apple |
| `a%` | 1 result: a%b |
| `a_` | 1 result: a_b |
| `字` | 1 result: 字典 |
| `مر` | 1 result: مرحبا |
| `missing` | 0 results |

Switch to Exact headword with `app`: zero results. This distinguishes exact
from prefix matching. No existing database is edited.

## Preceding qualification

GUI cancellation and recovery are complete for the tested SQLite → MDX path:
the user provided a Cancelled job and a post-cancellation filesystem report,
then a later same-session Succeeded job. An independent stdlib MDX decoder
verified the uploaded recovery output `see.mdx` contained all five expected
records, both 字 definitions, Title `dict22` and Description `hi new world`.
Text evidence is retained under `docs/evidence/m4-gui-cancel-qualified/`.
