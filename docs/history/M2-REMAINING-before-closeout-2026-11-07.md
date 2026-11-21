# M2 remaining work: backend closeout ledger

Reviewed 2026-10-30 against the implemented code, accepted user-run reports and
the conditions in `ENGINE-DECISION.md`. M2 is still partial. This ledger replaces
the stale top-level remaining list; it does not relabel earlier evidence or
claim production capabilities from bounded tests.

**Three work areas remain: production sizing/indexing/resource limits, real-input
qualification and final closeout.** These are work areas, not a promise of three
small test runs. A failure or a material change can require another iteration.

## Completed in the tested envelope

| Area | Accepted evidence |
| --- | --- |
| Versioned MDX v2 packing, strict reopen and duplicate-aware lookup | `m2-foundation-user-run` |
| MDD packing, resource lookup and staged safe extraction on macOS | `m2-resources-user-run` |
| Explicit TXT profiles and UTF-8 CC-CEDICT converter | `m2-text-user-run` |
| Common-cell XLSX normalization | `m2-xlsx-user-run` |
| Five MOE converters against original Python plugins | `m2-moe-user-run` |
| Shared native application job/progress/error/cancellation API | `m2-application-user-run` |
| Bounded serial background worker and polling mailbox | `m2-jobs-user-run` |
| Background MDX pack/export and MDD manifest pack/extract | `m2-dictionary-jobs-user-run` |
| Bounded ordinary v2 MDX/MDD reader, lookup and redirects | `m2-v2-import-user-run` |
| One-shot ordinary v2 application API and serial import worker | `m2-import-jobs-user-run` |
| Metadata-only rebuild and native stylesheet controls | `m2-metadata-user-run`, `m2-metadata-native-user-confirmation` |
| Metadata-aware fresh packing and serial publication | `m2-metadata-jobs-user-run`, `m2-metadata-jobs-native-user-confirmation` |

These folders live under `docs/evidence`. No routine rerun of these accepted
batches or of M1/native-reader tests is requested by this review.

## 1. General v2 import and lookup — accepted bounded profile

The original Studio export verification still requires its policy tags and
narrow metadata profile. A separate ordinary-v2 import API now opens existing
unencrypted UTF-8/UTF-16 MDX/MDD without weakening that export verifier.

- Define an explicit supported v2 import profile, beginning with unencrypted
  UTF-8/UTF-16 MDX/MDD, rather than removing the Studio checks from export reopen.
- Retain strict checksums, physical record identity, duplicate order and exact
  resource bytes. Imported header flags and lookup normalization need an explicit
  contract; do not silently apply the Studio literal policy to foreign inputs.
- Add bounded redirect resolution with missing-target, cycle and depth errors.
- Route imports through the common error/cancellation boundary. Unsupported
  versions, encodings, encryption and policies must remain explicit refusals.

Exit evidence: independent readers agree on records/metadata, duplicate-aware
lookup and redirect boundary cases pass, corrupt/unsupported files fail cleanly,
and existing Studio export verification stays unchanged.

This area is accepted within the bounded one-shot profile. Legacy v1 and v3
are not included in the v2 import claim.

2026-11-01 update: the isolated ordinary-v2 reader, explicit lookup policies and
bounded redirect resolver are authored in `m2/v2-import`; see `M2-V2-IMPORT.md`.
Mac compilation, the corrected Rust test command and all 26 independent process
cases passed. The bounded synchronous reader/lookup/redirect subgate is accepted;
application/background import routing also passed in the subsequent batch.
See `docs/evidence/m2-v2-import-user-run`.

The application composition and dedicated import worker are now authored under
`studio_v2_import::application`; see `M2-IMPORT-JOBS.md`. They reuse the shared
job vocabulary while leaving the existing conversion/packing worker unchanged.
Mac compilation and all 56 sync/background qualification commands passed:
27 case pairs, including 15 matching successes and 12 expected failures.
Area 1 is complete within this envelope. See `docs/evidence/m2-import-jobs-user-run`.
Persistent dictionary sessions, GUI adapters and a combined queue for all work
are not claimed. The next implementation area is metadata/stylesheet preservation.

## 2. Metadata and stylesheet preservation — accepted bounded profile

The original narrow Studio-only core output remains unchanged. The explicit
ordinary-v2 metadata API now adds multiline title/description and numeric
stylesheets to metadata-only rebuilds and fresh MDX/MDD publication. Earlier M1
failures remain historical; acceptance concerns the declared new metadata profile.

- Preserve title, description, supported header values and numeric stylesheet
  triples through import/rebuild/export.
- Define XML escaping, multiline values and stylesheet terminal-LF behavior.
- Keep raw definition markers and stylesheet data consistent; do not replace
  preservation with undocumented inline formatting transformations.

