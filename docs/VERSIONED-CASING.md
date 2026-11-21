# Explicit Unicode casing policies

The received Unicode report compared all 1,112,064 scalar values. Python's
Unicode16 table changes 1460 single characters; Rust's Unicode17 table changes
1488. All 28 differences were retained, not waived. Its 45 selected contextual
examples agreed, but those words did not include the newly cased characters in
sigma contexts. No dictionary cases were reached in that run.

This batch adds a separate, explicitly named compatibility candidate. It does not
modify the vendor engine, existing legacy comparator code, dictionary reader
normalization or the already qualified literal export profile. Integration into
writer and lookup remains an explicit next gate after policy-data review.

## Run on the same Mac environment

Update in place, retaining .venv, vendor, old reports and dictionaries. No package
installation or pip update is needed:

```sh
.venv/bin/python scripts/casing_policy.py --output casing-out
```

Return BOTH casing-out/casing-policy-report.json and
casing-out/unicode16-casing.json. Include any log named by a failure. The second
file is generated policy data, not a private dictionary. It is needed to review
and freeze the exact data hash without relying on the author's different Python
Unicode version. Existing output folders are refused. No native app or MDX/MDD
generation is involved, and no previous reader/resource/stress test is repeated.
New Rust source is uncompiled in the authoring environment; the driver compiles
and tests it on the user's Mac with the existing dependency graph.

## Candidate data provenance

The generator requires CPython with unicodedata.unidata_version exactly 16.0.0.
It enumerates every scalar, recording non-identity str.lower mappings. It derives
Cased membership from the target's lowercase/uppercase/titlecase predicates.
Case_Ignorable membership is inferred from two Final_Sigma behavior probes:

- AΣ + character ends with final sigma at position 1.
- AΣ + character + A has ordinary sigma at position 1.

Their conjunction distinguishes ignorable characters from both cased and
uncased non-ignorable characters, including characters that are simultaneously
Cased and Case_Ignorable. Property memberships are stored as ordered ranges.
This is an oracle-derived candidate, not a claim that official UCD files were
downloaded or independently certified. Metadata in the report states that source.

Policy data uses the name python-unicode-16-root-lower-v1. Its tables contain
only semantics and version identifiers, so build timestamps and machine paths do
not change its hash. The report records the actual generator environment and the
data SHA-256. A production artifact must pin a reviewed hash; merely accepting
an arbitrary file labelled Unicode16 is insufficient.

## Rust implementation and checks

Rust consumes the Unicode16 mappings AND context-property ranges. Its compatibility
lowercase implementation never uses the compiler's Unicode property tables.
It uses two linear passes over the ORIGINAL input to evaluate Final_Sigma,
skipping Case_Ignorable before testing Cased. It retains one-to-many mappings,
including dotted I. It does not introduce casefold, locale tailoring or NFC/NFKC.

The modern comparison is separately named rust-unicode-17-root-lower-v1 and
requires the compiler to declare Unicode17. A future compiler Unicode version
does not silently change that comparison: the batch refuses it.

The batch requires exact compatibility for every single-scalar lowercase mapping
and checks selected plus deterministic generated context words against Python's
actual whole-string lower operation. Those words include all 28 newly cased
characters around sigma, combining marks, apostrophes and joiners. This catches
the failure of replacing only 28 emitted characters while still evaluating sigma
with newer context-property tables. The modern profile's observed differences
must equal the prior 28 exactly; that difference is intentional only because the
two policies are now explicitly named and separated.

Zero compatibility differences and a stable policy hash produce
versioned_casing_candidate_passed_engine_integration_pending_M1_open.
This is exhaustive for individual scalars and bounded for contextual strings,
not a proof over all possible strings. The generated table must still be reviewed
and frozen, then integrated consistently into sorting and lookup. The official
MdxBuilder historical mapping, native Unicode export qualification and M1
completion remain open.

Algorithm reference: Unicode 16 SpecialCasing.txt, including Final_Sigma and the
requirement that contexts refer to the original string:
https://www.unicode.org/Public/16.0.0/ucd/SpecialCasing.txt
