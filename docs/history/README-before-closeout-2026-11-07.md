# Mdict Studio Pro — M0 / M1 qualification workspace

**M2 is complete for the tested native backend foundation.** All five backend
exit areas are closed within their documented profiles. The closeout binds 23
accepted receipts/reader attestations and 324 source identities, with the recent
39 runtime tests and five block-writer tests covering the latest interactions.
Earlier reports keep their original partial-milestone fields and remain unchanged.

Read `docs/M2-CLOSEOUT.md` for the current support matrix, limits and Tauri handoff.
No routine Mac rerun is required. This is not a production desktop release or
full original GUI parity. Next is the Tauri shell and native command/job adapter,
then the modern GUI with Chinese/English/Arabic localization and RTL.

The sections below summarize individual accepted gates; any closeout-pending
statements in those historical summaries are superseded by the closeout decision.

**Full CC-CEDICT packing passed on Mac.** All 202,884 entries were packed in
both UTF-8 and UTF-16. Complete independent record comparisons and strict index
reopens passed. Native tests passed: 5 library tests and 39 runtime tests, including
byte-for-byte comparison with the old writer on smaller fixtures. All four native
command receipts succeeded.

Runtime peak RSS was 60,010,496 bytes (57.23 MiB), below the unchanged 384 MiB
target. Review checked 1,273 controller exchanges, 324 source identities,
reader exclusion, old-cap refusals, overwrite protection, one-transfer results
and zero final reservations/retention. Exact report and 24 source snapshots are
retained in `docs/evidence/m2-cc-pack-user-run`. No rerun is required.
See `docs/M2-CC-PACK.md`. This gate is included in the completed scoped M2 closeout.

**Real bounded packing and shared index-build admission passed on Mac.**
All 36 native tests and three native command receipts passed. Complete MDD,
Almaany and idioms sources produced five independently verified packed outputs
(both UTF-8 and UTF-16 for MDX). All four original dictionaries, including the
202,884-entry CC-CEDICT MDX, passed admitted index build and strict complete reopen.
The larger CC-CEDICT pack produced its required limit refusal, with no output.

Review checked 925 controller exchanges, 300 source identities, real reader/packer
overlap, reader/index exclusion, typed refusals, one-transfer results and zero
final reservations/retention. Highest reported runtime RSS was 177,405,952 bytes
(169.19 MiB), below 384 MiB. Exact report and 18 source snapshots are retained in
`docs/evidence/m2-real-publication-user-run`. No rerun is required. See
`docs/M2-REAL-PUBLICATION.md`. Full CC-CEDICT packing capacity and M2 closeout
remain open.

**All six full converters passed shared background integration on Mac.**
All 33 native tests and three native command receipts passed. Full outputs matched
the accepted standalone native hashes: CC-CEDICT 203,362 entries; Mini 4,311;
Idioms 5,489; Concise 44,445; Revised 162,636; WFG 161,182. The complete Concise
row comparison matched 45,178 rows and 677,670 fields against independent Python.

Concise now peaks at 73,392,128 bytes (69.99 MiB), down from 400.74 MiB with the
owned path. The highest peak across all six was 268,738,560 bytes (256.29 MiB),
below the unchanged 384 MiB target. Review checked 2,726 controller exchanges,
282 source identities, typed refusals, bounded retention, one-transfer results
and zero final reservations/reader retention. Exact report and 17 source snapshots
are retained in `docs/evidence/m2-full-converters-user-run`. No rerun is needed.

See `docs/M2-FULL-CONVERTERS.md` for the profile and evidence scope. M2 remains
incomplete; next is real dictionary packing and index-build admission.

**Full official Mini and Idioms conversion passed on Mac.** Mini produced 4,311
entries and Idioms 5,489; both complete TXT outputs matched the original Python
references. Review checked all 732 controller exchanges and source/lock identities.
Peak observed RSS was 202,477,568 bytes (193.10 MiB); final reservations and reader
retention were zero. Exact report and three harness/source snapshots are retained
in `docs/evidence/m2-official-converters-user-run`. No rerun is needed.

**Full official Concise conversion passed on Mac.** All 45,178 data rows produced
44,445 entries and a 25,093,253-byte TXT, matching the independent original-Python
reference under the previously qualified reference-field set-order normalization.
Raw TXT hashes differ as expected under that ordering rule. Both native command
receipts succeeded. Review checked all 893 controller exchanges, six job refusals,
one wrong-converter API refusal, source/lock bindings and zero final reservations.
Peak reported RSS was 342,503,424 bytes (326.64 MiB). Report and twelve exact source
snapshots are retained in `docs/evidence/m2-concise-full-user-run`. No rerun needed.
See `docs/M2-CONCISE-FULL.md` for the scoped qualification and memory limitation.

