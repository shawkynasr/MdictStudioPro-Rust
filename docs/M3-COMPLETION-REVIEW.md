> Current follow-up: [first-release readiness checklist](M3-FIRST-RELEASE-CHECKLIST.md). The review below is a historical source-bound snapshot; folder/native discovery, compatibility and standalone/dialog follow-ups now have later evidence. Full M3 remains open.

# M3 completion review — 20 November 2026

**Review complete. The tested Mac desktop feature checkpoints are accepted;
full M3 parity and production release qualification remain open.** This records
the existing evidence rather than redefining full M3 as the smaller feature set.
No new native run, feature implementation or dependency change is claimed.

## Requirements and evidence

| Requirement | Reviewed result | Evidence and limits |
| --- | --- | --- |
| Native command/job adapter and explicit profiles | Qualified on the user Mac | Latest discovery gate: 86 runtime and 27 adapter tests; coordinated jobs, cancellation, receipts and publication. Existing size/profile caps remain. |
| Modern desktop GUI | Accepted for tested Mac workflows | Tauri/Svelte builds and user interactions cover build, extraction, reader tools, Database and Python plugins. Six built-in converter routes are native-qualified and GUI-compiled; six fresh manual GUI runs are not claimed. |
| English/Chinese/Arabic, RTL and appearance | Implemented with partial manual coverage | EN/ZH/AR labels and RTL implemented; user screenshots and restart checks cover selected appearances and Arabic. No exhaustive translation, accessibility or all-platform rendering qualification. |
| Isolated rendered dictionary preview | Accepted in the static supported profile | Plain/HTML, numeric styles, split view and scoped resource previews; scripts and external connections disabled. No arbitrary dictionary website compatibility claim. |
| Optional Python plugin bridge | Accepted within trusted selected-file profile | Dedicated authenticated channel and separate stdout/stderr; options, presets, failure/cancel guidance, selected-file class discovery and generated scalar forms. Exact six-record GUI output and receipt hashes verified. Inspection imports trusted code; it is not a security sandbox. |
| Platform packaging and release qualification | Partial: local Intel Mac preview accepted | Reviewed locks, offline .app build, Database rendering and Arabic/Light restart persistence. Signing, notarization, updater, distribution and other platforms/architectures are not qualified. |

The latest Mac gate passes all eleven stages, including nine Python wrapper
tests, 43 frontend logic tests, Svelte check/Vite build and desktop compilation.
The user-run report matches all 210 available delivered source identities and
the two exact previously reviewed Mac-only files. All 324 protected M2 identities
and seven final lock identities match. The authoring environment did not execute
Rust, Svelte or a native application; the evidence distinguishes local tests,
user-run native reports and supplied GUI observations.

The separate bounded M4 Database milestone remains complete under its own
decision. Its earlier failed strict lock audit remains a failed historical
report with a separately reviewed normalization decision. Nothing here rewrites
or broadens accepted M1/M2/M4 contracts.

## Remaining work, with explicit boundaries

| Area | Current boundary | Follow-up |
| --- | --- | --- |
| Folder-wide plugin discovery | Only one explicitly selected .py file is inspected; local classes are listed | Next functional parity slice: explicitly selected folder scan, bounded file/class inventory, stable identities/collision handling and per-file errors, preserving explicit trust and subprocess isolation. No background startup import. |
| Arbitrary plugin option schemas | New scalar-fields-v1 supports string, boolean, number and choice; unsupported schemas fall back to JSON | Additional schema types need a defined contract and fixtures. The original base declared an empty future schema; arbitrary legacy form compatibility was not implemented there. |
| Morphology | Original selectors only; addflex.py and wordforms contract unavailable | Deferred until a real executable/data contract exists. Do not request the same absent files again. |
| Dictionary resources and formats | Static scoped resources and existing v2/encoding/lookup profiles | JS/audio/SVG, CSS imports, multi-volume MDD, wider sort flags, larger caps and MDX v3 remain separate decisions. |
| Runtime/release hardening | Logical reservations and cooperative cancellation; no global production claim | Crash recovery, hard OS resource enforcement and wider security/accessibility checks remain open. |
| Distribution | Local unsigned Intel Mac artifact only | Signing/notarization, installer/updater and Apple Silicon/Windows/Linux qualification remain open. |

**Artifact freshness matters:** the accepted standalone preview executable
`830d10f91f3ed884d210b7bb341864ef066a9fe43acf86bff18f644a3df9d509`
predates selected-file discovery/forms. Those later features are qualified in
the updated development application. No claim is made that the older .app
contains them. Refreshing the preview can be batched after the next functional
changes; it does not require reopening completed dictionary-reader benchmarks.

## Decision and next step

Accept the existing scoped Mac checkpoints and finish this review. Keep full
M3, full original-app parity and production release readiness false. The next
functional implementation is explicit folder-wide plugin discovery; release
packaging remains a separate workstream. No routine native, Database closeout or
independent-reader rerun is required merely to record this review.

The machine-readable review is
[evidence/m3-completion-review/decision.json](evidence/m3-completion-review/decision.json).
It binds retained evidence hashes and the current runtime source identities.
Historical source-tree STATUS files and old reports retain their original
wording; this review and docs/STATUS.json describe the current decision.
