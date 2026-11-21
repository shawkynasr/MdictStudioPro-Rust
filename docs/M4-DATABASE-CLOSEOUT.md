# Database milestone closeout — final regression pending

Checkpoints 1 and 2 are accepted. The scoped Database feature set is implemented and has reviewed Mac native/oracle, user GUI and reader evidence. This final checkpoint consolidates that evidence and reruns the regression. **The final regression report is still required before marking this scoped milestone complete.** This is not full M3 completion, original-app parity or production release readiness.

## Qualified feature scope

| Area | Accepted scope | Retained evidence directory under `docs/evidence/` |
| --- | --- | --- |
| Storage and conversion | Supported closed SQLite schema; TXT and JSONL import/export; MDX v2 import/rebuild | `m4-database-qualified`, `m4-database-jsonl-qualified`, `m4-database-jsonl-import-qualified`, `m4-mdx-import-qualified`, `m4-mdx-rebuild-qualified` |
| Browse and search | Persistent validated snapshots, paging, exact/prefix, Unicode lowercase, whole-key patterns and stored-definition search | `m4-database-reader-gui-qualified`, `m4-database-case-qualified`, `m4-database-pattern-qualified`, `m4-database-definition-qualified` |
| Preview | Rendered/Split/HTML; Original/Paper/Dark; inline HTML and stored numeric stylesheet; scripts/network disabled | `m4-database-preview-qualified` |
| Metadata | Title, description and numeric stylesheet replacement into new copies | `m4-database-metadata-copy-qualified`, `m4-database-stylesheet-copy-native-reader-qualified` |
| Entry operations | Edit a selected definition, rename a selected key, delete one physical row, append an entry; keep duplicates separate | `m4-database-entry-copy-qualified`, `m4-database-rename-qualified`, `m4-database-delete-qualified`, `m4-database-add-qualified` |
| Publication | Snapshot/hash identity checks, shared worker admission, cancellation and no-clobber publication | `m4-database-failures-qualified`, `m4-gui-cancel-qualified`, plus later native tests |
| Combined workflow | Metadata/edit/rename/add/delete, UTF-8/UTF-16 MDX rebuild and independent reimport; user reader confirmation | `m4-database-workflow-qualified` |
| Sizing | 100,000-record / 31,999,991-decoded-byte synthetic source; over-limit refusals; 6,148-record real MDX import/lookups/export | `m4-database-sizing-real-qualified`, `m4-database-sizing-boundaries-qualified` |

Historical reports retain their original partial/pending status. Later scoped confirmations qualify only the features they record. The combined reader conclusion includes user confirmation; cropped screenshots do not independently label every reader/encoding combination. The nested shell reports referenced by uploaded parent reports were not always attached separately. The closeout manifest records exact hashes for 57 retained evidence files and 104 qualified M3/M4 production/fixture/example identities, as well as the protected M2 identities and dependency locks.

## Final command