**Full CC-CEDICT passed on Mac with exclusive admission and chunked TXT publication.**
All 203,362 entries (125,369 primary plus 77,993 traditional) matched both the fresh
Mac Python output and the independent full local reference exactly. The native
receipt counted 30 comments and no skipped nonempty source lines. Both native
command receipts succeeded. Review checked all 1,440 exchanges, seven typed job
refusals, two API refusals and zero final reservations/reader retention. Peak
reported process RSS was 240,029,696 bytes (228.91 MiB), below the provisional
384 MiB target. No overlapping work appeared in the full-data admission ledger.
Report and twelve exact source snapshots are retained under
`docs/evidence/m2-cc-full-user-run`; no rerun needed. See `docs/M2-CC-FULL.md`.

**The full Revised disk-backed row reader passed on Mac.** All 163,909 normalized
rows and 2,950,362 fields matched the original Python helper and independent full
reference. All 27 process cases passed (10 successes, 17 expected refusals), along
with native test/release-build receipts. Independent review also recomputed shared
string and JSONL extents: 615,738 strings, 102,800,416 row-spool bytes and 175,812,245
private bytes total. Release-process RSS was 152.44 MiB for the complete workbook,
156.45 MiB maximum across cases (under the provisional 192 MiB target). Report,
review oracles and twelve exact source snapshots are retained under
`docs/evidence/m2-xlsx-spool-user-run`. No rerun needed. See `docs/M2-XLSX-SPOOL.md`.

**Full Revised/WFG grouped TXT publication passed on Mac.** Revised produced
162,636 entries (1,454 redirects) matching the qualified normalized Python reference;
WFG produced 161,182 entries matching Python raw bytes exactly. All 30 process cases
passed: six publications and 24 expected refusals, with native test/release-build
receipts successful. Review independently recomputed the group plan from all 163,909
source rows: 161,182 groups, at most six rows / 11,220 input bytes per group, and a
54,397,924-byte index plan charge. Peak reported release-process RSS was 168,136,704
bytes (160.35 MiB), below the provisional 256 MiB target. Exact report, independent
review oracles and twelve source snapshots are retained under
`docs/evidence/m2-revised-render-user-run`; no rerun needed. See
`docs/M2-REVISED-RENDER.md` for scope and comparison rules.

**Next: connect the grouped converters to shared background jobs/admission.**
Standalone output parity does not establish queued-worker cancellation, retention,
admission or reader concurrency for these new profiles. All 253 prior source
identities remain unchanged (265 including this gate). Real packing workflows,
index-build shared admission and M2 closeout also remain. Keep `.venv`, `vendor`,
private inputs and all earlier outputs.

**The first real dictionary reader gate passed on Mac.** The three MDX files
contain 296,110 entries and the MDD contains 17 resources. Complete independent
scan comparisons, verified indexes, 36 raw-exact pages and MDD extraction passed;
review checked 346 controller exchanges and recomputed all resource hashes from
retained M1 audit evidence. Final reservations/reader retention were zero. Maximum
observed RSS was 12,664,832 bytes (12.08 MiB rounded). The source-bound report and
four source snapshots are retained in `docs/evidence/m2-real-readers-user-run`.
Actual private files are not bundled and report pages contain hashes rather than
definitions. No rerun is needed. Keep `.venv`, `vendor`, private inputs and old
outputs. Real converter inputs, index-build admission and final M2 closeout remain
open. See `docs/M2-REAL-READERS.md`.

**Larger converters and shared admission passed the first Mac gate.** All six
converter scenarios and the Rust test/build receipts passed: six publications,
35 expected failures and 48 pre-cancelled jobs. Review independently regenerated
and ran the original Python plugins, checking 68,000 normalized records and
2,964 controller exchanges. All final shared reservations and reader retention
were zero. Peak observed RSS was 192,593,920 bytes (183.67 MiB rounded). Revised
and Concise raw differences follow the documented Python set-order comparison;
other converter output bytes matched. Report, local oracle receipts and eleven
exact source snapshots are retained in `docs/evidence/m2-converter-runtime-user-run`;
the original E0753 compile failure is retained separately. No rerun is needed.
Keep `.venv`, `vendor`, private inputs and previous outputs. Representative real
inputs, index-build admission and final M2 closeout remain open. See
`docs/M2-CONVERTER-RUNTIME.md`.

**Shared larger publication runtime passed its first Mac gate.** The corrected
Rust test/build receipts and both controller scenarios passed: nine publications,
eight expected job failures and 16 precancelled jobs. Review checked 3,331
controller exchanges, recomputed reported fingerprints for 196,608 physical
records, and recomputed four export plus four extraction file hashes. Reader
sessions overlapped packing and export; all final shared reservations, handles
and retained reader replies were zero. Maximum observed RSS was 108,470,272 bytes
(103.45 MiB rounded). The accepted report and nine exact source snapshots are
retained in `docs/evidence/m2-publication-runtime-user-run`; the original E0223
compile failure is retained separately. No rerun is needed. Keep `.venv`, `vendor`,
private inputs and previous outputs. Converter sizing/admission is next;
representative real inputs and M2 closeout remain open. See
`docs/M2-PUBLICATION-RUNTIME.md`.

