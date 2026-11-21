# Database closeout checkpoints

The scoped Database features have user-run native/oracle and manual GUI evidence: browsing/search, isolated previews, TXT/JSONL/MDX conversion, metadata and numeric stylesheets, selected definition editing, headword renaming, deletion and single-entry addition. Scope remains the existing bounded profiles; this is not full original GUI parity or production release qualification. Newer per-slice evidence supersedes historical pending text in earlier reproduction documents.

Three closeout checkpoints were proposed after the Add entry GUI verification:

1. **Combined workflow and readers — accepted for the scoped fixtures.** See [M4-DATABASE-WORKFLOW.md](M4-DATABASE-WORKFLOW.md). The Mac report passes both encodings and every intermediate stage. The user confirmed both rebuilt encodings after the MDict/GoldenDict checklist; reviewed screenshot crops support expected rendering but do not independently label every reader/encoding combination. See `evidence/m4-database-workflow-qualified`.
2. **Real dictionary sizing and performance — accepted within the existing profile.** See [M4-DATABASE-SIZING.md](M4-DATABASE-SIZING.md). The Mac run passes the synthetic boundaries, controlled refusals and complete 6,148-record real-dictionary conversion, 25 lookup samples and JSONL export. See `evidence/m4-database-sizing-real-qualified`. Larger profiles remain separate.
3. **Final regression and closeout — accepted after reviewed lock normalization.** See [M4-DATABASE-CLOSEOUT.md](M4-DATABASE-CLOSEOUT.md). All native/frontend commands and UTF-8/UTF-16 workflow oracles passed. The strict final seed-lock audit refusal is retained and resolved separately in `evidence/m4-database-final-qualified/decision.json`. Current status is finalized; no further Mac rerun is required for this evidence/documentation closeout.

Larger limits, further rebuild lookup policies, crash recovery, additional-platform packaging/signing/updating, full application parity and production release checks remain separate follow-ups. MDX v3 remains deferred. All three checkpoints are complete within the documented Database profile; this does not close all future application work.
