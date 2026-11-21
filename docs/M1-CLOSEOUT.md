# M1 closeout: qualify the engine, then build the application

Updated 2026-10-29. **M1 is complete for the scoped engine qualification.**
The final Mac report passed all eight gates and was reviewed; see
ENGINE-DECISION.md for the selected engine, scope and implementation conditions.
The report itself remains unchanged with its original decision-pending fields.
The last-gate instructions below are retained for reproduction, not a new run.
The native Unicode gate is now passed by user report: required stored markers
and all eight duplicate payloads were accessible in both readers for all four
files, including after restart, with no crashes. The focused subset is 13 raw
queries per file, not an exhaustive native check of all 166 records. The six
additional reader-behavior queries have no supplied per-query observations.

## Fixed milestone boundary

M1 decides whether the pinned mdictlib 0.2.8 candidate, maintained writer patches
and Studio adapter are a viable basis for the next implementation milestone.
It does not deliver the production desktop application or prove every format
variant. Historical failures remain in the evidence; later successful scoped
tests do not rewrite them. M0's GUI runtime capture is still partial.

| Area | Qualified behavior | Boundary |
| --- | --- | --- |
| Fresh export | UTF-8 and UTF-16LE v2 MDX, synthetic MDD and fresh-source parity | Six converters still execute original Python; Rust XLSX is later work |
| Lookup policy | Explicit `unicode16-literal-v1`, raw-exact first then whole-string lowercase fallback, stable duplicate order | Unicode17 is a comparison profile; library locator is not an interchangeable fallback |
| Header policy | Canonical literal `StripKey=No`, explicit HTML fields in qualified adapter | Legacy C-locale export profiles remain separate; no claim of exact official MDXBuilder sorting |
| Casing | Frozen Unicode16 data; all scalar mappings and 2,017 contexts compared to Python16 | No locale casing, casefold, accent folding or NFC conversion implied |
| Independent readers | User-reported native plain, punctuation, multilingual, corrected stylesheet, resource, real rebuild and focused Unicode success | Only tested macOS reader versions; not universal reader behavior |
| Real corpus | 296,110 records and 17 resources checked; rebuild preserves source headers/order | Three unencrypted UTF-8 v2 MDX files with empty embedded stylesheet |
| Checksums | Explicit Verify plus full materialization catches tested corruptions | Historical default reader paths do not enforce this automatically |
| Size/failure behavior | Bounded stress and interrupted-write recovery passed | Not a production memory guarantee or multi-gigabyte qualification |

## Resource and error review completed

Review targets: `experiments/real-rebuild/src/integrated.rs`, `src/strict.rs`
and `crates/studio-engine-probe/src/lib.rs`. These findings describe the current
code; they are not claims of fixes or new runtime tests.

| Control | Present implementation | Production implication |
| --- | --- | --- |
| Specification | 2 MiB check before read; at most 1,000 entries and 8 MiB decoded input | Qualification cap only; JSON is materialized and has no concurrent-change protection |
| Dictionary/index | 16 MiB file check, 1,000 rows, 8 MiB accumulated decoded key/body bytes | Entry decompression happens before accumulated limit check; compressed expansion and allocation are not hard-capped by these checks |
| Index memory | Exact and normalized BTreeMap indexes with ordinal vectors; owned rows | Cloned keys, normalized expansions and output JSON add memory beyond the decoded counter; do not extrapolate to corpus-scale indexes |
| Queries | 1,024 queries under specification-size cap | Results and built-in comparison payloads are materialized; this is a diagnostic batch interface |
| Integrity | Verify option; complete strict scan before staged publication | Checksums detect corruption, not authenticity or resource exhaustion; use the wrapper on every production import path |
| Policy errors | Unknown/unavailable policy, mismatching persisted tag and Unicode16 identity refused | Preserve explicit failure; never silently substitute host casing or built-in locate |
| Publication | Temporary sibling directory, cleanup on ordinary errors, destination checks | Check then rename has a race; production needs atomic no-replace publication and an explicit durability/cancellation contract |
| Extraction | Traversal, UNC, drive paths and ambiguous segments refused; new staging directory | Need target-filesystem collision and link handling before general production extraction |

These are handoff requirements for production work, not reasons to keep adding
new format experiments to M1. Current small adapter limits must stay in place
until replaced with a measured index design. A production preview must not load
arbitrary dictionaries through this probe as if it were a general reader.

## Deferred explicitly

- Encrypted/protected dictionaries, MDX v3, unqualified LZO and legacy-encoding
  combinations, platform/locale variants and exact official MDXBuilder mapping.
- General metadata serialization: corrected numeric stylesheet fixture with its
  final LF passed native testing; arbitrary XML multiline stylesheet semantics
  remain unresolved (the historical ten failures stay visible).
- Production index/storage, hard decompression limits, atomic publication,
  complete import routing, cancellation and redirect resolution/cycle handling.
- Rust converters and spreadsheet normalization, Tauri GUI, Chinese/English/
  Arabic localization and RTL, preview isolation and plugin IPC.

This is a milestone boundary, not removal of planned application features.

## Last gate: one consolidated regression

Update the project in place and run:

```sh
cd "$HOME/Downloads/mdict-studio-m0-m1"
.venv/bin/python scripts/m1_closeout.py --output m1-final-out
```

The runner checks retained evidence and current integrated source identity,
verifies the existing v2/v6 vendor trees against the checksum-pinned archive,
runs the local Python suites and the three Rust test workspaces with `--locked`.
It does not regenerate corpus, casing data, stress dictionaries or native kits.
Rust unit tests create only their own temporary fixtures. Existing output folders
are left alone; a new output directory is required. No pip update is needed.

Return `m1-final-out/m1-closeout-report.json`; on failure also return the named
log. Success is `regression_passed_engine_decision_pending`, not automatic M1
completion. After review, record the engine decision for the scoped next milestone
and close M1. No repeat native-reader test is requested unless a relevant change
or failure justifies it.

### First final regression: test harness portability corrections

The first Mac run passed evidence, both vendor checks and baseline, then stopped
at Python contracts before reaching Rust tests. Its unchanged report and log are
retained under `docs/evidence/closeout-first-user-run`. Four subtest failures came
from comparing macOS `/var` temporary paths against canonical `/private/var`
paths. One error came from a mocked subprocess intercepting Python 3.14 platform
detection. Test fixtures now use canonical temporary roots and the isolated CLI
test supplies its own platform value. Dictionary-engine and adapter sources,
expected payloads and qualification rules are unchanged.

After updating in place, rerun the short consolidated gate with a new output:

```sh
.venv/bin/python scripts/m1_closeout.py --output m1-final-out-v2
```

This retains the first failure and runs the corrected Python suite followed by
the previously unreached Rust tests. No dictionaries or casing data are rebuilt
outside the Rust tests' temporary fixtures. Return the new report and any named
failure log. This describes the earlier pending state. The final report has now
passed and the scoped decision is recorded in ENGINE-DECISION.md; no rerun is due.
