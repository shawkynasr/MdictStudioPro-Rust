# Numeric stylesheet export

The original Python GUI's Export .style action is now available in Dictionary
Tools → **Details → Metadata → Export numeric stylesheet…**. This saves the
decoded MDX `StyleSheet` header value as UTF-8 text. The default name is
`<dictionary>_style.txt`; the save dialog adds `.txt` when needed.

The action uses verified cached metadata from the admitted reader, including
its source digest. It does not scrape preview HTML or parse the original
CLI's textual metadata output. The exact decoded attribute text is preserved:
no BOM, added newline, whitespace stripping, XML escaping, or CR/LF rewriting.
An empty/absent stylesheet returns no file. External CSS files are separate
resources and use MDD extraction instead of this action.

The native adapter constructs the export request after checking reader state,
MDX kind, collected open manifest and verified header cache. A raw Submit JSON
request cannot construct this snapshot-bound operation. The ordinary serial
publication queue stages and verifies the file, checks cancellation and
publishes exclusively. Existing files are refused; cancellations and failed
publication remove the private stage. Receipts transfer once through Jobs
and include the snapshot source SHA-256, output SHA-256, byte count and UTF-8
encoding. If the public MDX path changes after metadata was verified, the
export still describes the cached reader snapshot, identified in the receipt.

This operation uses the existing Export reservation (96 MiB logical / 768 MiB
temporary), coexisting with one open MDX reader under the two-operation cap.
Detach an attached MDD reader first; the UI explains this and disables Export
while it is attached. No M2 files, limits, Tauri permissions or registry
dependencies change. Cached metadata and native request payloads retain their
existing 64 KiB budgets. English, Chinese and Arabic labels are provided.

## Validation

Native tests are authored for UTF-8 and UTF-16 MDX inputs, multilingual wrappers,
exact text bytes, source snapshot binding after public-file replacement,
not-ready and missing-style refusal, raw Submit rejection, one-transfer
receipts, existing-destination and publication-race refusal, and cancellation
during staging/commit. Rust and Svelte checks cannot run in the authoring
environment; run on Mac:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
python3 scripts/m3_shell.py --output m3-shell-out-v16
```

Launch the GUI:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1/m3/desktop
npm run tauri dev
```

Reuse the existing small `preview.mdx` and `preview-mdx.idx` generated during
the rendered-preview tests. Open only its MDX reader. In Details → Metadata,
export the numeric stylesheet to a new file. The original fixture's expected
contents are these three lines, with a final LF:

```text
2
<span style="color:blue">
</span>
```

Collect the receipt in Jobs and confirm the saved text. Repeat with the same
destination to check refusal and that the original export stays unchanged.
Opening a plain dictionary without a numeric stylesheet should show the
explanatory note and disable the export button.

If the old fixture folder was removed, generate it once from the project root
using a new folder name (do not replace an existing fixture folder):

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
cargo run --manifest-path m3/native-adapter/Cargo.toml --example preview_fixture -- m3-shell-out-style-fixture
```