**Larger packing and export passed the first Mac gate.** The isolated
`m2/large-io` workspace passed its Rust test/build commands and 47 process cases:
16 publications and 31 expected refusals. Both MDX encodings and the MDD case
contain 65,536 records/resources; a 1 MiB definition also passed. Review recomputed
reported fingerprints for 327,681 physical records and seven export file hashes.
The complete source-bound report and ten exact source snapshots are retained in
`docs/evidence/m2-large-io-user-run`. Peak observed RSS was 105,115,648 bytes for
packing (100.25 MiB rounded), and 4,231,168 bytes for exports (4.04 MiB rounded).
Packing retains a 32 MiB decoded-input cap and an owned builder; this does not
qualify a streaming writer, every ceiling combination or hard process RSS limits.
No rerun is needed. Keep `.venv`, `vendor`, private inputs and previous outputs.
Shared-runtime integration of this new path is next; converter sizing, real
inputs and final M2 closeout remain open. See `docs/M2-LARGE-IO.md`.

**Background extraction and shared reader admission passed on Mac.** The isolated
`m2/extraction-jobs` runtime combines managed persistent readers and a serial
streaming-extraction publisher under one logical operation/memory/temp-space
gate. Committed output stays successful on late cancellation; panic outcomes
are explicitly uncertain. Rust test/build commands and all three process scenarios
passed. Review recomputed 4,101 reported file hashes and reviewed 1,166 controller
exchanges, including shared-admission refusal/release and concurrent reader use.
All final reservations were zero. Maximum observed RSS was 6,664,192 bytes.
Report and nine exact source snapshots are retained in
`docs/evidence/m2-extraction-jobs-user-run`. No rerun is needed. Keep `.venv`,
`vendor`, private inputs and previous outputs. Larger packing/converter paths,
real inputs and final M2 closeout remain open.
See `docs/M2-EXTRACTION-JOBS.md`.

**Streaming MDD extraction passed its first Mac gate.** The isolated
`m2/stream-extract` workspace copies source-bound resource spans without full
resource materialization, preflights paths/sizes, verifies staged file bytes and
publishes a new directory exclusively. The corrected Rust test/build commands,
four successful extractions and 26 expected refusals passed. Review recomputed
all 4,105 reported file hashes and aggregate digests. The largest resource was
32 MiB plus seven bytes; the many-file case created 4,096 files. Maximum reported
RSS was 4,792,320 bytes. The original compile failure and accepted report/source
snapshots are preserved under `docs/evidence`. No rerun is needed. Keep `.venv`,
`vendor`, private inputs and previous outputs. Background publication/admission,
larger packing/converter paths and M2 closeout remain open.
See `docs/M2-STREAM-EXTRACT.md`.

**Persistent application sessions and background page jobs passed on Mac.**
The isolated `m2/sessions` workspace keeps a verified reader/index open on one
actor thread per session. It adds bounded queued jobs, progress snapshots,
cancellation, single-transfer results, close acknowledgement and pool-wide
reader/retained-reply admission. Rust test/build commands and all five process
scenarios passed. Review recomputed 37 page replies and the logical ledger in
497 controller exchanges; final reader/handle/reply reservations were zero in
every scenario. Maximum observed RSS was 6,262,784 bytes. Original report and
eight source snapshots are retained in `docs/evidence/m2-sessions-user-run`.
No rerun is needed. Keep `.venv`, `vendor`, private inputs and previous outputs.
Larger resource/converter/packing paths and M2 closeout remain open. See
`docs/M2-SESSIONS.md`.

**Persistent disk index and paged lookup passed on Mac.** The new isolated
`m2/indexed-engine` workspace adds a content-bound cache with frozen Unicode16
normalization, exact-first selection and duplicate-preserving pages. External
sorting avoids retaining the full key/body collection. Cache attachment verifies
every key; startup remains linear. Rust test/build commands and all 55 process
cases passed: 12 builds, 20 query runs (180 embedded pages) and 23 expected
refusals. Largest index fixtures contain 65,536 MDX entries / MDD resources;
maximum observed RSS was 6,189,056 bytes. The report and 11 source snapshots
are retained in `docs/evidence/m2-index-user-run`; page values were independently
recomputed. Keep `.venv`, `vendor`, real inputs and prior outputs. No rerun is
needed. Larger application/background integration and M2 closeout remain open.
See `docs/M2-INDEX.md`.

**First production-sizing gate passed on Mac.** The isolated `m2/bounded-engine`
workspace adds explicit engine allocation limits and complete streaming v2
validation, retaining no full definition vector or lookup locator. It measures
larger synthetic files and hostile declaration refusals, parser accounting and
OS peak RSS. It does not raise existing application/packing budgets or complete
M2 area 3. The corrected Mac batch passed its Rust test/build commands and all
29 process cases: eight scan/query successes and 21 expected refusals. The
largest MDX fixture had 262,144 entries and 64 MiB logical bodies, with maximum
observed reader RSS 4,677,632 bytes. No locator was retained. This is a measured
synthetic result, not full-ceiling or production-path qualification. Original
failure and accepted report/source snapshots are retained under `docs/evidence`.
No rerun or reader-app check is requested. Next is persistent indexing and
paged matching with the frozen lookup policy.
Keep `.venv`, `vendor` and previous outputs. See `docs/M2-SIZING.md`.

