# M2 closeout — scoped native backend foundation complete

Decision date: 2026-11-07. **M2 is complete within the tested native backend
profiles on the user's Mac.** The next milestone is Tauri shell and GUI
integration. This is not a production desktop release, full original-app parity,
a universal format reader or cross-platform qualification. M0 GUI runtime capture
remains partial; M1's scoped decision is unchanged.

The machine-readable decision is
`docs/evidence/m2-closeout-review/decision.json`. It binds five exit criteria to
23 unique accepted receipts/reader attestations and all 324 qualified source
identities. Original reports retain their historical `M2_complete: false` fields;
this later review decision records completion without rewriting them. Failed
attempts remain failures in the evidence history.

## Exit criteria and evidence

| Exit area | Reviewed result | Evidence under `docs/evidence` |
| --- | --- | --- |
| Ordinary v2 import and lookup | Explicit supported profiles, strict verification, duplicate identity, bounded redirects; application/background import and indexed sessions | `m2-v2-import-user-run`, `m2-import-jobs-user-run`, `m2-sessions-user-run`, `m2-real-readers-user-run` |
| Metadata and stylesheets | Supported header/stylesheet preservation, metadata-only rebuild and fresh publication; scoped MDict/GoldenDict attestations | `m2-metadata-user-run`, `m2-metadata-jobs-user-run`, both corresponding native confirmations |
| Sizing, indexing and resources | Bounded parser/index/result envelopes, paged sessions, safe streaming extraction, shared active admission and publication lifecycle | sizing/index/session/extraction/publication gates, then the full-converter, real-publication and CC-pack gates |
| Representative complete inputs | Six full converters, three original MDX dictionaries and 17-resource MDD, complete real repacks and full CC packing | `m2-full-converters-user-run`, `m2-real-readers-user-run`, `m2-real-publication-user-run`, `m2-cc-pack-user-run` and their preceding source/oracle gates |
| Regression and closeout | Recent combined native runtime regressions, unchanged earlier sources, full evidence/provenance validation, baseline/Python contracts and scope reconciliation | Latest CC-pack receipt plus closeout decision and package verification logs |

No new native command was run for closeout. The most recent Mac gate already ran
39 combined runtime tests and five block-writer library tests, including the new
profile's interactions with readers, index jobs, queues and publication. Earlier
native paths and dependency versions remain unchanged; their original accepted
receipts are retained. Closeout reruns local evidence/snapshot/contract checks,
not every old Rust/native-reader batch. Overlapping suites are not added together
as a count of unique tests. No routine Mac rerun is required.

## Supported envelope

| Capability | Qualified boundary and routing |
| --- | --- |
| Ordinary dictionary import | Tested unencrypted UTF-8/UTF-16 v2 profiles; strict full scans and explicit limits. Three selected real MDX files and one MDD are qualified, not every dictionary |
| Lookup and duplicate paging | `raw_exact`, explicit `header_ascii_v1`, frozen Unicode16 and physical ordinal identity; bounded pages/results and source-bound caches |
| Redirects | Bounded resolver in the ordinary one-shot facade; large indexed-session redirect resolution is not implemented/qualified |
| Metadata | The explicit `mdict-v2-metadata-v1` profile and bounded metadata APIs; preserve their XML/native stylesheet whitespace rules and unsupported cases. Larger generic metadata edits are not implied |
| Six native converters | Full CC-CEDICT source: 203,362 output entries; Mini 4,311; Idioms 5,489; Concise 44,445; Revised 162,636; WFG 161,182. Concise/Revised retain the declared narrow set-order comparison scope |
| Standard packing/export | Existing 100,000-record, 32 MiB decoded, 16 MiB plan profile; successful real MDD/Almaany/idioms packs. Larger generic exports remain capped |
| Larger CC MDX packing | Explicit `cc_packing` profile: 250,000 records, 96 MiB decoded, 48 MiB descriptor plan; complete original 202,884-entry CC source passed both encodings. This is a different input from the converter source above |
| Resources | Selected macOS MDD packing, raw lookup and staged safe extraction; path/collision/link controls and bounded copy. No general Windows resource-filesystem claim |
| Shared admission | 384 MiB logical memory / 4 GiB temporary ledger; converters, index builds and CC packs exclusive. Smaller packing/export/extraction use their qualified charges |
| Results and cancellation | Bounded queues/retention, coalesced progress, one-transfer results, close/release barriers, no-clobber commits, success winning over late cancellation and explicit panic uncertainty |
| Platform | Native receipts from the tested user Mac environment. Local Python validation on another host is not Rust qualification for that platform |

