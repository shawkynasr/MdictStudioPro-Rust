# MDX v2 keyword-index encrypted export

Status: implementation and independent Python wire checks complete; Rust and GUI qualification pending on the user's Mac. This is an additive M3 compatibility slice, not full encrypted-format support or M3 completion.

## User behavior

The app now admits declared MDX v2 (`GeneratedByEngineVersion` and `RequiredEngineVersion` equal `2` or `2.0`) with exactly `Encrypted="2"` for TXT/JSONL exports and MDX to SQLite. The pinned mdictlib 0.2.8 engine already decodes keyword-index encryption. A dedicated M3 header policy now permits this flag; M2's 324 protected source identities are unchanged. No decryption implementation or dependency upgrade is introduced into application code.

The ordinary dictionary export and database import retain their 100,000-record / 32 MiB decoded profile; the separately selected larger export retains its existing 250,000-record / 96 MiB profile. All routes keep checksum verification, private source snapshots, physical duplicate order, metadata, cancellation before publication and no-clobber output. No source header or file is rewritten. Database metadata records the actual source `Encrypted=2` value. The existing SQLite-to-MDX rebuild policy still refuses encrypted-source metadata; this slice does not silently reclassify or re-encrypt it. Indexed readers, metadata editing, MDD encryption, passcode modes (`1`/`3`), other flag values, legacy encodings, v1 and v3 are not newly enabled.

Canonical TXT still refuses carriage returns, embedded terminator lines and unrepresentable headwords. JSONL and SQLite preserve original definition text exactly. The user's sample `疑难字三考.mdx` has carriage returns in all 1,829 definitions, so strict TXT refusal remains expected; choose JSONL or SQLite. No implicit newline normalization is performed.

## Qualification

Quit the app and stop its development server before applying the ZIP or running the gate. Keep the original MDX in Downloads (or pass `--source /absolute/path/file.mdx`). Use a fresh output directory:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_keyinfo.py --output m3-shell-out-keyinfo
```

The gate checks the existing exact dependency locks without fetching/upgrading packages. It runs independent fixture contracts, export/runtime/adapter tests, existing plugin regression tests, frontend tests/build and offline desktop compilation. Native runtime tests exercise UTF-8 and UTF-16 synthetic encrypted-index fixtures, duplicate keys, empty text, Arabic, source preservation, cancellation/no-clobber and SQLite metadata. Export tests cover corrupted headers/sections/index data, lower caps and explicit policy refusal. The real file is decoded by a separate bounded Python zlib/uncompressed oracle and compared with native JSONL and SQLite including every physical row and all original header attributes. The native optional real-file test writes to the fresh gate output, not to the project fixtures.

Upload `m3-shell-out-keyinfo/report.json`. A passing report is a prerequisite for claiming Rust compatibility. Then launch the development app and export this MDX as JSONL or import it into SQLite, confirming 1,829 records. The older standalone preview binary does not include this change until rebuilt.

Only synthetic fixtures are bundled. User dictionary payloads and exported real rows are excluded from delivery. Local evidence retains hashes/counts and explicitly does not claim native execution.

## References

- Pinned engine scope: https://docs.rs/crate/mdictlib/0.2.8
- Independent format reference: https://github.com/liuyug/mdict-utils/blob/master/mdict_utils/base/readmdict.py
- Frozen local alternate implementation: `reference/safari-mdx/src/storage/key_block_index_unit.rs`

The Python fixture/oracle implements the published RIPEMD-128 transform only for independent test data, with published digest vectors and self-generated fixture byte checks; application work is performed by the existing native engine.

## Native follow-up, 2026-11-20

The source-bound Mac report passed all 14 stages: seven export tests, 96 runtime tests, 29 adapter tests, 51 frontend tests, Svelte (zero errors/warnings), Vite and offline desktop compilation. Independent JSONL and SQLite comparison passed for all 1,829 records and original metadata; the real source hash was unchanged. Strict TXT refusal left no output. All 236 delivered source identities, two exact previously reviewed Mac-only files, 324 protected M2 identities and seven resolved locks match. See `docs/evidence/m3-keyinfo-qualified/review.json`. GUI smoke remains pending. The implementation-stage pending label above is historical.
