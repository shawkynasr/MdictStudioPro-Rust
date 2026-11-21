# Mdict Studio Pro Rust — experimental community preview

A Rust/Tauri refactor of [MdictStudioPro](https://github.com/shawkynasr/MdictStudioPro), with new features and improvements and English, Chinese and Arabic UI options.

## Downloads

Choose the installer whose target matches your machine:

| Machine | Filename contains | Installer |
| --- | --- | --- |
| Windows x64 | `x86_64-pc-windows-msvc` | `.exe` |
| Intel Mac | `x86_64-apple-darwin` | `.dmg` |
| Apple Silicon Mac | `aarch64-apple-darwin` | `.dmg` |
| Linux x64 | `x86_64-unknown-linux-gnu` | `.deb` or `.AppImage` |

The target-specific SHA256SUMS and BUILD files identify these installers and their source commit. macOS builds use ad-hoc signing and are not notarized; Windows builds are unsigned. If your OS blocks launch, report the exact message. No system protection changes are requested.

Download the included target-specific `cedict` fixture and `TESTING` guide for a small first test. Built-in converters do not require Python. Optional trusted Python plugins require your own interpreter/dependencies and currently support macOS/Linux only. Some resource operations are also Unix-only; full cross-platform feature parity is not claimed.

This is a community preview. Hosted build/test success does not verify installation or GUI behavior on your machine. Earlier local Intel v6 tests do not certify these new installers. Full original-app parity, clean-machine/platform qualification and stable readiness remain open.

Use copies of dictionaries and fresh output paths. SQLite is capped at 100,000 records / 32 MiB decoded text; separate large MDX export permits up to 250,000 / 96 MiB, with other limits also applying. Existing outputs are kept. Password-protected and general v3 dictionaries are unsupported; narrower legacy/key-info profiles remain limited to their recorded scope.

Please report your OS/version, architecture, preview tag, exact installer, transfer route, operation and receipt/error through the repository's bug-report issue template. Remove private paths or dictionary content before sharing logs. A failed test is useful feedback.

## License and source

New project-authored Rust/Tauri code: **AGPL-3.0-only**, copyright 2026 Shawky Nasr. Third-party and retained historical components keep their own terms. See LICENSE and THIRD_PARTY_NOTICES.md at this release's source tag. Each target includes a LEGAL ZIP with collected notices and an explicit list of any gaps. The installer also includes these materials in its legal resources.