Engine working-memory and parser limits are not total process-memory enforcement.
The 384 MiB RSS value is an observed qualification threshold, not an OS-enforced
limit or a guarantee for all inputs that fit a cap. Compressed expansion, index,
record and reply budgets remain explicit. No maximum-cap combination or
multi-gigabyte dictionary support is inferred from the selected full datasets.

## Recent measured results

All six full converters passed independent reference comparisons and shared
background integration. Highest reported converter RSS was 256.29 MiB; disk-backed
Concise was 69.99 MiB. Bounded real packing plus admitted indexing passed with a
169.19 MiB maximum controller peak. Full CC block-spooled packing passed at
57.23 MiB, preserving all 202,884 entries in both output encodings. These are
separate gate/process measurements, not an application-wide simultaneous peak.

The latest detailed reviews cover 2,726 converter exchanges, 925 real-publication
exchanges and 1,273 CC-packing exchanges. All final reservations and reader
retention were zero. Complete independent record digests and strict native
reopens establish content/order identity under the documented profiles. Reader-app
attestations are scoped to the files/checklists actually confirmed; they are not
invented visual checks of the newer full packed files. No private corpus,
workbook definitions or rebuilt dictionaries are bundled in this package.

## Handoff to the Tauri milestone

The broadest qualified native facade currently lives in `m2/cc-pack-runtime`.
It includes conversion, ordinary packing/export, extraction, explicit larger
packing, admitted index construction and managed readers. It is a qualification
workspace with historical dependencies/copies, not the final production crate
layout. Promote/consolidate behind a deliberate application boundary when wiring
the shell; preserve these exact snapshots and regression coverage.

The UI adapter must select explicit profiles and show typed size/policy refusals.
It must not expose an older 1,000-entry probe as a general importer, silently raise
caps, partially truncate dictionaries, or route around admission. Separate bounded
metadata and redirect APIs still require deliberate coordination before concurrent
GUI exposure; this closeout does not claim that every historical API is one
unified production scheduler.

The next implementation starts the Tauri shell and native command/job adapter,
then builds the modern interface around verified jobs, files, status and cleanup.
Chinese, English and Arabic localization with RTL remain requirements. Rendered
dictionary HTML/resources must remain isolated from privileged commands. Optional
Python plugins need their own bridge, with protocol traffic separated from user
stdout. Their absence does not make the six built-in native converters Python
runtime dependencies; Python here is also used for independent test oracles.

## Explicit work outside this completion decision

Desktop feature parity and remaining M0 runtime capture; the Tauri GUI, rendered
preview and plugin bridge; install/sign/update workflows; native Windows/Linux
qualification; hard memory enforcement and arbitrary-size inputs; power-loss
and crash-orphan recovery policy; larger export/metadata/redirect envelopes; and
unqualified formats/encodings/protection remain separate work. MDX v3 packing and
unpacking remain on the user's later roadmap. This decision does not advertise
unqualified LZO/legacy/protected behavior merely because a linked engine may
contain related decoding code.

The old closeout ledger is archived at
`docs/history/M2-REMAINING-before-closeout-2026-11-07.md`. Current remaining work
is summarized in `M2-REMAINING.md`; historical per-slice status strings are not
the current milestone decision.
