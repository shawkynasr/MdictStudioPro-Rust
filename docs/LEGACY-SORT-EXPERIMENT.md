# Optional mdictlib sort experiment — synthetic subset passed on user's machine

That result applies to revision 1. Revision 2 additionally fixes header framing
after independent Python-reader failures. V2 has local Python regression tests
but no Rust/runtime evidence yet. Its vendor directory is versioned separately.

The original Mac report applies to the unmodified probe. The user subsequently
supplied a separate sorting report and experiment Cargo.lock, retained under
`docs/evidence/legacy-sort-user-run`. All four C-locale order comparisons and
the recorded duplicate/multiblock/lookup invariants passed. No local Rust rerun
has occurred, and source bytes for the vendored patch were not uploaded.

## Source findings

The published writer source shows a private fixed comparator used before
record offsets and summaries are generated. WriteOptions has no sort selector.
The builder reserves KeyCaseSensitive/StripKey and writes both as No. Lookup
documentation specifies raw-exact before header-normalized fallback.

Inspected pages identify current release as 0.2.8:

- https://docs.rs/mdictlib/latest/src/mdictlib/write/mod.rs.html
- https://docs.rs/mdictlib/latest/src/mdictlib/lib.rs.html
- https://docs.rs/mdictlib/latest/mdictlib/struct.MdxFile.html

The private collation source could not be retrieved. The patch changes only
the explicit sort call and leaves the default branch pointing at upstream.

## Experiment design and commands

The preparation script verifies the cached published .crate archive against
the uploaded root lockfile's SHA-256, copies it to a new vendor directory,
checks exact patch anchors, and preserves its original MIT LICENSE. It emits
a diff and hashes, and never edits Cargo's cache or the root lockfile.

The optional profiles use Unicode/ASCII lowercase respectively, preserve the
legacy backslash quirk, and use stable sorting. Scope is C locale only;
complete Python/Rust Unicode lowercase equivalence is not established.
Header flags and reader code remain unchanged. V2 adds the terminating UTF-16LE
zero pair to XML header payloads before length/checksum calculation.

```sh
python scripts/prepare_sort_experiment.py
cargo test --locked --manifest-path experiments/legacy-sort/Cargo.toml
cargo run --locked --manifest-path experiments/legacy-sort/Cargo.toml -- sort-out-next
```

Supply --crate PATH if the exact mdictlib-0.2.8.crate is outside Cargo's usual
cache. Preparation refuses to overwrite existing vendor output. The lockfile
from the successful user run is now included; use --locked.

Tests compare four physical orders with the Python oracles across small blocks,
duplicate payloads, exact queries, default order, and header/fallback behavior.
Send sort-report.json and the experiment Cargo.lock, or any compiler errors.
This prototype allocates comparison strings; it is not performance optimized.
No local Rust rerun or external-reader compatibility pass is claimed here.
