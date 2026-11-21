# Real dictionary sizing and performance checkpoint

This is checkpoint 2 of the three Database closeout checkpoints. It measures the accepted database operations on a real dictionary and verifies behavior near the current profile boundaries. It does not change production code, dependencies, limits, deadlines or admission settings.

Close the app before updating the project. On the Mac, run from the project root using a fresh output folder:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m4_database_sizing.py --output m4-database-out-sizing
```

A macOS file picker asks you to select a **real MDX dictionary**. Choose one within the current profile: up to 100,000 records, 32 MiB decoded headwords plus definitions, 128 MiB input/output files, 4 KiB per headword and 1 MiB per stored definition. The original dictionary remains unchanged. You can instead provide `--mdx '/absolute/path/to/dictionary.mdx'` to avoid the picker or to run outside macOS. The test is for the MDX definitions; MDD resources are separate.

The runner performs the full desktop gate and compiles a separate adapter example. It uses the same publication jobs and persistent database reader as the GUI:

1. Import a synthetic source with **100,000 records** and just under **32,000,000 decoded bytes** (over 95% of the 32 MiB cap). Keep three separate duplicate records.
2. Open one validated snapshot, run first/last browsing, exact lookup, prefix lookup and definition search **five times each**, then close the snapshot and export JSONL. Python checks every sampled row ID/body/order, result count, pagination, source hash, full exported rows and released admission lease.
3. Refuse synthetic sources above 100,000 records and above 32 MiB decoded text. The native adapter must return `limit_exceeded`, preserve its source and leave no database or staged output.
4. Independently decode the chosen real MDX, convert all supported records to SQLite, verify every row and stored MDX metadata, run the same repeated lookups and check a complete JSONL export. A real query uses one result per page to avoid needlessly filling the response envelope with large definitions.

The report records import time, validated snapshot open time, export time, and first, warm median, minimum, p95 and maximum query round-trip times. Each query has five samples. Timings exclude compilation and Python verification, include adapter calls/polling (1 ms polling interval), and are specific to this Mac and input. OS file caches are not cleared; first-sample time is not a proven cold-cache measurement. GUI painting, RSS/peak memory, crash recovery and OS-level resource enforcement are not measured. Correctness and controlled refusal determine pass/fail; no universal speed threshold is asserted. The report records OS release and architecture without hostname. Raw lookup pages and full exports remain in the local output folder; the summary report contains counts, hashes and timings rather than definition text.

A successful supported real input produces:

```text
status: database_sizing_native_and_oracle_passed
m4-database-out-sizing/report.json
```

Send that report for review. If the real source exceeds a known profile bound, the runner verifies the native controlled refusal and reports `sizing_passed_real_input_refused_choose_supported_dictionary` with exit code 1. **That does not complete checkpoint 2**: rerun with a supported real dictionary and a fresh output folder. Unsupported/malformed inputs, other failures and unexpected refusal codes produce a failed report. Inputs are never silently truncated or sampled as substitutes for full real-dictionary conversion. Larger dictionaries, including a CC-CEDICT version over 100,000 records, still require a separately qualified larger profile.

The generated synthetic inputs, databases, exports, configurations, raw adapter results and logs stay in `m4-database-out-sizing`; packaging excludes these outputs. The real MDX is read at its selected path, not bundled. Local oracle unit tests exercise limit boundaries and tampered query results but cannot qualify Rust compilation or performance. Native sizing and real-dictionary results remain pending until the Mac report passes. Final regression/evidence closeout remains checkpoint 3.


## Preflight update

The updated runner screens the selected MDX **before** native compilation, the desktop gate or synthetic sizing. See [M4-DATABASE-PREFLIGHT.md](M4-DATABASE-PREFLIGHT.md). A rejected candidate now writes `preflight_rejected_choose_supported_dictionary`, with exact first-violation details and observed-prefix counts; `native_tests_executed` and `native_jobs_executed` stay false. This is a Python preflight refusal, not a new native controlled-refusal qualification. The v2 report schema includes `preflight`. The old post-test generic-refusal status described above is retained only in historical package-162 evidence. A size-fitting candidate proceeds with the full test, and only native/oracle success qualifies the real dictionary.

You can screen candidates without creating a sizing output directory:

```sh
.venv/bin/python scripts/m4_database_preflight.py
```