Exit evidence: independent metadata/body comparisons and focused rendered reader
checks for newly changed stylesheet behavior. The earlier failed metadata report
remains historical evidence, not a success to be overwritten.

2026-11-02: the first metadata subgate is authored under
`studio_v2_import::application::metadata`. It rebuilds a header while retaining
all binary sections, verifies every physical record and publishes exclusively.
It defines separate XML-character-reference and native stylesheet-LF contracts.
The corrected Rust/offline batch passed: 14 rebuilds and 18 expected refusals,
with exact binary sections, metadata and physical records preserved. The two
native controls passed Python stylesheet expansion. The user subsequently
confirmed all five entries work without crashes in response to the MDict/
GoldenDict checklist for both files; the scoped attestation is retained in
`docs/evidence/m2-metadata-native-user-confirmation`. Source entry repacking and
a metadata publication worker remain to be implemented in this area.
See `M2-METADATA.md`. Area 2 remains open.

2026-11-03: metadata-aware fresh MDX/MDD packing and a dedicated publication
worker are authored under `metadata::publication`; see `M2-METADATA-JOBS.md`.
They reuse the accepted serializer and publisher and preserve the older workers.
The Rust test command and both process batches passed: 20 successful publications
and 36 expected refusals across the two routes, with metadata/physical records
and source identities verified. Fresh-packing native controls passed Python
stylesheet expansion. The user then confirmed all five entries correct, without
crashes or missing entries, in response to the two-file MDict/GoldenDict checklist.
The scoped attestation is retained in
`docs/evidence/m2-metadata-jobs-native-user-confirmation`. Area 2 is complete
within the bounded `mdict-v2-metadata-v1` profile. Standard XML/native whitespace
differences and explicit refusals remain documented; this is not universal
metadata/native behavior or a production-size guarantee. Area 3 is next.

## 3. Production sizing, indexing and resource limits

2026-11-06: the first larger six-converter/shared-admission gate passed on Mac in
`m2/converter-runtime`; see `M2-CONVERTER-RUNTIME.md`. The original E0753 failure is
retained. Corrected Rust test/build receipts and six controller scenarios passed:
six successful conversions, 35 expected failures and 48 pre-cancelled jobs. Review
independently reran the original Python converters on regenerated full fixtures,
recomputing 68,000 normalized records and checking 2,964 controller exchanges.
All final shared reservations and reader retention were zero; peak RSS was
183.67 MiB rounded. Evidence/sources/oracle receipts:
`docs/evidence/m2-converter-runtime-user-run`; no rerun is needed. Revised/Concise
raw set-order differences remain the documented narrow comparison. Full candidate
ceilings and hard RSS enforcement are not established. Representative real inputs,
index-build admission and final backend closeout remain open.

2026-11-05: the first shared larger-publication-runtime gate passed on Mac in
`m2/publication-runtime`; see `M2-PUBLICATION-RUNTIME.md`. The original E0223
fixture-constructor failure is retained; the corrected Rust command receipts and
two controller scenarios passed. Review checked 3,331 exchanges, nine successful
publications, eight expected job failures and 16 precancelled jobs, recomputing
196,608 reported record fingerprints, four export hashes and four extraction
file hashes. Reader overlap with packing/export was observed; all final shared
reservations and reader retention were zero. Peak RSS was 103.45 MiB rounded.
Evidence/sources: `docs/evidence/m2-publication-runtime-user-run`; no rerun is needed.
The logical 384 MiB admission profile is not OS memory enforcement. Converter
sizing/admission is next, followed by real-input qualification and final closeout.

2026-11-05: the first larger packing/export gate passed on Mac in `m2/large-io`;
see `M2-LARGE-IO.md`. Rust test/build receipts and 47 process cases passed:
16 publications and 31 expected refusals. Both MDX encodings and the MDD have
65,536 records/resources; a 1 MiB definition passed. Review recomputed 327,681
reported record fingerprints and seven export file hashes. Maximum RSS was
100.25 MiB rounded for packing, 4.04 MiB for exports. Evidence and exact sources:
`docs/evidence/m2-large-io-user-run`; no rerun is needed. This does not raise old
worker defaults, implement a streaming dictionary writer or qualify every cap
combination. Shared runtime admission for this path is next; converter sizing,
real inputs and final closeout remain open.

2026-11-05: background streaming extraction and shared active admission with
persistent reader sessions passed their first Mac gate in `m2/extraction-jobs`; see
`M2-EXTRACTION-JOBS.md`. Late-cancel publication semantics, managed close/release
barriers and reader/extractor contention passed the Rust command and three process
scenarios. Review recomputed 4,101 reported file hashes and examined 1,166 controller
exchanges; final reservations were zero. Evidence:
`docs/evidence/m2-extraction-jobs-user-run`; no rerun is needed. Earlier runtime
sources remain unchanged. Larger packing/conversion paths, real inputs and final
M2 closeout remain open.

