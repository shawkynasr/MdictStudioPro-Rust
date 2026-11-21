# Focused native Unicode compatibility

**Result, 2026-10-29:** user confirmed required stored markers and all eight
duplicate payloads in both readers for all four files, including after restart,
with no crashes. Separate observations and the unchanged staging report/blank
CSV are retained in `docs/evidence/native-unicode-user-run`. The six diagnostic
behavior queries have no supplied per-query transcript. No repeat native test is
requested. The instructions below describe the original reproducible procedure.

The user's integrated report passed four MDX cases, each with 166 records and
192 adapter queries, separate-process reopen, exact physical/lookup order and
three policy refusals. Its evidence and source snapshots are retained under
docs/evidence/integrated-casing-user-run. That proves the bounded adapter path;
it does not make external readers honor StudioCasingPolicy.

## Prepare without rebuilding

Update in place, keeping the existing integrated-out folder, .venv and vendor:

```sh
.venv/bin/python scripts/native_unicode.py \
  --source integrated-out --output unicode-native-out
```

The command requires the exact received qualified report, verifies source and
dictionary SHA-256 values, and independently reads all existing files through
Python before copying. It never builds dictionaries, runs Cargo or launches an
app. Existing destination directories are refused. Only complete validation
publishes ready; negative-control files are never copied.

Open unicode-native-out/checklist.html. It provides selectable raw query fields,
code points and expected payload markers. The clipboard operation remains manual:
click a field to select it and copy. Visually identical accents or sigma variants
must be copied exactly. This page has no external dependencies.

## Test sequence

Add just ONE numbered ready subfolder to a reader at a time, keeping other test
dictionaries out of its group/scan folder:

1. 01-unicode16-utf8
2. 02-unicode16-utf16
3. 03-unicode17-comparison-utf8
4. 04-unicode17-comparison-utf16

Use MDict for macOS 2.2.6 (build 200) and the user's GoldenDict
26.6.1-7548db1682 (master). Remove the prior test folder from the reader before
adding the next. Only the copied MDX in that folder is needed; there is no MDD,
font installation or source conversion step.

Each file has 13 focused stored-headword checks and six behavior observations.
The extra full-inventory.csv lists all 166 raw key/payload identities for deeper
checking if an issue appears; the focused subset is not a claim that every native
lookup has been individually exercised.

## What to record

For stored-definition checks, the listed PINNED/DUP markers must remain
accessible. Greek ΟΣ has two distinct raw-exact payloads. The duplicate headword
must expose DUP_01 through DUP_08. Native readers may group additional case
variants; that alone is not a missing-record failure. Check fullwidth/BMP versus
supplementary characters and composed versus decomposed accents in particular.

Newly assigned characters may lack a glyph in an older macOS font. A square/tofu
glyph alone does not mean the entry is missing: copy the raw query and look for
its ASCII payload marker. Record rendering limitations separately from content
access or search failures.

For reader-behavior observations, record actual results and which markers are
shown. The studio adapter's output appears only as a reference, NOT as an
external compatibility standard. Other readers may ignore the policy attributes
or use their own contextual/simple casing and case-group rules. In particular,
query οΣ and a꟏Σ can intentionally produce different adapter results by policy.
Distinguish actual dictionary hits from similar-word suggestions.

Restart each reader with the selected file and reopen representative entries.
Record crashes, unavailable stored markers and any restart change. Do not add
the unknown-policy or wrong-policy-hash diagnostic files from integrated-out.

Return unicode-native-out/native-unicode-report.json and your observations. You
can fill checklist.csv's MDict_actual/GoldenDict_actual columns, or describe any
failure by exact numbered folder, query/code points and visible/missing markers.
The preparation report itself stays native_untested: manual results are separate
evidence and must not be relabelled automatically by file copying.

Native test success would qualify this focused export subset, not prove that
all readers implement our policy IDs or finish M1. Production index/import paths,
broader Unicode portability and remaining metadata contracts are still separate.