Close the app, update the project, then run on the Mac from its root using a fresh output folder:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m4_database_closeout.py --output m4-database-out-closeout
```

The runner audits retained evidence and source bindings, runs baseline and Python contracts, verifies historical evidence/reference snapshots, then runs the combined workflow gate. That child gate executes the full Rust backend/runtime/adapter tests, frontend tests/build, Tauri check and both native workflow encodings with independent intermediate and MDX-reimport oracles. The already accepted real-dictionary benchmark is reused through its frozen evidence and unchanged production identities; there is no dictionary picker or repeated 100,000-record benchmark.

One known non-build prefix, `m3/desktop/mdict-studio-m0-m1/`, is excluded from the production comparison because Mac reports show an accidentally nested archive extraction there. Actual manifests build the outer project. The files are not deleted; complete runner source snapshots still record the nested tree. New source files in actual build trees are not excluded.

Expected status is `database_closeout_final_regression_passed_review_pending`. Upload `m4-database-out-closeout/report.json`. After review, the scoped closeout decision and status can be finalized without another feature or benchmark round. A failed run leaves the milestone pending and supplies its failed stage/log. The runner does not rewrite the manifest or claim completion merely because retained evidence passed an integrity audit. Newly rebuilt MDX artifacts have fresh automated checks; prior rendering evidence remains attributed to the earlier source-identical workflow and user tests.

## Limits and remaining work

The accepted Database profile remains at 100,000 records, 32 MiB decoded key/body text, 128 MiB input/output, 4 KiB per key and 1 MiB per stored definition. GUI edits/additions accept 8 KiB definition drafts within a 64 KiB complete command; oversized text is refused, never truncated. Read pages remain limited to 128 records and the existing 2 MiB response envelope. SQLite inputs must use the supported closed schemas, without live WAL/SHM/journal sidecars, triggers/views, arbitrary SQL or MDD resource tables. Copies preserve sources; existing destinations are not overwritten. Deleting the only row is refused.

MDX rebuilding remains v2, UTF-8/UTF-16 and the qualified stored No/No lookup flags. Other rebuild comparator policies require actual writer changes and reader qualification. Resources inside MDD are not edited through the Database feature or loaded by its static preview. Timing evidence is specific to the reported Darwin x86_64 execution environment and adapter operations; it proves neither GUI frame time, cold-cache behavior, RSS bounds nor native Apple Silicon execution.

Larger profiles (including the rejected full dictionaries), crash recovery, hard OS memory protection, wider original-app GUI parity, Windows/Linux release testing, installers/signing/updating and production release qualification remain separate. MDX v3 stays deferred. Accepted M1/M2 decisions and 324 protected source identities are unchanged.


## Platform audit correction

The first final-regression attempt stopped before native execution because two additional Mac files were not in the packaged source inventory. Neither an existing qualified source nor a lock changed. `platform-bindings.json` now binds the exact hashes of `m3/desktop/src-tauri/permissions/autogenerated/studio_call.toml` and `m3/fixtures/build-source_副本.txt` to their identities in the earlier passing package-163 Mac report. Those exact files are optional on other machines; if present, their bytes must match the qualified hashes. Different files, changed hashes and other additional build-tree files still fail. The nested archive exclusion remains unchanged. Audit errors now list missing, extra and changed source paths. No production code or limit changed; the final regression is still pending.

## macOS contract-runner correction

The second closeout receipt passed the 104-source / 324-protected-source audit,
then stopped in Python contracts before native execution. The shell orchestration
test now stubs platform identification separately from its subprocess mock. The
contract entry point canonicalizes the temporary root (macOS /var aliases
/private/var), preserving the historical protected reader test unchanged. The
historical CC receipt reviewer excludes only Finder's .DS_Store metadata from
its recursive inventory and reports exact missing/extra/changed paths; this
addresses a possible Finder inventory extra without presuming its identity from
the earlier generic error. Unexpected files and modified source bytes still fail.
Failure reports now retain the failed command's log tail. No Rust sources,
dependency locks, caps, or protected M2 files changed; final native regression
remains pending.

The third Mac attempt resolved the temporary-path, platform-mock and historical
inventory failures, but still failed both install modes of the shell orchestration
test. This was reproduced locally with desktop lockfiles present outside the
test root. That test now binds both ROOT and DESKTOP to its isolated project,
checks the two synthetic lock identities, and includes a regression case with
external installed lockfiles. Failure assertions also include the runner's own
traceback instead of only its return code. Backend sources remain unchanged.

## Final reviewed decision — complete

All three checkpoints are accepted; see
[evidence/m4-database-final-qualified/decision.json](evidence/m4-database-final-qualified/decision.json).
All five outer commands, all 15 native/frontend shell commands and both
seven-record UTF-8/UTF-16 workflows passed on the Mac. The original final report
still says failed because Cargo normalized four seed locks before the strict
final audit. The separate reviewed decision accepts the exact reported seed and
resolved hashes, with no unapproved registry dependencies. Export lock bytes
were independently compared; the other three lock identities rely on the
source-bound Mac verifier. The revised audit accepts only these recorded pairs.
The original input manifest is retained beside the reports.

This supersedes pending instructions above for milestone completion. No new Mac
run or reader test is requested for this evidence/audit/documentation update.
The frozen 104 production identities, 324 protected M2 identities, runtime
behavior, limits and distributed seed locks remain unchanged. Full M3 and
production release qualification remain open.
