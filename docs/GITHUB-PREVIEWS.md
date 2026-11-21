# Rust refactor repository and community previews

The separate repository is [MdictStudioPro-Rust](https://github.com/shawkynasr/MdictStudioPro-Rust). Suggested description:

> A Rust/Tauri refactor of MdictStudioPro, with new features and improvements. Experimental desktop previews for Windows, macOS and Linux.

Credit and link the [original MdictStudioPro](https://github.com/shawkynasr/MdictStudioPro). Preserve applicable licenses and third-party notices; the final distribution license review is still pending. Do not select a conflicting default license when creating the repository. This workflow does not relicense the retained code or reference sources.

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

Native compilation requires the platform toolchain, Node and Tauri prerequisites. The first hosted matrix run remains pending; workflow structure and local script tests do not establish that all targets compile or launch.
