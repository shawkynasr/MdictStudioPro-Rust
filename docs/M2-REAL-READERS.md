# First real-input reader/index/session gate

Accepted first selected real-reader gate 2026-11-06. Ten locked native build/index
command receipts and all four selected cases passed: 296,110 MDX entries,
17 resources, 36 raw-exact pages and 346 controller exchanges. Complete scan
comparisons and MDD extraction passed the source-bound Mac harness. Final
reservations, handles and reader reply retention were zero. Maximum observed RSS
was 12,664,832 bytes (12.08 MiB rounded).

Report and four exact source snapshots: `docs/evidence/m2-real-readers-user-run`.
Review cross-checked source SHA identities, counts and decoded extents against
retained M1 independent audit evidence and recomputed all 17 resource hashes and
their cryptographic frame. Private dictionaries/caches/outputs and successful
native stdout were not attached; full MDX FNV/body comparison and cleanup are
represented by the exact-source-bound harness rather than a second local reread.

No qualified Rust source, dependency lock or limit changed. No rerun is needed.
The command below is retained for reproduction only; choose a new output folder
for a requested rerun.

Keep `.venv`, `vendor`, private corpora and old outputs. The accepted run used:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m2_real_readers.py --inputs real-corpus-inputs --output m2-real-readers-out
```

For a requested reproduction, return its `m2-real-readers-report.json`, including on failure.
Do not attach dictionary files, extracted resources or index caches. The output
directory must be new and its name must start with `m2-real-readers-out`, so
private generated files remain excluded from distributable packages.

## Selected corpus

The default reuses the four named files in the existing M1 corpus manifest,
resolved inside the explicitly selected `--inputs` directory:

| Case | File |
| --- | --- |
| CC-CEDICT MDX | `CC-CEDICT 092026.mdx` |
| CC-CEDICT resources | `CC-CEDICT 092026.mdd` |
| English/Arabic MDX | `almaanyEnAr-ArEn.mdx` |
| Chinese idioms MDX | `新华成语词典（第2版）.mdx` |

The files are not bundled. A missing input stops with a selection list in the
report before any Rust build or dictionary operation. Use the appropriate input
directory if the folder has moved. The batch does not scan other directories.
Current file SHA-256 identities and counts are measured, not assumed from M1.

For different selected files, `--manifest PATH.json` accepts this bounded shape:

```json
{"cases":[{"id":"selected-mdx","path":"dictionary.mdx","lookup_keys":["word"]}]}
```

Select 1..16 MDX/MDD cases with distinct simple IDs and at most eight bounded
lookup keys each. Relative paths are based on `--inputs`; all resolved sources
must remain inside that selected directory. The selection manifest is limited
to 256 KiB. The default adds the first physical key and a missing-key probe.

## Independent comparison

The new Python oracle decodes unencrypted declared v2 UTF-8/UTF-16 MDX and typed
MDD keys using stdlib plain/zlib blocks. It validates header and key-summary
ADLER32, compressed-block checksums, counts, key boundaries, monotone offsets,
record framing, strict decoding and EOF. SQLite key offsets and a temporary disk
payload spool avoid owning the complete dictionary body collection. Selected
query records alone are retained in a disk database for later page comparisons.

The first oracle profile has 500,000 records, 512 MiB selected-file size, 64 KiB
header, 16 MiB key metadata, 8 MiB decoded blocks, 8,192 key/record blocks, 2 MiB
encoded record spans and 2 GiB decoded spool/scan ceilings. These are a bounded
subset of formats, not a new universal MDX decoder. LZO, encryption and other
versions require another declared oracle path. They are not silently skipped.
MDD extraction additionally requires noncolliding safe paths and its existing
100,000-resource / other extraction caps. The known M1 MDD has 17 resources.

The complete independently decoded ordinal/key/payload stream produces the same
framed FNV-64 count/byte summary used by the qualified bounded Rust reader. The
batch compares that entire summary to a separate Rust verified cache attach with
no materialized query results. It also binds each source with whole-file SHA-256.
FNV is a stream consistency checksum, not a cryptographic equality proof by
itself. A SHA-256 record frame is recorded independently; MDD extraction's native
cryptographic receipt is checked against that frame as well.

Raw exact lookup is explicit for this first real-input gate. Some existing files
omit StripKey or case flags, so HeaderAsciiV1 cannot be assumed. No missing flags
are invented and no native-reader normalization is inferred. Page checks compare
every returned text/binary byte, physical ordinal, duplicate count, offset and
next offset against the independent query database. They include ordinary,
duplicate-offset and out-of-range/count-only pages. Very large diagnostic replies
are changed to count-only requests before submission; complete body traversal
is still covered by the independent/native scan comparison.

## Runtime paths and output handling

Two locked offline builds use the already qualified converter runtime and index
CLI. Accepted synthetic Rust tests are not rerun routinely because their source
identities are checked unchanged. Index construction and a verified full scan
run serially in separate measured CLI processes before a reader session opens.
This does **not** add index-build admission to the shared runtime.

For each file, the runtime opens a managed persistent raw-exact reader with the
verified cache, serves the selected pages and closes/releases it through the
accepted cleanup barrier. The MDD case also extracts through the shared serial
publication queue while that reader stays open. All extracted paths, sizes and
file hashes must match the oracle. No original input is rebuilt, repaired,
renamed, overwritten or extracted beside its source.

Generated caches and extracted files stay under the new local output folder.
Native and Python snapshots/spools have separate private scratch directories;
both must be empty after normal completion. Original input/cache hashes and final
shared reservations/reader retention are checked. Page definitions are compared
in memory and replaced with ordinal/key/length/SHA-256 fields before transcript
storage, including before a payload mismatch is raised. Successful reports do
not embed dictionary definitions or binary resource contents.

Native index build, index verification and runtime RSS are recorded independently
with `/usr/bin/time`, excluding Python oracle memory and compilation. The existing
384 MiB provisional observation threshold remains; it is not OS enforcement or
qualification of every candidate ceiling. Native commands/jobs have finite
timeouts; an index or reader that exceeds its envelope fails with evidence.

All 210 prior qualified source identities and the current 66-package lock are
checked unchanged. New tests check source selection/containment, complete wire
frames/pages in both encodings and binary empty tails, corruption rejection,
an oracle scan above 100,000 records and report payload redaction.

## Remaining real-input work

This is the first real dictionary reader/index/session/extraction gate. It does
not qualify real CC-CEDICT source conversion, actual MOE workbooks, fresh packing
of these full dictionaries, native rendering, index-build shared admission or
final M2 readiness. In particular, a real MDX above the owned writer's 100,000-row
or 32 MiB decoded cap is not repacked by quietly raising that cap. Real converter
inputs need their own explicit selections and original-Python comparison batch.