**Metadata-aware packing and publication passed offline and native checks.** The
new API packs fresh UTF-8/UTF-16 MDX and raw-key MDD with the accepted metadata
policy, verifies physical rows and metadata, then reuses the exclusive publisher.
A dedicated worker preserves committed success on late cancellation and marks
panic outcomes as publication-uncertain. Rust tests and all 56 sync/background
job outcomes passed: 20 successful publications and 36 expected refusals. Source
identities and the dependency lock match. Both new native controls passed
Python marker expansion. The user confirmed all five entries correct, with no
crashes or missing entries, in response to the two-file MDict/GoldenDict
checklist. The scoped attestation is retained in
`docs/evidence/m2-metadata-jobs-native-user-confirmation`. No rerun is requested.
M2's metadata area is accepted within the tested v2 profile. The accepted
offline report and snapshots are retained in `docs/evidence/m2-metadata-jobs-user-run`.
Keep `.venv`,
`vendor` and prior outputs. See `docs/M2-METADATA-JOBS.md`.

**Metadata-only rebuild passed offline and the native-reader checklist.** The
rebuild path edits the header, copies all key/record sections unchanged, verifies
the staged output and publishes without overwrite. It preserves multiline
metadata and uses the native-tested literal-LF stylesheet convention. The
corrected batch passed all 36 commands: 14 rebuild comparisons and 18 expected
refusals, plus seed and Rust test commands. Both native controls passed Python
marker expansion. The user confirmed all five entries work with no crashes in
response to the two-file MDict/GoldenDict checklist. That scoped attestation is
retained under `docs/evidence/m2-metadata-native-user-confirmation`. No rerun
is requested. Metadata-aware entry packing and a publication worker remain
within M2 area 2. The original report and snapshots are retained under
`docs/evidence/m2-metadata-user-run`. See
`docs/M2-METADATA.md`. Keep `.venv`, `vendor` and previous outputs.

**Ordinary v2 application requests and background import jobs passed.**
The new application composition adds typed import/query actions, a separate
serial import worker, bounded whole replies and single-owner result collection.
It reuses the shared cancellation/progress/lifecycle types and preserves the
existing conversion/packing runner. All 56 Mac commands passed: 27 cases through
both synchronous and background routes, with 15 matching successful cases and
12 expected job failures. Rust lifecycle/cancellation tests also passed.
The unchanged report and matching sources are retained in
`docs/evidence/m2-import-jobs-user-run`. No rerun is requested.
See `docs/M2-IMPORT-JOBS.md`. Keep `.venv`, `vendor` and previous outputs.

**Ordinary v2 import/lookup passed the bounded Mac qualification batch.**
The isolated `m2/v2-import` workspace imports unencrypted UTF-8/UTF-16 v2 MDX/MDD
without Studio tags, preserving physical duplicates, raw headers and resource
bytes. Lookup is explicitly raw-exact or header-guided ASCII/Unicode16; redirects
are opt-in and bounded. Existing core/application/runner sources and locks stay
unchanged. All 26 cases passed: 15 successful imports/comparisons and 11 expected
refusals. The batch checked 420 MDX lookup/redirect results (328 exact results,
92 expected query errors), four MDD exact queries, raw metadata and checksums.
The original passing report and matching sources are retained in
`docs/evidence/m2-v2-import-user-run`; earlier failures remain intact. See
`docs/M2-V2-IMPORT.md`. Its application/background integration above is also accepted.
Keep `.venv`, `vendor` and prior outputs. No old batch/native-reader rerun is needed.

**M2 gap review: three backend work areas remain.** Production sizing/index/resource
limits are followed by representative
real-input qualification and final backend closeout. Completed converters,
MDD APIs and background jobs are no longer listed as unfinished. See
`docs/M2-REMAINING.md`. The next area is production sizing and resource limits;
v3 packing/unpacking remains deferred for later roadmap planning.

**Background MDX/MDD operations passed the bounded batch on the user's Mac.**
The runner adds TXT-to-MDX packing, Studio MDX-to-TXT export, resource-manifest
MDD packing and staged extraction through the existing qualified core APIs.
All 19 jobs matched expectations: twelve successes and seven controlled failures.
Both encodings/TXT profiles, independent Python reads and v2 structural audits,
exact TXT exports, six extracted resources and recovery after failed jobs passed.
The report and 20 matching source/data snapshots are retained under
`docs/evidence/m2-dictionary-jobs-user-run`. All 95 protected identities and the
60-package graph matched. See `docs/M2-DICTIONARY-JOBS.md`. No rerun is needed.
MDX v3 packing/unpacking is deferred for later user roadmap planning. Current
qualified dictionary jobs retain their Studio v2 scope; M2 remains partial.

**Background conversion jobs passed the bounded batch on the user's Mac.**
The shared API now exposes a serial worker, bounded queue and polling mailbox,
independent cancellation, retained terminal status and nonblocking shutdown.
Both Rust commands passed: workspace tests and the 17-job batch. Twelve
successful outputs matched the earlier qualified application hashes; all five
expected per-job failures were typed correctly. The batch reports 50 delivered
events with terminal-status checks passed. All 90 protected identities and the
60-package dependency graph matched. The report and 12 source snapshots are
retained in `docs/evidence/m2-jobs-user-run`. See `docs/M2-JOBS.md`.
No rerun is needed. MDX/MDD background operations and Tauri wiring remain
subsequent work; M2 remains partial.

