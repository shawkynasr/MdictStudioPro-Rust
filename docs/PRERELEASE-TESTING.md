# Rust preview tester guide — Windows, macOS and Linux

Record your preview tag, exact installer filename, OS/version and CPU architecture. Download the matching installer, `SHA256SUMS`, `BUILD`, `TESTING` and `cedict` files from the same release. A successful CI build is not a claim that installation or GUI behavior has already been tested on your platform.

## Install and launch

- Windows x64: run the NSIS `.exe`. Builds are unsigned; report any block exactly. WebView2 is required; the installer may download its runtime when missing.
- Intel/Apple Silicon macOS: choose the matching `.dmg`, mount it and copy the preview app to Applications. It is ad-hoc signed, not notarized. Report launch blocks; do not disable system protections to force a pass.
- Linux x64: install the `.deb` with your distribution's package installer, or make the `.AppImage` executable and open it. Distribution dependencies vary. Report distribution/version and exact missing-library or FUSE errors rather than treating Ubuntu CI as universal Linux support.

Open the installed app independently of a development server. Built-in converters do not need Python, Node or Cargo. Optional trusted Python plugins require your own interpreter and dependencies and currently support macOS/Linux only. Some resource operations are Unix-only too.

## Small first test

1. Open **Converters → CC-CEDICT**.
2. Choose the included `cedict-<target>.txt` (the filename differs by platform; its content is identical).
3. Choose a new `result.txt` in a writable folder. Click Convert, then **Jobs → Collect receipt**.
4. Expect **3 entries / 885 bytes**, including `字`, `书` and `書`, with accented pinyin preserved.
5. Quit and reopen normally. Confirm the app opens. Interrupted jobs should not resume.

| File | SHA-256 |
| --- | --- |
| Included CC-CEDICT fixture | `463a04e1ad8ff8c3142e1456dc0fb529de2fa62affbe3dd70d4f70afd8e42dec` |
| Expected result.txt (885 bytes) | `83288a2c708f4d03a12d08e72eb7a71af3904d37528447ffc3ee1e95fe8415b1` |

Return the receipt and observations through the bug-report issue template. Include installer identity, architecture, native versus translated execution (if applicable), launch route and whether this is a development or clean machine. Remove private paths/content before sharing logs.

Optional tests: check English/Chinese/Arabic UI and Settings persistence, duplicate database entries, rendered/Split/HTML previews, and cancellation to a new destination. Use copies of files. Report the exact operation and error; do not widen limits or overwrite existing outputs to force a test pass. Full compatibility, parity and general crash recovery remain open.
