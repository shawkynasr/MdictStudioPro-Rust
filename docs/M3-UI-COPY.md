# Interface wording and language pass

Status: implemented; local frontend logic and Python checks run during packaging. Mac frontend compilation/build and visual confirmation are pending. This is a focused wording pass, not exhaustive localization or accessibility qualification.

## Changes

- Settings now describes language and appearance, rather than showing the morphology deferral message.
- The title/footer identifies the app as a local preview, avoiding a misleading development-shell label in the standalone app.
- Entry export uses a general MDX source label and shows the supported input scope: v2 UTF-8/UTF-16 (including Encrypted=2) and unencrypted ISO8859-1-labelled v1.2 with ASCII headwords/definitions only. This appears for MDX export, not MDD extraction.
- TXT help explains that CR/CRLF definitions or a standalone terminator line require JSONL for unchanged text. No normalization or new export mode is introduced.
- Database import help reflects the qualified v1.2 ASCII profile as well as v2.
- Base build/source/preview help no longer describes already implemented TXT input or rendered preview as future work.

Every changed label is provided in English, Chinese and Arabic. Format identifiers remain literal. Native error messages, plugin-supplied labels, brand/product names, and the wider translation/accessibility inventory remain outside this pass. Packing labels that specifically describe v2 output remain v2. No CSS, theme persistence, native operation, Python behavior, input acceptance policy, limits, dependencies or locks changed.

## Verification and build

The previous preview-v3 binary remains accepted for its tested scope. It predates this wording pass. Reuse the existing source-bound, locked offline Mac build gate with a fresh folder; no repeat of native dictionary qualification is needed for text changes:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_mac_preview.py --output m3-shell-out-mac-preview-v4
```

Quit the app and development server before applying the updated ZIP/building. Send `m3-shell-out-mac-preview-v4/report.json`. On a passing build, launch that folder's `Mdict Studio Pro Preview.app` from Finder. Switch English/Chinese/Arabic and check Settings, the MDX export support note, TXT help under More options, and MDX-to-SQLite help. Confirm Arabic stays RTL and that MDD extraction does not display the MDX compatibility note. Keep user dictionaries and existing destinations unchanged; this visual check needs no new conversion jobs.

Full M3, signing/notarization, other platforms and broad legacy encoding support remain open.

## Mac build and Settings follow-up

Preview v4 passed all eight build stages and Svelte zero errors/warnings. The user reported an existing navigation defect: Settings appeared inline above Build. Wording compilation is qualified, but visual acceptance is incomplete. The selected fix is a compact modal dialog, described in [M3-SETTINGS-DIALOG.md](M3-SETTINGS-DIALOG.md), built as preview v5.
