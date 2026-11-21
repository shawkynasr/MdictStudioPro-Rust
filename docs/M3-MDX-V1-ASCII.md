# Narrow MDX v1.2 ASCII export compatibility

Status: accepted scoped native Mac and development-app JSONL/SQLite workflow. This is an ASCII compatibility profile, not general v1 or Latin-1 support.

## Behavior and boundary

Declared `GeneratedByEngineVersion=1.2` and `RequiredEngineVersion=1.2`, unencrypted MDX files with `Encoding=ISO8859-1` may now be exported to JSONL or imported into SQLite if every decoded headword and definition is ASCII. Representable content may also be exported as canonical TXT. MDD v1, other v1 declarations, encrypted v1, non-ASCII content and general legacy encoding mappings remain unsupported.

The user's Legal Latin file contains 310 physical records, including two entries with the same headword. Its key and definition bytes are entirely ASCII. Independent LZO decompression, block checksums, index summaries, record geometry and EOF checks pass. All definitions contain CR characters, so this file still requires JSONL or SQLite for exact preservation; strict TXT refusal is expected.

The protected M2 source and pinned engine dependencies remain unchanged. The existing engine understands v1 wire geometry but deliberately refuses the ISO8859-1 label. This additive M3 path verifies the original header, retains the original snapshot/hash/decoded metadata, and creates a temporary decoder view with only the text encoding declaration changed to UTF-8. It preserves the v1.2 version and every byte after the original header. The decoder header is reserialized with a correct checksum; it is never published. UTF-8 is used only to validate the ASCII subset: every decoded key and definition is additionally checked with `is_ascii()` before output publication. Invalid UTF-8 or valid non-ASCII UTF-8 both fail; no Latin-1/Windows-1252 guessing occurs. Original source bytes are never edited.

The v1 source is capped at 128 MiB before making the additional private view; the decoder header is capped at 64 KiB and copied through a fixed 64 KiB buffer with cancellation checkpoints. The ordinary export/SQLite route retains 100,000 records and 32 MiB decoded text. The separately selected larger exporter keeps its existing ceilings. The added temporary copy stays within the existing export admission reservation. Existing checksum verification, row order, duplicate identity, numeric stylesheet metadata, cancellation and no-clobber publication remain in place. SQLite-to-MDX rebuilding, metadata editing and indexed reading of v1 inputs are not enabled by this slice.

## Mac verification

Quit the app and stop its development server before applying the updated source. Keep `法学拉丁语小词典(1).mdx` in Downloads, or supply `--source /absolute/path/file.mdx`. Run from the project root with a fresh output directory:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_v1_ascii.py --output m3-shell-out-v1-ascii
```

The offline gate retains the exact existing dependency locks. It runs the independent fixture/oracle tests, native export/runtime/adapter tests, existing plugin regressions, frontend tests/build and desktop compilation. A source-bound real-file check compares all JSONL/SQLite rows and all original metadata, including literal stylesheet LF triplets, with an independent bounded Python v1/LZO decoder. Native tests cover duplicate keys across key blocks, a definition crossing record blocks, empty text, non-ASCII refusal, corruption, lower limits, cancellation during the extra snapshot and before publication, no-clobber and source preservation. The synthetic MDX fixtures are bundled; the user's dictionary is not.

Send `m3-shell-out-v1-ascii/report.json`. Only after native qualification, use the development app to export JSONL or import into SQLite and confirm 310 records. The previous standalone preview does not contain this feature until rebuilt. Full M3 and production release remain open.

## Acceptance, 2026-11-20

All 15 source-bound Mac gate stages passed: nine export tests, 98 runtime tests, 29 adapter tests, 51 frontend tests, Svelte zero errors/warnings and offline desktop compilation. Every real JSONL/SQLite row and original metadata attribute matched the independent decoder. The source hash was unchanged; all 243 delivered source identities, two previously bound Mac-only files, 324 protected identities and seven resolved locks matched. The user then supplied successful development-app receipts for both exports with 310 records and matching source/metadata. See `docs/evidence/m3-v1-ascii-qualified/`. No further routine v1 qualification run is required.
