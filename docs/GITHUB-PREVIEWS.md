# Rust refactor repository and community previews

The separate repository is [MdictStudioPro-Rust](https://github.com/shawkynasr/MdictStudioPro-Rust). Suggested description:

> A Rust/Tauri refactor of MdictStudioPro, with new features and improvements. Experimental desktop previews for Windows, macOS and Linux.

Credit and link the [original MdictStudioPro](https://github.com/shawkynasr/MdictStudioPro). New project-authored code uses AGPL-3.0-only, as selected by the author. Preserve all component-specific licenses and notices. CI collects dependency license materials; review the new LEGAL archives and reported gaps before publishing. The root license does not relicense retained code or reference sources.

## First upload

1. Extract the latest project ZIP. Upload the **contents of `mdict-studio-m0-m1`** to the new repository root, including `.github`, `scripts`, `m2`, `m3`, `m4`, baseline/reference material and lockfiles. The existing layout supplies path dependencies; uploading only `m3/desktop` will fail.
2. Do not copy local corpora, output folders, settings, `.venv`, `node_modules`, `vendor` or build caches. The distribution ZIP excludes these; review any additions from your Mac before committing.
3. Push to `main` or `master`, or run **Actions → Rust desktop previews → Run workflow**. Initial runs must resolve online dependencies. No local Python environment, Cargo cache or private dictionary is required.
4. Inspect all four build jobs. Download the per-target workflow artifacts and test installation/launch. Keep the first failed run logs if a target needs a compatibility fix.
5. After the source and license/notice review, tag the desired commit `v0.1.0-preview.1`. The workflow builds again and creates a **draft prerelease** after all four jobs succeed. Review its assets and notes, then publish it manually on GitHub.

The new workflow uses the current repository automatically; no old repository token or hard-coded destination is present. Branch/PR/manual builds upload Actions artifacts only. No workflow or release has been run from this authoring workspace.

## Build matrix

| Platform | Runner | Rust target | Installer |
| --- | --- | --- | --- |
| Windows x64 | `windows-2022` | `x86_64-pc-windows-msvc` | NSIS `.exe` |
| macOS Intel | `macos-15-intel` | `x86_64-apple-darwin` | `.dmg` |
| macOS ARM | `macos-15` | `aarch64-apple-darwin` | `.dmg` |
| Linux x64 | `ubuntu-22.04` | `x86_64-unknown-linux-gnu` | `.deb`, `.AppImage` |

Linux ARM and Windows ARM are not included. Native build success is distinct from installation, GUI and clean-machine compatibility. The minimum supported OS versions are not qualified by this matrix.

## Build inputs and outputs

`ci_prepare_desktop.py` downloads the exact published mdictlib 0.2.8 crate, verifies its size/SHA-256 against the reviewed pin and root lock, then runs the existing revision-6 patch generator. Cargo registry caches are not modified. Its upstream license and patch provenance remain in the generated vendor tree. CI uses `npm ci`, the existing desktop Cargo lock with `--locked`, frontend tests and Tauri's production build, including frontend checks and native Rust compilation.

`tauri.ci.conf.json` provides a separate preview identity and generated platform icons, inheriting the existing production security configuration. No desktop dependency lock, protected M2 source or existing local v6 bundle configuration is changed. macOS uses ad-hoc signing, without notarization or an Apple Developer certificate. Windows is unsigned. No signing secrets are required for these experimental builds.

Each job uploads native installers, target-specific `SHA256SUMS`, `BUILD` identity JSON, a tiny synthetic CC-CEDICT fixture and tester instructions. Installer names include the Rust target so ARM/Intel and release downloads cannot collide. Reports record the source commit and explicitly leave runtime/clean-machine qualification false. Artifact download ZIPs are GitHub containers; the checksum files cover the installers inside them.

Preview tags never replace assets in an existing release: a rerun will fail if the release already exists. Inspect a failed draft-creation run before choosing a new preview tag. Avoid deleting/reusing a published tag. The generic release body works for subsequent preview tags too.

## Current feature differences

The optional Python converter/inspection/folder plugin profiles support macOS and Linux only. Windows returns a controlled unsupported-platform error. Descriptor-relative resource packing and some resource-publication operations are Unix-only as well. This change adds distribution automation, not Windows implementations for those features. Built-in Rust converters do not require an end-user Python installation.

Earlier Intel v6 evidence and its test-kit checksum are retained separately in `docs/releases/local-intel-v6-preview.md` and `SHA256SUMS-preview.1.txt`. They do not certify CI-built installers. New CI hashes must come from each run.

## Local preparation checks

```sh
python3 -m unittest discover -s scripts -p test_ci_preview.py -v
python3 scripts/package.py
```

Native compilation requires the platform toolchain, Node and Tauri prerequisites. The first hosted matrix run is observed successful in user screenshots (commit `7dbb2fe`, four jobs and four artifacts). Installation and launch of those new installers remain untested. See `docs/evidence/ci-first-preview-run/review.json`.

## Historical qualification workflow diagnostic

The first `qualify.yml` run passed baseline, all three engine jobs, all three sort jobs, the separate patched interoperability suite and reader fixtures; its metadata step exited nonzero. The attached report exactly reproduces the archived revision-3 diagnostic: 91 passed, 10 standard-XML StyleSheet newline comparisons failed, two legacy GB18030 writes unsupported and eight dependent checks blocked. This report and later application metadata profiles are different scopes.

`ci_legacy_metadata.py` now runs the unchanged diagnostic and checks all 111 names, statuses, failure reasons and blocked dependencies against the SHA-256-pinned archived report. Missing checks, new failures, changed outcomes, setup failures and reused outputs remain CI failures. It emits `archived_diagnostic_reproduced` separately; the underlying diagnostic remains **failed**, and unsupported/blocked cases never become passes. This is a regression check for preserved historical behavior, not a claim of universal metadata compatibility. A changed outcome requires review, even if it appears to be an improvement.

The original XML comparisons and engine sources are unchanged. Later scoped metadata/stylesheet behavior is documented in `M2-METADATA.md` and `M4-DATABASE-CLOSEOUT.md`. Do not change the serializer, normalize newlines, add `continue-on-error`, or remove assertions to hide the archived limitations. The corrected CI workflow still needs a hosted run.

The license collection step precedes native tests and bundling because the CI Tauri override embeds the generated legal resource directory. Archives are added to each target artifact after installer collection. Review actual dependency metadata and missing-license lists from that run before creating the public preview.
