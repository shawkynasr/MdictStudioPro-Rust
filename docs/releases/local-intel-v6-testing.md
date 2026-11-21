# Preview 1 tester guide — Intel macOS

This guide covers the reviewed preview v6 app packaged as `Mdict-preview-v6-Intel-test.zip`. The proposed GitHub tag is `v0.1.0-preview.1`; the app bundle version is `0.1.0`.

## First launch

1. Record your Mac chip (Intel or Apple Silicon), macOS version and ZIP filename. Note whether this is the development Mac, another Mac, or a separate macOS account.
2. Extract the ZIP with Finder. Open `Mdict Studio Pro Preview.app` inside `Mdict-v6-Intel-test` directly from Finder, with any development app/server closed.
3. If macOS blocks launch, capture the exact text and stop. Report the transfer route too (browser download, USB, etc.). Do not remove quarantine, disable Gatekeeper or install development tools to force a test pass.
4. Once open, the built-in test below should be possible without Python setup. Optional plugins are a separate feature and require an external interpreter and dependencies.

A separate account on a development Mac provides fresh-user evidence only: installed system-wide libraries/tools are still present. An Apple Silicon/Rosetta result is useful but must be labelled separately from Intel evidence.

## Small initial test

1. Open **Converters → CC-CEDICT** (not Convert with a plugin).
2. Choose the included `cedict.txt` next to the app.
3. Choose a new `result.txt` in a folder you can write to. Do not pre-create or overwrite it.
4. Click Convert, then **Jobs → Collect receipt**.
5. Expect **3 entries / 885 bytes**: `字`, `书`, `書`. The `字` definition contains character and word; the other two contain book, with accented pinyin `zì` and `shū` preserved.
6. Quit normally and reopen the same app. Confirm it opens normally. Jobs are process-local and do not resume.

Return the receipt, `result.txt` and launch/reopen observations. If a step fails, return the exact error and the step; a failure report is useful. The receiving tester does not need to install a verification script or interpreter. The reviewer can compare these fixed identities:

| Item | SHA-256 |
| --- | --- |
| Included cedict.txt | `463a04e1ad8ff8c3142e1456dc0fb529de2fa62affbe3dd70d4f70afd8e42dec` |
| Expected result.txt (885 bytes) | `83288a2c708f4d03a12d08e72eb7a71af3904d37528447ffc3ee1e95fe8415b1` |
| App executable (reviewed v6) | `2fdde5759b44256afcf8fddf9e52c2dad59f17c756742e588c478c3bda9b140d` |

## Optional focused tests

Use copies and a fresh destination for each operation. Choose the feature you normally use; you do not need to run everything.

| Area | Useful observations |
| --- | --- |
| Language/appearance | English/Chinese/Arabic, Arabic direction, text clipping, theme and keyboard focus |
| Dictionary build/export | Input/output counts, duplicate keys, Unicode, metadata/styles; exact operation/profile and any cap error |
| Database | Browsing, previews, query results and saving edits into a new copy |
| MDD resources | Missing resources, extraction behavior and resource paths with a shareable small sample |
| Failures | Exact errors for missing inputs, unavailable output folders or existing destinations, and whether a subsequent valid job succeeds |
| Optional Python | Interpreter version/path (redact private portions), plugin hash/name/class/options, explicit trust flow and receipt; run only code you trust |

Do not stress a full disk or deliberately crash an unrelated process for this first test. Forced termination has a separate controlled fixture protocol. If the app crashes during normal use, record the steps and attach the relevant macOS crash report after checking it for private information.

## Sending a useful report

Use **Bug report / prerelease test** in GitHub Issues. Include the tag/asset, hardware/OS, test environment, exact steps, expected vs actual result, and receipt/error. Attach only a minimal sample you can share, and do not paste passwords, tokens or a full private dictionary. Screenshots alone may not reveal a failed job's cause; include the text error when possible.

Check [release notes](local-intel-v6-preview.md) for known limitations. Passing this small test qualifies that environment and route only; it does not establish full parity or stable-release readiness.