**Shared Rust application conversion API passed on the user's Mac.**
`m2/application` brings XLSX reading and all six converter types behind one job,
progress, cancellation and typed-error interface, with common output validation
and staged TXT publication. The qualified crates and their locks are unchanged.
The new joint lock contains only versions/checksums from their qualified graphs.
All 49 command outcomes matched: 39 successes and ten controlled refusals.
Twelve converter cases matched original plugin content, staged TXT publication,
shared progress and repeatability; active/named workbook access also matched.
All 81 protected source identities and the 60-package joint graph are unchanged.
The accepted report and nine application source/lock snapshots are retained in
`docs/evidence/m2-application-user-run`. See `docs/M2-APPLICATION.md`.
No rerun is needed. The API remains synchronous; background job execution and
GUI integration are subsequent work. M2 remains partial.

**All five MOE Rust converters passed the bounded synthetic profile on the Mac.**
All 36 command outcomes matched expectations: 31 successes and five controlled
refusals. Ten baseline/extended cases matched original plugin content, staged TXT
publication and deterministic repeats. Seven matched raw Python bytes; three
differed only in documented set-derived ordering. The accepted report and 27
source snapshots are retained in `docs/evidence/m2-moe-user-run`, alongside both
earlier failed attempts. All 35 protected source identities and the XLSX lock
remain unchanged. No rerun is needed. See `docs/M2-MOE.md` for the exact scope.
Keep the existing folder, `.venv`, `vendor` and all prior outputs when updating.
No previous qualification batch or native-reader test needs repeating.

**Rust XLSX common-cell reading and normalization passed on the user's Mac.**
The isolated `m2/xlsx-reader` crate preserves active-sheet selection, duplicate
headers, blank-row rules, raw string escapes and numeric normalization against
the original helper. It has explicit size/geometry limits and unsupported-cell
errors. All 12 supported cases matched the original helper, including a 2,000-row
table; all seven controlled refusals, dependency resolution and Rust tests passed.
See `docs/M2-XLSX.md`. The exact new lock is now retained alongside the report
and 32 source/data snapshots in `docs/evidence/m2-xlsx-user-run`. The 35 protected
dictionary source/lock identities remain unchanged. Dates/durations stay
unsupported in this profile. No rerun is needed. The MOE ports passed above.

**Rust TXT I/O and UTF-8 CC-CEDICT passed on the user's Mac.**
The core has explicit canonical/legacy-body-span profiles and staged TXT export.
The first converter port preserves original HTML, duplicates, pinyin and entry
order. All 43 gates passed: 38 successful commands and five controlled refusals.
Six captured converter TXT outputs
are checked for I/O parity; MOE Rust implementations are now qualified above.
See `docs/M2-TEXT-CONVERTERS.md` for the exact contracts and bounded scope.

Both profiles re-exported all six files exactly; four two-encoding MDX pipelines
passed, and the two CC-CEDICT fixtures matched the original plugin's bytes and
counters. Ten pinyin probes matched. The unchanged report and all 32 matching
source/data snapshots are retained in `docs/evidence/m2-text-user-run`.
No rerun of the TXT batch is needed. The XLSX reader passed above; the five MOE
ports passed their bounded synthetic qualification above.

**MDD APIs and staged extraction passed on the user's Mac.** The
core now includes binary resource packing, strict archive reopen, exact resource
lookup, conservative path/collision planning and descriptor-relative extraction
with exclusive directory publication implemented for macOS/Linux. The Mac report
passed all 13 gates: ten successful commands and three expected controlled
refusals. All six binary/font/CSS/Unicode/empty resources matched independent
Python and extraction inventories. Linux runtime qualification remains pending.
See `docs/M2-RESOURCES.md` for scope and retained exact source snapshots.

No MDD slice rerun, native-reader test, M1 batch or old foundation smoke rerun is
needed. TXT import/export and the first converter port are now Mac-qualified above;
the earlier MDD report remains preserved at its exact qualified source snapshot.

**Current implementation: M2 studio-core foundation passed on the user's Mac.**
The new `m2/` workspace exposes packing, strict reopen, versioned lookup,
structured errors, explicit budgets, progress and cooperative cancellation.
It retains conservative size limits and handles Studio MDX outputs only.
See `docs/M2-CORE.md` for the exact scope and remaining implementation work.

All ten commands passed, including Rust workspace tests, the two-encoding smoke
and eight separate-process lookups. Independent Python and wire checks passed
for both 15-record outputs. The report and matching source snapshots are retained
under `docs/evidence/m2-foundation-user-run`. No repeat of this slice, M1 or native
reader tests is needed. M2 remains partial. MDD resource APIs and staged
extraction are now Mac-qualified; converter/import work and larger
index limits remain subsequent implementation work.

