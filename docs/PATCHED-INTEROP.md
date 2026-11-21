# Passed synthetic gate: Python binary interoperability for both patched profiles

The revision-2 user run passed all fourteen checks. Its original report is under
`docs/evidence/interop-v2-user-run`. Commands below reproduce that subset.
Next: `docs/METADATA-CODECS.md`.

The new UTF-16 label candidate can be tested with
`--writer-revision 3 --output interop-out-v3` after preparing it with
`python3 scripts/prepare_sort_experiment.py --revision 3 --reuse`.
This selects a new vendor tree through Cargo's patch-path override; the default
manifest still points at the passing v2 tree. The candidate is not yet proven.

Revision 2: the first run exposed ten header-parse failures and two MDX source
newline expectation errors; both reverse MDD checks passed. See
`docs/INTEROP-FINDINGS.md`. The v2 corrections have not been run in Rust here.

The uploaded sorting report and experiment lockfile are retained unchanged in
`docs/evidence/legacy-sort-user-run`. The lockfile uses a local mdictlib path,
so it records dependency resolution but not the identity of local source bytes.
The new interop harness records source hashes along with its results.

## What is already established

All four C-locale physical-order comparisons pass. The report confirms exact
lookups over nine MDX / twelve MDD key blocks, stable duplicates, unchanged
default order and unchanged reader/header behavior. This is a synthetic gate,
not a universal reader compatibility result.

## Run on the Mac

From an updated package root, using a Python version with tomllib (3.11+):

```sh
python3 scripts/prepare_sort_experiment.py
python3 -m venv .venv
.venv/bin/python -m pip install mdict-utils==1.3.14
.venv/bin/python scripts/patched_interop.py --output interop-out-v2
```

Run the first command even if the old v1 vendor directory exists: it creates
the NEW `mdictlib-0.2.8-studio-sort-v2` directory and preserves v1. If v2 is
already prepared, skip it. It refuses to overwrite either prepared output.
The output directory must not exist; use another name for reruns. This tests
synthetic files only and never reads production dictionaries.

## Checks

- Original Rust default MDX/MDD -> independent Python low-level reader.
- Both patched Rust MDX/MDD profiles -> Python, with exact physical row/payload
  comparison against the existing oracle (including backslash keys).
- Duplicate fixture MDX/MDD files -> Python, preserving payload multiplicity.
- Original Python app custom writer, both profiles and both formats -> Rust
  reader, preserving all expected bodies and binary resources.

The original Python writer class is extracted from its AST with the REAL
mdict-utils dependencies. PyQt and the GUI module are not imported. Bodies are
compared exactly, without stripping whitespace, Unicode normalization, silent
record merging, or removal of NULs by our harness. For legacy TXT import, the
expected body explicitly retains the delimiter-preceding line ending; raw
builder fixtures do not acquire one. The independent reader may
have its own documented decoding behavior; failures are evidence to investigate.

There are fourteen cross-engine checks. The root CLI gains a `dump-json` command
for physical entry/resource inspection; this new command has not been compiled
in this environment. The library and existing proof semantics are unchanged.

The harness writes `interop-report.json` with passed/failed/blocked status and
retains generated dictionaries plus `interop.log`. Nonzero exit indicates a
failed check or missing prerequisites. Forward and reverse results stay separate.
A preparation failure is not a format-compatibility failure.

Send the report and, on failure, interop.log. If pip cannot install dependencies,
send that installation error. No native reader apps, legacy codecs or large
dictionary checks are claimed by this step.
