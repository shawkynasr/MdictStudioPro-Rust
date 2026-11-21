# One pinned casing policy for adapter sorting and lookup

The user's casing candidate passed all 1,112,064 scalar values and 2,017 selected
context strings against Python16. Its reviewed 27,209-byte data file is retained
as baseline/unicode/unicode16-casing.json, SHA-256:

f69d2e55d6b8c8d5fe33f764cc47b829bccc6d73aaff1791e1216328a1c24071

Evidence and the qualified original sources are retained under
docs/evidence/casing-policy-user-run. The integration embeds those bytes with
include_str, so runtime file changes cannot change an already compiled adapter.
The qualification driver and packaging tests enforce the reviewed hash before
building/shipping. Rust's schema loader validates the embedded table structure;
it does not independently compute SHA-256. Production builds must retain source
integrity checks rather than trusting an editable version label.

## Run

Update in place, retaining .venv, vendor and old results. No pip update or new
dependency is needed:

```sh
.venv/bin/python scripts/integrated_casing.py --output integrated-out
```

Return integrated-out/integrated-casing-report.json and any named failure log.
The Python oracle must still use Unicode16; the modern comparison requires the
compiler's Unicode17. The full scalar sweep and data generation are not repeated.
New Rust integration code is uncompiled in the authoring environment and must
run on the user's Mac. No native reader testing is requested in this batch.

## Implemented boundary

This is a bounded engine-adapter integration, not a modification of mdictlib's
internal comparator or locate implementation. Existing source probes, legacy
profiles and previously accepted export files are unchanged.

Two explicit adapter modes are tested:

- unicode16-literal-v1 uses the embedded contextual Python16 casing data.
- unicode17-literal-comparison-v1 uses Rust17 whole-string lowercase and refuses
  an unknown compiler Unicode version. It remains a comparison mode.

The adapter precomputes each row's normalized key and uses stable sorting. The
wire writer receives PreserveInput, preventing its own comparator from changing
that versioned order. UTF-8 and UTF-16 variants of both modes produce four MDX
cases with canonical StripKey=No, KeyCaseSensitive=No and HTML metadata.

StudioCasingPolicy records the selected mode in each dictionary. Unicode16 files
also contain StudioCasingDataSha256. These are studio-specific attributes, not
part of a universally supported MDict casing standard. Other readers may ignore
them and apply different casing or search ordering.

After opening a file with strict checksums, the adapter verifies the requested
policy agrees with the persisted tag and reviewed data identity. It reconstructs
an exact-key index and a normalized-key index using the SAME whole-string policy
as the writer. Exact raw rows win; normalized fallback runs only when no raw-exact
rows exist. Every duplicate keeps its distinct physical identity and payload.

The adapter deliberately does not delegate versioned fallback to the built-in
locator: that locator uses its own casing rules. Built-in lookup observations
remain in the report as diagnostics so differences are visible. There is no claim
that an unchanged mdictlib locate call now honors StudioCasingPolicy.

The index is bounded to 1,000 rows and 8 MiB decoded data in this qualification
adapter. It materializes rows in memory. It is not yet the final production index,
all import paths, a persistent index, or an integration of MDD casing policies.

## Verification

The fixture combines the previous Unicode edges with all 28 newly cased
characters, their lowercase counterparts, sigma contexts, exact duplicates and
queries designed to distinguish the two profiles. Independent Python code checks
physical order, payloads, duplicate association and grouped lookup results.
Unicode16 normalized keys are also compared directly against Python16 str.lower.
The Unicode17 reference comes from the separate existing casing probe; this
checks integration against the compiler's behavior, not an independent Unicode17
conformance implementation. The earlier exhaustive scalar result remains evidence.

Each dictionary is reopened by a separate Rust process, rebuilding indexes from
the actual MDX. Its complete query matrix must still pass with unchanged bytes.
Strict full scans and independent v2 checksum/block/terminator audits are required.
At least one query must distinguish the profiles and the frozen16 adapter from
the built-in locator, proving no hidden host-policy fallback was used.

Negative controls refuse a mismatched requested policy, an unknown persisted
policy, and a wrong persisted Unicode16 data identity before emitting rows.
Negative-control dictionaries must never enter native reader scan folders.

Success is versioned_adapter_sort_lookup_roundtrip_passed_native_and_production_pending_M1_open.
It qualifies this adapter path only. Native Unicode search compatibility,
production index design, remaining metadata contracts, official MdxBuilder
mapping and M1 completion are still open. Do not import these files into native
readers until the report has been reviewed.
