# Database publication failure qualification

The preceding seven-record MDX → SQLite → MDX fixture passed independent
checks for UTF-8 and UTF-16. Both rebuilt files matched the original SHA-256,
including nonempty numeric stylesheets. The user completed reader checks;
screenshots show blue marker text, bold text and duplicate definitions in
MDict/GoldenDict, with explicit UTF-8 and UTF-16 examples.

This next step checks failed publication. Production conversion code and
supported limits are unchanged. Only one native adapter regression test and
a focused qualification runner are added.

From the updated project root, keeping the existing vendor tree and caches:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m4_database_failures.py --output m4-database-out-failures
```

Choose a new output name if it exists. The runner uses the existing Rust setup
offline and freezes each isolated M3 lock after approved dependency checking.
It does not install anything, read real dictionaries or use the GUI. Native
tests create small fixtures in private temporary directories and clean them up.
The output folder holds only logs and a source-bound JSON report.

| Test | Required behavior |
| --- | --- |
| Existing destination, both directions | `destination_exists`; sentinel bytes unchanged |
| MDX with damaged header checksum | `integrity`; no SQLite output |
| File without a SQLite header | `invalid_input`; no MDX output |
| Failure cleanup | No unexpected destination-directory files; source bytes unchanged |
| Job recovery | Failed jobs have no receipt; forgotten jobs disappear; later conversion succeeds |
| MDX import cancellation | Cancel during decode and before commit, for UTF-8 and UTF-16; no output |
| MDX rebuild cancellation | Cancel during spool, copy, verification and before commit; no output |
| Final destination race | A sentinel created just before commit survives unchanged |

Cancellation uses existing worker-level progress callbacks to stop at exact
phases. This is deterministic native publication coverage, not a claim about
GUI click timing. Adapter tests cover the ordinary shared worker and result
lifecycle. Exactly one passing Rust test is required per selected test name;
a successful Cargo command that ran zero tests is rejected.

Expected status: `database_failure_checks_passed`. Share
`m4-database-out-failures/m4-database-failures-report.json` if any step fails.
The user subsequently returned `database_failure_checks_passed` from the Mac.
All three selected tests passed, including compilation and execution of the
new adapter test. The runtime and adapter dependency checks also passed.
This qualifies the listed native assertions; GUI click cancellation remains
the separate next step in `M4-GUI-CANCEL.md`.
