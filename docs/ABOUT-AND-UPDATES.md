# About and update delivery

The sidebar now has an About button opening a native HTML dialog. It shows Mdict Studio Pro, installed Tauri app version, Shawky Nasr, shawkynasr@126.com and the official Rust repository. Labels cover English, Chinese and Arabic. Esc closes it, browser-native modal focus containment applies, and closing returns focus to About. About does not change workspace selection or start a dictionary job.

Repository and View releases open the system browser through a main-webview-only native command admitting only two fixed target names. It does not accept URLs, paths, executables or command arguments from the frontend. Failures leave the visible addresses available to copy. The existing dictionary preview CSP and sandbox are unchanged. The only new permissions are this fixed project-link command and reading the installed app version. No dependency or lockfile changes are required.

## Preview update behavior

This slice provides **manual release access**, not automatic update detection, notification, downloading or installation. About explains that updates are installed manually. Nothing checks GitHub at startup. The Releases page may be empty before the first public preview.

Recommended next stage: a manual Check for updates action and optional startup notification, with preview/stable channel selection, cached/rate-limited checks, explicit offline/error states, and no application replacement during active jobs. Do not call a browser link an automatic version check or claim that an empty/error response means up to date.

Before enabling installation through the Tauri updater:

- Give each release a unique semantic app version matching its release metadata. Current bundle 0.1.0 alone cannot distinguish every preview rebuild.
- Generate and retain the updater signing key outside the repository; keep the private key in maintainer/CI secrets and embed only its public key in the app. The updater requires signed packages. This signing is distinct from Apple Developer signing/notarization and Windows signing.
- Produce the platform-specific updater artifacts and HTTPS manifest through CI after all platform builds succeed. Separate preview and stable feeds; exclude drafts and prevent unintended channel switches/downgrades.
- Ask before downloading/installing, wait for dictionary jobs and handles to close, and test interrupted downloads, bad signatures, platform matching and restart behavior before enabling distribution.

No signing key was generated and no updater was enabled by this change. Reference: https://v2.tauri.app/plugin/updater/

## Validation and remaining checks

The local Node suite and Python contract suite validate existing GUI helpers, configuration boundaries and unchanged backend identities. CI now runs the new native fixed-link allowlist test on all four targets before bundling. Native CI execution and actual browser opening, About focus/Esc, version display and translated layout still need a new build/test. The authoring environment has no Rust toolchain and could not install the locked frontend dependencies offline (uncached npm package); a Svelte production build is therefore pending CI.

## Windows native test configuration fix

The first About build's direct `cargo test` used the development Tauri config rather than the preview override. On Windows, tauri-build therefore requested the nonexistent default `icons/icon.ico` although CI generated `icons/ci/icon.ico`. This was a build-configuration mismatch, not a dictionary converter failure. The native test now runs through `ci_test_desktop.py`, which passes the actual preview override as JSON in `TAURI_CONFIG` (the same merge mechanism used by Tauri CLI), checks that generated icons exist, preserves `--locked` and propagates Cargo failures. Bundling still uses its existing preview override. No fallback icon, test skipping or dependency/lockfile change is introduced. Windows native rerun remains pending.
