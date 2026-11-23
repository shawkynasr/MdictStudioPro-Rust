# First community feedback: next-preview changes

Prepared on 2026-11-23. These are source changes awaiting CI compilation and native GUI checks; this document does not qualify a new installer or modify the preview.1 tag.

## Readability and first use

The UI now uses a 15 px base with system sans-serif and explicit Chinese/Arabic fallbacks, larger labels and explanatory text, and darker secondary text. Settings offers Standard / Large / Extra large (15 / 17 / 19 px base), saved with the existing language/theme preference. Text uses relative units so the setting scales controls and labels. Dictionary iframe contents retain their own typography.

JavaScript contrast checks cover primary and secondary text against all four light/dark UI surfaces. Native font rendering, wrapping at each size, and preference persistence still need GUI confirmation.

The README now includes real Windows English/Chinese screenshots and a [Chinese quick-start guide](QUICK-START.zh-CN.md). Captions identify the screenshots as first-preview captures before the readability update.

## Rebuild output collisions

An existing output still produces `destination_exists`: it is never overwritten. Build now suggests `<source>-rebuilt.mdx` (or `.mdd`) instead of a generic/original dictionary name, clears an incompatible destination when changing between publication forms, and clears the destination when choosing a new build source. Opening Jobs/Settings does not discard the current form destination. Displayed errors omit the spurious `Line 0:` for this filesystem error; original diagnostics remain unchanged. Build failures give a concrete new-name example.

## A larger, explicit export profile

The user-supplied MDX is declared unencrypted v2 / UTF-8. An independent stdlib wire scan verified all block checksums and decoded text. It found:

| Measure | Observed |
|---|---:|
| Compressed source bytes | 17,375,077 |
| Entries | 64,364 |
| UTF-8 headword bytes | 701,816 |
| UTF-8 definition bytes | 149,605,048 |
| Total decoded key/text bytes | 150,306,864 (143.3 MiB) |
| Largest definition | 151,491 bytes |
| First entry exceeding 96 MiB | 41,928 |

This explains the existing cap error. It is not evidence that an MDX version or encryption mode was rejected.

The default Large export stays at 250,000 entries / 96 MiB decoded text. The new opt-in Extended export profile allows 250,000 entries / 256 MiB decoded text and 512 MiB output. Per-entry (1 MiB), headword, header, engine block and reader limits remain unchanged. The profile appears directly in the Extract form. The receipt names it `studio-m3-stream-export-256-v1`.

Both routes use the existing snapshot, sequential reader, disk staging, strict reparse/digest verification, cancellation and no-clobber publication. Extended export keeps the existing exclusive 384 MiB logical memory / 3 GiB temporary reservation. No larger in-memory record collection or locator is introduced; these reservation figures are not newly measured process peaks or OS-enforced limits.

Structured limit failures now carry the observed value and selected ceiling. The UI recommends Extended only for decoded-text limits at or below 96 MiB on export operations, not for SQLite, build, or already-extended operations.

**Extended is export-only.** It does not expand SQLite or MDX build caps and does not promise that this 143.3 MiB dictionary can be rebuilt in the current packing profiles. MDX v3 and password-protected dictionaries remain outside this change.

## Validation and next native check

CI now runs the export crate's native tests on all four targets, including a synthetic 145 MiB TXT/JSONL export, default-cap rejection without publication, lowered/raised limits, cancellation and existing-destination preservation. It also tests default/explicit/invalid profile deserialization in the runtime.

Local JavaScript and Python checks are recorded separately in [the source review](evidence/preview-feedback-2026-11-23/review.json). Rust, Svelte and native GUI execution are pending; no dependency or lockfile changes are required.

After CI succeeds, install a new preview build and check:

1. Settings → Large / Extra large, Chinese and English labels, light/dark contrast, and restart persistence.
2. Rebuild a small TXT into a new `-rebuilt.mdx`; deliberately selecting an existing output must preserve its bytes.
3. Export the supplied dictionary with Extended to a fresh TXT path. Its source SHA-256 must be `a95b898276c4f3f90598f38ffa2ed7eb177904700e40bd7bd16316069b37761c`. Expected result: 64,364 records, 150,693,048 TXT bytes, SHA-256 `34c11c552159aaad978f943dec3f104f173a17a9c6a6f65a77ac9ce2e18f6f6e`. The independent expected framed-record digest is `0ed77eb39780fb6319e0a526777c4b3a42dd14e31fe74edc57035eeb7b1123e9`.

The supplied dictionary and its extracted contents are not included in the source ZIP or CI fixtures.

## CI seed-lock correction (2026-11-23)

The first CI attempt stopped before `large_export::tests` because `--locked` rejected the standalone runtime seed lock. The direct test commands had omitted the existing local shell workflow’s seed-normalization step. Both new standalone CI test steps now use `scripts/ci_test_exports.py`: verify accepted registry versions/checksums, resolve the isolated M3 lock’s local edges offline, verify pins again, then execute `cargo test --offline --locked`. Metadata failure or registry drift stops the run before testing. No committed lockfile or dependency version was changed by this correction. Native success remains pending a new CI run.

### Fresh-runner cache follow-up

The next CI attempt found `crc32fast v1.5.3` missing from the standalone export test cache. Building the desktop graph does not guarantee all standalone test/development archives are cached. The wrapper now checks the seed pins, runs `cargo fetch` for the selected standalone manifest and target, checks pins again, performs offline metadata normalization, checks pins again, and only then runs offline locked tests. Fetch may normalize local seed edges but does not compile code; unapproved registry versions/checksums stop the run before compilation. Both export and runtime suites use this sequence. Six wrapper regression checks pass locally; native CI success remains pending.
