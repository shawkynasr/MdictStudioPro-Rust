# First-release readiness review — 20 November 2026

This is a current review of the existing evidence, with a proposed Mac-first public-release path. It does not approve a reduced definition of full M3, mark the project production-ready, or claim other-platform qualification. No application code or dependencies changed for this review. The current v5 app can be used for the next check without rebuilding.

## Current evidence

| Area | Current result | Precise boundary |
| --- | --- | --- |
| Engine and dictionary workflows | M1/M2 and bounded M4 accepted | Existing profiles/caps; no arbitrary-size or universal-format claim |
| MDX v2 Encrypted=2 | Native and development-app JSONL/SQLite accepted | Keyword-index mode only; no passcode modes or v3 |
| Legacy Legal Latin v1.2 | Native and development-app JSONL/SQLite accepted, 310 rows | Unencrypted ISO8859-1-labelled ASCII content only; no general legacy encoding mapping |
| Selected-file Python discovery/options and simplified workflow | Native plus development-app GUI accepted | One selected file, trusted import, scalar schema, external interpreter; not a Python sandbox |
| Advanced folder discovery | Native/frontend plus scoped standalone GUI accepted | Four candidate files, three distinct choices and intentional per-file error displayed; folder-triggered conversion is not newly claimed |
| Standalone Mac preview | v3 and v5 release bundles built; scoped Finder/Database/style/preferences checks | Local unsigned Intel Mac only; no public installer/notarization or clean-machine coverage |
| Active Python force-quit cleanup | Native tests, v6 build and scoped standalone cleanup/reopen accepted | Idle SlowPlugin active-job case only; old stages and broader crash phases remain open |
| Settings dialog | Prior v5 checks plus scoped v6 keyboard/draft/workspace user confirmation and Chinese/Dark screenshots accepted | Dialog/Extract actions attested by user; screenshots show retained draft and trigger focus; no exhaustive accessibility claim |
| Packaged Python execution | Accepted scoped | User-supplied standalone receipt and exact 203-byte/six-record output match all input/plugin/options/output hashes; external interpreter remains required |
| Six built-in converters | All six scoped standalone fixture checks accepted, reusing native qualification | Revised permits documented alias-order normalization; no universal-input or clean-machine claim |

Latest full compatibility gate: nine export tests, 98 runtime tests, 29 adapter tests, 51 frontend tests. Latest v5 bundle gate: eight stages, frontend tests, Svelte zero errors/warnings, offline release build, source/lock/copy checks. These are separate reports, not one newly executed all-platform suite. All 324 protected M2 identities remain intact.

## Packaged converter check — completed

The steps below are the completed test recipe, retained for reference. The standalone receipt and output(5).txt passed exactly; see `docs/evidence/m3-plugin-standalone-qualified/GUI-confirmation.json`. No routine repeat is requested.

1. Open Converters, then Convert with a plugin. Choose the external interpreter once if Python setup is unconfigured:
   `/Users/shawky/Downloads/mdict-studio-m0-m1/.venv/bin/python`
2. Choose this single plugin file:
   `m3/fixtures/plugin-folder/options.py`
   under the project root. Check import trust and click Import plugin. Its single OptionsPlugin should be selected automatically; the display name is Folder options demo.
3. Set Prefix to `字 مرحبا` and enable Uppercase source.
4. Select `m3/fixtures/build-source.txt` as input. Choose a new output folder, accept conversion trust and run.
5. Collect the job receipt. Expected: six records, two option fields, input SHA-256 `66417f81f2d2da12dcae7635d4458b7e91fff4425bd8d2a960add9740b5f3e96`, plugin SHA-256 `e70b84fa0ba345547479efab5774394506632c4ea57b799e89656d9b32938644`, options SHA-256 `508848469becdce55606f5e131957f73d2a1fddb80c43a8702b53f115e8ceeb8`, output SHA-256 `737ce0b126a6a952729903c679fb7659121dd7a6d909711a35fa33be67cdb45d`, summary Folder options fixture completed. Both duplicate definitions must remain. The output is 203 bytes; the receipt's bytes field counts all result files and may be larger.
6. Send the receipt, and optionally output.txt for an exact byte comparison. This is a packaged-app check; previous development-app plugin acceptance remains valid.

Python is currently external. Bundling Python/dependencies is a separate product/packaging decision. Avoid assuming that an app licensing key grants dictionary permissions; the current compatibility checks do not add passcode support.

## Remaining public-release areas

| Priority | Work | Completion evidence |
| --- | --- | --- |
| 1 | Finish standalone coverage of enabled functions | Packaged Python receipt above; six built-in fixture routes accepted; remaining enabled-route and language/keyboard coverage; language/keyboard checks tied to the app build |
| 2 | Settle distribution scope and verify installation | Decide the intended architectures/platforms and distribution method; prepare actual signing/notarization/installer work when the necessary account/setup exists; test on a clean supported machine |
| 3 | Review operational readiness | Assess unexpected exit/recovery/temp cleanup behavior, access failures and remaining accessibility/security limits; distinguish logical reservations from hard OS limits |

Apple Silicon, Windows and Linux are open qualification targets, not implicitly included in the accepted Intel preview. Arbitrary option schemas, morphology without an executable/data contract, audio/JS/SVG/CSS imports/multi-volume resources, broader encodings/sort profiles/caps and MDX v3 remain explicit feature decisions. The absent morphology files are not requested again.

The bounded local preview is usable for its accepted workflows. Public release, full M3 and full original-app parity remain open. Existing source-bound evidence can be reused when the relevant implementation identities match; this review requests no dictionary benchmark or native-suite rerun.

## Current next step

Review the prepared experimental Intel macOS GitHub prerelease materials: [publishing handoff](releases/PUBLISHING-CHECKLIST.md), [release notes](releases/v0.1.0-preview.1.md), [tester guide](PRERELEASE-TESTING.md) and the root GitHub bug-report template. The Mac kit report is accepted; independent/clean-target execution remains pending for community testing. No remote publication, tag or upload was performed. The native app is unchanged and needs no rebuild for this documentation review.
