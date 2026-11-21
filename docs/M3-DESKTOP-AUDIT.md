Current review: [M3 completion review](M3-COMPLETION-REVIEW.md), 20 November 2026.
The package-177 audit below is historical; lock capture, the local Mac preview
and selected-file discovery/forms have since been accepted. Do not rerun its old
next-step commands solely because they remain in this history.

# Desktop completion audit

Reviewed 2026-11-19 against the delivered package-177 sources and retained
native/GUI evidence. The audit is complete; full M3 and production release
remain open. Historical per-slice pending text is interpreted against later
evidence, not deleted or promoted to global qualification.

The remaining path for a bounded macOS development preview is dependency
capture, a standalone .app build, and packaged-app smoke checks. This is a
scoped finish line, not a declaration of full original-app parity. No runtime
code or dependency versions changed during this audit.

| Area | Finding |
| --- | --- |
| MDX build from TXT/JSONL | accepted scoped — Canonical/legacy TXT and bounded/block profiles; UTF-8/UTF-16 reader checks. No generic arbitrary-size guarantee. |
| MDD build from resource folder/manifest | accepted scoped — Paired dictionary/resource GUI attestation; bounded portable resource policy. |
| MDX TXT/JSONL export and MDD extraction | accepted scoped — GUI confirmation includes exact 17-resource comparison; native export gate passed. |
| Six built-in converters | native qualified GUI compiled — All six native converter profiles qualified under M2. GUI routes compile; no claim of six separate fresh GUI runs. |
| Indexed lookup, duplicate selection and redirects | accepted scoped — Single-hop/chain/duplicate/cycle/missing GUI cases retained. |
| Title/description copy edit | accepted scoped — Five records and edited metadata reported correct in both independent readers. |
| Numeric stylesheet export | accepted scoped — Uploaded 36-byte fixture export compared exactly. |
| Database workspaces | complete bounded M4 — Three closeout checkpoints accepted after separately reviewed Cargo seed normalization. |
| Trusted Python converter isolation | accepted scoped — Dedicated authenticated socket, stdout/stderr and sidecars; original failure/cancel/no-clobber GUI fixtures. Not a Python sandbox. |
| Scalar options and local presets | accepted scoped — Native option delivery, exact six-record GUI output, save/restart/load user confirmation and frontend tests. |
| Job errors, cancellation and interpreter guidance | accepted scoped — 40 frontend tests/build; user error/detail/preflight text accepted. New color mapping lacks screenshot attestation. |
| Localization, RTL, appearance and static previews | implemented partial manual coverage — EN/ZH/AR implementation, light/dark user screenshots and scoped previews; not exhaustive locale/accessibility/browser security qualification. |
| Automatic plugin/class discovery and schema-generated forms | deferred — Current explicit file/class + scalar-map options and presets are not full legacy plugin discovery or arbitrary options_schema compatibility. |
| Morphology | deferred missing contract — Original app had selectors only. User has no addflex.py/wordforms.txt; no executable format to reproduce. |
| Dictionary JS/audio/SVG and full resource behavior | deferred — Preview intentionally static; no claim of arbitrary website/plugin behavior or multi-volume MDD. |
| Additional sort/rebuild flags, larger envelopes, MDX v3 | deferred — Existing profile contracts and caps remain. Additional writer policies require independent qualification. |
| Resolved frontend/desktop dependencies | next required — Only SHA identities of frontend/desktop resolved locks retained; actual full bytes must be captured from the Mac before reproducible app packaging. |
| Standalone Mac application | next required — Development shell compiled/launched; bundle.active is false. Release CSP, packaged paths, external Python and preferences need packaged-app smoke checks. |
| Full M3, original-app parity and production release | open — No current completion decision for full M3. macOS signing/notarization/updater, Windows/Linux, crash recovery and hard memory enforcement remain separate. |

The machine-readable audit binds each evidence path and SHA-256 in
[evidence/m3-desktop-audit/audit.json](evidence/m3-desktop-audit/audit.json).
Native regression, GUI attestations and local-only checks remain distinguished.
The M3/M4 historical status files inside source trees are not rewritten simply
to make old pending wording disappear; docs/STATUS.json and later reviewed
decisions identify current scope.

## Next: preserve the actual Mac locks

Close the app and run from the project root:

```sh
.venv/bin/python scripts/m3_capture_mac_locks.py --output m3-shell-out-lock-capture
```

Attach m3-shell-out-lock-capture/lock-snapshot.zip. The command copies seven
existing lockfiles into a new output folder and includes a hash/source-stability
report. It does not resolve dependencies, invoke Cargo/npm, install anything,
modify active locks, build the app or read your saved presets. Missing locks
produce an explicit incomplete report rather than fabricated replacements.
No new frontend/native regression is requested for this read-only collection.

The captured bytes will be checked against the accepted native/frontend receipt
hashes and existing registry policy. Any mismatch is reviewed before adopting
the lock; it is not automatically accepted as a dependency upgrade.

After that review, use a separate app-bundle override rather than changing the
qualified development config silently. The first artifact is a local unsigned
Mac development preview. Signing, notarization, distribution/updater and native
Apple Silicon/Windows/Linux qualification are not implied by Intel-Mac success.
The packaged app must be checked under production CSP and a new WebView origin;
dev presets may not share that origin. Optional Python requires a user-selected
external interpreter and its dependencies; Python is not silently bundled.

## Dependency capture follow-up

All seven lock bytes were supplied and reviewed. Desktop/frontend/SQLite match
accepted hashes; the four restored M3 seed locks are exact known variants.
See evidence/m3-mac-lock-capture/review.json and M3-MAC-PREVIEW.md. Dependency
capture is complete; the next command is the standalone Mac preview build,
followed by packaged-app smoke checks. Full M3 remains open.
