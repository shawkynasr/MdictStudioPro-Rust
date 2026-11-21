# M2: five MOE Rust converter ports

The five converters passed the bounded synthetic common-cell profile on the
user's Mac on 2026-10-30. M1 remains complete within its scope. M2 is still partial.

The final report records 36 expected command outcomes: 31 successful commands
and five controlled refusals. All ten baseline/extended conversion cases matched
the original plugins under the documented ordering contract, passed staged TXT
publication and repeated identically in a separate Rust process. Seven also
matched raw Python TXT bytes; baseline Revised, extended Revised and extended
Concise differed only in the allowed set-derived ordering. All 27 source hashes,
35 protected source identities and the unchanged XLSX dependency graph matched.
The original final report and exact source snapshots are retained under
`docs/evidence/m2-moe-user-run`. No rerun is needed. Full real MOE corpus,
application/core facade integration and production scale remain unqualified.

## Historical attempts

The first Mac run stopped during compilation: four E0425 diagnostics reported
the same missing `crate::py_space` import in the idiom table formatter. The
import is now added. No conversion comparison ran in that attempt. The original
report/log and all 27 matching source snapshots are retained unchanged under
`docs/evidence/m2-moe-first-user-run`. The runner now embeds the last 64,000
characters of unexpected failed-command output in its report.
Retry this new batch with `--output m2-moe-out-v2`; Rust verification of the fix
remains pending. Dictionary core and dependency locks are unchanged.

The second Mac attempt compiled successfully. The numeric test, all six reader
tests and three MOE tests passed. The remaining baseline test incorrectly
compared set-derived alias-reference ordering exactly (`和平；和諧；和平` versus
`和平；和平；和諧`). The actual compared bodies otherwise match under the existing
documented ordering contract. The Rust fixture comparator now normalizes only
those reference blocks; duplicate counts and every other byte remain checked.
An additional Rust test checks that content, duplicate and target mutations
still fail, and a Python regression checks the actual reported left/right data.
Converter code, core and dependency locks are unchanged by this correction.
The original second report and its 27 source snapshots are retained under
`docs/evidence/m2-moe-second-user-run`.

The final `--output m2-moe-out-v3` attempt subsequently passed as recorded above.

## Reproducing the accepted batch (not requested)

Update the existing folder with the current ZIP. Keep `.venv`, `vendor`, real
inputs and existing output folders. From the project directory:

```sh
.venv/bin/python scripts/m2_moe.py --output m2-moe-out
```

Return `m2-moe-out/m2-moe-report.json`. On failure, return the log or actual/expected
files named in its error. The output directory must be new; use `m2-moe-out-v2`
for a later retry. No package installation, M1 rerun or native-reader check is
requested. Use the already prepared v6 vendor folder and existing environment.

The batch runs the isolated Rust reader/converter tests, then ten full conversion
cases (baseline and extended inputs for each of five plugins). Each case compares
with the actual captured Python plugin, publishes through the qualified core TXT
writer and repeats conversion in a separate process. Four CLI refusals and one
no-overwrite refusal are checked. Source workbooks, original core/oracles, and
both existing dependency locks must remain unchanged.

## Architecture and contracts

`m2/xlsx-reader/src/moe` exposes `convert(Table, Converter, Limits, ReadControl)`.
The `studio-moe` binary reads XLSX and emits a structured conversion result on
stdout; progress and errors use stderr. It creates no destination file. The batch
passes its entries to the existing `studio-cli txt-write ... canonical_v1` API,
which stages, verifies and publishes without overwriting. This is a native Rust
conversion path; Python runs only the independent qualification oracle.

The implementation remains in the isolated XLSX workspace to avoid changing the
qualified dictionary core or merging dependency graphs during converter parity
work. It adds no dependencies or lock changes. A shared application facade and
uniform cross-crate job types remain integration work; this slice does not claim
that the complete GUI or `studio-core` public API is connected to XLSX yet.

| Converter | Preserved behavior |
| --- | --- |
| Revised | First-seen headword groups, positive-first stable pronunciation sorting, raw-pronunciation deduplication, variants, POS blocks, highlighting, GIF/PNG markers and alias redirects |
| Revised WFG | Numeric stable pronunciation sorting, homophone numerals, POS spacers, examples, quotation wrapping, circled numbering and per-row synonym/antonym spans |
| Concise | Positive-first pronunciation sorting, numbered pronunciation/definition blocks, variant labels and full rendered-pronunciation deduplication |
| Idioms | First row of each group, source/annotation numbering, examples, reference links, comparison table, main-entry mark and hidden entry ID |
| Mini | Original row order, pronunciation numerals, radical line, exact multiline CSS head and ruby formatting |

No implicit HTML escaping, headword sorting, NFC, redirect resolution, alias
conflict merging, style cleanup or external asset copying is added. Referenced
CSS/JS/images must be supplied independently, as in the original converter.
The original Mini cleaner computes image substitution and then discards it:
`&sample.png;` therefore stays literal. This quirk is preserved deliberately.

### Explicit ordering change

The old Revised/Concise plugins use Python sets for reference values, and Revised
uses a set for aliases. Their order can vary with process hash seed. Rust uses
first-seen order for those values and aliases. Duplicate aliases within a group
are removed; the same alias in different groups remains duplicated. Alias
records stay immediately after their originating main entry.

The comparator ignores only order within these set-derived reference fields and
the aliases following each main entry. Content, duplicates, alias targets,
headword group order, pronunciation order and all remaining HTML must match.
The report records whether raw Python TXT bytes also matched. This is documented
semantic parity with a deliberate stable-order improvement, not a claim that
every original process emits identical byte order.

### Supported envelope

The qualified `openpyxl-values-v1` common-cell input profile is required; date and
duration cells remain unsupported. Defaults retain the bounded qualification
envelope: 10,000 input rows, 16 MiB normalized input, 1,000 output records,
4 KiB keys, 1 MiB rendered bodies and 8 MiB combined key/body bytes. XLSX reader
limits apply separately. Counts and byte arithmetic are checked.

This first converter profile accepts ASCII numeric syntax and ASCII filenames
inside image markers. Non-ASCII numeric sorting/number-marker syntax and
non-ASCII image-marker filenames are refused explicitly. Generic legacy GIF
markers additionally require ASCII adjacent characters to avoid depending on a
compiler-specific Unicode word-boundary table. Numeric runs and sorting fields
are limited to 4,096 bytes. Expanding this Unicode syntax profile needs a pinned
Python-compatible character-property table and new qualification; ordinary
Chinese/Arabic text remains supported outside those syntax restrictions.

Empty/all-invalid headword groups return `malformed_source`. Unrepresentable TXT
keys/bodies return `unrepresentable_source`. Budget and cancellation errors
return no partial conversion result. Progress checks occur during row grouping
and between rendered groups; cancellation cannot interrupt one formatting
operation. Intermediate rendering precedes the rendered-output budget check.
These limits do not establish hard RSS, streaming, real-corpus throughput,
production decompression limits or hostile multi-process publication guarantees.

The new batch does not rebuild MDX/MDD or qualify Tauri preview execution. HTML
remains dictionary content and requires isolation when preview integration is
implemented.

## Evidence status

Five new Python contract tests pass in the authoring environment. They exercise
the actual original plugins, bundled baseline expectations, extended branch
coverage and comparator mutations. Existing evidence stays bound to its archived
qualified sources. Rust tests and ten end-to-end cases passed on the user's Mac;
this authoring environment has no Rust toolchain. The accepted command report
does not include the final successful Rust test log, so no new per-test count is
inferred from it. Qualification applies only to the bounded profile above.