**M1 complete: scoped engine qualification, 2026-10-29.** The final Mac report
passed all eight gates, including Python contracts and the three Rust test
workspaces. Focused native Unicode checks also passed in both readers, including
required markers, all eight duplicates and restart, with no crashes.

**Selected for the next milestone:** mdictlib =0.2.8, maintained writer patches
and the versioned Studio adapter. See `docs/ENGINE-DECISION.md` for the review
decision and `docs/M1-CLOSEOUT.md` for scope and resource/error findings. Production
indexing, allocation limits, metadata generalization and application integration
remain implementation work. M0's full GUI behavior baseline is still partial.

No further M1 commands or native tests are requested. Keep .venv, vendor and your
existing outputs when updating in place. studio-core implementation has now
started in the separate M2 workspace; the Tauri UI follows that core work.

The sections below retain historical batch instructions for reproduction.
Completed batches do not need to be repeated.

**Completed batch: versioned casing in MDX sorting and lookup.** The reviewed
Unicode16 data is now embedded and pinned. Run
`.venv/bin/python scripts/integrated_casing.py --output integrated-out` and return
`integrated-out/integrated-casing-report.json`, plus any named failure log.
This checks four real MDX files, shared sort/lookup policy, separate-process reopen
and policy-mismatch refusals. No data regeneration, scalar sweep, native reader
tests or real corpus is needed. See `docs/INTEGRATED-CASING.md`.

**Completed candidate step: explicit casing versions.** The Unicode run found 28 scalar
differences between Python16 and Rust17. Run
`.venv/bin/python scripts/casing_policy.py --output casing-out` and return both
`casing-out/casing-policy-report.json` and `casing-out/unicode16-casing.json`.
This generates a Python16 policy-data candidate and checks it in Rust, including
contextual sigma and newly cased characters. No existing engine/export policy is
changed and no native testing is needed. See `docs/VERSIONED-CASING.md`.

**Previous step: Unicode profile qualification.** The explicit literal-header
candidate passed offline and user-reported native testing in both encodings and
readers with no missing entries or crashes. Do not repeat that previous batch.
Run `.venv/bin/python scripts/unicode_profiles.py --output unicode-out` and return
`unicode-out/unicode-profile-report.json`, plus any named failure log. This checks
Python/Rust single-scalar lowercase mappings and selected Unicode sort/lookup
edges. No real corpus, fonts or large stress run is needed. Wait for report review
before native testing of these new files. See `docs/UNICODE-PROFILES.md`.

**Previous step: finish the existing header batch.** The uploaded conflict log
confirms a correct upstream rejection. The old checker required the wrapper's
different wording and reported a false failure. After updating in place, run
`.venv/bin/python scripts/finalize_header_lookup.py --output header-out`.
This reuses your verified files and rechecks only the final conflict refusal;
it preserves the original report and prepares native candidates on success.
See `docs/HEADER-LOOKUP.md` for the subsequent reader checks.

**Full batch for a new run: explicit headers and lookup behavior.** Run
`.venv/bin/python scripts/header_lookup.py --output header-out` and return
`header-out/header-lookup-report.json`, plus any log named by an error.
The new literal candidate uses canonical StripKey=No, HTML metadata and the
previously tested punctuation-preserving comparator. Separate diagnostics retain
both original legacy comparators. Alias handling, conflicting flags and duplicate
groups crossing key blocks are checked. Do not import these files into readers
until the report is reviewed. See `docs/HEADER-LOOKUP.md`.

**Latest result: fresh packing subset passed.** All 14 MDX and two MDD cases
passed on the user's Mac; no rerun is needed. Header/lookup policy remains open:
Rust uses StripKey=No while the legacy MDX writer uses Stripkey=Yes and emits
additional format defaults. Full native lookup equivalence is not yet proven.

**Completed batch: fresh-source packing parity.** Strict checksum qualification
passed on the user's Mac. Install the pinned oracle dependencies with
`.venv/bin/python -m pip install mdict-utils==1.3.14 openpyxl==3.1.5`, then run
`.venv/bin/python scripts/fresh_pack.py --output fresh-out`.
Return `fresh-out/fresh-pack-report.json`, plus any log named by a failure.
This batch verifies the six original converters against their golden outputs,
then compares fresh Python/Rust packing under both legacy C-locale profiles.
It does not implement Rust XLSX conversion. No real corpus, fonts, native reader
tests or large stress rerun is needed. See `docs/FRESH-PACK.md`.

**Previous step: bounded stress and failure recovery.** The real rebuild has now
passed offline checks and user-reported native testing in both readers. Run
`.venv/bin/python scripts/stress_qualification.py --output stress-out`.
Return `stress-out/stress-report.json`. These are offline fixtures only: do not
import stress/damaged files into native readers. See `docs/STRESS-QUALIFICATION.md`
for volumes, measured RSS scope, watchdog limits and remaining M1 gates.

