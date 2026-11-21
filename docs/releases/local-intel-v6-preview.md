# Mdict Studio Pro 0.1.0 Preview 1 — Intel macOS

**Draft release notes. Proposed tag: `v0.1.0-preview.1`. Create as a GitHub prerelease. Nothing is published by this document.**

This experimental desktop preview brings the Rust dictionary engine into a Tauri interface with English, Chinese and Arabic UI options. It is intended for community testing with copies of your files.

## Download and start

- Asset: `Mdict-preview-v6-Intel-test.zip` (the reviewed internal preview v6).
- Platform tested: Intel Mac, macOS 15.8.3. Other macOS versions are unverified; this is not a declaration of the minimum supported version.
- The app is unsigned and not notarized. macOS may block launch. If it does, report the exact message and stop; this testing guide does not ask you to change system protections.
- Extract the ZIP, open `Mdict-v6-Intel-test`, then open `Mdict Studio Pro Preview.app` in Finder.
- The included `READ-ME.txt` and `cedict.txt` provide a small initial test. The built-in converter test does not require installing Python, Node, Cargo or the source workspace.
- The app's About/bundle version remains `0.1.0`; use the GitHub prerelease tag and ZIP filename in reports to identify this build.

See [the tester guide](local-intel-v6-testing.md) for expected results and reporting instructions.

## Available for testing

- Bounded MDX/MDD build, export and resource workflows, with progress, cancellation and existing-destination protection.
- SQLite import/export, browsing, previews and copy-based entry/metadata/stylesheet edits within the supported database profiles.
- Six built-in converters: CC-CEDICT, MOE Mini, MOE Idioms, MOE Concise, MOE Revised and MOE Revised WFG.
- Optional, explicitly trusted Python plugin import, supported scalar option controls and Advanced folder discovery. Python and plugin dependencies are external; importing/running a plugin executes code with your account's permissions.
- Rendered, split and HTML definition views, plus appearance/language preferences.
- Targeted cleanup when the app is force-quit during an active idle Python bridge job.

## Evidence behind this preview

All six built-in converter fixtures passed in the standalone app. Selected-file Python conversion, folder inventory/error display, focused Settings keyboard/draft checks, missing-input handling, permission-denied output/retry and same-Mac relocated launch/conversion have scoped evidence. The active SlowPlugin force-quit test in v6 removed its bridge and owned temporary directory without manual diagnostic cleanup; no final output was published, and reopening worked.

Earlier native and independent MDict/GoldenDict checks remain accepted only for their documented profiles and inputs. These results do not establish every feature/input combination or every failure phase.

## Known limits and open testing

- Clean-machine/fresh-user installation has not been qualified. Community reports will provide evidence; the expectation that it works is not a passing test.
- Apple Silicon/Rosetta, Windows and Linux are unverified for this build. No native Apple Silicon, Windows or Linux asset is included.
- MDX v2 is the main profile. Keyword-index `Encrypted=2` export/import is supported within its tested v2 profile. Passcode modes and MDX v3 remain unsupported.
- The narrow legacy v1.2 path covers unencrypted `ISO8859-1`-labelled ASCII content; it does not imply general Latin-1 or other legacy-encoding support.
- Operations have profile-specific caps. SQLite storage/conversion is bounded to 100,000 records and 32 MiB decoded text; the separate large MDX export profile permits up to 250,000 records and 96 MiB decoded text. File, entry and other limits also apply. A limit error does not authorize silently truncating or widening a profile.
- Publication keeps existing destinations. Choose a new file/folder name; failed/cancelled jobs are not resumed after restarting.
- Jobs retain a bounded number of results. If `retention_full` appears, dismiss finished jobs; published output files are kept.
- Python parent-death cleanup is cooperative. GIL-blocking native extensions, detached/malicious plugin processes, crashes before the watcher or after the child exits, power loss and old abandoned temporary folders are outside the accepted active-job test. There is no general automatic crash-recovery claim.
- Preview rendering is static; scripts and external connections are disabled. Broader script/media/resource behavior, morphology and additional format/profile parity remain unfinished or deferred.

## Help test

Start with the included fixture, then test a copy of a small file you may share. Please include the release tag, Mac chip, macOS version, exact steps, expected/actual behavior, and job receipt/error details. Attach a minimal reproducible sample and output only when you can share them; redact private paths and credentials. Report launch blocks even if the app never opened. Use the repository's **Bug report / prerelease test** issue template.

This is an experimental prerelease. Full M3/original-app parity and stable public-release readiness remain open.

---

Maintainer note: publish the matching source revision and retain applicable existing license/third-party notices. This draft does not settle the workspace's final licensing or distribution review. No tag, release, upload or repository change has been made remotely.
