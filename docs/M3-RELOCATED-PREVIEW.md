# Same-Mac relocated preview v6 check

This checks an exact copy of the existing unsigned Intel v6 bundle outside the source project, with an input fixture also outside that project. It does not qualify a clean machine/new user, missing toolchains, notarization, Gatekeeper distribution, other architectures or all enabled features. The original project is not renamed, deleted or made inaccessible. The previously accepted plugin interpreter remains external and is not exercised here.

Quit preview apps and any dev server. Put scripts/m3_relocated_preview.py in the project scripts folder (or merge the updated ZIP while apps are closed). Run:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_relocated_preview.py prepare
```

This requires the source-bound v6 executable hash, copies its app using macOS ditto into a NEW sibling folder /Users/shawky/Downloads/mdict-v6-location-check-1, compares complete app bundle file/symlink inventories and hashes, and copies only the tiny known CC-CEDICT fixture. No existing destination is overwritten, app is launched, source permissions altered, quarantine removed, or system security setting changed. If preparation fails, send the error and do not continue. A previous folder requires a new --output name used consistently in prepare and verify. Only syntax/help checks run locally; the Mac copy/launch remains pending.

After preparation, CLOSE Terminal and any dev server. In Finder open the app INSIDE mdict-v6-location-check-1 (not the original v6 path or a Dock shortcut). Open Converters → CC-CEDICT; input /Users/shawky/Downloads/mdict-v6-location-check-1/cedict.txt, output /Users/shawky/Downloads/mdict-v6-location-check-1/result.txt. Convert and collect the receipt. Expected 3 entries, 885 bytes. Confirm which copy was opened and that Terminal/dev server were closed at launch. If macOS blocks launch, report its exact message; do not remove quarantine or disable protections to force a pass.

After conversion reopen Terminal and run from the project root:

```sh
.venv/bin/python scripts/m3_relocated_preview.py verify
```

Send mdict-v6-location-check-1/report.json and the job receipt. The verifier checks the copied bundle remains exact, the copied input unchanged and final output exact. Those bytes do not independently identify which app handled the GUI conversion, so Finder path confirmation is required. Returning to Terminal for this final verification is expected and does not contradict closing it before launch. Existing same-Mac v3/v6 tests remain accepted; this checkpoint adds relocation only.

## Scoped observed result

The user supplied a passed report showing unchanged copied bundle/input and the exact expected 885-byte output, plus the matching CC-CEDICT receipt. The user explicitly confirmed opening the app inside mdict-v6-location-check-1 from Finder. The latest confirmation names that path; Terminal/server closure was requested but is not separately asserted in the retained review. Same-Mac copied-bundle launch and conversion are accepted. See evidence/m3-relocated-preview-qualified/GUI-confirmation.json. No routine same-user repeat is requested.
