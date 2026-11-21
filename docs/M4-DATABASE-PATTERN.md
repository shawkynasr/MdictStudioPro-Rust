# Explicit wildcard database search

Database browsing now has **Headword pattern (? / *)** alongside All entries,
Exact headword and Headword prefix. Exact/prefix behavior remains literal.

| Pattern syntax | Meaning |
| --- | --- |
| `?` | Exactly one Unicode scalar value |
| `*` | Zero or more Unicode scalar values |
| `\?`, `\*`, `\\` | A literal question mark, star or backslash |
| `%`, `_`, brackets, punctuation and spaces | Literal characters |

Patterns match the complete headword. Use `*word*` for a contains search.
Empty patterns, trailing backslashes and escapes other than the three listed
above are refused. Combining marks count separately; for example, `i` plus a
combining dot needs two `?` characters. A non-BMP letter needs one `?`.

Both letter-matching choices are available. Unicode lowercase first applies the
existing pinned Unicode 16 root-lower policy to the whole headword and pattern,
then parses and matches the pattern. Its contextual sigma, dotted İ, no-accent-
normalization and no-full-case-folding rules remain as documented in
`M4-DATABASE-CASE.md`. Wildcards match the resulting lowercase text. This is an
explicit database search profile, not a claim of matching every external reader.

The backend adds `ReaderQuery::Pattern` and `LowerPattern`. Managed queries use
optional `wildcard: true`; it defaults to false. Wildcard queries require a key
and `prefix: false`; contradictory query flags are refused. No user pattern is
interpolated into SQL, and SQLite LIKE/GLOB/regular expressions are not used.
Source bytes, stored metadata, keys, bodies and duplicate rows are unchanged.

Searches reuse the existing snapshot and scan rows in physical order, retaining
only the requested page. The nonrecursive matcher uses constant control state
and bounded per-row character storage. A query has an additional limit of
50 million matcher steps across all rows, with cancellation/deadline checks
within the matcher every 1,024 steps and between rows. SQLite's existing statement
budget, 60-second cooperative job deadline, input/decoded/record/cell/reply caps
and shared admission remain unchanged. Exhaustion fails the query without
returning a partial page. The reader remains available for a simpler retry.

Progress uses `database_pattern_scan`; changing operation, pattern or letter
matching clears displayed results and preserves the snapshot. Escapes are sent
unchanged through the GUI bridge. English, Chinese and Arabic hints are included.

## Qualification

The preceding Unicode lowercase feature passed its Mac gate and the user's six
GUI screenshots: zero literal mixed-case matches, four lowercase prefix matches
across two pages, three lowercase exact matches across two pages, and zero after
switching back. The snapshot-open notice and previews remained present. That
source-bound evidence is retained in `evidence/m4-database-case-qualified` and
does not qualify this new wildcard implementation.

New native tests compare the matcher exhaustively against an independent dynamic
program for small patterns/strings and cover escapes, Unicode scalar semantics,
work exhaustion and cancellation. Reader/runtime/adapter tests cover explicit
wildcard routing, literal punctuation, duplicate pagination, preserved literal
modes, lowercase combinations, source immutability and retry. Frontend tests
check that wildcard intent and escapes are transported explicitly. Native tests
and Svelte/desktop compilation are pending the new Mac run.

Close the app and update files from the ZIP, then run:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_shell.py --output m3-shell-out-database-pattern
```

Upload `m3-shell-out-database-pattern/m3-shell-report.json`. Use a fresh output
name for retries. After compilation passes, launch with `npm run tauri dev` from
`m3/desktop` and browse `prefix-test.db` with page size 2:

1. Pattern `app*`, Case-sensitive: three rows across two pages (IDs 1/2, then 4).
2. Pattern `aPp*`, Unicode lowercase: four rows (IDs 1/2, then 3/4).
3. Pattern `a?b`, Case-sensitive: two rows, `a%b` and `a_b`.
4. Pattern `a%b`: one literal-percent row.
5. Exact `a?b`: zero rows; wildcard syntax is inactive in Exact mode.

Confirm previews and the snapshot-open notice remain correct while switching
modes. Native tests cover literal question-mark/star escapes even though the
existing GUI fixture does not contain those keys.
