# M1 engine qualification

## Current decision: candidate only; M1 NOT PASSED

The prototype selects mdictlib=0.2.8 as the first candidate because the uploaded
reference application integrates this exact version. No Safari77 source was
supplied or inspected, and it has not been rejected on technical grounds.

The user successfully compiled and tested the original prototype on a Mac:
five Rust tests passed, and the supplied report records eleven successful
synthetic checks. The exact report and Cargo.lock are retained with hashes in
`docs/evidence/macos-user-run/`. This is user-supplied execution evidence, not a
local rerun. The Rust source is unchanged from the package used for that run.

Rust/Cargo remain unavailable in this workspace; local dependency download
access was blocked. Rust compiler version, macOS version and CPU architecture
were not provided. Windows/Linux and independent reader tests are unrun.

API usage is grounded in the supplied reference application's Cargo.toml,
fixtures.rs, state.rs and export.rs. The user's successful build now confirms
the tested API calls compile against the supplied resolution. The candidate's
declared MSRV still needs an explicit check; the reference README says Rust 1.97+.

## What the probe implements

- Standalone Rust library and CLI, no Tauri or GUI dependency.
- Synthetic UTF-8/zlib MDX packing, physical entry enumeration and title check.
- Duplicate-aware multiset comparison and exact lookup body assertions.
- Arabic, Chinese, supplementary characters, accented case and punctuation.
- Redirect body preservation (not runtime redirect following).
- MDD binary round trip, exact lookup and staged resource extraction.
- UTF-8 source parser with explicit reserved delimiter checks.
- Invalid MDX and truncated MDD rejection.
- Default engine physical sort-order report against both Python C-locale oracles.
- Tests for source grammar, traversal paths, existing output and failed staging.

The `prove` command only writes `report.json` after all its synthetic assertions
succeed. Its status is `synthetic_subset_passed`, never `production_ready`.
Sort equality is reported independently. A mismatch remains a blocker even if
the other synthetic checks pass.

This CLI intentionally materializes entries/resources for small qualification
fixtures. It is not a production streaming or memory-bounded implementation.
It does not promise hostile-input safety, complete checksum verification,
race-free publication, or durable directory commits. The root writer remains
unchanged. The isolated optional sort experiment subsequently passed all four
synthetic C-locale comparisons on the user's machine; it is not promoted to
production. The user's root Cargo.lock is included unchanged;
subsequent commands and CI use --locked to prevent silent dependency changes.

## Commands

From the project root, with a suitable Rust toolchain and registry access:

```sh
cargo test --workspace --locked
cargo run --locked -p studio-engine-probe -- prove baseline/cases.json out-next
cargo run --locked -p studio-engine-probe -- inspect out-next/qualification.mdx
cargo run --locked -p studio-engine-probe -- lookup out-next/qualification.mdx apple
cargo run --locked -p studio-engine-probe -- unpack out-next/qualification.mdd extracted
cargo run --locked -p studio-engine-probe -- pack out-next/qualification.txt repacked
```

Output directory arguments must not exist, and their parent must exist. The
prove command produces small MDX/MDD files, source text, extracted resources,
sort probes, and a JSON report. Their filename and content are synthetic.

Historical upstream-only interoperability check (retained for comparison):

```sh
python -m pip install mdict-utils==1.3.14
python scripts/legacy_interop.py --report out-interop/report.json
```

It attempts Rust→legacy MDX, legacy→Rust MDX, Rust→legacy MDD. Failures in
source grammar, extraction layout or payload preservation fail the check;
they are not normalized away. It has not been run here. It does not test the
custom legacy writer or reverse-direction legacy MDD packing.

The user's later independent run exposed a UTF-16 header terminator mismatch
in upstream output. Use the revision-2 patched workflow in
`docs/PATCHED-INTEROP.md` for the active qualification gate. The historical
script above deliberately still exercises upstream output and may fail.

## Required evidence before M1 can pass

| Check | Current status | Required evidence |
|---|---|---|
| Dependency resolution / compile | Passed on user's Mac | Lockfiles retained; interop report records Rust 1.98.1, Intel Darwin 24.6.0 |
| Synthetic proof suite | Passed on user's Mac | Uploaded report retained; five passing tests reported in chat |
| Legacy Python binary interop | Passed synthetic UTF-8 subset, 14/14 | Revision-2 report retained; real corpus remains |
| Two sorting profiles | Optional patch passes 4 of 4 synthetic C-locale comparisons | Independent Python and reader-app checks remain |
| Description and embedded style | Raw metadata passes Rust and Python; XML stylesheet newline contract differs | Completed v3 report retains ten failures; resolve parser contract explicitly |
| Legacy encodings | All Rust codec checks pass; v3 UTF-16 samples pass both directions | Reverse GB18030 unavailable in legacy writer; real corpus remains |
| MDX/MDD reader versions/compression | Unproven | Independent real v1/v2, zlib/LZO and encryption corpus as applicable |
| Multi-block and large files | Unproven | Boundary fixtures and measured peak memory/time |
| External readers | MDict 2.2.6 build 200 startup crash confirmed by log; GoldenDict result unknown | Exact failing binaries needed; generated fixture imports paused |
| Error/limit policy | Partial small tests only | Corruption corpus and resource-limit behavior |

Self round trips can hide symmetric writer/reader bugs. Independent Python
checks and external reader testing are mandatory. Never mark a reader passed
because the application merely opened a file: query punctuation/case/Unicode
keys, duplicates, aliases, and resource paths too.

The user-run real corpus comparison now passes for three UTF-8 v2 dictionaries
and one MDD: 296110 MDX records, 17 resources, matching metadata and 36 sampled
lookups. See `docs/evidence/real-corpus-user-run`. This read-only result does not
establish writer/export parity or native rendering. Installed native reader
versions are recorded in `baseline/native-readers.json`; visual observations
remain NOT_RUN.