**Previous step: real dictionary rebuild/reopen.** Synthetic MDD rendering now
has user-reported success for both encodings in both readers. Run
`.venv/bin/python scripts/real_rebuild.py --manifest baseline/real-corpus-manifest.json --output rebuild-out`.
See `docs/REAL-REBUILD.md` for the optional Amiri path override and exact scope:
new key/record blocks with preserved source header bytes and physical order.
Original files are read-only. Only a fully verified corpus and declared
companions are published under `rebuild-out/verified-dictionaries/`.

The first real rebuild has now passed all four files and is waiting only for
Amiri. Use `scripts/finalize_real_rebuild.py` with the existing `rebuild-out`
and the original dictionary font path; see `docs/REAL-REBUILD.md`. This rechecks
existing hashes and publishes without repeating compilation or dictionary scans.

**Previous step: MDD resources.** Corrected stylesheet controls have now passed
user-reported UTF-8/UTF-16 visual and restart tests in both readers. Run
`.venv/bin/python scripts/resource_controls.py --output resource-out`.
On offline success, test the matched `06-mdd-resources-utf8.mdx` and `.mdd`
together. See `docs/MDD-RESOURCE-CONTROLS.md`. The custom font must show triangle,
plus and diamond shapes; ordinary ABC is a fallback and does not pass.

**Previous step: reference-matching Rust stylesheet candidate.** The official
reference now passes visual testing in both readers. Run
`.venv/bin/python scripts/stylesheet_controls.py --wire-candidate --output style-wire-out`.
On offline success, test `05-stylesheet-wire-utf16.mdx` alone in each reader.
See `docs/STYLESHEET-WIRE-CANDIDATE.md` for expected formatting and stop conditions.
This wrapper candidate adds the final stylesheet LF; definition text and the
v5 engine remain unchanged. Native success is not yet established.

**Previous step: official-builder reference comparison.** The stylesheet controls
failed native compatibility: MDict crashes; GoldenDict marker formatting is
missing. Do not repeat those imports. Use the ready source kit in
`baseline/reference-builder-kit/` with your MdxBuilder 3.0 RC1 and return
`official-stylesheet.mdx`. See `docs/REFERENCE-BUILDER-COMPARISON.md` for exact
settings and the optional comparison command. The Windows reference build has
not been run here; no native fix is claimed.

**Previous step: stylesheet rendering.** All six minimal v5 controls now
have successful native entry-lookup reports in MDict and GoldenDict. Prepare
the MDX-only inline-versus-marker controls with
`.venv/bin/python scripts/stylesheet_controls.py --output style-out`.
Return `style-out/stylesheet-controls-report.json` before importing these new
files. See `docs/STYLESHEET-CONTROLS.md`. Stylesheets and MDD remain unverified.

**Previous offline step:** revision 4 passed the user's wire checks on all 16 files.
The isolated revision-5 HeaderLiteralC comparator preserves punctuation/spaces
and is exercised by six minimal MDX controls, without stylesheet or resources.
Run `.venv/bin/python scripts/minimal_reader_controls.py --output minimal-out`.
Return `minimal-out/minimal-controls-report.json` before native imports.
See `docs/MINIMAL-READER-CONTROLS.md`. Revision 5 is uncompiled locally.

**Exact crashing binary inspected:** all 13 MDX definitions lack encoded terminal
NULs; headers omit legacy fields. An isolated v4 writer/profile candidate adds
the terminators before offsets/checksums are calculated and fills these header
gaps. The user has now passed its offline checks; it is not a confirmed native
fix. Native imports remain paused.

**Native compatibility blocker (2026-10-28):** the user reports that importing
the UTF-8 mdict-utils reader fixture pair crashes a reader and prevents launch
until the pair is removed. Keep generated fixtures outside reader scan folders
and pause other fixture imports. The affected app and binary cause remain
unknown in that initial report. The subsequent crash log identifies MDict
2.2.6 (build 200) failing during launch with the UTF-16 mdxbuilder pair too.
The binary cause remains unknown; GoldenDict results are unreported.
Automated fixture checks do not override this failure. See
`docs/evidence/native-import-crash/observation.json`.

**Verified here:** six original converter classes run on synthetic data; nine
golden artifacts reproduce; all six Python characterization tests pass.

**Verified on the user's Mac:** the uploaded log reports all five Rust tests
passed, and the attached engine report records eleven successful synthetic
checks covering eleven entries and four resources. The exact uploaded
`Cargo.lock` and report are retained. Rust has not been rerun in this workspace.

**Sorting update:** the optional patch passed all four C-locale sort comparisons
on the user's machine, with multi-block exact lookups and duplicate checks.
The original default comparisons remain unchanged. The uploaded experiment
lockfile and sorting report are preserved. No production engine is selected.

**Interoperability update:** revision 2 passed all 14 synthetic cross-engine
checks on the user's Intel Mac (Python 3.14.7, Rust 1.98.1, mdict-utils 1.3.14).
The original uploaded passing report and its source fingerprints are retained.

**Still open:** legacy encodings,
metadata/stylesheets, external readers, large files and cross-platform checks.
M0 remains partial; M1 is complete within the recorded qualification scope.
See `docs/STATUS.json` and `docs/ENGINE-DECISION.md` for the reviewed status.