2026-11-05: the streaming-MDD-extraction subgate passed its first Mac gate in
`m2/stream-extract`; see `M2-STREAM-EXTRACT.md`. It preflights bounded path/size
metadata, copies spans with record materialization disabled, verifies staged
files and publishes exclusively. Corrected Rust test/build commands, four
successful extractions and 26 expected refusals passed; 4,105 reported file
hashes were recomputed. Evidence: `docs/evidence/m2-stream-extract-user-run`.
No rerun is needed. Larger
packing/converter paths, shared publication admission, real inputs and final
M2 closeout remain open.

2026-11-05: persistent application sessions and per-session background open/page
jobs passed their first Mac gate under `m2/sessions`; see `M2-SESSIONS.md`.
Rust test/build receipts and five process scenarios passed; 37 page replies and
497 controller exchanges were independently reviewed, with all final logical
reservations released. Evidence: `docs/evidence/m2-sessions-user-run`; no rerun
is needed. Index construction and existing converter/
packing workers remain separate. Larger extraction/packing/converter paths,
real-input qualification and final M2 closeout remain open.

2026-11-03: the disk-index/paged-lookup subgate passed on Mac in
`m2/indexed-engine`; see `M2-INDEX.md`. It uses bounded external sorting, complete
source SHA-256 binding, full cache semantic verification and exact-first frozen16
matching. Rust test/build commands, 12 builds, 20 query runs (180 recomputed
pages) and 23 expected refusals passed. Sources/report are retained under
`docs/evidence/m2-index-user-run`; no rerun is needed. It does not claim fast startup,
new larger application/session routing or completion of area 3.

2026-11-03: the first sizing subgate passed on Mac in `m2/bounded-engine`; see
`M2-SIZING.md`. It uses explicit mdictlib limits and complete lazy scans without
a full owned dictionary or lookup locator, plus larger independent fixtures,
hostile declarations and process-RSS measurements. Rust test/build commands and
all 29 process cases passed (eight successes, 21 expected refusals). The largest
MDX scanned 262,144 entries / 64 MiB logical bodies at 4,677,632 bytes observed
peak RSS. Accepted report and sources: `docs/evidence/m2-sizing-user-run`.
Full candidate ceilings remain unqualified; no rerun is needed. Existing small
application caps remain unchanged. Persistent indexes,
larger writer/resource/converter paths and aggregate admission follow; area 3
has not been marked complete.

Current defaults retain a qualification envelope: 1,000 output entries, 8 MiB
decoded rows and 16 MiB files; XLSX has a separate 10,000-row default. In-memory
indexing and post-decompression checks do not establish production memory limits.

- Choose measured application size/memory targets for actual dictionaries and
  spreadsheets instead of merely raising probe caps.
- Implement the required file-backed/index or bounded traversal strategy and
  enforce expansion/allocation limits before decompression/materialization where
  required. Audit temporary copies, result/event serialization and resource reads.
- Carry cancellation, stable duplicate identity, complete-or-error results and
  no-clobber publication through the larger paths.

Exit evidence: realistic large-data measurements, adversarial expansion/count
declarations, bounded result behavior and cancellation/failure cleanup on the
supported platform. No multi-gigabyte or hard-RSS claim follows from current tests.

## 4. Representative real-input qualification

2026-11-07 update: full standalone Revised/WFG grouped TXT publication passed on
Mac: 162,636 Revised entries (1,454 aliases) match the qualified normalized Python
reference; 161,182 WFG entries match Python raw bytes. All 30 process cases passed,
including six publications and 24 expected refusals. Review checked exact source/
lock bindings and independently recomputed small original-plugin outputs and the
full source group plan (161,182 groups, largest six rows / 11,220 bytes; index plan
54,397,924 bytes). Release RSS max was 160.35 MiB, below the provisional 256 MiB
observation target. Evidence: `docs/evidence/m2-revised-render-user-run`, twelve
source snapshots; no rerun needed. All 253 prior identities remain unchanged
(265 including this gate). Shared background/admission integration for these new
profiles remains next; standalone parity does not complete M2 or real packing.

2026-11-07 update: the full Revised disk-backed normalized-row gate passed on Mac.
All 163,909 rows / 2,950,362 fields matched original-helper references. Review checked
27 process cases (10 successes, 17 expected refusals), both native command receipts,
source/lock bindings and independently recomputed SST/JSONL private-file extents.
Full source release RSS was 152.44 MiB; max all cases 156.45 MiB, below the provisional
192 MiB target. Exact report, independent review metadata and twelve source snapshots
are retained under `docs/evidence/m2-xlsx-spool-user-run`; no rerun needed. All 241
prior identities are unchanged (253 including this gate). See `M2-XLSX-SPOOL.md`.
Revised/WFG grouping, rendering and bounded publication now follow using verified
rows. This is not full native converter parity, application admission integration,
reader concurrency or M2 completion.

