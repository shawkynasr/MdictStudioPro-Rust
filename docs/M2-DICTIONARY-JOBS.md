# MDX/MDD background operations

The dictionary background jobs passed their bounded batch on the user's Intel
Mac on 2026-10-30. M1 remains complete within its reviewed engine scope. M2 remains
partial. No rerun of this batch or native reader test is requested.

Both command steps passed: Rust workspace tests and the 19-job batch. Twelve
successful jobs covered both encodings crossed with both TXT profiles, thirteen
entries per MDX, exact physical-order TXT export, six MDD resources and extraction,
plus successful pack/export after failures. Independent Python reads and full v2
structural audits passed for packed outputs. All seven expected failures matched
their error codes; existing destinations and input files were preserved.

All twenty source/data hashes, 95 protected source identities and the unchanged
60-package joint graph matched. The original report and exact snapshots are
retained in `docs/evidence/m2-dictionary-jobs-user-run`. The report records 55
delivered events and passed terminal comparisons. The successful Rust log and
event transcript were not separately attached; individual test counts and a
separately reviewed event trace are not inferred. Event counts may differ on
future runs because progress coalesces.

Per the user's instruction, MDX v3 packing/unpacking is deferred for later
roadmap planning. No v3 implementation is included. The `canonical_v1` and
`legacy_body_span_v1` names are TXT profile revisions; both produce MDX format v2.

## Reproducing the accepted batch (not requested)

Update the existing project folder from the ZIP and keep `.venv`, prepared v6
`vendor`, real corpus files and previous outputs. Run the new batch only:

```sh
.venv/bin/python scripts/m2_dictionary_jobs.py --output m2-dictionary-jobs-out
```

Return `m2-dictionary-jobs-out/m2-dictionary-jobs-report.json`. Unexpected command
failures embed their output in the report. A content/status mismatch may also
need `background-actual.json` or named output files. The output directory must
be new. No package update, old batch or native-reader test is requested.

## Operations and API

`studio_application::runner::dictionary::Request` adds four typed operations:

| Operation | Input | Publication |
| --- | --- | --- |
| `pack_mdx` | TXT file, explicit TXT profile, UTF-8/UTF-16 output encoding, title and description | Studio MDX file |
| `export_mdx` | Qualified Studio MDX file and explicit TXT profile | TXT in physical dictionary order |
| `pack_mdd` | JSON resource manifest with file paths | Studio MDD file |
| `extract_mdd` | Qualified Studio MDD file | New extraction directory |

Call `Runner::submit_dictionary(request, limits)` to use the same single worker,
pending/retention bounds, polling mailbox, cancellation token and shutdown rules
as conversion jobs. Queue payloads contain paths and bounded metadata, not
dictionary records or resource bytes. Source reading and binary work run on the
worker. Conversion submission remains `Runner::submit` with its existing types.

Snapshots now include an additive `operation` discriminator and optional
`dictionary_output`. Dictionary jobs populate that typed summary and leave the
existing converter `output` empty. Conversion jobs retain their previous output
and use `operation="convert_txt"`. No fake converter identity or ambiguous
resource-versus-entry count is used. Completed payloads contain counts, bytes,
policy/profile and destination; rendered entries/resources stay out of events.

The synchronous `dictionary::execute` adapter is also available for non-GUI
embedding and tests. UI handlers should submit jobs instead. Existing shared
conversion, core, reader, casing and converter implementations are unchanged.
Only the runner dispatch is intentionally extended. The original runner is
preserved in its accepted evidence snapshot; the new source hash is pinned by
the focused runner. Dependency manifests and all three Rust workspace locks are
unchanged.

## Resource manifests

Example:

```json
{
  "title": "Resources",
  "description": "Dictionary resources",
  "resources": [
    {"key": "\\css\\style.css", "source": "assets/style.css"},
    {"key": "\\fonts\\probe.ttf", "source": "assets/probe.ttf"}
  ]
}
```

Relative source paths resolve against the manifest's directory; absolute paths
are accepted for caller-selected resources. These are trusted user input paths,
not archive extraction paths. A future Tauri adapter must apply its own selected
file/path authorization. This API does not create GUI filesystem permissions.

Manifest JSON is capped at 128 KiB and the smaller configured file limit. Unknown
fields are refused. Resource count, key length, individual file bytes and combined
key/payload bytes obey the existing dictionary budgets. Each file must be regular,
is read through a cap+1 reader, and is checked for cancellation before/after read.
Resource archive keys pass the existing safe-path check before payload reading;
the core still performs its full collision plan before creating an output stage.
No directory walking or implicit extra resource inclusion occurs.

## Integrity, cancellation and scope

Core packing retains stable versioned sorting, strict complete reopen/verification
and no-clobber publication. Core extraction retains path/collision planning,
descriptor-relative writes and exclusive directory publication on qualified
macOS (Linux remains separately unqualified). Existing destinations are refused
before source work. Source work forwards shared `converting` progress; core pack,
export or extraction forwards `publishing` progress with its original phase names.
The same job token reaches every adapter/core operation.

No cancellation check occurs after successful publication. Ordinary cancellation
before commit removes staged outputs; a late request can return success. Engine
compression/decompression and one source read remain cooperative interruption
boundaries, not forcibly interruptible operations. Existing panic uncertainty,
nonblocking drop and explicit off-UI `join` rules continue unchanged.

This handles only the already qualified Studio output policies. It is not an
arbitrary foreign MDX/MDD importer, encryption/legacy-encoding extension, general
embedded stylesheet serializer, hard RSS limit, full corpus scale proof, resource
folder scanner or Tauri integration. Explicit legacy TXT body-span export is
still refused when source definitions cannot represent that profile.

## Authored checks

Five new Rust integration tests cover mixed conversion/dictionary execution,
both MDX encodings, duplicate-preserving TXT export, relative resource manifests,
exact binary/empty extraction, existing destination refusal, cancellation during
MDX/MDD verification and staged extraction, late extraction cancellation and
resource/manifest budget refusal. Earlier runner/application tests stay in the
workspace batch.

The process batch submits 19 serial jobs: twelve expected successes and seven
expected failures. It covers both encodings crossed with both TXT profiles,
MDX physical-order export, six binary/font/CSS/Unicode/empty MDD resources,
extraction inventory, overwrites, unsafe paths, logical path aliases, malformed
TXT, missing resource files and successful work after those failures. Independent
Python readers and a separate v2 structural audit check packed binaries.

Two new Python contract tests pass here. The runner verifies 95 prior source
identities while allowing only the pinned dispatch extension, and checks the
unchanged 60-package dependency graph. Rust compilation and the job batch passed
on the user's Mac; this authoring environment has no Rust toolchain. General
foreign-file import, production-scale limits, Tauri integration and M2 closeout
remain separate work.