**Real dictionary update:** an independent local structural audit passed all
296,110 records across the three attached MDX files and all 17 CC-CEDICT MDD
resources. Original hashes are retained; no input binaries are bundled.
This is not a Rust/Python comparison or native reader pass. New marker-style
controls and a streaming real-corpus comparison are prepared for the Mac;
follow `docs/READERS-AND-REAL-CORPUS.md`.

**User-run corpus comparison passed:** Rust and Python match all 296,110 MDX
records and 17 MDD resources, all metadata attributes and 36 sampled lookups.
Input hashes are unchanged. MDict for macOS 2.2.6 (build 200) and GoldenDict
26.6.1-7548db1682 are recorded for the remaining native rendering checks.
The latest evidence is under `docs/evidence/real-corpus-user-run`; visual
results remain NOT_RUN and no identical corpus rerun is needed.

The first failed interop report remains included as historical evidence.
The metadata/storage-codec user run passed 77/111 observations, including all
28 Rust checks. Failures identify XML stylesheet whitespace semantics, Python's
UTF-16 label handling, and unsupported legacy writer arguments (plus dependent
missing-file errors). Original report and log are preserved. An isolated v3
UTF-16 label candidate was subsequently tested for UTF-8 interop; its codec
qualification remains pending. Stylesheet semantics remain unresolved.
See `docs/METADATA-CODECS.md` for the next run.

Latest completed v3 result: 91 passed, 10 standard-XML stylesheet differences,
2 unsupported GB18030 writes and 8 blocked dependent checks. UTF-16 fixtures
now pass in both directions under both profiles. All 28 Rust observations and
the separate 14-check UTF-8 interop suite pass. The stylesheet contract, native
readers, real dictionaries and scale remain open. Original reports and logs are
preserved; no identical rerun is needed. See `docs/METADATA-CODECS.md`.

## Contents

- `baseline/legacy/`: unmodified selected Python sources, license and build files.
- `baseline/source-manifest.json`: source provenance and asset hashes.
- `baseline/cases.json`: human-readable synthetic fixture specification.
- `baseline/expected/`: six converter outputs and normalization/sort/metadata oracles.
- `baseline/test_baseline.py`: executable characterization tests.
- `crates/studio-engine-probe/`: Rust qualification library and CLI tested on the user's Mac.
- `Cargo.lock`: exact dependency resolution from that run.
- `docs/evidence/macos-user-run/`: original report and evidence hashes.
- `scripts/legacy_interop.py`: optional cross-engine assertions.
- `.github/workflows/qualify.yml`: prepared Windows/macOS/Linux engine checks and Python checks.
- `docs/`: behavior inventory, engine gates, status and manual reader matrix.

## Run the verified baseline

```sh
python -m pip install -r baseline/requirements.txt
python -m unittest discover -s baseline -v
python baseline/run.py check
```

Materialize synthetic input files for manual checks:

```sh
python scripts/make_inputs.py out-inputs
```

Use `baseline/run.py record` only when intentionally accepting baseline changes.
Check mode never replaces expected files. The original source archive is not
required to run checks: selected sources are included and hash-checked.

## Run M1 on a Rust-enabled machine

```sh
cargo test --workspace --locked
cargo run --locked -p studio-engine-probe -- prove baseline/cases.json out-next
```

Read `docs/ENGINE-QUALIFICATION.md` before interpreting results. Passing the
synthetic subset is not engine selection. Two sorting profiles, legacy codec
support, metadata/style fidelity and external readers remain release gates.

The workflow is prepared for this directory as a repository root. No remote
repository, workflow run, commit or pull request has been created.

`out-next` must not already exist; retain the earlier `out` directory for manual
reader checks. `--locked` refuses dependency changes. The Rust compiler version
is not pinned because the uploaded evidence does not identify it.

Validate the retained report and lockfile:

```sh
python scripts/validate_evidence.py
```

## Alternative engine inspection

The uploaded Safari77 forks are retained unchanged under `reference/`.
`docs/SAFARI-FORK-REVIEW.md` explains why their implemented ZDB v3 builder is
not a drop-in classic v2 writer. A user-run observation report is now retained:
physical reads passed but exact lookup, Big5 sort-key and source loading checks
show failures. Neither fork has been run in this workspace.

```sh
python scripts/check_safari_sources.py
cargo run --manifest-path experiments/safari-probe/Cargo.toml -- safari-out
```

The observation adapter is a separate workspace and requires its own dependency
resolution. Successful exit means a report was written, not all checks passed.
The optional mdictlib patch experiment has passed its synthetic subset on the
user's machine; see `docs/LEGACY-SORT-EXPERIMENT.md`. Neither experiment is a
selected production engine change. Next, follow `docs/METADATA-CODECS.md`.

## License and provenance

Legacy files retain their AGPL-3.0 license (`baseline/legacy/LICENSE`). New
qualification code in this package is supplied under AGPL-3.0-or-later.
Synthetic examples are authored for tests; no production dictionary dataset
or proprietary font has been redistributed. The uploaded mdict-editor source
was inspected for dependency/API usage but is not bundled in this package.
The Safari77 reference snapshots retain their original license notices.
