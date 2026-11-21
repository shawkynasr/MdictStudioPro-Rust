# Six full converter background profiles — qualified on Mac

All six complete datasets passed through the shared background runtime. The
accepted report is `docs/evidence/m2-full-converters-user-run/m2-full-converters-report.json`.
It is retained with 17 exact source snapshots, provenance and a repeatable receipt
review. No rerun is required for this gate. M2 remains incomplete.

| Converter | Entries | Peak RSS (MiB) | Request profile |
| --- | ---: | ---: | --- |
| CC-CEDICT | 203,362 | 191.23 | `cc` |
| MOE Mini | 4,311 | 124.91 | `small_moe` |
| MOE Idioms | 5,489 | 217.96 | `small_moe` |
| MOE Concise | 44,445 | 69.99 | `concise` |
| MOE Revised | 162,636 | 256.29 | `grouped_moe` |
| MOE Revised WFG | 161,182 | 158.53 | `grouped_moe` |

All final TXT hashes and counts match the previously accepted standalone native
references. Concise's receipt identifies its new `moe-concise-disk-groups-txt-v1`
pipeline; other conversion metadata remains equal. Earlier independent Python
output comparisons remain the oracle evidence, including the qualified
Concise/Revised reference-field ordering scope. This integration batch compared
accepted native output bytes rather than rerunning all Python output converters.

The complete Concise row reader also passed a fresh independent captured-Python
comparison: 45,178 normalized rows, 677,670 fields, 17,958,342 charge bytes, with
framing SHA-256 `98ab6f54f1a6500a3de22953b53af034ac3c0448675f0eed241347a4cb5de0a0`.
Its separate reader process peaked at 45,588,480 bytes (43.48 MiB), below its
192 MiB target. The reference was independently computed from the inspected
workbook locally and recomputed on Mac. Source values and definitions are not
bundled; only metadata, code, hashes and receipts are retained.

## Reviewed evidence

The three native commands succeeded: 33 Rust tests, release runtime build and
release row-reader build. The review verified 2,726 controller exchanges, the
exact 68-package dependency graph and 282 unique previous/new source identities.
None of the 265 previously qualified sources was changed.

For each full dataset, the report binds the conversion request, successful job,
thin receipt and accepted output hash. It checks overwrite preservation,
lowered-limit refusal, eight retained pre-cancelled jobs, retention overflow,
coalesced events, one-transfer results, late cancellation, forgetting all eleven
terminal jobs, shutdown and rejection after shutdown. Final reservations and
reader reply/handle retention were zero. Input identity and private cleanup are
assertions in the exact source-bound Mac harness; output file bytes and OS RSS
were measured there, not independently remeasured during receipt review.

Deterministic synthetic native tests cover reader contention and retry, queue
limits and queued cancellation, running cancellation, commit-winning late
cancellation, panic uncertainty with lease release, and lower-limit recovery.
Concise tests compare against the whole-table reference using matching bounded
limits, cover duplicate-headword grouping and cancel at indexing, rendering,
appending, verification, precommit and postcommit. Full-data runs deliberately
exclude overlapping readers; this is not a claim of simultaneous conversion and
reading of large dictionaries.

## Runtime and memory scope

Each conversion reserves 384 MiB logical memory and 768 MiB temporary capacity
within a shared 384 MiB / 4 GiB ledger (two operations maximum). Conversions exclude
readers, packing, export and extraction. Admission fails immediately when readers
hold capacity; close them, wait for cleanup and release handles before retrying.
The queue serializes publications and does not wait for reader capacity.
Reservations are accounting, not an OS memory limit. The independent process RSS
check remains 384 MiB; the maximum reported converter peak was 256.29 MiB.

Concise reads normalized rows from disk, indexes headword offsets and renders
one group at a time through the existing layout, avoiding the whole workbook
table and complete rendered-entry collection. The copied renderer/publication
logic is unchanged apart from dispatch, lower ceilings and module bindings. It
verifies canonical output after reopening, removes source spools before commit
and publishes without clobbering. Only prepared metadata is moved after commit.

The disk cell profile is the narrower General-numeric profile, with unsupported
number formats rejected. It is not every workbook supported by the older
calamine path. Concise ceilings include 50,000 worksheet rows, 750,000 cells,
32 MiB XML parts, 32 MiB normalized key/value charge, 32 MiB group index charge,
4,096 rows per headword, 16 MiB group input, 8 MiB group output, 100,000 entries,
32 MiB decoded output and 64 MiB TXT. Tighten options can only lower caps;
`workbook_decoded_bytes` limits normalized charge in this disk profile.

## Preserved attempts

The earlier reports are retained separately and remain failures: the first owned
Concise run exceeded RSS; the next test used default limits for its reference;
the corrected owned run still reached 420,204,544 bytes (400.74 MiB); and the first
disk embedding failed to compile because of a crate-root helper import. The
accepted run uses the corrected disk implementation and lowers Concise's measured
peak to 73,392,128 bytes (69.99 MiB). No memory ceiling was raised or waived.

## Reproduction and remaining scope

For reproduction only, merge the package into the existing directory, retain
`.venv`, `vendor` and previous outputs, and place the five inspected source ZIPs
in Downloads. Use a fresh excluded output directory:

```bash
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m2_full_converters.py --archives /Users/shawky/Downloads --output m2-full-converters-out-repeat
```

Next is real dictionary packing and index-build admission, followed by final M2
closeout review. This converter gate adds no MDX/MDD format capability and asks
for no independent dictionary-reader visual checks. Native commands were run on
the user's Mac; the local editing environment has no Rust toolchain.