2026-11-07 update: full CC-CEDICT passed its exclusive 384 MiB admission / chunked
TXT publication gate on Mac. All 203,362 entries matched both independent local
and fresh Mac Python outputs exactly. Review checked 1,440 exchanges, seven job
refusals, two API refusals, source/lock identities and zero final reservations.
Peak reported RSS was 228.91 MiB. Exact evidence and twelve source snapshots are
retained under `docs/evidence/m2-cc-full-user-run`; no rerun needed. All 229 prior
source identities remain unchanged (241 including this gate). Native test/build
return-code receipts cover reader contention; full-data controller ledgers show
exclusive reservations, without opening readers. No hard RSS/all-input claim.
Revised/WFG worksheet-memory work and full-source qualification remain next.

2026-11-06 update: the complete Concise gate passed on Mac with its explicit
50,000-row / 750,000-cell profile. All 45,178 data rows produced 44,445 entries,
matching both independent local Python references under the accepted reference
set-order normalization. Review checked all 893 controller exchanges, six typed
job refusals, one wrong-converter refusal and zero final reservations. Evidence:
`docs/evidence/m2-concise-full-user-run`, twelve source snapshots; no rerun needed.
All 217 prior source identities remain unchanged (229 including this gate).
Peak process RSS was 326.64 MiB, below the provisional 384 MiB target but above the
256 MiB logical conversion charge. Production admission sizing/full-size reader
concurrency remains open. See `M2-CONCISE-FULL.md`. CC-CEDICT and Revised/WFG still
need measured scaling; M2 is partial.

2026-11-06: all four official MOE workbooks and CC-CEDICT were fully inspected;
all six captured original Python conversions completed. Mini (4,311 records) and
Idioms (5,489) passed their full Mac comparison using the unchanged native
profile. Both complete TXT outputs matched original Python references; review
checked 732 exchanges, source/lock bindings and zero final reservations. Peak
observed RSS was 193.10 MiB. Exact evidence is retained in
`docs/evidence/m2-official-converters-user-run`; no rerun is needed.
Concise exceeded the original row/rectangle limits and subsequently passed its
explicit profile above. CC-CEDICT and Revised/WFG
exceed output entry/byte limits; Revised also exceeds worksheet/part limits.
See `M2-OFFICIAL-CONVERTER-SOURCES.md` and its source-bound metadata evidence.
All 214 accepted source identities remain unchanged. No data is sampled and no
native caps have been raised. Source sizing does not close this work area.

2026-11-06: the first selected real dictionary reader/index/session/extraction
gate passed on Mac; see `M2-REAL-READERS.md`. Three MDX files have 296,110 entries
and the MDD has 17 resources. Full scan comparisons, verified caches, 36 raw-exact
pages and extraction passed; review checked 346 exchanges and cross-checked M1
source/count/extent evidence plus all resource hashes. Final reservations and
reader retention were zero; peak RSS was 12.08 MiB rounded. Report/sources:
`docs/evidence/m2-real-readers-user-run`; no rerun is needed. Real converter-source
and workbook pipelines, full fresh-packing real workflows, index-build admission
and final closeout remain open. This does not close area 4 universally.

Apply the finished application paths above to representative original v2
dictionaries/MDD resources and real MOE/CC-CEDICT source data at the chosen target
sizes. Existing M1 real-dictionary engine evidence remains valid but does not
qualify a newly implemented application importer or full real spreadsheet ports.

Compare counts, payloads, duplicate order, resources, metadata and converter
outputs independently. Record any intentional ordering differences. Keep private
corpora outside the distributable package. Broaden only where changed paths or
new failures justify it; do not repeat every old native test routinely.

Exit evidence: source-bound reports for the supported real input classes and
measured limits, with unsupported classes stated accurately.

## 5. Final backend closeout

After areas 1–4 pass, reconcile the support matrix and run the regression checks
needed to cover their interactions. Record exact sources/locks, outstanding
limitations, publication/cancellation behavior and the decision on readiness for
Tauri wiring. Do not mark M2 complete simply because every existing small
synthetic batch passed.

## Subsequent application work and explicit deferrals

The Tauri shell, modern GUI, Chinese/English/Arabic localization and RTL,
isolated rendered preview, packaging, Python plugin IPC and additional platform
qualification remain in the full application roadmap. They are not counted as
extra backend implementation areas in this five-item ledger.

Per the user's instruction, MDX v3 packing/unpacking will be planned later.
Legacy v1/LZO/ISO8859-1 import and additional protected/encrypted formats also
require their own declared scope and qualification; the inspected Latin sample
is not proof those paths are implemented. No new format work is started here.
