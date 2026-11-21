# Explicit checksum verification for validation and rebuild operations

The user's standard stress report passed its bounded batch. It also demonstrated
that the default reader accepts a key-block checksum-only mutation, while the
independent auditor rejects it. That is consistent with the published 0.2.8
default ChecksumPolicy::Skip. Structural parsing/decompression are still active;
Skip must not be described as full wire-integrity validation.

The documented API is OpenOptions::new().with_checksum_policy(ChecksumPolicy::Verify),
passed by reference to MdxFile::open_with_options or MddFile::open_with_options.
See https://docs.rs/crate/mdictlib/latest (0.2.8, Checksum Verification section),
https://docs.rs/mdictlib/latest/mdictlib/enum.ChecksumPolicy.html and
https://docs.rs/mdictlib/latest/mdictlib/enum.Error.html.
The engine dependency remains checksum-pinned at 0.2.8; no upgrade is made.

## New path and policy

The real-rebuild probe now uses Verify for source opens and validates every
emitted output key and payload under Verify before its staged directory can be
published. Output bytes, source metadata preservation and physical order are
unchanged by this policy. No fallback to Skip is allowed on a validation error.

A new checksum-inspect verify command walks every physical key and materializes
every record/resource, forcing lazy key/record checks rather than stopping after
a successful open. It verifies the materialized count against the declared
count and returns structured rejection details, including ChecksumMismatch
context and scan phase. A non-cryptographic FNV-1a diagnostic fingerprint checks
that accepted checksum-only copies decode the same content; earlier corpus
parity gates continue to use SHA-256, not this diagnostic fingerprint.

The checksum-inspect skip command exists only as an explicit diagnostic control.
Historical read/compare and stress probes keep their previous behavior for
reproducibility. This change wires the real-rebuild entrypoint, not every future
app import path. The future studio-core validation/import code must adopt the
same explicit policy; the app implementation and persistent key-index checksum
policy remain separate open items.

## Run one offline batch

Update in place with the ZIP as before, retaining .venv, vendor, your corpus and
previous reports. From the project root run:

```sh
.venv/bin/python scripts/checksum_qualification.py \
  --manifest baseline/real-corpus-manifest.json \
  --output checksum-out
```

Return **checksum-out/checksum-report.json**, and the referenced log for failures.
No native readers are involved. No repeat of the 48 MiB stress generation is
needed. The new seed is only 128 definitions and 16 small resources; all copies
and mutations are confined to checksum-out. Original corpus files are read-only
and hashed before/after. Fonts/CSS are not needed for checksum-only reading.

## Matrix and integration checks

Both valid MDX and MDD controls must pass Verify and Skip with identical complete
content observations. Each has multiple key/record blocks. Eight one-byte
mutations are then made independently per format:

1. UTF-16 XML header checksum.
2. Keyword section header checksum.
3. Keyword index compressed-envelope checksum.
4. First key block checksum.
5. Last key block checksum.
6. First record block checksum.
7. Last record block checksum.
8. Zlib trailer checksum in the last record block.

Every Verify scan must reject. Outer wire failures require the typed
ChecksumMismatch variant; the zlib trailer may be reported as InvalidData by
the decompression path. Record mutations must be reached in the records phase.
Panics, signals, timeouts, unrelated parse errors and incomplete observations
are failures, not successful rejection. The independent auditor must also
reject every checksum copy. Skip behavior is observed, not presumed to ignore
every check; any accepted copy must preserve the valid file's content signature.

Clean MDX and MDD rebuilds must report strict source policy and complete output
verification. Rebuilds from last-record-checksum corruptions must fail cleanly
without publishing a final destination. The selected four real inputs then
undergo complete Verify scans, with original hashes unchanged.

The standard success status is strict_checksum_matrix_and_real_scans_passed_M1_open.
Without --manifest, the smaller success status explicitly says the real corpus
was not run. This qualifies the tested unencrypted v2 paths only: encrypted/v1
matrices, persistent indexes, all future import paths and broader M1 requirements
remain open.

## Received user result

The user's Mac run passed the complete batch, including all 16 strict corruption
rejections and both clean/corrupt rebuild integration checks. Full Verify scans
passed for 296,110 MDX records and 17 MDD resources across the four real inputs;
their before/after SHA-256 hashes are unchanged. All damaged copies were also
rejected by the independent auditor. Skip accepted the tested mutations, which
confirms why explicit Verify remains required for validation.

Evidence is retained under docs/evidence/checksum-user-run, with source snapshots
matched to the hashes in the uploaded report. Rust execution was on the user's
Mac; it remains unavailable in the authoring environment. This closes the tested
checksum gate. The next gate is fresh TXT/XLSX pack parity; M1 stays open.
