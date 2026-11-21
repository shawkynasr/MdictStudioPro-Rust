# Safari77 fork review — uploaded snapshots

This is a source inspection. Neither fork nor the new adapter was compiled or
executed in this workspace. Rust remains unavailable here. No comparison result
is reported as a runtime pass.

Update: the user subsequently supplied `docs/evidence/safari-user-run/safari-report.json`.
It confirms successful physical reading of all 11 v2 entries and four resources,
but three exact lookup misses, a duplicated Big5 trailing byte, blank-line
splitting, and a full build blocked by the default `root` locale. Header output
confirms version 3.0. Those are user-run results, not a local rerun.

The text loader returned an EMPTY payload. The earlier delimiter-span concern
was incomplete: `load_data` creates a Vec with capacity but zero length and
passes that empty slice to read_exact. Capacity does not initialize length.
Consequently delimiter_removed=true in the observation report is NOT a pass
for content preservation. No fork repair has been applied.

## Provenance

| Archive | Commit | SHA-256 |
|---|---|---|
| mdx-main.zip | 085d2a77fed2fc43a9a8e58c91bdb3be8aac4880 | a130ec982578bb673f5636469c62f0a2e2c914ff5024c75c72c1a0be25c651f9 |
| mdx_util-main.zip | 20493d99a5ce508ff400a782fa948e2c7b69115c | 52f8b5f06139fae8245700d4a800887d1c6136684af0bf57707affab24ece59f |

Unmodified snapshots are under `reference/safari-mdx` and
`reference/safari-mdx-util`. Both retain their original AGPL-3.0 licenses.
The manifests identify versions 0.5.4 and 0.6.1 respectively. Claims of fork
improvements relative to upstream cannot be verified without upstream snapshots.

## Main conclusion

The uploaded mdx library has a real library API and MDX/MDD v1/v2/v3 reader
paths. However, its implemented builder emits a version-3 ZDB container, not
the classic version-2 wire format required by the current packing baseline.
The filename extension does not select another writer.

Evidence in `reference/safari-mdx/src/builder/zdb_builder.rs`:

- `ZdbHeader` serializes with the ZDB root name.
- `ZdbHeader::from_config` sets both engine-version fields to 3.0.
- `build_db_header` writes UTF-8 XML plus a terminating NUL, rather than a
  classic MDX/MDD UTF-16LE header.
- The build path writes content and index units with the ZDB unit machinery.
- `BuilderConfig` has no output-version selector.

No alternate classic v2 writer was found in this source tree. The CLI's
`convert-db` and `build-mdd` both call this builder. Other readers may support
ZDB v3; no claim about universal incompatibility is made. External readers
still need testing if this output format is desired.

The ZDB header also lacks Title/Description fields and initializes StyleSheet
to empty. Existing metadata preservation would need explicit work; reading
those fields from an input file does not establish that the builder emits them.

## Comparison against the current candidate

| Requirement | Safari77 uploaded code | mdictlib qualification |
|---|---|---|
| Classic v2 packing | No v2 writer found; implemented builder is ZDB v3 | Synthetic v2 subset passed on user's Mac |
| Two legacy sort profiles | No direct modes; builder uses ICU locale collation | Default differs; optional isolated patch prepared, untested |
| Reader access by physical entry | Public get_index/get_data APIs | Ordinal API and duplicate fixture passed |
| Exact-match lookup | Binary-search path with best-match scan | Exact-first duplicate fixture passed |
| SQLite | No SQLite implementation/dependency found | App-level rusqlite module still needed |
| Encoding | Public helpers; strictness and multibyte issues need tests | UTF-8 subset only tested here |
| Memory | Retains entry index, loads bodies block by block in builder | Builder materializes data; large-file proof outstanding |
| Async integration | Rc/RefCell readers; keep on owning worker thread | Still needs app job integration |
| Dependency footprint | ICU, Tantivy, several native compression dependencies | Smaller tested probe resolution |
| License | AGPL-3.0 | MIT engine; application AGPL |

## Specific concerns, grounded in code

1. **Source parsing:** `MDictSourceLoader::is_text_end` treats a blank line as
   end-of-record. `content_length` is measured after reading the end marker;
   `load_data` returns that complete span. The delimiter can therefore enter
   the stored payload, and an internal blank line can split an intended entry.
   See `src/builder/mdict_source_loader.rs:20-30,88-97`.
2. **Big5/GBK sort-key loop:** `mb_get_sort_key` advances with `for i in ...`.
   On a recognized two-byte pair it appends both bytes then continues, but the
   next iteration processes the trailing byte again. This is visible at
   `src/utils/sort_key.rs:59-67`. The adapter probes a valid Big5 pair without
   transformations; no runtime result is invented.
3. **Lossy codec helpers:** `encode_string_to_bytes` and
   `decode_bytes_to_string` log conversion errors and return replacement output,
   conflicting with our strict-by-default requirement. See
   `src/storage/reader_helper.rs:84-114`.
4. **JSON config mismatch:** `build_mdd`, compression and encryption fields
   are serde-skipped. Setting them in JSON does not configure those fields.
   `TextFile` in the CLI README is not a `SourceType` variant. Several listed
   variants fall through to an unsupported-format error in `build_with_config`.
5. **Tauri integration:** reader state uses Rc and RefCell. It cannot simply be
   placed into shared Send/Sync application state; an owning worker/actor is
   a reasonable integration strategy. This does not imply the library is unusable.
6. **Build reproducibility:** mdx_util has an unpinned Git dependency on mdx
   and no included Cargo.lock. The mdx snapshot includes its own lockfile.
   Resolve/pin an intentional snapshot before any production integration.
7. **Documentation drift:** the CLI README's Rust 1.70+ requirement conflicts
   with edition 2024 and newer APIs in the source. Build requirements must be
   measured rather than copied from that README.

The default ICU backend is pure Rust ICU4X; system ICU is an alternative
feature. It is incorrect to say system ICU is always required. Other native
dependencies (e.g. compression libraries) still affect build complexity.

## Decision

Do not switch the primary classic-MDX/MDD writer to these snapshots. Keep them
as possible v3/read-side/FTS references and evaluate those needs separately.
The tested mdictlib baseline remains the first v2 writer candidate, not a final
engine selection. Complete sorting, metadata, codecs and independent readers.

## Optional runtime comparison

From the qualification package root, on a Rust-enabled machine:

```sh
cargo run --manifest-path experiments/safari-probe/Cargo.toml -- safari-out
```

The output directory must not exist. This is a separate workspace and generates
its own Cargo.lock; it does not change the uploaded root lockfile. Dependencies
may require additional downloads/toolchains/native build tools. The library
path points at the supplied mdx snapshot, not a moving Git branch. mdx_util is
retained for inspection but is not compiled by this adapter.

The adapter generates the existing v2 fixtures with mdictlib, observes Safari
physical reading and exact queries, writes a header and a tiny v3 dictionary,
and probes the source-loader/multibyte issues above. Failed observations are
recorded in `safari-report.json` instead of being redefined as passes. Exit zero
means a report was produced, NOT that this engine was selected or is compatible.

Send `safari-report.json` and `experiments/safari-probe/Cargo.lock` after running.
If compilation fails, the complete error log is the relevant evidence.
